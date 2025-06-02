"""Universal Cross-Reference File Scanner

High-performance async file scanning engine optimized for large codebases.
"""

import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any

import structlog

from .file_scanner import AsyncFileScanner, FileInfo, scan_project_files, ScannerStats
from .file_monitor import FileMonitor, MonitorManager, monitor_manager, FileChangeEvent
from .performance import ScannerPerformanceManager, ResourceUsage, PerformanceMetrics
from src.database.operations import get_or_create_project, get_project_summary
from src.utils.config import get_settings, get_project_config

logger = structlog.get_logger(__name__)

__all__ = [
    "UniversalScanner",
    "ScannerOrchestrator", 
    "AsyncFileScanner",
    "FileMonitor",
    "MonitorManager",
    "ScannerPerformanceManager",
    "FileInfo",
    "FileChangeEvent",
    "ResourceUsage",
    "PerformanceMetrics",
    "ScannerStats",
    "scan_project_files",
    "monitor_manager",
]


class UniversalScanner:
    """Universal file scanner with integrated monitoring and performance management."""
    
    def __init__(
        self,
        project_name: str,
        root_path: Path,
        config: Optional[Dict] = None,
        enable_monitoring: bool = True,
        enable_performance_management: bool = True,
    ):
        self.project_name = project_name
        self.root_path = Path(root_path).resolve()
        self.config = config or get_project_config().get_scanning_config()
        self.settings = get_settings()
        
        # State
        self.project_id: Optional[int] = None
        self._running = False
        self._callbacks: Dict[str, List[Callable]] = {
            "scan_progress": [],
            "scan_complete": [],
            "file_change": [],
            "performance_event": [],
            "error": [],
        }
        
        # Components
        self.scanner: Optional[AsyncFileScanner] = None
        self.monitor: Optional[FileMonitor] = None
        self.performance_manager: Optional[ScannerPerformanceManager] = None
        
        # Configuration flags
        self.enable_monitoring = enable_monitoring
        self.enable_performance_management = enable_performance_management
        
        logger.info(
            "Initialized universal scanner",
            project_name=project_name,
            root_path=str(self.root_path),
            enable_monitoring=enable_monitoring,
            enable_performance_management=enable_performance_management,
        )
    
    def add_callback(self, event_type: str, callback: Callable) -> None:
        """Add event callback."""
        if event_type in self._callbacks:
            self._callbacks[event_type].append(callback)
        else:
            raise ValueError(f"Unknown event type: {event_type}")
    
    def remove_callback(self, event_type: str, callback: Callable) -> bool:
        """Remove event callback."""
        if event_type in self._callbacks and callback in self._callbacks[event_type]:
            self._callbacks[event_type].remove(callback)
            return True
        return False
    
    def _emit_event(self, event_type: str, data: Any = None) -> None:
        """Emit event to callbacks."""
        for callback in self._callbacks.get(event_type, []):
            try:
                if asyncio.iscoroutinefunction(callback):
                    asyncio.create_task(callback(data))
                else:
                    callback(data)
            except Exception as e:
                logger.error("Error in event callback", event_type=event_type, error=str(e))
    
    async def initialize(self) -> None:
        """Initialize scanner components."""
        if self._running:
            logger.warning("Scanner already initialized")
            return
        
        try:
            # Get or create project
            project = await get_or_create_project(self.project_name, str(self.root_path))
            self.project_id = project.id
            
            # Initialize scanner
            self.scanner = AsyncFileScanner(self.project_id, self.root_path, self.config)
            
            # Initialize performance manager
            if self.enable_performance_management:
                self.performance_manager = ScannerPerformanceManager(self.settings)
                self.performance_manager.add_callback(self._handle_performance_event)
                await self.performance_manager.start()
            
            # Initialize monitor
            if self.enable_monitoring:
                self.monitor = FileMonitor(
                    self.project_id,
                    self.root_path,
                    change_callback=self._handle_file_changes,
                    config=self.config,
                )
                await self.monitor.start()
            
            self._running = True
            logger.info("Universal scanner initialized successfully", project_id=self.project_id)
            
        except Exception as e:
            logger.error("Failed to initialize scanner", error=str(e))
            await self.cleanup()
            raise
    
    async def cleanup(self) -> None:
        """Cleanup scanner components."""
        logger.info("Cleaning up universal scanner")
        
        if self.monitor:
            await self.monitor.stop()
            self.monitor = None
        
        if self.performance_manager:
            await self.performance_manager.stop()
            self.performance_manager = None
        
        self.scanner = None
        self._running = False
    
    async def scan_project(self) -> ScannerStats:
        """Perform full project scan."""
        if not self._running or not self.scanner:
            raise RuntimeError("Scanner not initialized")
        
        logger.info("Starting full project scan", project_id=self.project_id)
        
        try:
            # Use performance-managed scanning if available
            if self.performance_manager:
                stats = await self._scan_with_performance_management()
            else:
                stats = await self.scanner.scan_project(self._handle_scan_batch)
            
            self._emit_event("scan_complete", stats)
            logger.info("Project scan completed", stats=stats.to_dict())
            return stats
            
        except Exception as e:
            logger.error("Project scan failed", error=str(e))
            self._emit_event("error", {"type": "scan_error", "error": str(e)})
            raise
    
    async def _scan_with_performance_management(self) -> ScannerStats:
        """Scan with performance management integration."""
        if not self.performance_manager or not self.scanner:
            raise RuntimeError("Performance manager or scanner not available")
        
        async def performance_aware_batch_callback(file_batch: List[FileInfo]) -> None:
            """Process file batch with performance monitoring."""
            for file_info in file_batch:
                try:
                    # Acquire worker slot
                    await self.performance_manager.acquire_worker()
                    
                    # Process file (this would be done by the scanner normally)
                    # Here we just record the metrics
                    self.performance_manager.release_worker(file_info.size, False)
                    
                except Exception as e:
                    # Record error
                    self.performance_manager.release_worker(file_info.size, True)
                    logger.error("Error processing file", file=file_info.relative_path, error=str(e))
            
            # Save batch to database (done by scanner)
            await self.scanner._save_file_batch(file_batch)
            
            # Emit progress event
            self._emit_event("scan_progress", {
                "batch_size": len(file_batch),
                "performance_stats": self.performance_manager.get_comprehensive_stats(),
            })
        
        return await self.scanner.scan_project(performance_aware_batch_callback)
    
    async def _handle_scan_batch(self, file_batch: List[FileInfo]) -> None:
        """Handle scan batch processing."""
        # Save batch to database (done by scanner automatically)
        await self.scanner._save_file_batch(file_batch)
        
        # Emit progress event
        self._emit_event("scan_progress", {
            "batch_size": len(file_batch),
            "files": [f.relative_path for f in file_batch],
        })
    
    async def _handle_file_changes(self, changes: List[FileChangeEvent]) -> None:
        """Handle file change events."""
        self._emit_event("file_change", {
            "change_count": len(changes),
            "changes": [
                {
                    "type": change.event_type,
                    "path": str(change.file_path),
                    "is_directory": change.is_directory,
                    "timestamp": change.timestamp.isoformat(),
                }
                for change in changes
            ],
        })
    
    def _handle_performance_event(self, event_type: str, data: Any) -> None:
        """Handle performance management events."""
        self._emit_event("performance_event", {
            "event_type": event_type,
            "data": data,
        })
    
    async def trigger_incremental_scan(self) -> None:
        """Trigger incremental scan of changed files."""
        if not self.monitor:
            logger.warning("File monitor not available for incremental scan")
            return
        
        await self.monitor.trigger_full_scan()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive scanner statistics."""
        stats = {
            "project_id": self.project_id,
            "project_name": self.project_name,
            "root_path": str(self.root_path),
            "running": self._running,
            "components": {
                "scanner": bool(self.scanner),
                "monitor": bool(self.monitor),
                "performance_manager": bool(self.performance_manager),
            },
        }
        
        # Add monitor stats
        if self.monitor:
            stats["monitor"] = self.monitor.get_stats()
        
        # Add performance stats
        if self.performance_manager:
            stats["performance"] = self.performance_manager.get_comprehensive_stats()
        
        # Add scanner stats
        if self.scanner:
            stats["scanner"] = self.scanner.stats.to_dict()
        
        return stats


class ScannerOrchestrator:
    """Orchestrates multiple scanners and provides project management."""
    
    def __init__(self):
        self._scanners: Dict[str, UniversalScanner] = {}
        self._lock = asyncio.Lock()
        
    async def add_project(
        self,
        project_name: str,
        root_path: Path,
        config: Optional[Dict] = None,
        enable_monitoring: bool = True,
        enable_performance_management: bool = True,
    ) -> UniversalScanner:
        """Add a new project for scanning."""
        async with self._lock:
            if project_name in self._scanners:
                logger.warning("Project already exists", project_name=project_name)
                return self._scanners[project_name]
            
            scanner = UniversalScanner(
                project_name,
                root_path,
                config,
                enable_monitoring,
                enable_performance_management,
            )
            
            await scanner.initialize()
            self._scanners[project_name] = scanner
            
            logger.info("Added project scanner", project_name=project_name, root_path=str(root_path))
            return scanner
    
    async def remove_project(self, project_name: str) -> bool:
        """Remove a project scanner."""
        async with self._lock:
            if project_name not in self._scanners:
                return False
            
            scanner = self._scanners.pop(project_name)
            await scanner.cleanup()
            
            logger.info("Removed project scanner", project_name=project_name)
            return True
    
    async def get_project(self, project_name: str) -> Optional[UniversalScanner]:
        """Get a project scanner by name."""
        return self._scanners.get(project_name)
    
    async def scan_all_projects(self) -> Dict[str, ScannerStats]:
        """Scan all registered projects."""
        results = {}
        
        for project_name, scanner in self._scanners.items():
            try:
                logger.info("Scanning project", project_name=project_name)
                stats = await scanner.scan_project()
                results[project_name] = stats
            except Exception as e:
                logger.error("Failed to scan project", project_name=project_name, error=str(e))
                results[project_name] = None
        
        return results
    
    async def cleanup_all(self) -> None:
        """Cleanup all project scanners."""
        async with self._lock:
            for scanner in self._scanners.values():
                await scanner.cleanup()
            self._scanners.clear()
            
            logger.info("Cleaned up all project scanners")
    
    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all projects."""
        return {
            project_name: scanner.get_stats()
            for project_name, scanner in self._scanners.items()
        }
    
    async def get_project_summary(self, project_name: str) -> Optional[Dict[str, Any]]:
        """Get comprehensive project summary."""
        scanner = self._scanners.get(project_name)
        if not scanner or not scanner.project_id:
            return None
        
        return await get_project_summary(scanner.project_id)


# Global orchestrator instance
orchestrator = ScannerOrchestrator() 