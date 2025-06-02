"""Async File Scanner Engine

High-performance async file scanning and monitoring for large codebases.
"""

import asyncio
import hashlib
import mimetypes
import os
import time
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator, Dict, List, Optional, Set, Tuple, Any

import aiofiles
import structlog
from pathspec import PathSpec
from watchdog.events import FileSystemEventHandler, FileModifiedEvent, FileCreatedEvent, FileDeletedEvent
from watchdog.observers import Observer

from src.database.models import FileStatus, ProjectStatus
from src.database.operations import file_repo, project_repo, get_db_session
from src.utils.config import get_settings, get_project_config

logger = structlog.get_logger(__name__)


class FileInfo:
    """File information container."""
    
    def __init__(
        self,
        path: Path,
        root_path: Path,
        size: int = 0,
        modified_time: Optional[datetime] = None,
        created_time: Optional[datetime] = None,
        content_hash: Optional[str] = None,
        encoding: Optional[str] = None,
        mime_type: Optional[str] = None,
        file_type: Optional[str] = None,
        language: Optional[str] = None,
    ):
        self.path = path
        self.root_path = root_path
        self.size = size
        self.modified_time = modified_time or datetime.fromtimestamp(path.stat().st_mtime)
        self.created_time = created_time or datetime.fromtimestamp(path.stat().st_ctime)
        self.content_hash = content_hash
        self.encoding = encoding
        self.mime_type = mime_type
        self.file_type = file_type
        self.language = language
    
    @property
    def relative_path(self) -> str:
        """Get path relative to root."""
        return str(self.path.relative_to(self.root_path))
    
    @property
    def name(self) -> str:
        """Get file name."""
        return self.path.name
    
    @property
    def extension(self) -> str:
        """Get file extension."""
        return self.path.suffix.lower()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            "path": str(self.path),
            "relative_path": self.relative_path,
            "name": self.name,
            "extension": self.extension[1:] if self.extension else None,
            "size_bytes": self.size,
            "content_hash": self.content_hash or "",
            "encoding": self.encoding,
            "mime_type": self.mime_type,
            "file_type": self.file_type,
            "language": self.language,
            "file_created_at": self.created_time,
            "file_modified_at": self.modified_time,
            "status": FileStatus.DISCOVERED,
        }


class FileClassifier:
    """File type and language classification."""
    
    FILE_TYPE_MAPPING = {
        # Code files
        ".py": ("code", "python"),
        ".js": ("code", "javascript"),
        ".ts": ("code", "typescript"),
        ".jsx": ("code", "javascript"),
        ".tsx": ("code", "typescript"),
        ".java": ("code", "java"),
        ".cpp": ("code", "cpp"),
        ".c": ("code", "c"),
        ".h": ("code", "c"),
        ".cs": ("code", "csharp"),
        ".php": ("code", "php"),
        ".rb": ("code", "ruby"),
        ".go": ("code", "go"),
        ".rs": ("code", "rust"),
        ".swift": ("code", "swift"),
        ".kt": ("code", "kotlin"),
        ".scala": ("code", "scala"),
        ".clj": ("code", "clojure"),
        ".hs": ("code", "haskell"),
        ".ml": ("code", "ocaml"),
        ".fs": ("code", "fsharp"),
        ".elm": ("code", "elm"),
        ".dart": ("code", "dart"),
        ".lua": ("code", "lua"),
        ".r": ("code", "r"),
        ".m": ("code", "matlab"),
        ".pl": ("code", "perl"),
        ".sh": ("code", "shell"),
        ".bash": ("code", "shell"),
        ".zsh": ("code", "shell"),
        ".fish": ("code", "shell"),
        ".ps1": ("code", "powershell"),
        ".bat": ("code", "batch"),
        ".cmd": ("code", "batch"),
        
        # Styles
        ".css": ("style", "css"),
        ".scss": ("style", "scss"),
        ".sass": ("style", "sass"),
        ".less": ("style", "less"),
        ".styl": ("style", "stylus"),
        
        # Markup and templates
        ".html": ("markup", "html"),
        ".htm": ("markup", "html"),
        ".xml": ("markup", "xml"),
        ".svg": ("markup", "svg"),
        ".jsx": ("markup", "jsx"),
        ".tsx": ("markup", "tsx"),
        ".vue": ("markup", "vue"),
        ".svelte": ("markup", "svelte"),
        ".handlebars": ("template", "handlebars"),
        ".hbs": ("template", "handlebars"),
        ".mustache": ("template", "mustache"),
        ".twig": ("template", "twig"),
        ".jinja": ("template", "jinja"),
        ".j2": ("template", "jinja"),
        
        # Configuration
        ".json": ("config", "json"),
        ".yaml": ("config", "yaml"),
        ".yml": ("config", "yaml"),
        ".toml": ("config", "toml"),
        ".ini": ("config", "ini"),
        ".cfg": ("config", "ini"),
        ".conf": ("config", "conf"),
        ".env": ("config", "env"),
        ".properties": ("config", "properties"),
        ".plist": ("config", "plist"),
        
        # Documentation
        ".md": ("docs", "markdown"),
        ".rst": ("docs", "restructuredtext"),
        ".txt": ("docs", "text"),
        ".adoc": ("docs", "asciidoc"),
        ".org": ("docs", "org"),
        ".tex": ("docs", "latex"),
        
        # Database
        ".sql": ("database", "sql"),
        ".graphql": ("database", "graphql"),
        ".gql": ("database", "graphql"),
        
        # Test files
        ".test.js": ("test", "javascript"),
        ".test.ts": ("test", "typescript"),
        ".spec.js": ("test", "javascript"),
        ".spec.ts": ("test", "typescript"),
        ".test.py": ("test", "python"),
        ".spec.py": ("test", "python"),
        
        # Build and package
        ".dockerfile": ("build", "dockerfile"),
        ".dockerignore": ("build", "docker"),
        "Makefile": ("build", "makefile"),
        "CMakeLists.txt": ("build", "cmake"),
        ".gradle": ("build", "gradle"),
        "pom.xml": ("build", "maven"),
        "build.xml": ("build", "ant"),
        "package.json": ("build", "npm"),
        "composer.json": ("build", "composer"),
        "Cargo.toml": ("build", "cargo"),
        "setup.py": ("build", "python"),
        "requirements.txt": ("build", "python"),
        "Pipfile": ("build", "python"),
        "pyproject.toml": ("build", "python"),
    }
    
    SPECIAL_NAMES = {
        "README": ("docs", "readme"),
        "LICENSE": ("docs", "license"),
        "CHANGELOG": ("docs", "changelog"),
        "CONTRIBUTING": ("docs", "contributing"),
        "CODE_OF_CONDUCT": ("docs", "code_of_conduct"),
        "SECURITY": ("docs", "security"),
        ".gitignore": ("config", "gitignore"),
        ".gitattributes": ("config", "git"),
        ".editorconfig": ("config", "editorconfig"),
        ".eslintrc": ("config", "eslint"),
        ".prettierrc": ("config", "prettier"),
        ".babelrc": ("config", "babel"),
        "tsconfig.json": ("config", "typescript"),
        "webpack.config.js": ("config", "webpack"),
        "rollup.config.js": ("config", "rollup"),
        "vite.config.js": ("config", "vite"),
        "next.config.js": ("config", "nextjs"),
        "nuxt.config.js": ("config", "nuxtjs"),
        "gatsby-config.js": ("config", "gatsby"),
    }
    
    def classify_file(self, file_path: Path) -> Tuple[str, Optional[str]]:
        """Classify file type and language."""
        name = file_path.name
        stem = file_path.stem
        suffix = file_path.suffix.lower()
        
        # Check special file names first
        if name in self.SPECIAL_NAMES:
            return self.SPECIAL_NAMES[name]
        
        # Check stem for special patterns (like README.md)
        if stem.upper() in self.SPECIAL_NAMES:
            return self.SPECIAL_NAMES[stem.upper()]
        
        # Check for test files by name pattern
        if any(pattern in name.lower() for pattern in [".test.", ".spec.", "_test.", "_spec."]):
            base_ext = suffix
            if base_ext in self.FILE_TYPE_MAPPING:
                _, lang = self.FILE_TYPE_MAPPING[base_ext]
                return ("test", lang)
        
        # Check extension mapping
        if suffix in self.FILE_TYPE_MAPPING:
            return self.FILE_TYPE_MAPPING[suffix]
        
        # Default classification
        if suffix:
            return ("unknown", suffix[1:])
        else:
            return ("unknown", None)


class ScannerStats:
    """Scanner performance statistics."""
    
    def __init__(self):
        self.files_discovered = 0
        self.files_processed = 0
        self.files_skipped = 0
        self.files_errored = 0
        self.bytes_processed = 0
        self.start_time = time.time()
        self.directories_scanned = 0
        self.current_depth = 0
        self.max_depth = 0
        self.errors: List[str] = []
    
    @property
    def elapsed_time(self) -> float:
        """Get elapsed time in seconds."""
        return time.time() - self.start_time
    
    @property
    def files_per_second(self) -> float:
        """Get files processed per second."""
        elapsed = self.elapsed_time
        return self.files_processed / elapsed if elapsed > 0 else 0
    
    @property
    def bytes_per_second(self) -> float:
        """Get bytes processed per second."""
        elapsed = self.elapsed_time
        return self.bytes_processed / elapsed if elapsed > 0 else 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "files_discovered": self.files_discovered,
            "files_processed": self.files_processed,
            "files_skipped": self.files_skipped,
            "files_errored": self.files_errored,
            "bytes_processed": self.bytes_processed,
            "elapsed_time": self.elapsed_time,
            "files_per_second": self.files_per_second,
            "bytes_per_second": self.bytes_per_second,
            "directories_scanned": self.directories_scanned,
            "current_depth": self.current_depth,
            "max_depth": self.max_depth,
            "error_count": len(self.errors),
        }


class AsyncFileScanner:
    """High-performance async file scanner."""
    
    def __init__(self, project_id: int, root_path: Path, config: Optional[Dict] = None):
        self.project_id = project_id
        self.root_path = Path(root_path).resolve()
        self.config = config or get_project_config().get_scanning_config()
        self.settings = get_settings()
        
        # Initialize components
        self.classifier = FileClassifier()
        self.stats = ScannerStats()
        
        # Pattern matching
        self.include_spec = self._create_pathspec(self.config.get("include_patterns", []))
        self.exclude_spec = self._create_pathspec(self.config.get("exclude_patterns", []))
        
        # Performance limits
        self.max_file_size = self.settings.max_file_size_bytes
        self.max_concurrent = self.settings.max_concurrent_workers
        self.batch_size = self.settings.scan_batch_size
        
        # Emergency stops
        self.max_depth = self.config.get("scan_depth", {}).get("max_directory_depth", 20)
        self.emergency_file_limit = self.config.get("scan_depth", {}).get("emergency_stop_file_count", 100000)
        
        # State
        self._running = False
        self._paused = False
        self._semaphore = asyncio.Semaphore(self.max_concurrent)
        
        logger.info(
            "Initialized async file scanner",
            project_id=project_id,
            root_path=str(self.root_path),
            max_concurrent=self.max_concurrent,
            batch_size=self.batch_size,
        )
    
    def _create_pathspec(self, patterns: List[str]) -> PathSpec:
        """Create PathSpec from patterns."""
        if not patterns:
            return PathSpec.from_lines("gitwildmatch", [])
        return PathSpec.from_lines("gitwildmatch", patterns)
    
    def _should_include_file(self, file_path: Path) -> bool:
        """Check if file should be included in scan."""
        relative_path = str(file_path.relative_to(self.root_path))
        
        # Check file size
        try:
            if file_path.stat().st_size > self.max_file_size:
                logger.debug("File too large, skipping", file=relative_path, size=file_path.stat().st_size)
                return False
        except OSError:
            return False
        
        # Check exclude patterns first
        if self.exclude_spec.match_file(relative_path):
            return False
        
        # Check include patterns
        if self.include_spec.patterns:
            return self.include_spec.match_file(relative_path)
        
        # If no include patterns, include by default (unless excluded)
        return True
    
    def _should_include_directory(self, dir_path: Path) -> bool:
        """Check if directory should be scanned."""
        relative_path = str(dir_path.relative_to(self.root_path))
        
        # Check exclude patterns
        if self.exclude_spec.match_file(relative_path):
            return False
        
        # Always scan directories unless explicitly excluded
        return True
    
    async def _calculate_file_hash(self, file_path: Path) -> Optional[str]:
        """Calculate SHA-256 hash of file content."""
        try:
            hash_sha256 = hashlib.sha256()
            async with aiofiles.open(file_path, 'rb') as f:
                async for chunk in f:
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        except Exception as e:
            logger.warning("Failed to calculate file hash", file=str(file_path), error=str(e))
            return None
    
    async def _detect_encoding(self, file_path: Path) -> Optional[str]:
        """Detect file encoding."""
        try:
            import chardet
            
            async with aiofiles.open(file_path, 'rb') as f:
                raw_data = await f.read(8192)  # Read first 8KB
                result = chardet.detect(raw_data)
                return result.get('encoding') if result else None
        except Exception:
            return None
    
    async def _analyze_file(self, file_path: Path) -> Optional[FileInfo]:
        """Analyze a single file and extract metadata."""
        async with self._semaphore:
            try:
                # Basic file info
                stat = file_path.stat()
                file_info = FileInfo(
                    path=file_path,
                    root_path=self.root_path,
                    size=stat.st_size,
                    modified_time=datetime.fromtimestamp(stat.st_mtime),
                    created_time=datetime.fromtimestamp(stat.st_ctime),
                )
                
                # Classify file
                file_type, language = self.classifier.classify_file(file_path)
                file_info.file_type = file_type
                file_info.language = language
                
                # Detect MIME type
                mime_type, _ = mimetypes.guess_type(str(file_path))
                file_info.mime_type = mime_type
                
                # For text files, get encoding and hash
                if file_type in ["code", "config", "docs", "markup", "style", "template"]:
                    # Calculate hash for content comparison
                    file_info.content_hash = await self._calculate_file_hash(file_path)
                    
                    # Detect encoding for text files
                    file_info.encoding = await self._detect_encoding(file_path)
                
                self.stats.files_processed += 1
                self.stats.bytes_processed += stat.st_size
                
                return file_info
                
            except Exception as e:
                self.stats.files_errored += 1
                self.stats.errors.append(f"{file_path}: {str(e)}")
                logger.error("Error analyzing file", file=str(file_path), error=str(e))
                return None
    
    async def _discover_files(self, start_path: Optional[Path] = None) -> AsyncGenerator[Path, None]:
        """Discover files recursively with depth limits."""
        start_path = start_path or self.root_path
        
        async def _scan_directory(directory: Path, depth: int = 0) -> AsyncGenerator[Path, None]:
            if depth > self.max_depth:
                logger.warning("Maximum directory depth reached", path=str(directory), depth=depth)
                return
            
            if self.stats.files_discovered > self.emergency_file_limit:
                logger.error("Emergency file limit reached", limit=self.emergency_file_limit)
                return
            
            self.stats.current_depth = depth
            self.stats.max_depth = max(self.stats.max_depth, depth)
            
            try:
                # Check if directory should be included
                if not self._should_include_directory(directory):
                    logger.debug("Directory excluded", path=str(directory))
                    return
                
                self.stats.directories_scanned += 1
                
                # Scan directory contents
                entries = []
                try:
                    for entry in directory.iterdir():
                        entries.append(entry)
                except PermissionError:
                    logger.warning("Permission denied", path=str(directory))
                    return
                
                # Process files first
                for entry in entries:
                    if not self._running:
                        return
                    
                    if entry.is_file():
                        if self._should_include_file(entry):
                            self.stats.files_discovered += 1
                            yield entry
                        else:
                            self.stats.files_skipped += 1
                
                # Then recurse into subdirectories
                for entry in entries:
                    if not self._running:
                        return
                    
                    if entry.is_dir() and not entry.is_symlink():
                        async for file_path in _scan_directory(entry, depth + 1):
                            yield file_path
                            
            except Exception as e:
                logger.error("Error scanning directory", path=str(directory), error=str(e))
                self.stats.errors.append(f"Directory {directory}: {str(e)}")
        
        async for file_path in _scan_directory(start_path):
            yield file_path
    
    async def scan_project(self, batch_callback: Optional[callable] = None) -> ScannerStats:
        """Scan entire project and yield file batches."""
        logger.info("Starting project scan", project_id=self.project_id, root_path=str(self.root_path))
        
        self._running = True
        self.stats = ScannerStats()
        
        try:
            # Update project status
            async with get_db_session() as session:
                await project_repo.update(session, self.project_id, status=ProjectStatus.SCANNING)
            
            batch = []
            
            async for file_path in self._discover_files():
                if not self._running:
                    break
                
                # Analyze file
                file_info = await self._analyze_file(file_path)
                if file_info:
                    batch.append(file_info)
                
                # Process batch when full
                if len(batch) >= self.batch_size:
                    if batch_callback:
                        await batch_callback(batch)
                    else:
                        await self._save_file_batch(batch)
                    batch = []
                
                # Log progress periodically
                if self.stats.files_processed % 1000 == 0:
                    logger.info(
                        "Scan progress",
                        files_processed=self.stats.files_processed,
                        files_per_second=self.stats.files_per_second,
                        elapsed_time=self.stats.elapsed_time,
                    )
            
            # Process remaining files in batch
            if batch:
                if batch_callback:
                    await batch_callback(batch)
                else:
                    await self._save_file_batch(batch)
            
            # Update project status
            async with get_db_session() as session:
                await project_repo.update(session, self.project_id, status=ProjectStatus.INDEXED)
                await project_repo.update_statistics(session, self.project_id)
            
            logger.info(
                "Project scan completed",
                project_id=self.project_id,
                stats=self.stats.to_dict(),
            )
            
        except Exception as e:
            logger.error("Project scan failed", project_id=self.project_id, error=str(e))
            # Update project status to error
            async with get_db_session() as session:
                await project_repo.update(session, self.project_id, status=ProjectStatus.ERROR)
            raise
        finally:
            self._running = False
        
        return self.stats
    
    async def _save_file_batch(self, file_batch: List[FileInfo]) -> None:
        """Save a batch of files to database."""
        try:
            async with get_db_session() as session:
                for file_info in file_batch:
                    # Check if file already exists
                    existing_file = await file_repo.get_by_path(
                        session, self.project_id, file_info.relative_path
                    )
                    
                    if existing_file:
                        # Update existing file if hash changed
                        if existing_file.content_hash != file_info.content_hash:
                            await file_repo.update(
                                session,
                                existing_file.id,
                                **file_info.to_dict()
                            )
                    else:
                        # Create new file record
                        file_data = file_info.to_dict()
                        file_data["project_id"] = self.project_id
                        await file_repo.create(session, **file_data)
                        
        except Exception as e:
            logger.error("Failed to save file batch", error=str(e))
            raise
    
    def stop(self) -> None:
        """Stop the scanner."""
        logger.info("Stopping file scanner", project_id=self.project_id)
        self._running = False
    
    def pause(self) -> None:
        """Pause the scanner."""
        logger.info("Pausing file scanner", project_id=self.project_id)
        self._paused = True
    
    def resume(self) -> None:
        """Resume the scanner."""
        logger.info("Resuming file scanner", project_id=self.project_id)
        self._paused = False


# Convenience function for quick scanning
async def scan_project_files(
    project_id: int,
    root_path: Path,
    config: Optional[Dict] = None,
    batch_callback: Optional[callable] = None,
) -> ScannerStats:
    """Scan project files with default scanner."""
    scanner = AsyncFileScanner(project_id, root_path, config)
    return await scanner.scan_project(batch_callback) 