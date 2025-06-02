"""Database Connection and Session Management

Async PostgreSQL connection handling with connection pooling and configuration.
"""

import asyncio
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Dict, Optional

import structlog
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool, QueuePool

from src.utils.config import get_settings

logger = structlog.get_logger(__name__)


class DatabaseManager:
    """Manages database connections and sessions."""
    
    def __init__(self) -> None:
        self.engine: Optional[AsyncEngine] = None
        self.session_factory: Optional[async_sessionmaker] = None
        self._is_initialized = False
    
    async def initialize(self, database_url: Optional[str] = None) -> None:
        """Initialize database engine and session factory."""
        if self._is_initialized:
            logger.warning("Database manager already initialized")
            return
        
        settings = get_settings()
        
        # Use provided URL or get from settings
        db_url = database_url or settings.database_url
        
        if not db_url:
            raise ValueError("Database URL not provided")
        
        logger.info("Initializing database connection", database_url=db_url.split("@")[-1])
        
        # Connection pool configuration
        pool_config = self._get_pool_config(settings)
        
        # Create async engine
        self.engine = create_async_engine(
            db_url,
            echo=settings.log_level == "DEBUG",
            pool_pre_ping=True,  # Verify connections before use
            pool_recycle=3600,   # Recycle connections after 1 hour
            **pool_config
        )
        
        # Create session factory
        self.session_factory = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )
        
        self._is_initialized = True
        logger.info("Database connection initialized successfully")
    
    def _get_pool_config(self, settings: Any) -> Dict[str, Any]:
        """Get connection pool configuration based on settings."""
        pool_config = {
            "poolclass": QueuePool,
            "pool_size": settings.database_pool_size,
            "max_overflow": settings.database_max_overflow,
        }
        
        # For testing, use NullPool to avoid connection issues
        if hasattr(settings, "testing") and settings.testing:
            pool_config = {"poolclass": NullPool}
        
        return pool_config
    
    async def close(self) -> None:
        """Close database connections."""
        if self.engine:
            logger.info("Closing database connections")
            await self.engine.dispose()
            self.engine = None
            self.session_factory = None
            self._is_initialized = False
    
    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get an async database session with proper cleanup."""
        if not self._is_initialized or not self.session_factory:
            raise RuntimeError("Database manager not initialized")
        
        session = self.session_factory()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
    
    async def health_check(self) -> bool:
        """Check if database connection is healthy."""
        if not self.engine:
            return False
        
        try:
            async with self.get_session() as session:
                result = await session.execute("SELECT 1")
                return result.scalar() == 1
        except Exception as e:
            logger.error("Database health check failed", error=str(e))
            return False
    
    async def get_connection_info(self) -> Dict[str, Any]:
        """Get database connection information."""
        if not self.engine:
            return {"status": "not_initialized"}
        
        pool = self.engine.pool
        return {
            "status": "initialized",
            "pool_size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
            "is_healthy": await self.health_check(),
        }


# Global database manager instance
db_manager = DatabaseManager()


async def init_db(database_url: Optional[str] = None) -> None:
    """Initialize database connection."""
    await db_manager.initialize(database_url)


async def close_db() -> None:
    """Close database connection."""
    await db_manager.close()


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get a database session - convenience function."""
    async with db_manager.get_session() as session:
        yield session


async def wait_for_db(max_retries: int = 30, retry_delay: float = 1.0) -> bool:
    """Wait for database to become available."""
    logger.info("Waiting for database to become available", max_retries=max_retries)
    
    for attempt in range(max_retries):
        try:
            if await db_manager.health_check():
                logger.info("Database is available", attempt=attempt + 1)
                return True
        except Exception as e:
            logger.debug("Database not ready", attempt=attempt + 1, error=str(e))
        
        if attempt < max_retries - 1:
            await asyncio.sleep(retry_delay)
    
    logger.error("Database did not become available", max_retries=max_retries)
    return False


class DatabaseConfig:
    """Database configuration utilities."""
    
    @staticmethod
    def get_database_url(
        host: str = "localhost",
        port: int = 5432,
        username: str = "postgres",
        password: str = "",
        database: str = "crossref_db",
        driver: str = "asyncpg"
    ) -> str:
        """Build database URL from components."""
        return f"postgresql+{driver}://{username}:{password}@{host}:{port}/{database}"
    
    @staticmethod
    def parse_database_url(url: str) -> Dict[str, Any]:
        """Parse database URL into components."""
        # Simple parsing - for production use proper URL parsing
        if "://" not in url:
            raise ValueError("Invalid database URL format")
        
        scheme_part, rest = url.split("://", 1)
        scheme = scheme_part.replace("postgresql+", "")
        
        if "@" in rest:
            credentials, host_part = rest.split("@", 1)
            if ":" in credentials:
                username, password = credentials.split(":", 1)
            else:
                username, password = credentials, ""
        else:
            username, password = "", ""
            host_part = rest
        
        if "/" in host_part:
            host_port, database = host_part.split("/", 1)
        else:
            host_port, database = host_part, ""
        
        if ":" in host_port:
            host, port_str = host_port.split(":", 1)
            port = int(port_str)
        else:
            host, port = host_port, 5432
        
        return {
            "driver": scheme,
            "username": username,
            "password": password,
            "host": host,
            "port": port,
            "database": database,
        } 