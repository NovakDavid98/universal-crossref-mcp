"""Database Operations and Repository Pattern

CRUD operations and repository pattern for all database models.
"""

from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from uuid import uuid4

import structlog
from sqlalchemy import and_, func, or_, text, select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from src.database.connection import get_db_session
from src.database.models import (
    Base,
    Project,
    ProjectStatus,
    File,
    FileStatus,
    FileRelationship,
    RelationshipType,
    Pattern,
    ScanSession,
    CrossRefStatus,
)

logger = structlog.get_logger(__name__)


class BaseRepository:
    """Base repository with common CRUD operations."""
    
    def __init__(self, model_class: type[Base]):
        self.model_class = model_class
    
    async def create(self, session: AsyncSession, **kwargs) -> Base:
        """Create a new record."""
        obj = self.model_class(**kwargs)
        session.add(obj)
        await session.flush()
        await session.refresh(obj)
        return obj
    
    async def get_by_id(self, session: AsyncSession, id: int) -> Optional[Base]:
        """Get record by ID."""
        result = await session.execute(
            select(self.model_class).where(self.model_class.id == id)
        )
        return result.scalar_one_or_none()
    
    async def get_all(self, session: AsyncSession, limit: int = 100, offset: int = 0) -> List[Base]:
        """Get all records with pagination."""
        result = await session.execute(
            select(self.model_class).limit(limit).offset(offset)
        )
        return list(result.scalars().all())
    
    async def update(self, session: AsyncSession, id: int, **kwargs) -> Optional[Base]:
        """Update record by ID."""
        obj = await self.get_by_id(session, id)
        if obj:
            for key, value in kwargs.items():
                if hasattr(obj, key):
                    setattr(obj, key, value)
            await session.flush()
            await session.refresh(obj)
        return obj
    
    async def delete(self, session: AsyncSession, id: int) -> bool:
        """Delete record by ID."""
        obj = await self.get_by_id(session, id)
        if obj:
            await session.delete(obj)
            await session.flush()
            return True
        return False
    
    async def count(self, session: AsyncSession) -> int:
        """Count total records."""
        result = await session.execute(
            select(func.count(self.model_class.id))
        )
        return result.scalar()


class ProjectRepository(BaseRepository):
    """Repository for Project operations."""
    
    def __init__(self):
        super().__init__(Project)
    
    async def get_by_name(self, session: AsyncSession, name: str) -> Optional[Project]:
        """Get project by name."""
        result = await session.execute(
            select(Project).where(Project.name == name)
        )
        return result.scalar_one_or_none()
    
    async def get_by_root_path(self, session: AsyncSession, root_path: str) -> Optional[Project]:
        """Get project by root path."""
        result = await session.execute(
            select(Project).where(Project.root_path == root_path)
        )
        return result.scalar_one_or_none()
    
    async def get_with_stats(self, session: AsyncSession, project_id: int) -> Optional[Dict[str, Any]]:
        """Get project with file and relationship statistics."""
        project = await self.get_by_id(session, project_id)
        if not project:
            return None
        
        # Get file counts by status
        file_stats = await session.execute(
            select(File.status, func.count(File.id))
            .where(File.project_id == project_id)
            .group_by(File.status)
        )
        
        # Get relationship counts by type
        relationship_stats = await session.execute(
            select(FileRelationship.relationship_type, func.count(FileRelationship.id))
            .join(File, File.id == FileRelationship.source_file_id)
            .where(File.project_id == project_id)
            .group_by(FileRelationship.relationship_type)
        )
        
        return {
            "project": project,
            "file_stats": {status: count for status, count in file_stats.all()},
            "relationship_stats": {rel_type: count for rel_type, count in relationship_stats.all()},
        }
    
    async def update_statistics(self, session: AsyncSession, project_id: int) -> None:
        """Update project statistics."""
        # Count total files
        total_files = await session.execute(
            select(func.count(File.id)).where(File.project_id == project_id)
        )
        
        # Count analyzed files
        analyzed_files = await session.execute(
            select(func.count(File.id))
            .where(and_(
                File.project_id == project_id,
                File.status == FileStatus.ANALYZED
            ))
        )
        
        # Count total relationships
        total_relationships = await session.execute(
            select(func.count(FileRelationship.id))
            .join(File, File.id == FileRelationship.source_file_id)
            .where(File.project_id == project_id)
        )
        
        # Update project
        await session.execute(
            update(Project)
            .where(Project.id == project_id)
            .values(
                total_files=total_files.scalar(),
                analyzed_files=analyzed_files.scalar(),
                total_relationships=total_relationships.scalar(),
                last_scan_at=datetime.utcnow()
            )
        )


class FileRepository(BaseRepository):
    """Repository for File operations."""
    
    def __init__(self):
        super().__init__(File)
    
    async def get_by_path(self, session: AsyncSession, project_id: int, relative_path: str) -> Optional[File]:
        """Get file by project and relative path."""
        result = await session.execute(
            select(File).where(and_(
                File.project_id == project_id,
                File.relative_path == relative_path
            ))
        )
        return result.scalar_one_or_none()
    
    async def get_by_hash(self, session: AsyncSession, content_hash: str) -> List[File]:
        """Get files by content hash (for detecting duplicates)."""
        result = await session.execute(
            select(File).where(File.content_hash == content_hash)
        )
        return list(result.scalars().all())
    
    async def get_files_by_type(
        self, 
        session: AsyncSession, 
        project_id: int, 
        file_type: str,
        limit: int = 100
    ) -> List[File]:
        """Get files by type."""
        result = await session.execute(
            select(File)
            .where(and_(
                File.project_id == project_id,
                File.file_type == file_type
            ))
            .limit(limit)
        )
        return list(result.scalars().all())
    
    async def get_files_needing_analysis(
        self,
        session: AsyncSession,
        project_id: int,
        limit: int = 100
    ) -> List[File]:
        """Get files that need analysis."""
        result = await session.execute(
            select(File)
            .where(and_(
                File.project_id == project_id,
                File.status.in_([FileStatus.DISCOVERED, FileStatus.ANALYZING])
            ))
            .order_by(File.first_seen_at)
            .limit(limit)
        )
        return list(result.scalars().all())
    
    async def get_files_with_relationships(
        self,
        session: AsyncSession,
        project_id: int,
        limit: int = 100
    ) -> List[File]:
        """Get files with their relationships loaded."""
        result = await session.execute(
            select(File)
            .options(
                selectinload(File.outgoing_relationships).selectinload(FileRelationship.target_file),
                selectinload(File.incoming_relationships).selectinload(FileRelationship.source_file)
            )
            .where(File.project_id == project_id)
            .limit(limit)
        )
        return list(result.scalars().all())
    
    async def search_files(
        self,
        session: AsyncSession,
        project_id: int,
        query: str,
        file_types: Optional[List[str]] = None,
        limit: int = 100
    ) -> List[File]:
        """Search files by name or path."""
        conditions = [File.project_id == project_id]
        
        # Add text search condition
        search_condition = or_(
            File.name.ilike(f"%{query}%"),
            File.relative_path.ilike(f"%{query}%")
        )
        conditions.append(search_condition)
        
        # Add file type filter
        if file_types:
            conditions.append(File.file_type.in_(file_types))
        
        result = await session.execute(
            select(File)
            .where(and_(*conditions))
            .order_by(File.name)
            .limit(limit)
        )
        return list(result.scalars().all())


class FileRelationshipRepository(BaseRepository):
    """Repository for FileRelationship operations."""
    
    def __init__(self):
        super().__init__(FileRelationship)
    
    async def get_relationships_for_file(
        self,
        session: AsyncSession,
        file_id: int,
        relationship_types: Optional[List[RelationshipType]] = None
    ) -> List[FileRelationship]:
        """Get all relationships for a file (both incoming and outgoing)."""
        conditions = [
            or_(
                FileRelationship.source_file_id == file_id,
                FileRelationship.target_file_id == file_id
            )
        ]
        
        if relationship_types:
            conditions.append(FileRelationship.relationship_type.in_(relationship_types))
        
        result = await session.execute(
            select(FileRelationship)
            .options(
                joinedload(FileRelationship.source_file),
                joinedload(FileRelationship.target_file)
            )
            .where(and_(*conditions))
        )
        return list(result.scalars().all())
    
    async def create_relationship(
        self,
        session: AsyncSession,
        source_file_id: int,
        target_file_id: int,
        relationship_type: RelationshipType,
        **kwargs
    ) -> FileRelationship:
        """Create a new file relationship."""
        return await self.create(
            session,
            source_file_id=source_file_id,
            target_file_id=target_file_id,
            relationship_type=relationship_type,
            **kwargs
        )
    
    async def get_cross_reference_relationships(
        self,
        session: AsyncSession,
        project_id: int
    ) -> List[FileRelationship]:
        """Get all cross-reference relationships for a project."""
        result = await session.execute(
            select(FileRelationship)
            .join(File, File.id == FileRelationship.source_file_id)
            .options(
                joinedload(FileRelationship.source_file),
                joinedload(FileRelationship.target_file)
            )
            .where(and_(
                File.project_id == project_id,
                FileRelationship.relationship_type == RelationshipType.CROSS_REFERENCES
            ))
        )
        return list(result.scalars().all())
    
    async def find_missing_relationships(
        self,
        session: AsyncSession,
        project_id: int,
        relationship_type: RelationshipType
    ) -> List[Tuple[int, int]]:
        """Find missing bidirectional relationships."""
        # This would need more complex SQL to find files that should have
        # bidirectional relationships but don't
        # For now, return empty list
        return []


class PatternRepository(BaseRepository):
    """Repository for Pattern operations."""
    
    def __init__(self):
        super().__init__(Pattern)
    
    async def get_active_patterns(
        self,
        session: AsyncSession,
        project_id: int,
        pattern_type: Optional[str] = None
    ) -> List[Pattern]:
        """Get active patterns for a project."""
        conditions = [
            Pattern.project_id == project_id,
            Pattern.is_active == True
        ]
        
        if pattern_type:
            conditions.append(Pattern.pattern_type == pattern_type)
        
        result = await session.execute(
            select(Pattern)
            .where(and_(*conditions))
            .order_by(Pattern.confidence_score.desc())
        )
        return list(result.scalars().all())
    
    async def update_pattern_usage(
        self,
        session: AsyncSession,
        pattern_id: int,
        success: bool
    ) -> None:
        """Update pattern usage statistics."""
        pattern = await self.get_by_id(session, pattern_id)
        if pattern:
            pattern.usage_count += 1
            pattern.last_used_at = datetime.utcnow()
            
            if success:
                # Update success rate using exponential moving average
                alpha = 0.1  # Learning rate
                pattern.success_rate = (
                    alpha * 1.0 + (1 - alpha) * pattern.success_rate
                )
            else:
                pattern.success_rate = (
                    alpha * 0.0 + (1 - alpha) * pattern.success_rate
                )


class ScanSessionRepository(BaseRepository):
    """Repository for ScanSession operations."""
    
    def __init__(self):
        super().__init__(ScanSession)
    
    async def get_latest_session(
        self,
        session: AsyncSession,
        project_id: int
    ) -> Optional[ScanSession]:
        """Get the latest scan session for a project."""
        result = await session.execute(
            select(ScanSession)
            .where(ScanSession.project_id == project_id)
            .order_by(ScanSession.started_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
    
    async def get_active_session(
        self,
        session: AsyncSession,
        project_id: int
    ) -> Optional[ScanSession]:
        """Get active scan session for a project."""
        result = await session.execute(
            select(ScanSession)
            .where(and_(
                ScanSession.project_id == project_id,
                ScanSession.status == "running"
            ))
        )
        return result.scalar_one_or_none()


class CrossRefStatusRepository(BaseRepository):
    """Repository for CrossRefStatus operations."""
    
    def __init__(self):
        super().__init__(CrossRefStatus)
    
    async def get_status_for_session(
        self,
        session: AsyncSession,
        session_id: str,
        file_id: int
    ) -> Optional[CrossRefStatus]:
        """Get cross-reference status for a session and file."""
        result = await session.execute(
            select(CrossRefStatus)
            .where(and_(
                CrossRefStatus.session_id == session_id,
                CrossRefStatus.file_id == file_id
            ))
        )
        return result.scalar_one_or_none()
    
    async def mark_file_read(
        self,
        session: AsyncSession,
        session_id: str,
        file_id: int,
        read_time_seconds: Optional[int] = None
    ) -> CrossRefStatus:
        """Mark a file as read for a session."""
        status = await self.get_status_for_session(session, session_id, file_id)
        
        if status:
            status.is_read = True
            status.marked_read_at = datetime.utcnow()
            status.last_accessed_at = datetime.utcnow()
            status.access_count += 1
            if read_time_seconds:
                status.read_time_seconds = read_time_seconds
        else:
            status = await self.create(
                session,
                session_id=session_id,
                file_id=file_id,
                is_read=True,
                marked_read_at=datetime.utcnow(),
                read_time_seconds=read_time_seconds
            )
        
        return status


# Repository instances
project_repo = ProjectRepository()
file_repo = FileRepository()
relationship_repo = FileRelationshipRepository()
pattern_repo = PatternRepository()
scan_session_repo = ScanSessionRepository()
crossref_status_repo = CrossRefStatusRepository()


# Convenience functions for common operations
async def get_or_create_project(name: str, root_path: str, **kwargs) -> Project:
    """Get existing project or create new one."""
    async with get_db_session() as session:
        project = await project_repo.get_by_name(session, name)
        if not project:
            project = await project_repo.create(
                session,
                name=name,
                root_path=root_path,
                **kwargs
            )
        return project


async def get_project_summary(project_id: int) -> Optional[Dict[str, Any]]:
    """Get comprehensive project summary."""
    async with get_db_session() as session:
        return await project_repo.get_with_stats(session, project_id)


async def bulk_create_files(project_id: int, file_data: List[Dict[str, Any]]) -> List[File]:
    """Bulk create files for a project."""
    async with get_db_session() as session:
        files = []
        for data in file_data:
            data["project_id"] = project_id
            file_obj = await file_repo.create(session, **data)
            files.append(file_obj)
        return files 