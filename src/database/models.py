"""SQLAlchemy Models for Universal Cross-Reference System

Database models optimized for large codebases and complex relationship tracking.
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(AsyncAttrs, DeclarativeBase):
    """Base class for all database models."""
    pass


class ProjectStatus(str, Enum):
    """Project scanning status."""
    INITIALIZING = "initializing"
    SCANNING = "scanning"
    INDEXED = "indexed"
    ERROR = "error"
    PAUSED = "paused"


class FileStatus(str, Enum):
    """File processing status."""
    DISCOVERED = "discovered"
    ANALYZING = "analyzing"
    ANALYZED = "analyzed"
    ERROR = "error"
    DELETED = "deleted"


class RelationshipType(str, Enum):
    """Types of relationships between files."""
    IMPORTS = "imports"
    DEPENDS_ON = "depends_on"
    TESTED_BY = "tested_by"
    STYLES = "styles"
    CONFIGURES = "configures"
    DOCUMENTS = "documents"
    EXTENDS = "extends"
    IMPLEMENTS = "implements"
    CROSS_REFERENCES = "cross_references"
    SIMILAR_TO = "similar_to"


class Project(Base):
    """Project metadata and configuration."""
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    root_path: Mapped[str] = mapped_column(Text, nullable=False)
    hub_file: Mapped[str] = mapped_column(String(500), default="SYSTEM.md")
    
    # Configuration
    enforcement_level: Mapped[str] = mapped_column(String(50), default="strict")
    auto_update_hub: Mapped[bool] = mapped_column(Boolean, default=True)
    auto_create_hub: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Status and timing
    status: Mapped[ProjectStatus] = mapped_column(default=ProjectStatus.INITIALIZING)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    last_scan_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    
    # Scanning configuration (stored as JSON)
    scan_config: Mapped[dict] = mapped_column(JSONB, default=dict)
    
    # Statistics
    total_files: Mapped[int] = mapped_column(Integer, default=0)
    analyzed_files: Mapped[int] = mapped_column(Integer, default=0)
    total_relationships: Mapped[int] = mapped_column(Integer, default=0)
    
    # Relationships
    files: Mapped[List["File"]] = relationship("File", back_populates="project", cascade="all, delete-orphan")
    scan_sessions: Mapped[List["ScanSession"]] = relationship("ScanSession", back_populates="project")

    def __repr__(self) -> str:
        return f"<Project(name='{self.name}', status='{self.status}')>"


class ScanSession(Base):
    """Track individual scanning sessions for performance monitoring."""
    __tablename__ = "scan_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    
    # Session metadata
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(50), default="running")
    
    # Performance metrics
    files_discovered: Mapped[int] = mapped_column(Integer, default=0)
    files_analyzed: Mapped[int] = mapped_column(Integer, default=0)
    relationships_created: Mapped[int] = mapped_column(Integer, default=0)
    errors_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Resource usage
    peak_memory_mb: Mapped[Optional[float]] = mapped_column(Float)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float)
    
    # Configuration used for this scan
    scan_config_snapshot: Mapped[dict] = mapped_column(JSONB, default=dict)
    
    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="scan_sessions")

    def __repr__(self) -> str:
        return f"<ScanSession(id={self.id}, status='{self.status}')>"


class File(Base):
    """File metadata and content analysis."""
    __tablename__ = "files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    
    # File identification
    path: Mapped[str] = mapped_column(Text, nullable=False)
    relative_path: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    extension: Mapped[Optional[str]] = mapped_column(String(50))
    
    # File metadata
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    content_hash: Mapped[str] = mapped_column(String(64))  # SHA-256
    encoding: Mapped[Optional[str]] = mapped_column(String(50))
    mime_type: Mapped[Optional[str]] = mapped_column(String(100))
    
    # File type classification
    file_type: Mapped[str] = mapped_column(String(50))  # code, config, docs, test, etc.
    language: Mapped[Optional[str]] = mapped_column(String(50))  # programming language
    
    # Timestamps
    file_created_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    file_modified_at: Mapped[datetime] = mapped_column(DateTime)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_analyzed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    
    # Analysis status
    status: Mapped[FileStatus] = mapped_column(default=FileStatus.DISCOVERED)
    analysis_error: Mapped[Optional[str]] = mapped_column(Text)
    
    # Content analysis results
    line_count: Mapped[Optional[int]] = mapped_column(Integer)
    has_cross_references: Mapped[bool] = mapped_column(Boolean, default=False)
    is_hub_file: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Extracted content (for small files or important metadata)
    imports: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String))
    exports: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String))
    functions: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String))
    classes: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String))
    
    # Cross-reference data
    cross_ref_header: Mapped[Optional[str]] = mapped_column(Text)
    required_reading: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String))
    
    # Custom metadata (extensible)
    metadata: Mapped[dict] = mapped_column(JSONB, default=dict)
    
    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="files")
    
    # File relationships (as source)
    outgoing_relationships: Mapped[List["FileRelationship"]] = relationship(
        "FileRelationship", 
        foreign_keys="FileRelationship.source_file_id",
        back_populates="source_file",
        cascade="all, delete-orphan"
    )
    
    # File relationships (as target)
    incoming_relationships: Mapped[List["FileRelationship"]] = relationship(
        "FileRelationship",
        foreign_keys="FileRelationship.target_file_id", 
        back_populates="target_file"
    )

    # Indexes for performance
    __table_args__ = (
        Index("idx_file_project_path", "project_id", "relative_path"),
        Index("idx_file_type_lang", "file_type", "language"),
        Index("idx_file_modified", "file_modified_at"),
        Index("idx_file_status", "status"),
        Index("idx_file_hash", "content_hash"),
    )

    def __repr__(self) -> str:
        return f"<File(path='{self.relative_path}', type='{self.file_type}')>"


class FileRelationship(Base):
    """Relationships between files (imports, dependencies, cross-references, etc.)."""
    __tablename__ = "file_relationships"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_file_id: Mapped[int] = mapped_column(ForeignKey("files.id"))
    target_file_id: Mapped[int] = mapped_column(ForeignKey("files.id"))
    
    # Relationship metadata
    relationship_type: Mapped[RelationshipType] = mapped_column(nullable=False)
    strength: Mapped[float] = mapped_column(Float, default=1.0)  # Relationship strength (0.0-1.0)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)  # Detection confidence
    
    # Detection method
    detected_by: Mapped[str] = mapped_column(String(100))  # auto, manual, learned
    detection_context: Mapped[Optional[str]] = mapped_column(Text)  # Additional context
    
    # Cross-reference specific data
    is_bidirectional: Mapped[bool] = mapped_column(Boolean, default=False)
    is_required_reading: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    last_verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    
    # Additional metadata
    metadata: Mapped[dict] = mapped_column(JSONB, default=dict)
    
    # Relationships
    source_file: Mapped["File"] = relationship(
        "File", 
        foreign_keys=[source_file_id],
        back_populates="outgoing_relationships"
    )
    target_file: Mapped["File"] = relationship(
        "File",
        foreign_keys=[target_file_id], 
        back_populates="incoming_relationships"
    )

    # Indexes for performance
    __table_args__ = (
        Index("idx_relationship_source", "source_file_id"),
        Index("idx_relationship_target", "target_file_id"),
        Index("idx_relationship_type", "relationship_type"),
        Index("idx_relationship_bidirectional", "is_bidirectional"),
        Index("idx_relationship_required", "is_required_reading"),
        # Composite index for relationship queries
        Index("idx_relationship_source_type", "source_file_id", "relationship_type"),
        # Prevent duplicate relationships
        Index("idx_unique_relationship", "source_file_id", "target_file_id", "relationship_type", unique=True),
    )

    def __repr__(self) -> str:
        return f"<FileRelationship(type='{self.relationship_type}', strength={self.strength})>"


class Pattern(Base):
    """Learned cross-reference patterns for intelligent suggestions."""
    __tablename__ = "patterns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    
    # Pattern identification
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    pattern_type: Mapped[str] = mapped_column(String(100))  # file_type, directory, naming, etc.
    
    # Pattern definition
    trigger_conditions: Mapped[dict] = mapped_column(JSONB)  # When this pattern applies
    suggested_relationships: Mapped[dict] = mapped_column(JSONB)  # What relationships to suggest
    
    # Pattern performance
    confidence_score: Mapped[float] = mapped_column(Float, default=0.5)
    usage_count: Mapped[int] = mapped_column(Integer, default=0)
    success_rate: Mapped[float] = mapped_column(Float, default=0.0)
    
    # Pattern metadata
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_learned: Mapped[bool] = mapped_column(Boolean, default=True)  # vs manually created
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    
    # Pattern examples and context
    examples: Mapped[dict] = mapped_column(JSONB, default=dict)
    description: Mapped[Optional[str]] = mapped_column(Text)

    def __repr__(self) -> str:
        return f"<Pattern(name='{self.name}', confidence={self.confidence_score})>"


class CrossRefStatus(Base):
    """Track cross-reference reading status for enforcement."""
    __tablename__ = "crossref_status"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    
    # User/session identification (could be extended for multi-user)
    session_id: Mapped[str] = mapped_column(String(255), nullable=False)
    user_id: Mapped[Optional[str]] = mapped_column(String(255))
    
    # File access tracking
    file_id: Mapped[int] = mapped_column(ForeignKey("files.id"))
    
    # Status information
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    is_acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    read_time_seconds: Mapped[Optional[int]] = mapped_column(Integer)
    
    # Timestamps
    first_accessed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_accessed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    marked_read_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    
    # Additional tracking
    access_count: Mapped[int] = mapped_column(Integer, default=1)
    completion_percentage: Mapped[Optional[float]] = mapped_column(Float)  # For large files
    
    # Relationships
    file: Mapped["File"] = relationship("File")

    # Indexes
    __table_args__ = (
        Index("idx_crossref_session_file", "session_id", "file_id"),
        Index("idx_crossref_user", "user_id"),
        Index("idx_crossref_status", "is_read", "is_acknowledged"),
        # Unique constraint per session/file
        Index("idx_unique_session_file", "session_id", "file_id", unique=True),
    )

    def __repr__(self) -> str:
        return f"<CrossRefStatus(session='{self.session_id}', read={self.is_read})>" 