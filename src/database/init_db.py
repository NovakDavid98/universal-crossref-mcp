"""Database Initialization Script

Initialize PostgreSQL database with tables and basic configuration.
"""

import asyncio
import sys
from pathlib import Path

import click
import structlog
from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import create_async_engine

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.database.connection import DatabaseConfig, init_db, close_db, wait_for_db
from src.database.models import Base
from src.utils.config import get_settings

logger = structlog.get_logger(__name__)


async def create_database_if_not_exists(database_url: str) -> bool:
    """Create database if it doesn't exist."""
    # Parse database URL to get connection info
    db_config = DatabaseConfig.parse_database_url(database_url)
    
    # Connect to postgres database to check if target database exists
    postgres_url = DatabaseConfig.get_database_url(
        host=db_config["host"],
        port=db_config["port"],
        username=db_config["username"],
        password=db_config["password"],
        database="postgres",  # Connect to default postgres database
        driver=db_config["driver"]
    )
    
    engine = create_async_engine(postgres_url, isolation_level="AUTOCOMMIT")
    
    try:
        async with engine.connect() as conn:
            # Check if database exists
            result = await conn.execute(
                f"SELECT 1 FROM pg_database WHERE datname = '{db_config['database']}'"
            )
            
            if not result.fetchone():
                logger.info("Creating database", database=db_config["database"])
                await conn.execute(f"CREATE DATABASE {db_config['database']}")
                logger.info("Database created successfully")
                return True
            else:
                logger.info("Database already exists", database=db_config["database"])
                return False
                
    except Exception as e:
        logger.error("Failed to create database", error=str(e))
        raise
    finally:
        await engine.dispose()


async def create_tables() -> None:
    """Create all database tables."""
    logger.info("Creating database tables")
    
    # Initialize database connection
    await init_db()
    
    try:
        from src.database.connection import db_manager
        
        if not db_manager.engine:
            raise RuntimeError("Database engine not initialized")
        
        # Create all tables
        async with db_manager.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        logger.info("Database tables created successfully")
        
    except Exception as e:
        logger.error("Failed to create tables", error=str(e))
        raise
    finally:
        await close_db()


def run_migrations() -> None:
    """Run Alembic migrations."""
    logger.info("Running database migrations")
    
    try:
        # Get Alembic configuration
        alembic_cfg = Config("alembic.ini")
        
        # Set database URL
        settings = get_settings()
        alembic_cfg.set_main_option("sqlalchemy.url", settings.database_url)
        
        # Run migrations
        command.upgrade(alembic_cfg, "head")
        logger.info("Database migrations completed successfully")
        
    except Exception as e:
        logger.error("Failed to run migrations", error=str(e))
        raise


async def verify_database_setup() -> bool:
    """Verify database setup is correct."""
    logger.info("Verifying database setup")
    
    try:
        await init_db()
        
        from src.database.connection import db_manager
        from src.database.models import Project
        
        # Test basic database operations
        async with db_manager.get_session() as session:
            # Try to query projects table
            from sqlalchemy import text
            result = await session.execute(text("SELECT COUNT(*) FROM projects"))
            count = result.scalar()
            logger.info("Database verification successful", project_count=count)
            return True
            
    except Exception as e:
        logger.error("Database verification failed", error=str(e))
        return False
    finally:
        await close_db()


async def initialize_database(
    create_db: bool = True,
    run_migrations: bool = True,
    verify: bool = True
) -> bool:
    """Complete database initialization process."""
    logger.info("Starting database initialization")
    
    settings = get_settings()
    
    try:
        # Step 1: Create database if needed
        if create_db:
            await create_database_if_not_exists(settings.database_url)
        
        # Step 2: Wait for database to be available
        if not await wait_for_db(max_retries=10, retry_delay=2.0):
            logger.error("Database is not available")
            return False
        
        # Step 3: Run migrations (preferred) or create tables directly
        if run_migrations:
            try:
                run_migrations()
            except Exception as e:
                logger.warning("Migration failed, falling back to table creation", error=str(e))
                await create_tables()
        else:
            await create_tables()
        
        # Step 4: Verify setup
        if verify:
            if not await verify_database_setup():
                logger.error("Database verification failed")
                return False
        
        logger.info("Database initialization completed successfully")
        return True
        
    except Exception as e:
        logger.error("Database initialization failed", error=str(e))
        return False


@click.command()
@click.option("--no-create-db", is_flag=True, help="Skip database creation")
@click.option("--no-migrations", is_flag=True, help="Skip migrations, create tables directly")
@click.option("--no-verify", is_flag=True, help="Skip verification step")
@click.option("--database-url", help="Override database URL")
def main(no_create_db: bool, no_migrations: bool, no_verify: bool, database_url: str) -> None:
    """Initialize the Universal Cross-Reference MCP Server database."""
    
    # Configure structured logging
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # Override database URL if provided
    if database_url:
        import os
        os.environ["DATABASE_URL"] = database_url
    
    # Run initialization
    success = asyncio.run(
        initialize_database(
            create_db=not no_create_db,
            run_migrations=not no_migrations,
            verify=not no_verify
        )
    )
    
    if success:
        click.echo("✅ Database initialization completed successfully!")
        sys.exit(0)
    else:
        click.echo("❌ Database initialization failed!")
        sys.exit(1)


if __name__ == "__main__":
    main() 