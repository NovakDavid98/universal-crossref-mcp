"""Configuration Management

Centralized configuration using Pydantic settings with environment variable support.
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

import yaml
from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Database Configuration
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:password@localhost:5432/crossref_db",
        description="PostgreSQL database URL"
    )
    database_pool_size: int = Field(default=10, description="Database connection pool size")
    database_max_overflow: int = Field(default=20, description="Database connection pool max overflow")
    database_query_timeout: int = Field(default=30, description="Database query timeout in seconds")
    database_connection_timeout: int = Field(default=10, description="Database connection timeout in seconds")
    
    # Redis Cache Configuration (Optional)
    redis_url: Optional[str] = Field(default=None, description="Redis URL for caching")
    redis_cache_ttl: int = Field(default=3600, description="Redis cache TTL in seconds")
    
    # MCP Server Configuration
    mcp_server_host: str = Field(default="localhost", description="MCP server host")
    mcp_server_port: int = Field(default=8765, description="MCP server port")
    
    # Logging Configuration
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(default="structured", description="Log format: structured or text")
    log_file: Optional[str] = Field(default=None, description="Log file path")
    
    # Scanning Configuration
    max_file_size_mb: int = Field(default=10, description="Maximum file size to analyze in MB")
    max_concurrent_workers: int = Field(default=4, description="Maximum concurrent worker threads")
    scan_batch_size: int = Field(default=100, description="Batch size for file processing")
    
    # Performance Limits
    memory_limit_mb: int = Field(default=1024, description="Memory limit in MB")
    cpu_usage_limit: int = Field(default=50, description="CPU usage limit percentage")
    auto_pause_on_high_load: bool = Field(default=True, description="Auto pause on high system load")
    
    # Emergency Stop Triggers
    emergency_memory_limit_mb: int = Field(default=2048, description="Emergency memory limit in MB")
    emergency_file_count: int = Field(default=200000, description="Emergency file count limit")
    emergency_scan_time_minutes: int = Field(default=30, description="Emergency scan time limit in minutes")
    
    # Project Configuration
    default_hub_file: str = Field(default="SYSTEM.md", description="Default hub file name")
    enforcement_level: str = Field(default="strict", description="Cross-reference enforcement level")
    auto_update_hub: bool = Field(default=True, description="Auto update hub file")
    
    # File Patterns
    default_include_patterns: List[str] = Field(
        default=[
            "**/*.{js,ts,jsx,tsx}",
            "**/*.{py,java,cpp,c,h,cs}",
            "**/*.{css,scss,less,sass}",
            "**/*.{json,yaml,yml,toml,env}",
            "**/*.{md,rst,txt}",
            "**/*.{html,xml}",
            "**/*.{sql,graphql}",
        ],
        description="Default file include patterns"
    )
    
    default_exclude_patterns: List[str] = Field(
        default=[
            "**/node_modules/**",
            "**/build/**",
            "**/dist/**",
            "**/.git/**",
            "**/coverage/**",
            "**/__pycache__/**",
            "**/*.min.js",
            "**/*.bundle.js",
            "**/venv/**",
            "**/.venv/**",
        ],
        description="Default file exclude patterns"
    )
    
    # Development/Testing
    testing: bool = Field(default=False, description="Enable testing mode")
    debug: bool = Field(default=False, description="Enable debug mode")
    
    @computed_field
    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.log_level == "DEBUG" or self.debug
    
    @computed_field
    @property
    def max_file_size_bytes(self) -> int:
        """Get max file size in bytes."""
        return self.max_file_size_mb * 1024 * 1024
    
    def get_database_config(self) -> dict:
        """Get database configuration as dict."""
        return {
            "url": self.database_url,
            "pool_size": self.database_pool_size,
            "max_overflow": self.database_max_overflow,
            "query_timeout": self.database_query_timeout,
            "connection_timeout": self.database_connection_timeout,
        }
    
    def get_performance_config(self) -> dict:
        """Get performance configuration as dict."""
        return {
            "memory_limit_mb": self.memory_limit_mb,
            "cpu_usage_limit": self.cpu_usage_limit,
            "auto_pause_on_high_load": self.auto_pause_on_high_load,
            "max_concurrent_workers": self.max_concurrent_workers,
            "scan_batch_size": self.scan_batch_size,
        }


class ProjectConfig:
    """Project-specific configuration loaded from YAML files."""
    
    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or Path("config/default.yaml")
        self._config_data: Optional[dict] = None
    
    def load(self) -> dict:
        """Load configuration from YAML file."""
        if self._config_data is None:
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    self._config_data = yaml.safe_load(f)
            else:
                self._config_data = self._get_default_config()
        
        return self._config_data
    
    def _get_default_config(self) -> dict:
        """Get default project configuration."""
        return {
            "project": {
                "name": "universal-crossref",
                "hub_file": "SYSTEM.md",
                "enforcement_level": "strict",
                "auto_update_hub": True,
                "auto_create_hub": True,
            },
            "scanning": {
                "include_patterns": [
                    "**/*.{js,ts,jsx,tsx}",
                    "**/*.{py,java,cpp,c,h,cs}",
                    "**/*.{css,scss,less,sass}",
                    "**/*.{json,yaml,yml,toml,env}",
                    "**/*.{md,rst,txt}",
                    "**/*.{html,xml}",
                    "**/*.{sql,graphql}",
                ],
                "exclude_patterns": [
                    "**/node_modules/**",
                    "**/build/**",
                    "**/dist/**",
                    "**/.git/**",
                    "**/coverage/**",
                    "**/__pycache__/**",
                    "**/*.min.js",
                    "**/*.bundle.js",
                    "**/venv/**",
                    "**/.venv/**",
                ],
                "size_limits": {
                    "max_file_size_mb": 10,
                    "max_files_per_directory": 10000,
                },
                "scan_depth": {
                    "max_directory_depth": 20,
                    "emergency_stop_file_count": 100000,
                },
                "batch_size": 100,
                "max_concurrent_workers": 4,
            },
            "cross_reference": {
                "required_reading_format": "⚠️ IMPORTANT: When reading this file you HAVE TO read: {files}",
                "bidirectional_reference_format": "**Cross-reference**: This document supplements {hub_file}. Also read: {related_files}",
                "relationship_types": [
                    "imports", "depends_on", "tested_by", "styles",
                    "configures", "documents", "extends", "implements"
                ],
            },
            "database": {
                "pool_size": 10,
                "max_overflow": 20,
                "query_timeout": 30,
                "connection_timeout": 10,
            },
            "performance": {
                "memory_limit_mb": 1024,
                "cpu_usage_limit": 50,
                "auto_pause_on_high_load": True,
                "cache_ttl": 3600,
                "emergency_stop_triggers": {
                    "memory_usage_mb": 2048,
                    "file_count": 200000,
                    "scan_time_minutes": 30,
                },
            },
            "logging": {
                "level": "INFO",
                "format": "structured",
                "file_logging": False,
            },
        }
    
    def get(self, key: str, default=None):
        """Get configuration value by key (supports dot notation)."""
        config = self.load()
        keys = key.split('.')
        
        current = config
        for k in keys:
            if isinstance(current, dict) and k in current:
                current = current[k]
            else:
                return default
        
        return current
    
    def get_scanning_config(self) -> dict:
        """Get scanning configuration."""
        return self.get("scanning", {})
    
    def get_cross_reference_config(self) -> dict:
        """Get cross-reference configuration."""
        return self.get("cross_reference", {})


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


@lru_cache()
def get_project_config(config_path: Optional[str] = None) -> ProjectConfig:
    """Get cached project configuration instance."""
    path = Path(config_path) if config_path else None
    return ProjectConfig(path)


def load_config_file(file_path: str) -> dict:
    """Load configuration from a YAML file."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {file_path}")
    
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def validate_config(config: dict) -> bool:
    """Validate configuration structure."""
    required_sections = ["project", "scanning", "cross_reference"]
    
    for section in required_sections:
        if section not in config:
            raise ValueError(f"Missing required configuration section: {section}")
    
    # Validate project section
    project_config = config["project"]
    if "name" not in project_config:
        raise ValueError("Project name is required")
    
    # Validate scanning section
    scanning_config = config["scanning"]
    if "include_patterns" not in scanning_config:
        raise ValueError("Include patterns are required in scanning configuration")
    
    return True


def get_environment() -> str:
    """Get current environment (development, testing, production)."""
    return os.getenv("ENVIRONMENT", "development").lower()


def is_development() -> bool:
    """Check if running in development environment."""
    return get_environment() == "development"


def is_testing() -> bool:
    """Check if running in testing environment."""
    return get_environment() == "testing"


def is_production() -> bool:
    """Check if running in production environment."""
    return get_environment() == "production" 