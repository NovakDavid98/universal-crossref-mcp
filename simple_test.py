#!/usr/bin/env python3
"""Simple test of scanner with database"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.database.connection import init_db, close_db
from src.database.models import Base
from src.database.connection import db_manager
from src.utils.config import get_settings

async def setup_database():
    """Set up database tables"""
    print("🔧 Setting up database...")
    
    await init_db()
    
    # Create tables directly
    async with db_manager.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    print("✅ Database tables created")

async def test_scanner():
    """Test the scanner"""
    print("🔍 Testing scanner...")
    
    from src.scanner import UniversalScanner
    
    scanner = UniversalScanner(
        project_name="test_project",
        root_path=Path("."),
        enable_monitoring=False,
        enable_performance_management=False,
    )
    
    try:
        await scanner.initialize()
        print("✅ Scanner initialized")
        
        stats = await scanner.scan_project()
        print(f"✅ Scan completed: {stats.files_processed} files processed")
        
        return True
        
    except Exception as e:
        print(f"❌ Scanner failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await scanner.cleanup()

async def main():
    """Main test function"""
    try:
        # Setup database
        await setup_database()
        
        # Test scanner
        success = await test_scanner()
        
        if success:
            print("🎉 All tests passed!")
        else:
            print("❌ Tests failed!")
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await close_db()

if __name__ == "__main__":
    asyncio.run(main()) 