"""Pattern Detection Engine

Detects specific patterns in code and documentation that inform cross-reference
generation, identify anti-patterns, and suggest improvements.
"""

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any

import structlog
from src.analyzer.content_analyzer import AnalysisResult, ContentPattern
from src.utils.config import get_settings

logger = structlog.get_logger(__name__)


@dataclass
class DetectedPattern:
    """A detected pattern in the codebase."""
    pattern_id: str
    pattern_type: str  # crossref, architectural, anti_pattern, naming, etc.
    description: str
    files: List[str] = field(default_factory=list)
    confidence: float = 0.0
    severity: str = "info"  # info, warning, error, critical
    suggestions: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PatternReport:
    """Report of all detected patterns in a project."""
    patterns: List[DetectedPattern] = field(default_factory=list)
    pattern_counts: Dict[str, int] = field(default_factory=dict)
    quality_score: float = 0.0
    recommendations: List[str] = field(default_factory=list)


class CrossReferencePatternDetector:
    """Detects cross-reference patterns and anti-patterns."""
    
    def __init__(self):
        self.crossref_indicators = [
            # Strong cross-reference patterns
            (r'⚠️.*?IMPORTANT.*?HAVE TO.*?read', "strong_warning", 1.0),
            (r'Cross-reference:?', "explicit_crossref", 0.9),
            (r'MUST READ:?', "mandatory_reading", 0.9),
            (r'Also read with', "supplementary_reading", 0.8),
            (r'Read with.*?for complete', "complete_understanding", 0.8),
            
            # Hub file indicators
            (r'central hub|main.*?documentation', "hub_file", 0.9),
            (r'complete.*?picture|all related files', "comprehensive_reference", 0.8),
            (r'main entry point|primary.*?documentation', "entry_point", 0.8),
            
            # Weak patterns (should be strengthened)
            (r'see also', "weak_reference", 0.3),
            (r'related.*?file', "weak_related", 0.4),
            (r'check.*?file', "weak_check", 0.3),
        ]
    
    def detect_patterns(self, analysis_results: Dict[str, AnalysisResult]) -> List[DetectedPattern]:
        """Detect cross-reference patterns."""
        patterns = []
        
        # Count pattern occurrences
        pattern_counts = defaultdict(int)
        pattern_files = defaultdict(list)
        
        for file_path, result in analysis_results.items():
            file_content = ""  # We'd need to read the file again, but for now work with patterns
            
            for pattern in result.patterns:
                if pattern.pattern_type in ["cross_ref_header", "warning_crossref", "hub_file"]:
                    pattern_type = f"explicit_{pattern.pattern_type}"
                    pattern_counts[pattern_type] += 1
                    pattern_files[pattern_type].append(file_path)
        
        # Analyze cross-reference coverage
        total_files = len(analysis_results)
        files_with_crossrefs = len([
            f for f, r in analysis_results.items()
            if any(p.pattern_type in ["cross_ref_header", "warning_crossref"] for p in r.patterns)
        ])
        
        coverage = files_with_crossrefs / total_files if total_files > 0 else 0
        
        if coverage < 0.3:
            patterns.append(DetectedPattern(
                pattern_id="low_crossref_coverage",
                pattern_type="crossref_anti_pattern",
                description=f"Low cross-reference coverage: only {coverage:.1%} of files have cross-references",
                files=[],
                confidence=0.9,
                severity="warning",
                suggestions=[
                    "Add cross-reference headers to more files",
                    "Implement systematic cross-referencing",
                    "Create hub files for major components"
                ],
                metadata={"coverage": coverage, "files_with_crossrefs": files_with_crossrefs}
            ))
        
        # Detect missing hub file references
        hub_files = [
            f for f, r in analysis_results.items()
            if any(p.pattern_type == "hub_file" for p in r.patterns)
        ]
        
        if hub_files:
            files_without_hub_refs = []
            for file_path, result in analysis_results.items():
                if file_path not in hub_files:
                    has_hub_ref = any(
                        any(hub in p.content for hub in hub_files)
                        for p in result.patterns
                    )
                    if not has_hub_ref:
                        files_without_hub_refs.append(file_path)
            
            if files_without_hub_refs:
                patterns.append(DetectedPattern(
                    pattern_id="missing_hub_references",
                    pattern_type="crossref_improvement",
                    description=f"{len(files_without_hub_refs)} files don't reference hub files",
                    files=files_without_hub_refs[:10],  # Show first 10
                    confidence=0.8,
                    severity="info",
                    suggestions=[
                        "Add hub file references to non-hub files",
                        "Create cross-reference headers linking to main documentation"
                    ],
                    metadata={"hub_files": hub_files, "missing_count": len(files_without_hub_refs)}
                ))
        
        return patterns


class ArchitecturalPatternDetector:
    """Detects architectural patterns and anti-patterns."""
    
    def __init__(self):
        self.architectural_patterns = {
            # Good patterns
            "layered_architecture": [
                r"(?:controllers?|views?|models?)",
                r"(?:services?|repositories?|daos?)",
                r"(?:utils?|helpers?|libs?)"
            ],
            "mvc_pattern": [
                r"models?",
                r"views?", 
                r"controllers?"
            ],
            "factory_pattern": [
                r"factory",
                r"builder",
                r"creator"
            ],
            
            # Anti-patterns
            "god_object": [
                r"manager",
                r"handler", 
                r"processor",
                r"helper"
            ],
            "circular_dependency": [],  # Detected differently
        }
    
    def detect_patterns(self, analysis_results: Dict[str, AnalysisResult]) -> List[DetectedPattern]:
        """Detect architectural patterns."""
        patterns = []
        
        # Analyze file naming patterns
        file_names = [Path(f).stem.lower() for f in analysis_results.keys()]
        
        # Detect architectural layers
        layers = {
            "controller": len([n for n in file_names if "controller" in n]),
            "service": len([n for n in file_names if "service" in n]),
            "model": len([n for n in file_names if "model" in n]),
            "view": len([n for n in file_names if "view" in n]),
            "repository": len([n for n in file_names if "repo" in n or "repository" in n]),
            "util": len([n for n in file_names if "util" in n or "helper" in n]),
        }
        
        # Check for layered architecture
        active_layers = [layer for layer, count in layers.items() if count > 0]
        if len(active_layers) >= 3:
            patterns.append(DetectedPattern(
                pattern_id="layered_architecture",
                pattern_type="architectural_pattern",
                description=f"Layered architecture detected with {len(active_layers)} layers",
                files=[],
                confidence=0.8,
                severity="info",
                suggestions=["Maintain clear separation between layers"],
                metadata={"layers": layers, "active_layers": active_layers}
            ))
        
        # Detect potential god objects (files with many imports)
        god_object_candidates = []
        for file_path, result in analysis_results.items():
            if len(result.imports) > 20:  # Arbitrary threshold
                god_object_candidates.append(file_path)
        
        if god_object_candidates:
            patterns.append(DetectedPattern(
                pattern_id="potential_god_objects",
                pattern_type="architectural_anti_pattern",
                description=f"{len(god_object_candidates)} files with excessive imports (potential god objects)",
                files=god_object_candidates,
                confidence=0.7,
                severity="warning",
                suggestions=[
                    "Consider breaking down large files",
                    "Apply single responsibility principle",
                    "Extract common functionality to separate modules"
                ],
                metadata={"threshold": 20}
            ))
        
        return patterns


class DependencyPatternDetector:
    """Detects dependency patterns and issues."""
    
    def detect_patterns(self, analysis_results: Dict[str, AnalysisResult]) -> List[DetectedPattern]:
        """Detect dependency patterns."""
        patterns = []
        
        # Analyze dependency distribution
        all_dependencies = []
        file_dep_counts = {}
        
        for file_path, result in analysis_results.items():
            file_dep_counts[file_path] = len(result.dependencies)
            all_dependencies.extend(result.dependencies)
        
        dep_counter = Counter(all_dependencies)
        
        # Detect over-used dependencies
        total_files = len(analysis_results)
        overused_deps = [
            (dep, count) for dep, count in dep_counter.items()
            if count > total_files * 0.8  # Used in >80% of files
        ]
        
        if overused_deps:
            patterns.append(DetectedPattern(
                pattern_id="overused_dependencies",
                pattern_type="dependency_pattern",
                description=f"{len(overused_deps)} dependencies used in >80% of files",
                files=[],
                confidence=0.8,
                severity="info",
                suggestions=[
                    "Consider creating a common dependency module",
                    "Review if all files really need these dependencies"
                ],
                metadata={"overused_deps": overused_deps}
            ))
        
        # Detect files with no dependencies (potential utility files or isolated modules)
        no_deps_files = [f for f, count in file_dep_counts.items() if count == 0]
        
        if len(no_deps_files) > total_files * 0.2:  # >20% of files
            patterns.append(DetectedPattern(
                pattern_id="many_isolated_files",
                pattern_type="dependency_pattern",
                description=f"{len(no_deps_files)} files have no dependencies",
                files=no_deps_files[:10],
                confidence=0.7,
                severity="info",
                suggestions=[
                    "Review if isolated files should be better integrated",
                    "Consider grouping utility files"
                ],
                metadata={"isolated_count": len(no_deps_files)}
            ))
        
        return patterns


class NamingPatternDetector:
    """Detects naming patterns and conventions."""
    
    def detect_patterns(self, analysis_results: Dict[str, AnalysisResult]) -> List[DetectedPattern]:
        """Detect naming patterns."""
        patterns = []
        
        # Analyze file naming conventions
        file_paths = list(analysis_results.keys())
        
        # Check for consistent naming conventions
        naming_styles = {
            "snake_case": len([f for f in file_paths if "_" in Path(f).stem and not "-" in Path(f).stem]),
            "kebab_case": len([f for f in file_paths if "-" in Path(f).stem and not "_" in Path(f).stem]),
            "camelCase": len([f for f in file_paths if any(c.isupper() for c in Path(f).stem[1:])]),
            "PascalCase": len([f for f in file_paths if Path(f).stem[0].isupper()]),
        }
        
        total_files = len(file_paths)
        dominant_style = max(naming_styles.items(), key=lambda x: x[1])
        
        if dominant_style[1] < total_files * 0.8:  # Less than 80% consistency
            patterns.append(DetectedPattern(
                pattern_id="inconsistent_naming",
                pattern_type="naming_pattern",
                description=f"Inconsistent file naming: {dominant_style[0]} used in only {dominant_style[1]}/{total_files} files",
                files=[],
                confidence=0.9,
                severity="warning",
                suggestions=[
                    f"Standardize on {dominant_style[0]} naming convention",
                    "Create naming guidelines for the project"
                ],
                metadata={"naming_styles": naming_styles, "dominant": dominant_style}
            ))
        
        # Check for meaningful file names
        generic_names = ["util", "helper", "common", "misc", "temp", "test"]
        generic_files = [
            f for f in file_paths
            if any(generic in Path(f).stem.lower() for generic in generic_names)
        ]
        
        if generic_files:
            patterns.append(DetectedPattern(
                pattern_id="generic_file_names",
                pattern_type="naming_anti_pattern",
                description=f"{len(generic_files)} files have generic names",
                files=generic_files,
                confidence=0.8,
                severity="info",
                suggestions=[
                    "Use more descriptive file names",
                    "Avoid generic names like 'util' or 'helper'"
                ],
                metadata={"generic_names": generic_names}
            ))
        
        return patterns


class DocumentationPatternDetector:
    """Detects documentation patterns and gaps."""
    
    def detect_patterns(self, analysis_results: Dict[str, AnalysisResult]) -> List[DetectedPattern]:
        """Detect documentation patterns."""
        patterns = []
        
        # Find documentation files
        doc_files = [
            f for f, r in analysis_results.items()
            if r.language in ["markdown", "rst"] or Path(f).suffix.lower() in [".md", ".rst", ".txt"]
        ]
        
        code_files = [
            f for f, r in analysis_results.items()
            if r.language in ["python", "javascript", "typescript"] and f not in doc_files
        ]
        
        doc_ratio = len(doc_files) / len(code_files) if code_files else 0
        
        # Check documentation coverage
        if doc_ratio < 0.1:  # Less than 10% documentation
            patterns.append(DetectedPattern(
                pattern_id="low_documentation_coverage",
                pattern_type="documentation_anti_pattern",
                description=f"Low documentation ratio: {len(doc_files)} docs for {len(code_files)} code files",
                files=[],
                confidence=0.9,
                severity="warning",
                suggestions=[
                    "Add more documentation files",
                    "Create README files for major components",
                    "Document APIs and complex modules"
                ],
                metadata={"doc_ratio": doc_ratio, "doc_files": len(doc_files), "code_files": len(code_files)}
            ))
        
        # Check for README files
        readme_files = [f for f in doc_files if "readme" in Path(f).name.lower()]
        
        if not readme_files:
            patterns.append(DetectedPattern(
                pattern_id="missing_readme",
                pattern_type="documentation_gap",
                description="No README file found",
                files=[],
                confidence=1.0,
                severity="error",
                suggestions=[
                    "Create a README.md file",
                    "Document project purpose and setup instructions"
                ],
                metadata={}
            ))
        
        # Check for API documentation
        has_api_docs = any(
            "api" in Path(f).name.lower() or "docs" in Path(f).name.lower()
            for f in doc_files
        )
        
        has_code_with_exports = any(
            len(r.exports) > 0 for r in analysis_results.values()
            if r.language in ["python", "javascript", "typescript"]
        )
        
        if has_code_with_exports and not has_api_docs:
            patterns.append(DetectedPattern(
                pattern_id="missing_api_docs",
                pattern_type="documentation_gap",
                description="Code exports detected but no API documentation found",
                files=[],
                confidence=0.8,
                severity="info",
                suggestions=[
                    "Create API documentation",
                    "Document public interfaces and exports"
                ],
                metadata={"has_exports": has_code_with_exports}
            ))
        
        return patterns


class PatternDetector:
    """Main pattern detection engine."""
    
    def __init__(self):
        self.crossref_detector = CrossReferencePatternDetector()
        self.architectural_detector = ArchitecturalPatternDetector()
        self.dependency_detector = DependencyPatternDetector()
        self.naming_detector = NamingPatternDetector()
        self.documentation_detector = DocumentationPatternDetector()
        self.settings = get_settings()
    
    def detect_all_patterns(self, analysis_results: Dict[str, AnalysisResult]) -> PatternReport:
        """Detect all patterns in the analysis results."""
        logger.info("Starting pattern detection", file_count=len(analysis_results))
        
        all_patterns = []
        
        # Run all detectors
        all_patterns.extend(self.crossref_detector.detect_patterns(analysis_results))
        all_patterns.extend(self.architectural_detector.detect_patterns(analysis_results))
        all_patterns.extend(self.dependency_detector.detect_patterns(analysis_results))
        all_patterns.extend(self.naming_detector.detect_patterns(analysis_results))
        all_patterns.extend(self.documentation_detector.detect_patterns(analysis_results))
        
        # Count patterns by type
        pattern_counts = Counter(p.pattern_type for p in all_patterns)
        
        # Calculate quality score
        quality_score = self._calculate_quality_score(all_patterns, analysis_results)
        
        # Generate overall recommendations
        recommendations = self._generate_recommendations(all_patterns)
        
        report = PatternReport(
            patterns=all_patterns,
            pattern_counts=dict(pattern_counts),
            quality_score=quality_score,
            recommendations=recommendations
        )
        
        logger.info(
            "Pattern detection complete",
            total_patterns=len(all_patterns),
            quality_score=quality_score,
            recommendations=len(recommendations)
        )
        
        return report
    
    def _calculate_quality_score(self, patterns: List[DetectedPattern], analysis_results: Dict[str, AnalysisResult]) -> float:
        """Calculate overall quality score based on detected patterns."""
        base_score = 1.0
        
        # Deduct points for anti-patterns and issues
        severity_weights = {
            "critical": -0.3,
            "error": -0.2,
            "warning": -0.1,
            "info": -0.02
        }
        
        for pattern in patterns:
            if "anti_pattern" in pattern.pattern_type or "gap" in pattern.pattern_type:
                base_score += severity_weights.get(pattern.severity, 0) * pattern.confidence
        
        # Add points for good patterns
        good_patterns = [p for p in patterns if "pattern" in p.pattern_type and "anti_pattern" not in p.pattern_type]
        base_score += len(good_patterns) * 0.05
        
        # Cross-reference bonus
        crossref_patterns = [p for p in patterns if p.pattern_type.startswith("crossref")]
        if crossref_patterns:
            # Bonus for having cross-references
            base_score += 0.1
        
        return max(0.0, min(1.0, base_score))
    
    def _generate_recommendations(self, patterns: List[DetectedPattern]) -> List[str]:
        """Generate overall recommendations based on patterns."""
        recommendations = []
        
        # High priority issues
        critical_patterns = [p for p in patterns if p.severity in ["critical", "error"]]
        if critical_patterns:
            recommendations.append(f"Address {len(critical_patterns)} critical issues immediately")
        
        # Cross-reference improvements
        crossref_issues = [p for p in patterns if "crossref" in p.pattern_type and "anti_pattern" in p.pattern_type]
        if crossref_issues:
            recommendations.append("Implement systematic cross-referencing across the project")
        
        # Documentation improvements
        doc_issues = [p for p in patterns if "documentation" in p.pattern_type]
        if doc_issues:
            recommendations.append("Improve project documentation coverage and quality")
        
        # Architectural improvements
        arch_issues = [p for p in patterns if "architectural_anti_pattern" in p.pattern_type]
        if arch_issues:
            recommendations.append("Review and refactor architectural anti-patterns")
        
        # Naming consistency
        naming_issues = [p for p in patterns if "naming" in p.pattern_type]
        if naming_issues:
            recommendations.append("Standardize naming conventions across the project")
        
        return recommendations


# Convenience functions
async def detect_project_patterns(analysis_results: Dict[str, AnalysisResult]) -> PatternReport:
    """Detect all patterns in a project."""
    detector = PatternDetector()
    return detector.detect_all_patterns(analysis_results)


async def get_crossref_patterns(analysis_results: Dict[str, AnalysisResult]) -> List[DetectedPattern]:
    """Get only cross-reference patterns."""
    detector = CrossReferencePatternDetector()
    return detector.detect_patterns(analysis_results) 