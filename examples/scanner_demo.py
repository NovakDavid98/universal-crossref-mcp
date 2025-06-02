"""Scanner Engine Demo

Demonstrates the Universal Cross-Reference file scanner capabilities.
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.scanner import UniversalScanner, orchestrator
from src.database.connection import init_db, close_db
from src.database.init_db import initialize_database
from src.utils.config import get_settings
import structlog

# Configure logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


class ScannerDemo:
    """Demonstrates scanner engine capabilities."""
    
    def __init__(self):
        self.settings = get_settings()
        
    async def run_demo(self, project_path: str) -> None:
        """Run the complete scanner demo."""
        logger.info("🚀 Starting Universal Cross-Reference Scanner Demo")
        
        try:
            # Initialize database
            await self.setup_database()
            
            # Demo 1: Basic project scanning
            await self.demo_basic_scanning(project_path)
            
            # Demo 2: Performance monitoring
            await self.demo_performance_monitoring(project_path)
            
            # Demo 3: File monitoring
            await self.demo_file_monitoring(project_path)
            
            # Demo 4: Multiple project orchestration
            await self.demo_orchestration([project_path, "."])
            
        except Exception as e:
            logger.error("Demo failed", error=str(e))
            raise
        finally:
            await self.cleanup()
            logger.info("✅ Demo completed successfully!")
    
    async def setup_database(self) -> None:
        """Initialize the database."""
        logger.info("🗄️ Setting up database...")
        
        try:
            success = await initialize_database(
                create_db=True,
                run_migrations=True,
                verify=True
            )
            
            if not success:
                raise RuntimeError("Database initialization failed")
            
            logger.info("✅ Database setup complete")
            
        except Exception as e:
            logger.error("Database setup failed", error=str(e))
            raise
    
    async def demo_basic_scanning(self, project_path: str) -> None:
        """Demo basic file scanning capabilities."""
        logger.info("📁 Demo 1: Basic Project Scanning", project_path=project_path)
        
        # Create scanner
        scanner = UniversalScanner(
            project_name="demo_project",
            root_path=Path(project_path),
            enable_monitoring=False,  # Disable for basic demo
            enable_performance_management=False,
        )
        
        # Add progress callback
        def on_progress(data):
            logger.info(
                "Scan progress",
                batch_size=data["batch_size"],
                files_in_batch=len(data.get("files", [])),
            )
        
        def on_complete(stats):
            logger.info(
                "Scan completed",
                files_discovered=stats.files_discovered,
                files_processed=stats.files_processed,
                files_per_second=round(stats.files_per_second, 2),
                elapsed_time=round(stats.elapsed_time, 2),
            )
        
        scanner.add_callback("scan_progress", on_progress)
        scanner.add_callback("scan_complete", on_complete)
        
        try:
            # Initialize and scan
            await scanner.initialize()
            stats = await scanner.scan_project()
            
            # Show final stats
            comprehensive_stats = scanner.get_stats()
            logger.info("Scanner statistics", stats=comprehensive_stats)
            
        finally:
            await scanner.cleanup()
        
        logger.info("✅ Basic scanning demo complete")
    
    async def demo_performance_monitoring(self, project_path: str) -> None:
        """Demo performance monitoring capabilities."""
        logger.info("⚡ Demo 2: Performance Monitoring", project_path=project_path)
        
        # Create scanner with performance monitoring
        scanner = UniversalScanner(
            project_name="perf_demo_project",
            root_path=Path(project_path),
            enable_monitoring=False,
            enable_performance_management=True,  # Enable performance monitoring
        )
        
        # Add performance event callback
        def on_performance_event(data):
            event_type = data["event_type"]
            event_data = data["data"]
            logger.info("Performance event", type=event_type, data=event_data)
        
        def on_progress(data):
            if "performance_stats" in data:
                perf_stats = data["performance_stats"]
                current_usage = perf_stats.get("current_resource_usage")
                if current_usage:
                    logger.info(
                        "Resource usage",
                        cpu_percent=round(current_usage["cpu_percent"], 1),
                        memory_mb=round(current_usage["memory_mb"], 1),
                        files_per_second=round(
                            perf_stats["performance_metrics"]["files_per_second"], 2
                        ),
                    )
        
        scanner.add_callback("performance_event", on_performance_event)
        scanner.add_callback("scan_progress", on_progress)
        
        try:
            await scanner.initialize()
            
            # Scan with performance monitoring
            logger.info("Starting performance-monitored scan...")
            stats = await scanner.scan_project()
            
            # Show detailed performance stats
            comprehensive_stats = scanner.get_stats()
            if "performance" in comprehensive_stats:
                perf_data = comprehensive_stats["performance"]
                logger.info("Performance summary", performance=perf_data)
            
        finally:
            await scanner.cleanup()
        
        logger.info("✅ Performance monitoring demo complete")
    
    async def demo_file_monitoring(self, project_path: str) -> None:
        """Demo real-time file monitoring."""
        logger.info("👁️ Demo 3: Real-time File Monitoring", project_path=project_path)
        
        # Create scanner with file monitoring
        scanner = UniversalScanner(
            project_name="monitor_demo_project",
            root_path=Path(project_path),
            enable_monitoring=True,  # Enable file monitoring
            enable_performance_management=False,
        )
        
        # Track file changes
        change_count = 0
        
        def on_file_change(data):
            nonlocal change_count
            change_count += data["change_count"]
            logger.info(
                "File changes detected",
                change_count=data["change_count"],
                total_changes=change_count,
                changes=data["changes"][:3],  # Show first 3 changes
            )
        
        scanner.add_callback("file_change", on_file_change)
        
        try:
            await scanner.initialize()
            
            # Do initial scan
            logger.info("Performing initial scan...")
            await scanner.scan_project()
            
            # Monitor for changes for a few seconds
            logger.info("Monitoring for file changes (5 seconds)...")
            logger.info("💡 Try creating, modifying, or deleting files in the project directory!")
            
            await asyncio.sleep(5)
            
            # Show monitor stats
            if scanner.monitor:
                monitor_stats = scanner.monitor.get_stats()
                logger.info("Monitor statistics", stats=monitor_stats)
            
        finally:
            await scanner.cleanup()
        
        logger.info("✅ File monitoring demo complete")
    
    async def demo_orchestration(self, project_paths: list) -> None:
        """Demo multi-project orchestration."""
        logger.info("🎭 Demo 4: Multi-Project Orchestration", projects=len(project_paths))
        
        try:
            # Add multiple projects
            for i, path in enumerate(project_paths):
                project_name = f"orchestrated_project_{i+1}"
                logger.info("Adding project", name=project_name, path=path)
                
                await orchestrator.add_project(
                    project_name=project_name,
                    root_path=Path(path),
                    enable_monitoring=False,
                    enable_performance_management=True,
                )
            
            # Scan all projects
            logger.info("Scanning all projects...")
            results = await orchestrator.scan_all_projects()
            
            # Show results
            for project_name, stats in results.items():
                if stats:
                    logger.info(
                        "Project scan result",
                        project=project_name,
                        files_processed=stats.files_processed,
                        files_per_second=round(stats.files_per_second, 2),
                    )
                else:
                    logger.error("Project scan failed", project=project_name)
            
            # Show orchestrator stats
            all_stats = orchestrator.get_all_stats()
            logger.info("Orchestrator statistics", project_count=len(all_stats))
            
        finally:
            await orchestrator.cleanup_all()
        
        logger.info("✅ Orchestration demo complete")
    
    async def cleanup(self) -> None:
        """Cleanup resources."""
        logger.info("🧹 Cleaning up resources...")
        
        try:
            await orchestrator.cleanup_all()
            await close_db()
        except Exception as e:
            logger.error("Cleanup error", error=str(e))


async def main():
    """Main demo function."""
    # Get project path from command line or use current directory
    project_path = sys.argv[1] if len(sys.argv) > 1 else "."
    
    demo = ScannerDemo()
    await demo.run_demo(project_path)


if __name__ == "__main__":
    print("🔗 Universal Cross-Reference Scanner Engine Demo")
    print("=" * 50)
    print()
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n🛑 Demo interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Demo failed: {e}")
        sys.exit(1) 