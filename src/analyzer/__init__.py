"""Universal Content Analysis Engine

Comprehensive content analysis system for cross-reference detection, relationship
analysis, and pattern identification across any codebase.
"""

import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

import structlog

from .content_analyzer import (
    ContentAnalyzer,
    AnalysisResult,
    ImportInfo,
    CrossReference,
    ContentPattern,
    analyze_file_content,
    analyze_project_content,
)

from .relationship_detector import (
    RelationshipDetector,
    DependencyGraphBuilder,
    CrossReferenceRecommender,
    RelationshipAnalyzer,
    FileRelationship,
    DependencyGraph,
    CrossReferenceRecommendation,
    analyze_relationships,
    get_crossref_recommendations,
)

from .pattern_detector import (
    PatternDetector,
    DetectedPattern,
    PatternReport,
    detect_project_patterns,
    get_crossref_patterns,
)

from src.database.operations import get_db_session, project_repo
from src.utils.config import get_settings

logger = structlog.get_logger(__name__)

__all__ = [
    # Core analysis classes
    "UniversalAnalyzer",
    "AnalysisPipeline",
    
    # Content analysis
    "ContentAnalyzer",
    "AnalysisResult",
    "ImportInfo",
    "CrossReference",
    "ContentPattern",
    
    # Relationship analysis
    "RelationshipDetector",
    "DependencyGraphBuilder",
    "CrossReferenceRecommender",
    "RelationshipAnalyzer",
    "FileRelationship",
    "DependencyGraph",
    "CrossReferenceRecommendation",
    
    # Pattern detection
    "PatternDetector",
    "DetectedPattern",
    "PatternReport",
    
    # Convenience functions
    "analyze_file_content",
    "analyze_project_content",
    "analyze_relationships", 
    "get_crossref_recommendations",
    "detect_project_patterns",
    "get_crossref_patterns",
    "analyze_project",
]


class UniversalAnalyzer:
    """Universal content analyzer that orchestrates all analysis components."""
    
    def __init__(self):
        self.content_analyzer = ContentAnalyzer()
        self.relationship_analyzer = RelationshipAnalyzer()
        self.pattern_detector = PatternDetector()
        self.settings = get_settings()
        
        logger.info("Initialized universal analyzer")
    
    async def analyze_project(
        self,
        project_id: int,
        include_patterns: bool = True,
        include_relationships: bool = True,
        include_recommendations: bool = True,
    ) -> "AnalysisReport":
        """Perform comprehensive analysis of a project."""
        logger.info("Starting comprehensive project analysis", project_id=project_id)
        
        try:
            # Step 1: Content analysis
            logger.info("Phase 1: Content analysis")
            content_results = await self.content_analyzer.analyze_project_files(project_id)
            
            # Step 2: Pattern detection
            pattern_report = None
            if include_patterns:
                logger.info("Phase 2: Pattern detection")
                pattern_report = self.pattern_detector.detect_all_patterns(content_results)
            
            # Step 3: Relationship analysis
            relationships = []
            dependency_graph = None
            recommendations = []
            
            if include_relationships:
                logger.info("Phase 3: Relationship analysis")
                relationships, dependency_graph, recs = await self.relationship_analyzer.analyze_project_relationships(
                    project_id, content_results
                )
                
                if include_recommendations:
                    recommendations = recs
            
            # Create comprehensive report
            report = AnalysisReport(
                project_id=project_id,
                content_results=content_results,
                relationships=relationships,
                dependency_graph=dependency_graph,
                pattern_report=pattern_report,
                recommendations=recommendations,
                analysis_complete=True,
            )
            
            logger.info(
                "Comprehensive analysis complete",
                project_id=project_id,
                files_analyzed=len(content_results),
                relationships=len(relationships),
                patterns=len(pattern_report.patterns) if pattern_report else 0,
                recommendations=len(recommendations),
            )
            
            return report
            
        except Exception as e:
            logger.error("Project analysis failed", project_id=project_id, error=str(e))
            raise
    
    async def analyze_file(
        self,
        file_path: str,
        content: str,
        language: Optional[str] = None,
    ) -> AnalysisResult:
        """Analyze a single file."""
        return self.content_analyzer.analyze_file(file_path, content, language)


class AnalysisPipeline:
    """Analysis pipeline for batch processing and incremental updates."""
    
    def __init__(self):
        self.analyzer = UniversalAnalyzer()
    
    async def process_file_batch(
        self,
        file_batch: List[Tuple[str, str, Optional[str]]],  # (path, content, language)
    ) -> Dict[str, AnalysisResult]:
        """Process a batch of files."""
        results = {}
        
        for file_path, content, language in file_batch:
            try:
                result = await self.analyzer.analyze_file(file_path, content, language)
                results[file_path] = result
            except Exception as e:
                logger.error("Failed to analyze file", file=file_path, error=str(e))
        
        return results
    
    async def incremental_analysis(
        self,
        project_id: int,
        changed_files: List[str],
    ) -> "AnalysisReport":
        """Perform incremental analysis on changed files."""
        logger.info("Starting incremental analysis", project_id=project_id, changed_files=len(changed_files))
        
        # For now, we'll do a full re-analysis
        # In the future, this could be optimized to only re-analyze affected relationships
        return await self.analyzer.analyze_project(project_id)


class AnalysisReport:
    """Comprehensive analysis report for a project."""
    
    def __init__(
        self,
        project_id: int,
        content_results: Dict[str, AnalysisResult],
        relationships: List[FileRelationship],
        dependency_graph: Optional[DependencyGraph] = None,
        pattern_report: Optional[PatternReport] = None,
        recommendations: List[CrossReferenceRecommendation] = None,
        analysis_complete: bool = False,
    ):
        self.project_id = project_id
        self.content_results = content_results
        self.relationships = relationships
        self.dependency_graph = dependency_graph
        self.pattern_report = pattern_report
        self.recommendations = recommendations or []
        self.analysis_complete = analysis_complete
    
    def get_summary(self) -> Dict[str, Any]:
        """Get analysis summary."""
        return {
            "project_id": self.project_id,
            "files_analyzed": len(self.content_results),
            "total_imports": sum(len(r.imports) for r in self.content_results.values()),
            "total_exports": sum(len(r.exports) for r in self.content_results.values()),
            "total_dependencies": len(set(
                dep for result in self.content_results.values()
                for dep in result.dependencies
            )),
            "relationships": len(self.relationships),
            "hub_files": len(self.dependency_graph.hub_files) if self.dependency_graph else 0,
            "cycles": len(self.dependency_graph.cycles) if self.dependency_graph else 0,
            "clusters": len(self.dependency_graph.clusters) if self.dependency_graph else 0,
            "patterns": len(self.pattern_report.patterns) if self.pattern_report else 0,
            "quality_score": self.pattern_report.quality_score if self.pattern_report else 0.0,
            "recommendations": len(self.recommendations),
            "analysis_complete": self.analysis_complete,
        }
    
    def get_crossref_insights(self) -> Dict[str, Any]:
        """Get cross-reference specific insights."""
        insights = {
            "files_with_crossrefs": 0,
            "files_without_crossrefs": 0,
            "hub_files": [],
            "missing_hub_refs": 0,
            "crossref_coverage": 0.0,
            "top_recommendations": [],
        }
        
        # Analyze cross-reference coverage
        files_with_crossrefs = [
            f for f, r in self.content_results.items()
            if any(p.pattern_type in ["cross_ref_header", "warning_crossref"] for p in r.patterns)
        ]
        
        insights["files_with_crossrefs"] = len(files_with_crossrefs)
        insights["files_without_crossrefs"] = len(self.content_results) - len(files_with_crossrefs)
        insights["crossref_coverage"] = len(files_with_crossrefs) / len(self.content_results) if self.content_results else 0
        
        # Hub files
        if self.dependency_graph:
            insights["hub_files"] = self.dependency_graph.hub_files
        
        # Top recommendations
        high_priority_recs = [
            r for r in self.recommendations
            if r.priority in ["critical", "high"]
        ]
        insights["top_recommendations"] = [
            {
                "type": r.recommendation_type,
                "source": r.source_file,
                "targets": r.target_files[:3],  # First 3
                "confidence": r.confidence,
                "priority": r.priority,
                "reasoning": r.reasoning,
            }
            for r in high_priority_recs[:5]  # Top 5
        ]
        
        return insights
    
    def export_to_dict(self) -> Dict[str, Any]:
        """Export complete report to dictionary."""
        return {
            "summary": self.get_summary(),
            "crossref_insights": self.get_crossref_insights(),
            "content_results": {
                f: {
                    "imports": len(r.imports),
                    "exports": len(r.exports),
                    "dependencies": r.dependencies,
                    "patterns": [p.pattern_type for p in r.patterns],
                    "hub_candidate": bool(r.hub_file_candidates),
                    "language": r.language,
                }
                for f, r in self.content_results.items()
            },
            "relationships": [
                {
                    "source": rel.source_file,
                    "target": rel.target_file,
                    "type": rel.relationship_type,
                    "strength": rel.strength,
                    "confidence": rel.confidence,
                    "bidirectional": rel.bidirectional,
                }
                for rel in self.relationships
            ],
            "dependency_graph": {
                "nodes": len(self.dependency_graph.nodes) if self.dependency_graph else 0,
                "edges": len(self.dependency_graph.edges) if self.dependency_graph else 0,
                "hub_files": self.dependency_graph.hub_files if self.dependency_graph else [],
                "cycles": self.dependency_graph.cycles if self.dependency_graph else [],
                "clusters": self.dependency_graph.clusters if self.dependency_graph else [],
            } if self.dependency_graph else None,
            "patterns": {
                "total": len(self.pattern_report.patterns) if self.pattern_report else 0,
                "by_type": self.pattern_report.pattern_counts if self.pattern_report else {},
                "quality_score": self.pattern_report.quality_score if self.pattern_report else 0.0,
                "recommendations": self.pattern_report.recommendations if self.pattern_report else [],
            } if self.pattern_report else None,
            "crossref_recommendations": [
                {
                    "source": rec.source_file,
                    "targets": rec.target_files,
                    "type": rec.recommendation_type,
                    "confidence": rec.confidence,
                    "priority": rec.priority,
                    "reasoning": rec.reasoning,
                }
                for rec in self.recommendations
            ],
        }


# Global analyzer instance
universal_analyzer = UniversalAnalyzer()


# Convenience functions
async def analyze_project(
    project_id: int,
    include_patterns: bool = True,
    include_relationships: bool = True,
    include_recommendations: bool = True,
) -> AnalysisReport:
    """Analyze a complete project with all components."""
    return await universal_analyzer.analyze_project(
        project_id, include_patterns, include_relationships, include_recommendations
    )


async def quick_file_analysis(file_path: str, content: str, language: Optional[str] = None) -> AnalysisResult:
    """Quick analysis of a single file."""
    return await universal_analyzer.analyze_file(file_path, content, language) 