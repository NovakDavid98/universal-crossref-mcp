"""Performance Monitoring and Resource Management

System resource monitoring and performance optimization for file scanning.
"""

import asyncio
import psutil
import resource
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any

import structlog

from src.utils.config import get_settings

logger = structlog.get_logger(__name__)


@dataclass
class ResourceUsage:
    """System resource usage snapshot."""
    timestamp: datetime
    cpu_percent: float
    memory_mb: float
    memory_percent: float
    disk_io_read_mb: float
    disk_io_write_mb: float
    open_files: int
    active_threads: int


@dataclass
class PerformanceMetrics:
    """Scanner performance metrics."""
    files_per_second: float
    bytes_per_second: float
    avg_file_size_kb: float
    total_files: int
    total_bytes: int
    elapsed_time: float
    error_rate: float


class ResourceMonitor:
    """Monitors system resource usage."""
    
    def __init__(self, sample_interval: float = 5.0):
        self.sample_interval = sample_interval
        self._running = False
        self._samples: List[ResourceUsage] = []
        self._max_samples = 1000  # Keep last 1000 samples
        self._callbacks: List[Callable[[ResourceUsage], None]] = []
        
        # Baseline measurements
        self._process = psutil.Process()
        self._initial_io = self._get_io_counters()
        
    def add_callback(self, callback: Callable[[ResourceUsage], None]) -> None:
        """Add a callback to be called when new resource data is available."""
        self._callbacks.append(callback)
    
    def _get_io_counters(self) -> Dict[str, int]:
        """Get current IO counters."""
        try:
            io_counters = self._process.io_counters()
            return {
                "read_bytes": io_counters.read_bytes,
                "write_bytes": io_counters.write_bytes,
            }
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return {"read_bytes": 0, "write_bytes": 0}
    
    async def start(self) -> None:
        """Start resource monitoring."""
        if self._running:
            return
        
        self._running = True
        logger.info("Starting resource monitor")
        
        # Start monitoring loop
        asyncio.create_task(self._monitor_loop())
    
    async def stop(self) -> None:
        """Stop resource monitoring."""
        self._running = False
        logger.info("Stopping resource monitor")
    
    async def _monitor_loop(self) -> None:
        """Main monitoring loop."""
        while self._running:
            try:
                usage = await self._collect_usage()
                
                # Store sample
                self._samples.append(usage)
                if len(self._samples) > self._max_samples:
                    self._samples.pop(0)
                
                # Notify callbacks
                for callback in self._callbacks:
                    try:
                        callback(usage)
                    except Exception as e:
                        logger.error("Error in resource monitor callback", error=str(e))
                
                await asyncio.sleep(self.sample_interval)
                
            except Exception as e:
                logger.error("Error in resource monitoring loop", error=str(e))
                await asyncio.sleep(self.sample_interval)
    
    async def _collect_usage(self) -> ResourceUsage:
        """Collect current resource usage."""
        # CPU and memory
        cpu_percent = self._process.cpu_percent()
        memory_info = self._process.memory_info()
        memory_mb = memory_info.rss / (1024 * 1024)
        memory_percent = self._process.memory_percent()
        
        # IO counters
        current_io = self._get_io_counters()
        disk_read_mb = (current_io["read_bytes"] - self._initial_io["read_bytes"]) / (1024 * 1024)
        disk_write_mb = (current_io["write_bytes"] - self._initial_io["write_bytes"]) / (1024 * 1024)
        
        # Process info
        open_files = len(self._process.open_files())
        active_threads = self._process.num_threads()
        
        return ResourceUsage(
            timestamp=datetime.now(),
            cpu_percent=cpu_percent,
            memory_mb=memory_mb,
            memory_percent=memory_percent,
            disk_io_read_mb=disk_read_mb,
            disk_io_write_mb=disk_write_mb,
            open_files=open_files,
            active_threads=active_threads,
        )
    
    def get_recent_usage(self, minutes: int = 10) -> List[ResourceUsage]:
        """Get resource usage from the last N minutes."""
        cutoff = datetime.now() - timedelta(minutes=minutes)
        return [sample for sample in self._samples if sample.timestamp >= cutoff]
    
    def get_peak_usage(self, minutes: int = 10) -> ResourceUsage:
        """Get peak resource usage from the last N minutes."""
        recent = self.get_recent_usage(minutes)
        if not recent:
            return self._samples[-1] if self._samples else None
        
        # Find peak by memory usage
        return max(recent, key=lambda x: x.memory_mb)
    
    def get_average_usage(self, minutes: int = 10) -> Optional[ResourceUsage]:
        """Get average resource usage from the last N minutes."""
        recent = self.get_recent_usage(minutes)
        if not recent:
            return None
        
        total_cpu = sum(sample.cpu_percent for sample in recent)
        total_memory = sum(sample.memory_mb for sample in recent)
        total_memory_percent = sum(sample.memory_percent for sample in recent)
        total_read = sum(sample.disk_io_read_mb for sample in recent)
        total_write = sum(sample.disk_io_write_mb for sample in recent)
        total_files = sum(sample.open_files for sample in recent)
        total_threads = sum(sample.active_threads for sample in recent)
        
        count = len(recent)
        return ResourceUsage(
            timestamp=recent[-1].timestamp,
            cpu_percent=total_cpu / count,
            memory_mb=total_memory / count,
            memory_percent=total_memory_percent / count,
            disk_io_read_mb=total_read / count,
            disk_io_write_mb=total_write / count,
            open_files=int(total_files / count),
            active_threads=int(total_threads / count),
        )


class PerformanceTracker:
    """Tracks scanning performance metrics."""
    
    def __init__(self):
        self.start_time: Optional[float] = None
        self.files_processed = 0
        self.bytes_processed = 0
        self.errors_count = 0
        self._file_sizes: List[int] = []
        
    def start(self) -> None:
        """Start performance tracking."""
        self.start_time = time.time()
        self.files_processed = 0
        self.bytes_processed = 0
        self.errors_count = 0
        self._file_sizes.clear()
    
    def record_file(self, size_bytes: int, error: bool = False) -> None:
        """Record a processed file."""
        self.files_processed += 1
        self.bytes_processed += size_bytes
        self._file_sizes.append(size_bytes)
        
        if error:
            self.errors_count += 1
    
    def get_metrics(self) -> PerformanceMetrics:
        """Get current performance metrics."""
        elapsed = time.time() - (self.start_time or time.time())
        
        files_per_second = self.files_processed / elapsed if elapsed > 0 else 0
        bytes_per_second = self.bytes_processed / elapsed if elapsed > 0 else 0
        avg_file_size_kb = (sum(self._file_sizes) / len(self._file_sizes) / 1024) if self._file_sizes else 0
        error_rate = (self.errors_count / self.files_processed) if self.files_processed > 0 else 0
        
        return PerformanceMetrics(
            files_per_second=files_per_second,
            bytes_per_second=bytes_per_second,
            avg_file_size_kb=avg_file_size_kb,
            total_files=self.files_processed,
            total_bytes=self.bytes_processed,
            elapsed_time=elapsed,
            error_rate=error_rate,
        )


class ResourceLimiter:
    """Enforces resource limits and emergency stops."""
    
    def __init__(self, settings=None):
        self.settings = settings or get_settings()
        self._resource_monitor = ResourceMonitor()
        self._emergency_triggered = False
        self._paused = False
        self._callbacks: List[Callable[[str, Dict], None]] = []
        
        # Add callback to monitor for limits
        self._resource_monitor.add_callback(self._check_limits)
    
    def add_callback(self, callback: Callable[[str, Dict], None]) -> None:
        """Add callback for limit violations."""
        self._callbacks.append(callback)
    
    async def start(self) -> None:
        """Start resource monitoring."""
        await self._resource_monitor.start()
    
    async def stop(self) -> None:
        """Stop resource monitoring."""
        await self._resource_monitor.stop()
    
    def _check_limits(self, usage: ResourceUsage) -> None:
        """Check if any limits are exceeded."""
        # Check memory limits
        if usage.memory_mb > self.settings.emergency_memory_limit_mb:
            self._trigger_emergency("memory_limit", {
                "current_mb": usage.memory_mb,
                "limit_mb": self.settings.emergency_memory_limit_mb
            })
            return
        
        if usage.memory_mb > self.settings.memory_limit_mb:
            self._trigger_warning("memory_warning", {
                "current_mb": usage.memory_mb,
                "limit_mb": self.settings.memory_limit_mb
            })
        
        # Check CPU limits
        if usage.cpu_percent > self.settings.cpu_usage_limit and self.settings.auto_pause_on_high_load:
            self._trigger_pause("cpu_limit", {
                "current_percent": usage.cpu_percent,
                "limit_percent": self.settings.cpu_usage_limit
            })
    
    def _trigger_emergency(self, reason: str, details: Dict) -> None:
        """Trigger emergency stop."""
        if self._emergency_triggered:
            return
        
        self._emergency_triggered = True
        logger.error("Emergency stop triggered", reason=reason, details=details)
        
        for callback in self._callbacks:
            try:
                callback("emergency", {"reason": reason, "details": details})
            except Exception as e:
                logger.error("Error in emergency callback", error=str(e))
    
    def _trigger_warning(self, reason: str, details: Dict) -> None:
        """Trigger warning."""
        logger.warning("Resource limit warning", reason=reason, details=details)
        
        for callback in self._callbacks:
            try:
                callback("warning", {"reason": reason, "details": details})
            except Exception as e:
                logger.error("Error in warning callback", error=str(e))
    
    def _trigger_pause(self, reason: str, details: Dict) -> None:
        """Trigger pause."""
        if self._paused:
            return
        
        self._paused = True
        logger.warning("Scanning paused due to resource limits", reason=reason, details=details)
        
        for callback in self._callbacks:
            try:
                callback("pause", {"reason": reason, "details": details})
            except Exception as e:
                logger.error("Error in pause callback", error=str(e))
    
    def is_emergency_triggered(self) -> bool:
        """Check if emergency stop is triggered."""
        return self._emergency_triggered
    
    def is_paused(self) -> bool:
        """Check if scanning is paused."""
        return self._paused
    
    def reset_pause(self) -> None:
        """Reset pause state."""
        self._paused = False
        logger.info("Scanning pause reset")
    
    def get_current_usage(self) -> Optional[ResourceUsage]:
        """Get current resource usage."""
        samples = self._resource_monitor._samples
        return samples[-1] if samples else None


class ConcurrencyManager:
    """Manages concurrent operations with adaptive scaling."""
    
    def __init__(self, initial_workers: int = 4, max_workers: int = 16):
        self.initial_workers = initial_workers
        self.max_workers = max_workers
        self.current_workers = initial_workers
        
        self._semaphore = asyncio.Semaphore(initial_workers)
        self._performance_tracker = PerformanceTracker()
        self._last_adjustment = time.time()
        self._adjustment_interval = 30.0  # seconds
        
    async def acquire(self) -> None:
        """Acquire a worker slot."""
        await self._semaphore.acquire()
    
    def release(self) -> None:
        """Release a worker slot."""
        self._semaphore.release()
    
    async def adjust_concurrency(self, resource_usage: ResourceUsage) -> None:
        """Adjust concurrency based on performance and resource usage."""
        now = time.time()
        if now - self._last_adjustment < self._adjustment_interval:
            return
        
        self._last_adjustment = now
        metrics = self._performance_tracker.get_metrics()
        
        # Decide whether to scale up or down
        should_scale_up = (
            resource_usage.cpu_percent < 70 and
            resource_usage.memory_percent < 80 and
            metrics.error_rate < 0.05 and
            self.current_workers < self.max_workers
        )
        
        should_scale_down = (
            resource_usage.cpu_percent > 90 or
            resource_usage.memory_percent > 90 or
            metrics.error_rate > 0.1 or
            metrics.files_per_second < 1.0
        ) and self.current_workers > 1
        
        if should_scale_up:
            self._scale_up()
        elif should_scale_down:
            self._scale_down()
    
    def _scale_up(self) -> None:
        """Increase concurrency."""
        old_workers = self.current_workers
        self.current_workers = min(self.current_workers + 1, self.max_workers)
        
        if self.current_workers > old_workers:
            # Release additional permits
            self._semaphore._value += (self.current_workers - old_workers)
            logger.info("Scaled up concurrency", old=old_workers, new=self.current_workers)
    
    def _scale_down(self) -> None:
        """Decrease concurrency."""
        old_workers = self.current_workers
        self.current_workers = max(self.current_workers - 1, 1)
        
        if self.current_workers < old_workers:
            # This is tricky - we can't easily remove permits from a semaphore
            # Instead, we'll create a new semaphore with the right number
            current_value = self._semaphore._value
            used_permits = old_workers - current_value
            new_permits = max(0, self.current_workers - used_permits)
            
            self._semaphore = asyncio.Semaphore(new_permits)
            logger.info("Scaled down concurrency", old=old_workers, new=self.current_workers)
    
    def record_file_processed(self, size_bytes: int, error: bool = False) -> None:
        """Record a processed file for performance tracking."""
        self._performance_tracker.record_file(size_bytes, error)
    
    def get_performance_metrics(self) -> PerformanceMetrics:
        """Get current performance metrics."""
        return self._performance_tracker.get_metrics()


class ScannerPerformanceManager:
    """Comprehensive performance management for file scanner."""
    
    def __init__(self, settings=None):
        self.settings = settings or get_settings()
        
        # Components
        self.resource_monitor = ResourceMonitor()
        self.resource_limiter = ResourceLimiter(settings)
        self.concurrency_manager = ConcurrencyManager(
            initial_workers=self.settings.max_concurrent_workers,
            max_workers=self.settings.max_concurrent_workers * 2
        )
        
        # State
        self._running = False
        self._callbacks: List[Callable[[str, Any], None]] = []
        
        # Wire up callbacks
        self.resource_limiter.add_callback(self._handle_resource_event)
        self.resource_monitor.add_callback(self._handle_resource_update)
    
    def add_callback(self, callback: Callable[[str, Any], None]) -> None:
        """Add callback for performance events."""
        self._callbacks.append(callback)
    
    async def start(self) -> None:
        """Start performance management."""
        if self._running:
            return
        
        logger.info("Starting scanner performance manager")
        
        await self.resource_monitor.start()
        await self.resource_limiter.start()
        
        self._running = True
    
    async def stop(self) -> None:
        """Stop performance management."""
        if not self._running:
            return
        
        logger.info("Stopping scanner performance manager")
        
        await self.resource_monitor.stop()
        await self.resource_limiter.stop()
        
        self._running = False
    
    def _handle_resource_event(self, event_type: str, data: Dict) -> None:
        """Handle resource limit events."""
        for callback in self._callbacks:
            try:
                callback(f"resource_{event_type}", data)
            except Exception as e:
                logger.error("Error in performance callback", error=str(e))
    
    def _handle_resource_update(self, usage: ResourceUsage) -> None:
        """Handle resource usage updates."""
        # Adjust concurrency based on resource usage
        if self._running:
            asyncio.create_task(self.concurrency_manager.adjust_concurrency(usage))
    
    async def acquire_worker(self) -> None:
        """Acquire a worker slot with resource checking."""
        if self.resource_limiter.is_emergency_triggered():
            raise RuntimeError("Emergency stop triggered - cannot acquire worker")
        
        if self.resource_limiter.is_paused():
            # Wait for unpause or timeout
            for _ in range(60):  # Wait up to 60 seconds
                if not self.resource_limiter.is_paused():
                    break
                await asyncio.sleep(1)
            else:
                raise RuntimeError("Scanner paused due to resource limits")
        
        await self.concurrency_manager.acquire()
    
    def release_worker(self, file_size: int = 0, error: bool = False) -> None:
        """Release a worker slot and record metrics."""
        self.concurrency_manager.release()
        if file_size > 0:
            self.concurrency_manager.record_file_processed(file_size, error)
    
    def get_comprehensive_stats(self) -> Dict[str, Any]:
        """Get comprehensive performance statistics."""
        current_usage = self.resource_limiter.get_current_usage()
        peak_usage = self.resource_monitor.get_peak_usage()
        avg_usage = self.resource_monitor.get_average_usage()
        performance_metrics = self.concurrency_manager.get_performance_metrics()
        
        return {
            "current_resource_usage": current_usage.__dict__ if current_usage else None,
            "peak_resource_usage": peak_usage.__dict__ if peak_usage else None,
            "average_resource_usage": avg_usage.__dict__ if avg_usage else None,
            "performance_metrics": performance_metrics.__dict__,
            "concurrency": {
                "current_workers": self.concurrency_manager.current_workers,
                "max_workers": self.concurrency_manager.max_workers,
            },
            "limits": {
                "emergency_triggered": self.resource_limiter.is_emergency_triggered(),
                "paused": self.resource_limiter.is_paused(),
            },
        } 