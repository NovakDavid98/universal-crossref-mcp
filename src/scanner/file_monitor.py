"""Real-Time File Monitoring System

File system monitoring for real-time change detection and incremental scanning.
"""

import asyncio
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set, Callable, Any

import structlog
from watchdog.events import (
    FileSystemEventHandler,
    FileSystemEvent,
    FileCreatedEvent,
    FileModifiedEvent,
    FileDeletedEvent,
    FileMovedEvent,
    DirCreatedEvent,
    DirDeletedEvent,
    DirModifiedEvent,
    DirMovedEvent,
)
from watchdog.observers import Observer

from src.database.models import FileStatus
from src.database.operations import file_repo, project_repo, get_db_session
from src.scanner.file_scanner import AsyncFileScanner, FileInfo
from src.utils.config import get_settings, get_project_config

logger = structlog.get_logger(__name__)


class FileChangeEvent:
    """Represents a file system change event."""
    
    def __init__(
        self,
        event_type: str,
        file_path: Path,
        is_directory: bool = False,
        old_path: Optional[Path] = None,
        timestamp: Optional[datetime] = None,
    ):
        self.event_type = event_type  # created, modified, deleted, moved
        self.file_path = file_path
        self.is_directory = is_directory
        self.old_path = old_path  # For move events
        self.timestamp = timestamp or datetime.now()
    
    def __repr__(self) -> str:
        return f"<FileChangeEvent({self.event_type}, {self.file_path})>"


class ChangeBuffer:
    """Buffer file changes to avoid excessive processing."""
    
    def __init__(self, buffer_time: float = 2.0, max_size: int = 1000):
        self.buffer_time = buffer_time  # seconds to wait before processing
        self.max_size = max_size
        self._changes: Dict[Path, FileChangeEvent] = {}
        self._last_change_time: Dict[Path, float] = {}
        self._lock = asyncio.Lock()
    
    async def add_change(self, event: FileChangeEvent) -> None:
        """Add a change event to the buffer."""
        async with self._lock:
            current_time = time.time()
            
            # Update the change (later events override earlier ones for same file)
            self._changes[event.file_path] = event
            self._last_change_time[event.file_path] = current_time
            
            # If buffer is getting too large, force a flush
            if len(self._changes) >= self.max_size:
                logger.warning("Change buffer at capacity, forcing flush", size=len(self._changes))
    
    async def get_ready_changes(self) -> List[FileChangeEvent]:
        """Get changes that are ready to be processed."""
        async with self._lock:
            current_time = time.time()
            ready_changes = []
            paths_to_remove = []
            
            for path, last_change_time in self._last_change_time.items():
                if current_time - last_change_time >= self.buffer_time:
                    if path in self._changes:
                        ready_changes.append(self._changes[path])
                        paths_to_remove.append(path)
            
            # Remove processed changes
            for path in paths_to_remove:
                self._changes.pop(path, None)
                self._last_change_time.pop(path, None)
            
            return ready_changes
    
    async def flush_all(self) -> List[FileChangeEvent]:
        """Get all buffered changes immediately."""
        async with self._lock:
            changes = list(self._changes.values())
            self._changes.clear()
            self._last_change_time.clear()
            return changes
    
    @property
    def pending_count(self) -> int:
        """Get number of pending changes."""
        return len(self._changes)


class AsyncFileSystemEventHandler(FileSystemEventHandler):
    """Async file system event handler."""
    
    def __init__(self, monitor: "FileMonitor"):
        super().__init__()
        self.monitor = monitor
        
    def on_created(self, event: FileCreatedEvent) -> None:
        """Handle file/directory creation."""
        asyncio.create_task(self.monitor._handle_event("created", event))
    
    def on_modified(self, event: FileModifiedEvent) -> None:
        """Handle file/directory modification."""
        asyncio.create_task(self.monitor._handle_event("modified", event))
    
    def on_deleted(self, event: FileDeletedEvent) -> None:
        """Handle file/directory deletion."""
        asyncio.create_task(self.monitor._handle_event("deleted", event))
    
    def on_moved(self, event: FileMovedEvent) -> None:
        """Handle file/directory move."""
        asyncio.create_task(self.monitor._handle_event("moved", event))


class FileMonitor:
    """Real-time file system monitor."""
    
    def __init__(
        self,
        project_id: int,
        root_path: Path,
        change_callback: Optional[Callable[[List[FileChangeEvent]], None]] = None,
        config: Optional[Dict] = None,
    ):
        self.project_id = project_id
        self.root_path = Path(root_path).resolve()
        self.change_callback = change_callback
        self.config = config or get_project_config().get_scanning_config()
        self.settings = get_settings()
        
        # Initialize components
        self.scanner = AsyncFileScanner(project_id, root_path, config)
        self.change_buffer = ChangeBuffer(buffer_time=2.0)
        
        # Watchdog setup
        self.observer = Observer()
        self.event_handler = AsyncFileSystemEventHandler(self)
        
        # State
        self._running = False
        self._processing_lock = asyncio.Lock()
        
        # Statistics
        self.events_received = 0
        self.changes_processed = 0
        self.last_scan_time: Optional[datetime] = None
        
        logger.info(
            "Initialized file monitor",
            project_id=project_id,
            root_path=str(self.root_path),
        )
    
    async def start(self) -> None:
        """Start file monitoring."""
        if self._running:
            logger.warning("File monitor already running")
            return
        
        logger.info("Starting file monitor", project_id=self.project_id)
        
        try:
            # Start watchdog observer
            self.observer.schedule(
                self.event_handler,
                str(self.root_path),
                recursive=True
            )
            self.observer.start()
            
            self._running = True
            
            # Start change processing loop
            asyncio.create_task(self._process_changes_loop())
            
            logger.info("File monitor started successfully")
            
        except Exception as e:
            logger.error("Failed to start file monitor", error=str(e))
            raise
    
    async def stop(self) -> None:
        """Stop file monitoring."""
        if not self._running:
            return
        
        logger.info("Stopping file monitor", project_id=self.project_id)
        
        self._running = False
        
        # Stop watchdog observer
        if self.observer.is_alive():
            self.observer.stop()
            self.observer.join()
        
        # Process any remaining changes
        remaining_changes = await self.change_buffer.flush_all()
        if remaining_changes:
            await self._process_changes(remaining_changes)
        
        logger.info("File monitor stopped")
    
    async def _handle_event(self, event_type: str, event: FileSystemEvent) -> None:
        """Handle a file system event."""
        self.events_received += 1
        
        try:
            file_path = Path(event.src_path)
            
            # Skip if not within our root path
            if not self._is_within_root(file_path):
                return
            
            # Skip if should be excluded
            if not self.scanner._should_include_file(file_path) and not event.is_directory:
                return
            
            if not self.scanner._should_include_directory(file_path) and event.is_directory:
                return
            
            # Create change event
            old_path = None
            if hasattr(event, 'dest_path'):
                old_path = Path(event.dest_path)
            
            change_event = FileChangeEvent(
                event_type=event_type,
                file_path=file_path,
                is_directory=event.is_directory,
                old_path=old_path,
            )
            
            # Add to buffer
            await self.change_buffer.add_change(change_event)
            
        except Exception as e:
            logger.error("Error handling file event", event=event, error=str(e))
    
    def _is_within_root(self, path: Path) -> bool:
        """Check if path is within the monitored root path."""
        try:
            path.relative_to(self.root_path)
            return True
        except ValueError:
            return False
    
    async def _process_changes_loop(self) -> None:
        """Background loop to process buffered changes."""
        while self._running:
            try:
                # Get ready changes
                changes = await self.change_buffer.get_ready_changes()
                
                if changes:
                    await self._process_changes(changes)
                
                # Check every second
                await asyncio.sleep(1.0)
                
            except Exception as e:
                logger.error("Error in change processing loop", error=str(e))
                await asyncio.sleep(5.0)  # Wait longer on error
    
    async def _process_changes(self, changes: List[FileChangeEvent]) -> None:
        """Process a batch of file changes."""
        if not changes:
            return
        
        async with self._processing_lock:
            logger.info("Processing file changes", count=len(changes))
            
            try:
                # Group changes by type
                created_files = []
                modified_files = []
                deleted_files = []
                moved_files = []
                
                for change in changes:
                    if change.is_directory:
                        continue  # Skip directory changes for now
                    
                    if change.event_type == "created":
                        created_files.append(change.file_path)
                    elif change.event_type == "modified":
                        modified_files.append(change.file_path)
                    elif change.event_type == "deleted":
                        deleted_files.append(change.file_path)
                    elif change.event_type == "moved":
                        moved_files.append((change.old_path, change.file_path))
                
                # Process each type of change
                if created_files:
                    await self._process_created_files(created_files)
                
                if modified_files:
                    await self._process_modified_files(modified_files)
                
                if deleted_files:
                    await self._process_deleted_files(deleted_files)
                
                if moved_files:
                    await self._process_moved_files(moved_files)
                
                self.changes_processed += len(changes)
                self.last_scan_time = datetime.now()
                
                # Call user callback if provided
                if self.change_callback:
                    try:
                        await self.change_callback(changes)
                    except Exception as e:
                        logger.error("Error in change callback", error=str(e))
                
            except Exception as e:
                logger.error("Error processing changes", error=str(e))
    
    async def _process_created_files(self, file_paths: List[Path]) -> None:
        """Process newly created files."""
        logger.debug("Processing created files", count=len(file_paths))
        
        for file_path in file_paths:
            try:
                if not file_path.exists():
                    continue
                
                # Analyze the new file
                file_info = await self.scanner._analyze_file(file_path)
                if file_info:
                    # Save to database
                    await self._save_file_info(file_info)
                    
            except Exception as e:
                logger.error("Error processing created file", file=str(file_path), error=str(e))
    
    async def _process_modified_files(self, file_paths: List[Path]) -> None:
        """Process modified files."""
        logger.debug("Processing modified files", count=len(file_paths))
        
        async with get_db_session() as session:
            for file_path in file_paths:
                try:
                    if not file_path.exists():
                        continue
                    
                    # Get existing file record
                    relative_path = str(file_path.relative_to(self.root_path))
                    existing_file = await file_repo.get_by_path(
                        session, self.project_id, relative_path
                    )
                    
                    if existing_file:
                        # Re-analyze the file
                        file_info = await self.scanner._analyze_file(file_path)
                        if file_info:
                            # Update existing record
                            await file_repo.update(
                                session,
                                existing_file.id,
                                **file_info.to_dict()
                            )
                    else:
                        # File wasn't in database, treat as created
                        file_info = await self.scanner._analyze_file(file_path)
                        if file_info:
                            await self._save_file_info(file_info)
                    
                except Exception as e:
                    logger.error("Error processing modified file", file=str(file_path), error=str(e))
    
    async def _process_deleted_files(self, file_paths: List[Path]) -> None:
        """Process deleted files."""
        logger.debug("Processing deleted files", count=len(file_paths))
        
        async with get_db_session() as session:
            for file_path in file_paths:
                try:
                    relative_path = str(file_path.relative_to(self.root_path))
                    existing_file = await file_repo.get_by_path(
                        session, self.project_id, relative_path
                    )
                    
                    if existing_file:
                        # Mark as deleted rather than removing from database
                        await file_repo.update(
                            session,
                            existing_file.id,
                            status=FileStatus.DELETED
                        )
                    
                except Exception as e:
                    logger.error("Error processing deleted file", file=str(file_path), error=str(e))
    
    async def _process_moved_files(self, moved_files: List[tuple[Path, Path]]) -> None:
        """Process moved/renamed files."""
        logger.debug("Processing moved files", count=len(moved_files))
        
        async with get_db_session() as session:
            for old_path, new_path in moved_files:
                try:
                    old_relative = str(old_path.relative_to(self.root_path))
                    existing_file = await file_repo.get_by_path(
                        session, self.project_id, old_relative
                    )
                    
                    if existing_file:
                        if new_path.exists():
                            # Re-analyze file at new location
                            file_info = await self.scanner._analyze_file(new_path)
                            if file_info:
                                # Update existing record with new path info
                                await file_repo.update(
                                    session,
                                    existing_file.id,
                                    **file_info.to_dict()
                                )
                        else:
                            # File moved outside our scope, mark as deleted
                            await file_repo.update(
                                session,
                                existing_file.id,
                                status=FileStatus.DELETED
                            )
                    
                except Exception as e:
                    logger.error("Error processing moved file", old=str(old_path), new=str(new_path), error=str(e))
    
    async def _save_file_info(self, file_info: FileInfo) -> None:
        """Save file info to database."""
        try:
            async with get_db_session() as session:
                file_data = file_info.to_dict()
                file_data["project_id"] = self.project_id
                await file_repo.create(session, **file_data)
                
        except Exception as e:
            logger.error("Failed to save file info", file=file_info.relative_path, error=str(e))
    
    async def trigger_full_scan(self) -> None:
        """Trigger a full project scan."""
        logger.info("Triggering full project scan", project_id=self.project_id)
        
        try:
            stats = await self.scanner.scan_project()
            logger.info("Full scan completed", stats=stats.to_dict())
        except Exception as e:
            logger.error("Full scan failed", error=str(e))
    
    def get_stats(self) -> Dict[str, Any]:
        """Get monitoring statistics."""
        return {
            "project_id": self.project_id,
            "root_path": str(self.root_path),
            "running": self._running,
            "events_received": self.events_received,
            "changes_processed": self.changes_processed,
            "pending_changes": self.change_buffer.pending_count,
            "last_scan_time": self.last_scan_time.isoformat() if self.last_scan_time else None,
        }


class MonitorManager:
    """Manages multiple file monitors."""
    
    def __init__(self):
        self._monitors: Dict[int, FileMonitor] = {}
        self._lock = asyncio.Lock()
    
    async def add_monitor(
        self,
        project_id: int,
        root_path: Path,
        change_callback: Optional[Callable] = None,
        config: Optional[Dict] = None,
    ) -> FileMonitor:
        """Add a new file monitor."""
        async with self._lock:
            if project_id in self._monitors:
                logger.warning("Monitor already exists for project", project_id=project_id)
                return self._monitors[project_id]
            
            monitor = FileMonitor(project_id, root_path, change_callback, config)
            await monitor.start()
            self._monitors[project_id] = monitor
            
            logger.info("Added file monitor", project_id=project_id, root_path=str(root_path))
            return monitor
    
    async def remove_monitor(self, project_id: int) -> bool:
        """Remove a file monitor."""
        async with self._lock:
            if project_id not in self._monitors:
                return False
            
            monitor = self._monitors.pop(project_id)
            await monitor.stop()
            
            logger.info("Removed file monitor", project_id=project_id)
            return True
    
    async def get_monitor(self, project_id: int) -> Optional[FileMonitor]:
        """Get a file monitor by project ID."""
        return self._monitors.get(project_id)
    
    async def stop_all(self) -> None:
        """Stop all file monitors."""
        async with self._lock:
            for monitor in self._monitors.values():
                await monitor.stop()
            self._monitors.clear()
            
            logger.info("Stopped all file monitors")
    
    def get_all_stats(self) -> Dict[int, Dict[str, Any]]:
        """Get statistics for all monitors."""
        return {
            project_id: monitor.get_stats()
            for project_id, monitor in self._monitors.items()
        }


# Global monitor manager instance
monitor_manager = MonitorManager() 