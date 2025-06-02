"""Content Analysis Engine

Analyzes file content to extract imports, dependencies, cross-reference patterns,
and relationships for comprehensive cross-reference generation.
"""

import re
import ast
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any, Union

import structlog
from src.database.operations import file_repo, get_db_session
from src.utils.config import get_settings

logger = structlog.get_logger(__name__)


@dataclass
class ImportInfo:
    """Information about an import statement."""
    module: str
    alias: Optional[str] = None
    is_relative: bool = False
    line_number: int = 0
    import_type: str = "import"  # import, from_import, include, require, etc.
    file_path: Optional[str] = None  # For relative imports


@dataclass
class CrossReference:
    """Represents a cross-reference between files."""
    source_file: str
    target_file: str
    reference_type: str  # import, mention, link, dependency
    confidence: float = 1.0
    line_number: Optional[int] = None
    context: Optional[str] = None


@dataclass
class ContentPattern:
    """Detected pattern in content."""
    pattern_type: str  # cross_ref_header, hub_file, dependency, etc.
    content: str
    line_number: int
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AnalysisResult:
    """Result of content analysis."""
    file_path: str
    imports: List[ImportInfo] = field(default_factory=list)
    cross_references: List[CrossReference] = field(default_factory=list)
    patterns: List[ContentPattern] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    exports: List[str] = field(default_factory=list)
    hub_file_candidates: List[str] = field(default_factory=list)
    language: Optional[str] = None
    encoding: Optional[str] = None
    analysis_timestamp: Optional[str] = None


class LanguageAnalyzer(ABC):
    """Base class for language-specific analyzers."""
    
    @abstractmethod
    def analyze_imports(self, content: str, file_path: str) -> List[ImportInfo]:
        """Extract import information from content."""
        pass
    
    @abstractmethod
    def analyze_exports(self, content: str) -> List[str]:
        """Extract export information from content."""
        pass
    
    @abstractmethod
    def analyze_dependencies(self, content: str) -> List[str]:
        """Extract dependency information from content."""
        pass


class PythonAnalyzer(LanguageAnalyzer):
    """Analyzer for Python files."""
    
    def analyze_imports(self, content: str, file_path: str) -> List[ImportInfo]:
        """Extract Python imports."""
        imports = []
        
        try:
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(ImportInfo(
                            module=alias.name,
                            alias=alias.asname,
                            line_number=node.lineno,
                            import_type="import"
                        ))
                
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        for alias in node.names:
                            imports.append(ImportInfo(
                                module=f"{node.module}.{alias.name}" if alias.name != "*" else node.module,
                                alias=alias.asname,
                                is_relative=node.level > 0,
                                line_number=node.lineno,
                                import_type="from_import"
                            ))
        
        except SyntaxError:
            # Fallback to regex parsing for files with syntax errors
            imports.extend(self._regex_parse_imports(content))
        
        return imports
    
    def _regex_parse_imports(self, content: str) -> List[ImportInfo]:
        """Fallback regex-based import parsing."""
        imports = []
        lines = content.split('\n')
        
        # Match: import module [as alias]
        import_pattern = re.compile(r'^\s*import\s+([a-zA-Z_][a-zA-Z0-9_.]*)\s*(?:as\s+([a-zA-Z_][a-zA-Z0-9_]*))?\s*$')
        
        # Match: from module import name [as alias]
        from_import_pattern = re.compile(r'^\s*from\s+([a-zA-Z_][a-zA-Z0-9_.]*)\s+import\s+([a-zA-Z_*][a-zA-Z0-9_,\s*]*)\s*$')
        
        for i, line in enumerate(lines, 1):
            # Simple import
            match = import_pattern.match(line)
            if match:
                imports.append(ImportInfo(
                    module=match.group(1),
                    alias=match.group(2),
                    line_number=i,
                    import_type="import"
                ))
                continue
            
            # From import
            match = from_import_pattern.match(line)
            if match:
                module = match.group(1)
                names = match.group(2)
                
                if names.strip() == "*":
                    imports.append(ImportInfo(
                        module=module,
                        line_number=i,
                        import_type="from_import"
                    ))
                else:
                    for name in names.split(','):
                        name = name.strip()
                        if ' as ' in name:
                            actual_name, alias = name.split(' as ', 1)
                            imports.append(ImportInfo(
                                module=f"{module}.{actual_name.strip()}",
                                alias=alias.strip(),
                                line_number=i,
                                import_type="from_import"
                            ))
                        else:
                            imports.append(ImportInfo(
                                module=f"{module}.{name}",
                                line_number=i,
                                import_type="from_import"
                            ))
        
        return imports
    
    def analyze_exports(self, content: str) -> List[str]:
        """Extract Python exports (__all__, class/function definitions)."""
        exports = []
        
        try:
            tree = ast.parse(content)
            
            # Look for __all__ definition
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id == "__all__":
                            if isinstance(node.value, (ast.List, ast.Tuple)):
                                for elt in node.value.elts:
                                    if isinstance(elt, ast.Str):
                                        exports.append(elt.s)
                                    elif isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                                        exports.append(elt.value)
                
                # Public functions and classes
                elif isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
                    if not node.name.startswith('_'):
                        exports.append(node.name)
        
        except SyntaxError:
            # Fallback to regex
            all_pattern = re.compile(r'__all__\s*=\s*\[(.*?)\]', re.DOTALL)
            match = all_pattern.search(content)
            if match:
                items = re.findall(r'["\']([^"\']+)["\']', match.group(1))
                exports.extend(items)
        
        return exports
    
    def analyze_dependencies(self, content: str) -> List[str]:
        """Extract dependencies from Python files."""
        dependencies = set()
        
        # Extract from imports
        for imp in self.analyze_imports(content, ""):
            # Split module to get top-level package
            top_level = imp.module.split('.')[0]
            dependencies.add(top_level)
        
        return list(dependencies)


class JavaScriptAnalyzer(LanguageAnalyzer):
    """Analyzer for JavaScript/TypeScript files."""
    
    def analyze_imports(self, content: str, file_path: str) -> List[ImportInfo]:
        """Extract JavaScript/TypeScript imports."""
        imports = []
        lines = content.split('\n')
        
        # ES6 import patterns
        import_patterns = [
            # import module from 'path'
            re.compile(r'^\s*import\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s+from\s+["\']([^"\']+)["\']\s*;?\s*$'),
            # import { named } from 'path' 
            re.compile(r'^\s*import\s+\{\s*([^}]+)\s*\}\s+from\s+["\']([^"\']+)["\']\s*;?\s*$'),
            # import * as alias from 'path'
            re.compile(r'^\s*import\s+\*\s+as\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s+from\s+["\']([^"\']+)["\']\s*;?\s*$'),
            # import 'path'
            re.compile(r'^\s*import\s+["\']([^"\']+)["\']\s*;?\s*$'),
        ]
        
        # CommonJS require patterns
        require_patterns = [
            # const module = require('path')
            re.compile(r'^\s*(?:const|let|var)\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*=\s*require\s*\(\s*["\']([^"\']+)["\']\s*\)\s*;?\s*$'),
            # const { named } = require('path')
            re.compile(r'^\s*(?:const|let|var)\s+\{\s*([^}]+)\s*\}\s*=\s*require\s*\(\s*["\']([^"\']+)["\']\s*\)\s*;?\s*$'),
        ]
        
        for i, line in enumerate(lines, 1):
            # ES6 imports
            for pattern in import_patterns:
                match = pattern.match(line)
                if match:
                    if len(match.groups()) == 2:
                        imports.append(ImportInfo(
                            module=match.group(2),
                            alias=match.group(1),
                            is_relative=match.group(2).startswith('.'),
                            line_number=i,
                            import_type="es6_import"
                        ))
                    else:
                        imports.append(ImportInfo(
                            module=match.group(1),
                            is_relative=match.group(1).startswith('.'),
                            line_number=i,
                            import_type="es6_import"
                        ))
                    break
            
            # CommonJS requires
            for pattern in require_patterns:
                match = pattern.match(line)
                if match:
                    imports.append(ImportInfo(
                        module=match.group(2),
                        alias=match.group(1),
                        is_relative=match.group(2).startswith('.'),
                        line_number=i,
                        import_type="commonjs_require"
                    ))
                    break
        
        return imports
    
    def analyze_exports(self, content: str) -> List[str]:
        """Extract JavaScript/TypeScript exports."""
        exports = []
        lines = content.split('\n')
        
        export_patterns = [
            # export default
            re.compile(r'^\s*export\s+default\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*;?\s*$'),
            # export function/class/const
            re.compile(r'^\s*export\s+(?:function|class|const|let|var)\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*'),
            # export { named }
            re.compile(r'^\s*export\s+\{\s*([^}]+)\s*\}\s*;?\s*$'),
        ]
        
        for line in lines:
            for pattern in export_patterns:
                match = pattern.match(line)
                if match:
                    if 'export default' in line:
                        exports.append('default')
                    elif 'export {' in line:
                        # Parse named exports
                        names = match.group(1)
                        for name in names.split(','):
                            name = name.strip()
                            if ' as ' in name:
                                name = name.split(' as ')[1].strip()
                            exports.append(name)
                    else:
                        exports.append(match.group(1))
                    break
        
        return exports
    
    def analyze_dependencies(self, content: str) -> List[str]:
        """Extract dependencies from JavaScript/TypeScript files."""
        dependencies = set()
        
        for imp in self.analyze_imports(content, ""):
            if not imp.is_relative:
                # Extract package name (handle scoped packages)
                module = imp.module
                if module.startswith('@'):
                    parts = module.split('/')
                    if len(parts) >= 2:
                        dependencies.add(f"{parts[0]}/{parts[1]}")
                else:
                    dependencies.add(module.split('/')[0])
        
        return list(dependencies)


class MarkdownAnalyzer(LanguageAnalyzer):
    """Analyzer for Markdown files."""
    
    def analyze_imports(self, content: str, file_path: str) -> List[ImportInfo]:
        """Extract markdown links and includes."""
        imports = []
        lines = content.split('\n')
        
        # Link patterns
        link_patterns = [
            # [text](path)
            re.compile(r'\[([^\]]+)\]\(([^)]+)\)'),
            # [text]: path
            re.compile(r'^\s*\[([^\]]+)\]:\s*(.+)$'),
        ]
        
        for i, line in enumerate(lines, 1):
            for pattern in link_patterns:
                matches = pattern.findall(line)
                for text, path in matches:
                    # Filter out external URLs
                    if not path.startswith(('http:', 'https:', 'mailto:')):
                        imports.append(ImportInfo(
                            module=path,
                            alias=text,
                            is_relative=True,
                            line_number=i,
                            import_type="markdown_link"
                        ))
        
        return imports
    
    def analyze_exports(self, content: str) -> List[str]:
        """Extract headings as exports."""
        exports = []
        lines = content.split('\n')
        
        heading_pattern = re.compile(r'^(#{1,6})\s+(.+)$')
        
        for line in lines:
            match = heading_pattern.match(line)
            if match:
                exports.append(match.group(2).strip())
        
        return exports
    
    def analyze_dependencies(self, content: str) -> List[str]:
        """Extract referenced files from markdown."""
        dependencies = set()
        
        for imp in self.analyze_imports(content, ""):
            # Clean the path
            path = imp.module.split('#')[0]  # Remove anchors
            if path and not path.startswith(('http:', 'https:')):
                dependencies.add(path)
        
        return list(dependencies)


class CrossReferenceDetector:
    """Detects cross-reference patterns in content."""
    
    def __init__(self):
        # Cross-reference header patterns from methodology
        self.crossref_patterns = [
            # Warning patterns
            re.compile(r'⚠️\s*IMPORTANT:?\s*When reading this file you HAVE TO.*?read.*?files?.*?`([^`]+)`', re.IGNORECASE | re.DOTALL),
            re.compile(r'Cross-reference:?\s*(?:This document|Read with|Also read).*?`([^`]+)`', re.IGNORECASE),
            re.compile(r'MUST READ:?\s*`([^`]+)`', re.IGNORECASE),
            re.compile(r'Related files?:?\s*`([^`]+)`', re.IGNORECASE),
            
            # Hub file patterns
            re.compile(r'central hub|main.*?documentation|primary.*?system.*?documentation', re.IGNORECASE),
            re.compile(r'mandatory reading|complete.*?picture|all related files', re.IGNORECASE),
        ]
    
    def detect_crossref_headers(self, content: str) -> List[ContentPattern]:
        """Detect cross-reference headers in content."""
        patterns = []
        lines = content.split('\n')
        
        for i, line in enumerate(lines, 1):
            for pattern in self.crossref_patterns:
                match = pattern.search(line)
                if match:
                    pattern_type = "cross_ref_header"
                    confidence = 0.9
                    
                    # Determine specific type
                    if "⚠️" in line or "IMPORTANT" in line.upper():
                        pattern_type = "warning_crossref"
                        confidence = 1.0
                    elif "hub" in line.lower() or "central" in line.lower():
                        pattern_type = "hub_file_reference"
                        confidence = 0.8
                    
                    patterns.append(ContentPattern(
                        pattern_type=pattern_type,
                        content=line.strip(),
                        line_number=i,
                        confidence=confidence,
                        metadata={"referenced_files": match.groups() if match.groups() else []}
                    ))
        
        return patterns
    
    def detect_hub_files(self, content: str, file_path: str) -> List[ContentPattern]:
        """Detect if file is a hub file (central documentation)."""
        patterns = []
        
        # Check file name patterns
        file_name = Path(file_path).name.lower()
        hub_names = ['readme', 'index', 'main', 'system', 'about', 'overview']
        
        if any(name in file_name for name in hub_names):
            patterns.append(ContentPattern(
                pattern_type="hub_file",
                content=f"Hub file detected: {file_name}",
                line_number=1,
                confidence=0.8,
                metadata={"hub_type": "filename_based"}
            ))
        
        # Check content patterns
        hub_indicators = [
            "mandatory reading",
            "cross-reference reading requirement",
            "complete system",
            "central hub",
            "main entry point",
        ]
        
        content_lower = content.lower()
        for indicator in hub_indicators:
            if indicator in content_lower:
                patterns.append(ContentPattern(
                    pattern_type="hub_file",
                    content=f"Hub content detected: {indicator}",
                    line_number=1,
                    confidence=0.9,
                    metadata={"hub_type": "content_based", "indicator": indicator}
                ))
        
        return patterns


class ContentAnalyzer:
    """Main content analysis engine."""
    
    def __init__(self):
        self.language_analyzers = {
            'python': PythonAnalyzer(),
            'javascript': JavaScriptAnalyzer(),
            'typescript': JavaScriptAnalyzer(),  # Use JS analyzer for TS
            'markdown': MarkdownAnalyzer(),
        }
        
        self.crossref_detector = CrossReferenceDetector()
        self.settings = get_settings()
        
    def analyze_file(self, file_path: str, content: str, language: Optional[str] = None) -> AnalysisResult:
        """Analyze a single file's content."""
        logger.debug("Analyzing file content", file=file_path, language=language)
        
        result = AnalysisResult(
            file_path=file_path,
            language=language,
        )
        
        try:
            # Get appropriate analyzer
            analyzer = self._get_analyzer(language)
            
            if analyzer:
                # Extract imports and dependencies
                result.imports = analyzer.analyze_imports(content, file_path)
                result.exports = analyzer.analyze_exports(content)
                result.dependencies = analyzer.analyze_dependencies(content)
            
            # Detect cross-reference patterns
            result.patterns.extend(self.crossref_detector.detect_crossref_headers(content))
            result.patterns.extend(self.crossref_detector.detect_hub_files(content, file_path))
            
            # Generate cross-references from imports
            result.cross_references = self._generate_cross_references(result.imports, file_path)
            
            # Identify hub file candidates
            if any(p.pattern_type == "hub_file" for p in result.patterns):
                result.hub_file_candidates.append(file_path)
            
            logger.debug(
                "File analysis complete",
                file=file_path,
                imports=len(result.imports),
                exports=len(result.exports),
                patterns=len(result.patterns),
                cross_refs=len(result.cross_references),
            )
            
        except Exception as e:
            logger.error("Error analyzing file content", file=file_path, error=str(e))
        
        return result
    
    def _get_analyzer(self, language: Optional[str]) -> Optional[LanguageAnalyzer]:
        """Get appropriate language analyzer."""
        if not language:
            return None
        
        # Map language variations
        language_mapping = {
            'js': 'javascript',
            'jsx': 'javascript', 
            'ts': 'typescript',
            'tsx': 'typescript',
            'py': 'python',
            'md': 'markdown',
            'rst': 'markdown',  # Use markdown analyzer for reStructuredText
        }
        
        mapped_language = language_mapping.get(language.lower(), language.lower())
        return self.language_analyzers.get(mapped_language)
    
    def _generate_cross_references(self, imports: List[ImportInfo], source_file: str) -> List[CrossReference]:
        """Generate cross-references from import information."""
        cross_refs = []
        
        for imp in imports:
            # Determine reference type
            ref_type = "import"
            if imp.import_type in ["markdown_link"]:
                ref_type = "link"
            
            # Calculate confidence based on import type
            confidence = 1.0
            if imp.is_relative:
                confidence = 0.9  # Relative imports are high confidence
            elif imp.import_type == "markdown_link":
                confidence = 0.7  # Links have medium confidence
            
            cross_refs.append(CrossReference(
                source_file=source_file,
                target_file=imp.module,
                reference_type=ref_type,
                confidence=confidence,
                line_number=imp.line_number,
                context=f"{imp.import_type}: {imp.module}" + (f" as {imp.alias}" if imp.alias else "")
            ))
        
        return cross_refs
    
    async def analyze_project_files(self, project_id: int) -> Dict[str, AnalysisResult]:
        """Analyze all files in a project."""
        logger.info("Starting project content analysis", project_id=project_id)
        
        results = {}
        
        try:
            async with get_db_session() as session:
                # Get all text files from the project
                files = await file_repo.get_text_files_by_project(session, project_id)
                
                total_files = len(files)
                logger.info("Analyzing project files", project_id=project_id, file_count=total_files)
                
                for i, file_record in enumerate(files, 1):
                    content = None
                    resolved_encoding = file_record.encoding
                    try:
                        # Read file content
                        file_path = Path(file_record.path)
                        if file_path.exists() and file_path.is_file():
                            try:
                                content = file_path.read_text(encoding=resolved_encoding or 'utf-8')
                            except UnicodeDecodeError as ude:
                                logger.warning(
                                    "Encoding error with detected encoding", 
                                    file=file_record.relative_path, 
                                    detected_encoding=resolved_encoding,
                                    error=str(ude)
                                )
                                # If detected encoding failed and it wasn't utf-8, try utf-8
                                if resolved_encoding and resolved_encoding.lower() != 'utf-8':
                                    logger.info("Retrying with UTF-8 encoding", file=file_record.relative_path)
                                    try:
                                        content = file_path.read_text(encoding='utf-8')
                                        resolved_encoding = 'utf-8'
                                    except UnicodeDecodeError as ude_utf8:
                                        logger.error(
                                            "Encoding error even with UTF-8", 
                                            file=file_record.relative_path, 
                                            error=str(ude_utf8)
                                        )
                                        # As a last resort, try 'latin-1' which rarely fails but might produce mojibake
                                        try:
                                            content = file_path.read_text(encoding='latin-1')
                                            resolved_encoding = 'latin-1'
                                            logger.warning("Read file with Latin-1 as last resort", file=file_record.relative_path)
                                        except Exception as e_latin1:
                                            logger.error("Failed to read file with any encoding", file=file_record.relative_path, error=str(e_latin1))
                                            continue # Skip this file
                                else:
                                    # If detected was already utf-8 or None, and it failed, try latin-1
                                    logger.info("Retrying with Latin-1 encoding", file=file_record.relative_path)
                                    try:
                                        content = file_path.read_text(encoding='latin-1')
                                        resolved_encoding = 'latin-1'
                                        logger.warning("Read file with Latin-1 as last resort", file=file_record.relative_path)
                                    except Exception as e_latin1:
                                        logger.error("Failed to read file with any encoding", file=file_record.relative_path, error=str(e_latin1))
                                        continue # Skip this file

                            if content is not None:
                                # Analyze content
                                result = self.analyze_file(
                                    file_record.relative_path,
                                    content,
                                    file_record.language
                                )
                                # Update AnalysisResult with the encoding that worked
                                result.encoding = resolved_encoding 
                                results[file_record.relative_path] = result
                            else:
                                logger.warning("Skipping file due to read error", file=file_record.relative_path)
                        
                        # Log progress
                        if i % 100 == 0 or i == total_files:
                            logger.info(
                                "Analysis progress",
                                project_id=project_id,
                                processed=i,
                                total=total_files,
                                percent=round((i / total_files) * 100, 1)
                            )
                    
                    except Exception as e:
                        logger.error(
                            "Error analyzing file",
                            project_id=project_id,
                            file=file_record.relative_path,
                            error=str(e)
                        )
                
                logger.info(
                    "Project content analysis complete",
                    project_id=project_id,
                    analyzed_files=len(results)
                )
        
        except Exception as e:
            logger.error("Project analysis failed", project_id=project_id, error=str(e))
            raise
        
        return results


# Convenience function for single file analysis
async def analyze_file_content(file_path: str, content: str, language: Optional[str] = None) -> AnalysisResult:
    """Analyze content of a single file."""
    analyzer = ContentAnalyzer()
    return analyzer.analyze_file(file_path, content, language)


# Convenience function for project analysis
async def analyze_project_content(project_id: int) -> Dict[str, AnalysisResult]:
    """Analyze all files in a project."""
    analyzer = ContentAnalyzer()
    return await analyzer.analyze_project_files(project_id) 