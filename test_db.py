#!/usr/bin/env python3
"""Simple database connection test"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.utils.config import get_settings
from src.database.connection import init_db, close_db, db_manager

async def test_database():
    """Test database connection"""
    print("🔍 Testing database connection...")
    
    settings = get_settings()
    print(f"Database URL: {settings.database_url}")
    
    try:
        print("1. Initializing database connection...")
        await init_db()
        print("✅ Database initialized successfully!")
        
        print("2. Testing health check...")
        health = await db_manager.health_check()
        print(f"✅ Health check result: {health}")
        
        print("3. Getting connection info...")
        info = await db_manager.get_connection_info()
        print(f"✅ Connection info: {info}")
        
        await close_db()
        print("✅ Database test completed successfully!")
        
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(test_database()) 