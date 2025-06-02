"""Relationship Detection Engine

Detects and analyzes relationships between files based on content analysis,
building comprehensive dependency graphs and cross-reference networks.
"""

import asyncio
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any

import structlog
from src.analyzer.content_analyzer import AnalysisResult, CrossReference, ContentPattern
from src.database.operations import get_db_session, file_repo, project_repo
from src.utils.config import get_settings

logger = structlog.get_logger(__name__)


@dataclass
class FileRelationship:
    """Represents a relationship between two files."""
    source_file: str
    target_file: str
    relationship_type: str  # import, reference, hub_link, semantic_similarity
    strength: float = 0.0  # 0.0 to 1.0
    confidence: float = 0.0  # 0.0 to 1.0
    bidirectional: bool = False
    evidence: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DependencyGraph:
    """Represents a dependency graph for a project."""
    nodes: Set[str] = field(default_factory=set)
    edges: List[FileRelationship] = field(default_factory=list)
    hub_files: List[str] = field(default_factory=list)
    cycles: List[List[str]] = field(default_factory=list)
    depth_map: Dict[str, int] = field(default_factory=dict)
    clusters: List[List[str]] = field(default_factory=list)


@dataclass
class CrossReferenceRecommendation:
    """Recommendation for adding cross-references."""
    source_file: str
    target_files: List[str]
    recommendation_type: str  # missing_import_ref, hub_file_ref, semantic_ref
    confidence: float = 0.0
    reasoning: str = ""
    priority: str = "medium"  # low, medium, high, critical


class RelationshipDetector:
    """Detects and analyzes relationships between files."""
    
    def __init__(self):
        self.settings = get_settings()
        
        # Relationship scoring weights
        self.scoring_weights = {
            "direct_import": 1.0,
            "relative_import": 0.9,
            "markdown_link": 0.7,
            "hub_file_reference": 0.8,
            "semantic_similarity": 0.5,
            "shared_dependencies": 0.3,
            "common_patterns": 0.4,
        }
        
        # Confidence thresholds
        self.confidence_thresholds = {
            "high": 0.8,
            "medium": 0.6,
            "low": 0.4,
        }
    
    def detect_relationships(self, analysis_results: Dict[str, AnalysisResult]) -> List[FileRelationship]:
        """Detect relationships between files based on analysis results."""
        logger.info("Detecting file relationships", file_count=len(analysis_results))
        
        relationships = []
        
        # 1. Direct import/reference relationships
        relationships.extend(self._detect_import_relationships(analysis_results))
        
        # 2. Hub file relationships
        relationships.extend(self._detect_hub_relationships(analysis_results))
        
        # 3. Semantic similarity relationships
        relationships.extend(self._detect_semantic_relationships(analysis_results))
        
        # 4. Shared dependency relationships
        relationships.extend(self._detect_shared_dependency_relationships(analysis_results))
        
        # 5. Cross-reference pattern relationships
        relationships.extend(self._detect_crossref_pattern_relationships(analysis_results))
        
        # Remove duplicates and merge similar relationships
        relationships = self._merge_relationships(relationships)
        
        logger.info("Relationship detection complete", relationship_count=len(relationships))
        return relationships
    
    def _detect_import_relationships(self, analysis_results: Dict[str, AnalysisResult]) -> List[FileRelationship]:
        """Detect relationships from import statements."""
        relationships = []
        
        for file_path, result in list(analysis_results.items()):
            for cross_ref in result.cross_references:
                # Calculate relationship strength based on import type
                strength = self.scoring_weights.get(cross_ref.reference_type, 0.5)
                
                # Adjust for relative vs absolute imports
                if cross_ref.reference_type in ["import", "from_import"]:
                    # Check if target file exists in the project
                    target_exists = self._resolve_import_target(cross_ref.target_file, analysis_results)
                    if target_exists:
                        strength = self.scoring_weights["direct_import"]
                        confidence = cross_ref.confidence
                    else:
                        strength = 0.3  # External dependency
                        confidence = 0.5
                else:
                    confidence = cross_ref.confidence
                
                relationships.append(FileRelationship(
                    source_file=file_path,
                    target_file=cross_ref.target_file,
                    relationship_type="import",
                    strength=strength,
                    confidence=confidence,
                    evidence=[f"Line {cross_ref.line_number}: {cross_ref.context}"],
                    metadata={
                        "import_type": cross_ref.reference_type,
                        "line_number": cross_ref.line_number,
                    }
                ))
        
        return relationships
    
    def _detect_hub_relationships(self, analysis_results: Dict[str, AnalysisResult]) -> List[FileRelationship]:
        """Detect hub file relationships."""
        relationships = []
        
        # Identify hub files
        hub_files = []
        for file_path, result in list(analysis_results.items()):
            if result.hub_file_candidates:
                hub_files.extend(result.hub_file_candidates)
        
        hub_files = list(set(hub_files))  # Remove duplicates
        
        # Create relationships from all files to hub files
        for file_path, result in list(analysis_results.items()):
            for hub_file in hub_files:
                if file_path != hub_file:
                    # Check if there's already a reference to the hub
                    has_reference = any(
                        pattern.pattern_type in ["cross_ref_header", "hub_file_reference"]
                        and hub_file in pattern.content
                        for pattern in result.patterns
                    )
                    
                    strength = 0.8 if has_reference else 0.6
                    confidence = 0.9 if has_reference else 0.7
                    
                    relationships.append(FileRelationship(
                        source_file=file_path,
                        target_file=hub_file,
                        relationship_type="hub_link",
                        strength=strength,
                        confidence=confidence,
                        bidirectional=True,
                        evidence=[f"Hub file relationship with {hub_file}"],
                        metadata={"hub_file": True, "has_explicit_reference": has_reference}
                    ))
        
        return relationships
    
    def _detect_semantic_relationships(self, analysis_results: Dict[str, AnalysisResult]) -> List[FileRelationship]:
        """Detect semantic similarity relationships."""
        relationships = []
        
        # Group files by language and type
        language_groups = defaultdict(list)
        for file_path, result in list(analysis_results.items()):
            if result.language:
                language_groups[result.language].append(file_path)
        
        # Find semantic relationships within language groups
        for language, files in language_groups.items():
            for i, file1 in enumerate(files):
                for file2 in files[i+1:]:
                    result1 = analysis_results[file1]
                    result2 = analysis_results[file2]
                    
                    # Calculate semantic similarity
                    similarity = self._calculate_semantic_similarity(result1, result2)
                    
                    if similarity > 0.4:  # Threshold for meaningful similarity
                        relationships.append(FileRelationship(
                            source_file=file1,
                            target_file=file2,
                            relationship_type="semantic_similarity",
                            strength=similarity,
                            confidence=0.7,
                            bidirectional=True,
                            evidence=[f"Semantic similarity: {similarity:.2f}"],
                            metadata={"similarity_score": similarity, "language": language}
                        ))
        
        return relationships
    
    def _detect_shared_dependency_relationships(self, analysis_results: Dict[str, AnalysisResult]) -> List[FileRelationship]:
        """Detect relationships based on shared dependencies."""
        relationships = []
        
        # Build dependency map
        dependency_map = defaultdict(list)
        for file_path, result in list(analysis_results.items()):
            for dependency in result.dependencies:
                dependency_map[dependency].append(file_path)
        
        # Find files with shared dependencies
        for dependency, files in dependency_map.items():
            if len(files) > 1:
                for i, file1 in enumerate(files):
                    for file2 in files[i+1:]:
                        # Calculate shared dependency strength
                        result1 = analysis_results[file1]
                        result2 = analysis_results[file2]
                        
                        shared_deps = set(result1.dependencies) & set(result2.dependencies)
                        total_deps = set(result1.dependencies) | set(result2.dependencies)
                        
                        if total_deps:
                            strength = len(shared_deps) / len(total_deps)
                            
                            if strength > 0.3:  # Meaningful shared dependency
                                relationships.append(FileRelationship(
                                    source_file=file1,
                                    target_file=file2,
                                    relationship_type="shared_dependencies",
                                    strength=strength * self.scoring_weights["shared_dependencies"],
                                    confidence=0.6,
                                    bidirectional=True,
                                    evidence=[f"Shared dependencies: {', '.join(shared_deps)}"],
                                    metadata={
                                        "shared_dependencies": list(shared_deps),
                                        "dependency_overlap": strength
                                    }
                                ))
        
        return relationships
    
    def _detect_crossref_pattern_relationships(self, analysis_results: Dict[str, AnalysisResult]) -> List[FileRelationship]:
        """Detect relationships from existing cross-reference patterns."""
        relationships = []
        
        for file_path, result in list(analysis_results.items()):
            for pattern in result.patterns:
                if pattern.pattern_type in ["cross_ref_header", "warning_crossref"]:
                    # Extract referenced files from pattern metadata
                    referenced_files = pattern.metadata.get("referenced_files", [])
                    
                    for ref_file in referenced_files:
                        relationships.append(FileRelationship(
                            source_file=file_path,
                            target_file=ref_file,
                            relationship_type="explicit_crossref",
                            strength=0.9,
                            confidence=pattern.confidence,
                            evidence=[f"Line {pattern.line_number}: {pattern.content[:100]}..."],
                            metadata={
                                "pattern_type": pattern.pattern_type,
                                "line_number": pattern.line_number,
                            }
                        ))
        
        return relationships
    
    def _resolve_import_target(self, import_path: str, analysis_results: Dict[str, AnalysisResult]) -> bool:
        """Check if an import target exists in the project."""
        # Simple resolution for relative imports
        if import_path.startswith('.'):
            return True  # Assume relative imports are internal
        
        # Check if any file matches the import
        for file_path in analysis_results.keys():
            file_stem = Path(file_path).stem
            if import_path == file_stem or import_path.endswith(f"/{file_stem}"):
                return True
        
        return False
    
    def _calculate_semantic_similarity(self, result1: AnalysisResult, result2: AnalysisResult) -> float:
        """Calculate semantic similarity between two files."""
        similarity = 0.0
        
        # Shared exports
        exports1 = set(result1.exports)
        exports2 = set(result2.exports)
        if exports1 or exports2:
            export_similarity = len(exports1 & exports2) / len(exports1 | exports2) if (exports1 | exports2) else 0
            similarity += export_similarity * 0.3
        
        # Shared dependencies
        deps1 = set(result1.dependencies)
        deps2 = set(result2.dependencies)
        if deps1 or deps2:
            dep_similarity = len(deps1 & deps2) / len(deps1 | deps2) if (deps1 | deps2) else 0
            similarity += dep_similarity * 0.4
        
        # Shared patterns
        patterns1 = set(p.pattern_type for p in result1.patterns)
        patterns2 = set(p.pattern_type for p in result2.patterns)
        if patterns1 or patterns2:
            pattern_similarity = len(patterns1 & patterns2) / len(patterns1 | patterns2) if (patterns1 | patterns2) else 0
            similarity += pattern_similarity * 0.3
        
        return min(similarity, 1.0)
    
    def _merge_relationships(self, relationships: List[FileRelationship]) -> List[FileRelationship]:
        """Merge duplicate relationships and consolidate evidence."""
        # Group relationships by source-target pair
        relationship_groups = defaultdict(list)
        
        for rel in relationships:
            key = (rel.source_file, rel.target_file)
            relationship_groups[key].append(rel)
        
        merged = []
        for (source, target), group in relationship_groups.items():
            if len(group) == 1:
                merged.append(group[0])
            else:
                # Merge multiple relationships
                merged_rel = FileRelationship(
                    source_file=source,
                    target_file=target,
                    relationship_type=group[0].relationship_type,  # Use first type
                    strength=max(rel.strength for rel in group),  # Use max strength
                    confidence=max(rel.confidence for rel in group),  # Use max confidence
                    bidirectional=any(rel.bidirectional for rel in group),
                    evidence=[],
                    metadata={}
                )
                
                # Combine evidence
                for rel in group:
                    merged_rel.evidence.extend(rel.evidence)
                    merged_rel.metadata.update(rel.metadata)
                
                # Add merged type info
                merged_rel.metadata["merged_types"] = [rel.relationship_type for rel in group]
                
                merged.append(merged_rel)
        
        return merged


class DependencyGraphBuilder:
    """Builds and analyzes dependency graphs from relationships."""
    
    def __init__(self):
        self.settings = get_settings()
    
    def build_graph(self, relationships: List[FileRelationship]) -> DependencyGraph:
        """Build a dependency graph from relationships."""
        logger.info("Building dependency graph", relationship_count=len(relationships))
        
        graph = DependencyGraph()
        
        # Collect all nodes
        for rel in relationships:
            graph.nodes.add(rel.source_file)
            graph.nodes.add(rel.target_file)
        
        # Add relationships as edges
        graph.edges = relationships
        
        # Identify hub files (high in-degree nodes)
        in_degree = defaultdict(int)
        for rel in relationships:
            in_degree[rel.target_file] += 1
        
        # Hub files have significantly more incoming connections
        if in_degree:
            avg_in_degree = sum(in_degree.values()) / len(in_degree)
            threshold = avg_in_degree * 2  # 2x average
            
            graph.hub_files = [
                file for file, degree in in_degree.items()
                if degree >= threshold and degree >= 3  # At least 3 connections
            ]
        
        # Detect cycles
        graph.cycles = self._detect_cycles(relationships)
        
        # Calculate depth map (distance from hub files)
        graph.depth_map = self._calculate_depth_map(graph.hub_files, relationships)
        
        # Detect clusters
        graph.clusters = self._detect_clusters(relationships)
        
        logger.info(
            "Dependency graph built",
            nodes=len(graph.nodes),
            edges=len(graph.edges),
            hub_files=len(graph.hub_files),
            cycles=len(graph.cycles),
            clusters=len(graph.clusters),
        )
        
        return graph
    
    def _detect_cycles(self, relationships: List[FileRelationship]) -> List[List[str]]:
        """Detect cycles in the dependency graph."""
        # Build adjacency list
        adj = defaultdict(list)
        for rel in relationships:
            if rel.relationship_type in ["import", "explicit_crossref"]:
                adj[rel.source_file].append(rel.target_file)
        
        # DFS to detect cycles
        cycles = []
        visited = set()
        rec_stack = set()
        path = []
        
        def dfs(node):
            if node in rec_stack:
                # Found cycle
                cycle_start = path.index(node)
                cycles.append(path[cycle_start:] + [node])
                return
            
            if node in visited:
                return
            
            visited.add(node)
            rec_stack.add(node)
            path.append(node)
            
            for neighbor in adj[node]:
                dfs(neighbor)
            
            rec_stack.remove(node)
            path.pop()
        
        for node in list(adj):  # Iterate over a copy to prevent dictionary size change
            if node not in visited:
                dfs(node)
        
        return cycles
    
    def _calculate_depth_map(self, hub_files: List[str], relationships: List[FileRelationship]) -> Dict[str, int]:
        """Calculate distance from hub files using BFS."""
        if not hub_files:
            return {}
        
        # Build adjacency list (bidirectional for depth calculation)
        adj = defaultdict(list)
        for rel in relationships:
            adj[rel.source_file].append(rel.target_file)
            if rel.bidirectional:
                adj[rel.target_file].append(rel.source_file)
        
        depth_map = {}
        
        # BFS from each hub file
        for hub in hub_files:
            queue = deque([(hub, 0)])
            visited = {hub}
            
            while queue:
                node, depth = queue.popleft()
                
                if node not in depth_map or depth < depth_map[node]:
                    depth_map[node] = depth
                
                for neighbor in adj[node]:
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append((neighbor, depth + 1))
        
        return depth_map
    
    def _detect_clusters(self, relationships: List[FileRelationship]) -> List[List[str]]:
        """Detect clusters of strongly connected files."""
        # Build adjacency list with bidirectional connections
        adj = defaultdict(set)
        all_nodes = set()
        
        for rel in relationships:
            if rel.strength > 0.6:  # Only strong relationships
                adj[rel.source_file].add(rel.target_file)
                if rel.bidirectional:
                    adj[rel.target_file].add(rel.source_file)
                all_nodes.add(rel.source_file)
                all_nodes.add(rel.target_file)
        
        # Find connected components
        clusters = []
        visited = set()
        
        for node in all_nodes:
            if node not in visited:
                cluster = []
                stack = [node]
                
                while stack:
                    current = stack.pop()
                    if current not in visited:
                        visited.add(current)
                        cluster.append(current)
                        stack.extend(adj[current] - visited)
                
                if len(cluster) > 1:  # Only meaningful clusters
                    clusters.append(cluster)
        
        return clusters


class CrossReferenceRecommender:
    """Recommends cross-reference additions based on relationships."""
    
    def __init__(self):
        self.settings = get_settings()
    
    def generate_recommendations(
        self,
        relationships: List[FileRelationship],
        dependency_graph: DependencyGraph,
        analysis_results: Dict[str, AnalysisResult]
    ) -> List[CrossReferenceRecommendation]:
        """Generate cross-reference recommendations."""
        logger.info("Generating cross-reference recommendations")
        
        recommendations = []
        
        # 1. Missing hub file references
        recommendations.extend(self._recommend_hub_references(dependency_graph, analysis_results))
        
        # 2. Missing import references
        recommendations.extend(self._recommend_import_references(relationships, analysis_results))
        
        # 3. Semantic similarity references
        recommendations.extend(self._recommend_semantic_references(relationships, analysis_results))
        
        # 4. Cluster-based references
        recommendations.extend(self._recommend_cluster_references(dependency_graph, analysis_results))
        
        # Sort by priority and confidence
        recommendations.sort(key=lambda x: (
            {"critical": 4, "high": 3, "medium": 2, "low": 1}[x.priority],
            x.confidence
        ), reverse=True)
        
        logger.info("Cross-reference recommendations generated", count=len(recommendations))
        return recommendations
    
    def _recommend_hub_references(
        self,
        dependency_graph: DependencyGraph,
        analysis_results: Dict[str, AnalysisResult]
    ) -> List[CrossReferenceRecommendation]:
        """Recommend references to hub files."""
        recommendations = []
        
        for file_path, result in list(analysis_results.items()):
            if file_path not in dependency_graph.hub_files:
                # Check if file already references hub files
                existing_refs = set()
                for pattern in result.patterns:
                    if pattern.pattern_type in ["cross_ref_header", "warning_crossref"]:
                        existing_refs.update(pattern.metadata.get("referenced_files", []))
                
                # Recommend missing hub file references
                missing_hubs = [hub for hub in dependency_graph.hub_files if hub not in existing_refs]
                
                if missing_hubs:
                    recommendations.append(CrossReferenceRecommendation(
                        source_file=file_path,
                        target_files=missing_hubs,
                        recommendation_type="hub_file_ref",
                        confidence=0.8,
                        reasoning=f"File should reference hub files: {', '.join(missing_hubs)}",
                        priority="high"
                    ))
        
        return recommendations
    
    def _recommend_import_references(
        self,
        relationships: List[FileRelationship],
        analysis_results: Dict[str, AnalysisResult]
    ) -> List[CrossReferenceRecommendation]:
        """Recommend cross-references for strong import relationships."""
        recommendations = []
        
        # Group relationships by source file
        source_relationships = defaultdict(list)
        for rel in relationships:
            if rel.relationship_type == "import" and rel.strength > 0.7:
                source_relationships[rel.source_file].append(rel)
        
        for source_file, rels in source_relationships.items():
            if len(rels) >= 3:  # Files with many imports should have cross-refs
                # Check existing cross-references
                result = analysis_results[source_file]
                existing_crossrefs = any(
                    pattern.pattern_type in ["cross_ref_header", "warning_crossref"]
                    for pattern in result.patterns
                )
                
                if not existing_crossrefs:
                    target_files = [rel.target_file for rel in rels[:5]]  # Top 5
                    
                    recommendations.append(CrossReferenceRecommendation(
                        source_file=source_file,
                        target_files=target_files,
                        recommendation_type="missing_import_ref",
                        confidence=0.7,
                        reasoning=f"File has {len(rels)} strong dependencies that should be cross-referenced",
                        priority="medium"
                    ))
        
        return recommendations
    
    def _recommend_semantic_references(
        self,
        relationships: List[FileRelationship],
        analysis_results: Dict[str, AnalysisResult]
    ) -> List[CrossReferenceRecommendation]:
        """Recommend cross-references based on semantic similarity."""
        recommendations = []
        
        # Find high-similarity pairs
        semantic_rels = [
            rel for rel in relationships
            if rel.relationship_type == "semantic_similarity" and rel.strength > 0.7
        ]
        
        for rel in semantic_rels:
            # Check if files already cross-reference each other
            source_result = analysis_results[rel.source_file]
            target_mentioned = any(
                rel.target_file in pattern.content
                for pattern in source_result.patterns
            )
            
            if not target_mentioned:
                recommendations.append(CrossReferenceRecommendation(
                    source_file=rel.source_file,
                    target_files=[rel.target_file],
                    recommendation_type="semantic_ref",
                    confidence=rel.confidence,
                    reasoning=f"High semantic similarity ({rel.strength:.2f}) with {rel.target_file}",
                    priority="low"
                ))
        
        return recommendations
    
    def _recommend_cluster_references(
        self,
        dependency_graph: DependencyGraph,
        analysis_results: Dict[str, AnalysisResult]
    ) -> List[CrossReferenceRecommendation]:
        """Recommend cross-references within clusters."""
        recommendations = []
        
        for cluster in dependency_graph.clusters:
            if len(cluster) >= 3:  # Meaningful clusters
                # Each file in cluster should reference others
                for file_path in cluster:
                    other_files = [f for f in cluster if f != file_path]
                    
                    # Check existing references
                    result = analysis_results[file_path]
                    existing_refs = set()
                    for pattern in result.patterns:
                        existing_refs.update(pattern.metadata.get("referenced_files", []))
                    
                    missing_refs = [f for f in other_files if f not in existing_refs]
                    
                    if len(missing_refs) >= 2:
                        recommendations.append(CrossReferenceRecommendation(
                            source_file=file_path,
                            target_files=missing_refs[:3],  # Top 3
                            recommendation_type="cluster_ref",
                            confidence=0.6,
                            reasoning=f"File is part of a cluster with {len(cluster)} related files",
                            priority="low"
                        ))
        
        return recommendations


# Main analysis pipeline
class RelationshipAnalyzer:
    """Main analyzer that orchestrates relationship detection and analysis."""
    
    def __init__(self):
        self.relationship_detector = RelationshipDetector()
        self.graph_builder = DependencyGraphBuilder()
        self.recommender = CrossReferenceRecommender()
    
    async def analyze_project_relationships(
        self,
        project_id: int,
        analysis_results: Dict[str, AnalysisResult]
    ) -> Tuple[List[FileRelationship], DependencyGraph, List[CrossReferenceRecommendation]]:
        """Perform complete relationship analysis for a project."""
        logger.info("Starting project relationship analysis", project_id=project_id)
        
        # 1. Detect relationships
        relationships = self.relationship_detector.detect_relationships(analysis_results)
        
        # 2. Build dependency graph
        dependency_graph = self.graph_builder.build_graph(relationships)
        
        # 3. Generate recommendations
        recommendations = self.recommender.generate_recommendations(
            relationships, dependency_graph, analysis_results
        )
        
        logger.info(
            "Project relationship analysis complete",
            project_id=project_id,
            relationships=len(relationships),
            hub_files=len(dependency_graph.hub_files),
            recommendations=len(recommendations)
        )
        
        return relationships, dependency_graph, recommendations


# Convenience functions
async def analyze_relationships(analysis_results: Dict[str, AnalysisResult]) -> Tuple[List[FileRelationship], DependencyGraph]:
    """Analyze relationships from content analysis results."""
    analyzer = RelationshipAnalyzer()
    relationships = analyzer.relationship_detector.detect_relationships(analysis_results)
    dependency_graph = analyzer.graph_builder.build_graph(relationships)
    return relationships, dependency_graph


async def get_crossref_recommendations(
    relationships: List[FileRelationship],
    dependency_graph: DependencyGraph,
    analysis_results: Dict[str, AnalysisResult]
) -> List[CrossReferenceRecommendation]:
    """Get cross-reference recommendations."""
    recommender = CrossReferenceRecommender()
    return recommender.generate_recommendations(relationships, dependency_graph, analysis_results) 