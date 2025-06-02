"""Content Analysis Engine Demo

Demonstrates Step 1.4: Content Analysis & Pattern Detection capabilities
including cross-reference detection, relationship analysis, and pattern identification.
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.analyzer import (
    universal_analyzer,
    analyze_project,
    quick_file_analysis,
    AnalysisReport,
)
from src.scanner import orchestrator
from src.database.connection import init_db, close_db, db_manager
from src.database.models import Base
from src.utils.config import get_settings
import structlog

# Configure logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


class AnalysisDemo:
    """Demonstrates content analysis and pattern detection capabilities."""
    
    def __init__(self):
        self.settings = get_settings()
        
    async def run_demo(self, project_path: str) -> None:
        """Run the complete content analysis demo."""
        logger.info("🧠 Starting Universal Content Analysis Demo")
        print("=" * 60)
        print("🔗 Universal Cross-Reference Content Analysis Demo")
        print("   Step 1.4: Content Analysis & Pattern Detection")
        print("=" * 60)
        
        try:
            # Initialize database
            await self.setup_database()
            
            # Demo 1: Single file analysis
            await self.demo_single_file_analysis()
            
            # Demo 2: Full project content analysis
            project_id = await self.demo_project_analysis(project_path)
            
            # Demo 3: Relationship detection
            await self.demo_relationship_detection(project_id)
            
            # Demo 4: Pattern detection
            await self.demo_pattern_detection(project_id)
            
            # Demo 5: Cross-reference recommendations
            await self.demo_crossref_recommendations(project_id)
            
            # Demo 6: Comprehensive analysis report
            await self.demo_comprehensive_analysis(project_id)
            
        except Exception as e:
            logger.error("Demo failed", error=str(e))
            raise
        finally:
            await self.cleanup()
            print("\n✅ Content Analysis Demo completed successfully!")
    
    async def setup_database(self) -> None:
        """Initialize the database."""
        logger.info("🗄️ Setting up database...")
        
        try:
            # Initialize the db_manager
            await init_db()
            
            # Create tables
            async with db_manager.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            
            logger.info("✅ Database setup complete")
            
        except Exception as e:
            logger.error("Database setup failed", error=str(e))
            raise
    
    async def demo_single_file_analysis(self) -> None:
        """Demo single file content analysis."""
        print("\n📄 Demo 1: Single File Content Analysis")
        print("-" * 40)
        
        # Create a sample Python file for analysis
        sample_code = '''"""Sample module for analysis demo.

Cross-reference: This module should be read with `config.py` and `utils.py` 
for complete understanding of the system.
"""

import os
import json
from pathlib import Path
from typing import Dict, List, Optional

from .config import get_settings
from .utils import validate_input, process_data

class DataProcessor:
    """Main data processing class."""
    
    def __init__(self, config_path: Optional[str] = None):
        self.settings = get_settings()
        self.config_path = config_path
    
    def process_file(self, file_path: str) -> Dict[str, Any]:
        """Process a single file."""
        data = self.load_data(file_path)
        validated = validate_input(data)
        return process_data(validated)
    
    def load_data(self, path: str) -> Dict:
        """Load data from file."""
        with open(path, 'r') as f:
            return json.load(f)

def main():
    """Main function."""
    processor = DataProcessor()
    result = processor.process_file("data.json")
    print(result)

if __name__ == "__main__":
    main()
'''
        
        try:
            # Analyze the sample file
            result = await quick_file_analysis("sample_module.py", sample_code, "python")
            
            print(f"✓ File analyzed: {result.file_path}")
            print(f"✓ Language: {result.language}")
            print(f"✓ Imports found: {len(result.imports)}")
            print(f"✓ Exports found: {len(result.exports)}")
            print(f"✓ Dependencies: {len(result.dependencies)}")
            print(f"✓ Patterns detected: {len(result.patterns)}")
            print(f"✓ Cross-references: {len(result.cross_references)}")
            
            # Show detailed results
            if result.imports:
                print("\n📥 Imports detected:")
                for imp in result.imports[:5]:  # Show first 5
                    print(f"  • {imp.module} ({imp.import_type})")
            
            if result.exports:
                print("\n📤 Exports detected:")
                for exp in result.exports[:5]:
                    print(f"  • {exp}")
            
            if result.patterns:
                print("\n🔍 Patterns detected:")
                for pattern in result.patterns:
                    print(f"  • {pattern.pattern_type}: {pattern.content[:80]}...")
                    
            if result.cross_references:
                print("\n🔗 Cross-references detected:")
                for ref in result.cross_references:
                    print(f"  • {ref.source_file} → {ref.target_file} ({ref.reference_type})")
            
        except Exception as e:
            logger.error("Single file analysis failed", error=str(e))
            raise
        
        print("✅ Single file analysis complete")
    
    async def demo_project_analysis(self, project_path: str) -> int:
        """Demo full project content analysis."""
        print("\n📁 Demo 2: Full Project Content Analysis")
        print("-" * 40)
        
        try:
            # First, scan the project with the file scanner
            scanner_config = {
                "include_patterns": ["*.py", "*.md", "*.txt"],  # Scan Python, Markdown, and Text files
                "exclude_patterns": ["__pycache__/", "node_modules/", "dist/", "build/", ".git/", ".hg/", ".svn/"] # Simplified excludes
            }
            scanner = await orchestrator.add_project(
                project_name="analysis_demo_project",
                root_path=Path(project_path),
                enable_monitoring=False,
                enable_performance_management=False,
                config=scanner_config  # Pass the custom scanner configuration
            )
            
            print("🔍 Scanning project files...")
            stats = await scanner.scan_project()
            project_id = scanner.project_id
            
            print(f"✓ Project scanned: {stats.files_processed} files processed")
            print(f"✓ Project ID: {project_id}")
            
            # Now analyze the content
            print("🧠 Analyzing file content...")
            analysis_results = await universal_analyzer.content_analyzer.analyze_project_files(project_id)
            
            print(f"✓ Files analyzed: {len(analysis_results)}")
            
            # Show analysis summary
            total_imports = sum(len(r.imports) for r in analysis_results.values())
            total_exports = sum(len(r.exports) for r in analysis_results.values())
            total_patterns = sum(len(r.patterns) for r in analysis_results.values())
            
            print(f"✓ Total imports: {total_imports}")
            print(f"✓ Total exports: {total_exports}")  
            print(f"✓ Total patterns: {total_patterns}")
            
            # Show language breakdown
            languages = {}
            for result in analysis_results.values():
                if result.language:
                    languages[result.language] = languages.get(result.language, 0) + 1
            
            if languages:
                print("\n📊 Language breakdown:")
                for lang, count in sorted(languages.items(), key=lambda x: x[1], reverse=True):
                    print(f"  • {lang}: {count} files")
            
            return project_id
            
        except Exception as e:
            logger.error("Project analysis failed", error=str(e))
            raise
        
        print("✅ Project content analysis complete")
    
    async def demo_relationship_detection(self, project_id: int) -> None:
        """Demo relationship detection."""
        print("\n🔗 Demo 3: Relationship Detection")
        print("-" * 40)
        
        try:
            # Get content analysis results
            content_results = await universal_analyzer.content_analyzer.analyze_project_files(project_id)
            
            # Detect relationships
            print("🔍 Detecting file relationships...")
            relationships = universal_analyzer.relationship_analyzer.relationship_detector.detect_relationships(content_results)
            
            # Build dependency graph
            print("📊 Building dependency graph...")
            dependency_graph = universal_analyzer.relationship_analyzer.graph_builder.build_graph(relationships)
            
            print(f"✓ Relationships detected: {len(relationships)}")
            print(f"✓ Graph nodes: {len(dependency_graph.nodes)}")
            print(f"✓ Graph edges: {len(dependency_graph.edges)}")
            print(f"✓ Hub files: {len(dependency_graph.hub_files)}")
            print(f"✓ Cycles detected: {len(dependency_graph.cycles)}")
            print(f"✓ Clusters found: {len(dependency_graph.clusters)}")
            
            # Show relationship types
            if relationships:
                rel_types = {}
                for rel in relationships:
                    rel_types[rel.relationship_type] = rel_types.get(rel.relationship_type, 0) + 1
                
                print("\n📊 Relationship types:")
                for rel_type, count in sorted(rel_types.items(), key=lambda x: x[1], reverse=True):
                    print(f"  • {rel_type}: {count}")
            
            # Show hub files
            if dependency_graph.hub_files:
                print("\n🏛️ Hub files detected:")
                for hub in dependency_graph.hub_files[:5]:  # Show first 5
                    print(f"  • {hub}")
            
            # Show cycles if any
            if dependency_graph.cycles:
                print("\n🔄 Dependency cycles:")
                for cycle in dependency_graph.cycles[:3]:  # Show first 3
                    print(f"  • {' → '.join(cycle)}")
            
        except Exception as e:
            logger.error("Relationship detection failed", error=str(e))
            raise
        
        print("✅ Relationship detection complete")
    
    async def demo_pattern_detection(self, project_id: int) -> None:
        """Demo pattern detection."""
        print("\n🔍 Demo 4: Pattern Detection")
        print("-" * 40)
        
        try:
            # Get content analysis results
            content_results = await universal_analyzer.content_analyzer.analyze_project_files(project_id)
            
            # Detect patterns
            print("🔍 Detecting project patterns...")
            pattern_report = universal_analyzer.pattern_detector.detect_all_patterns(content_results)
            
            print(f"✓ Patterns detected: {len(pattern_report.patterns)}")
            print(f"✓ Quality score: {pattern_report.quality_score:.2f}")
            print(f"✓ Recommendations: {len(pattern_report.recommendations)}")
            
            # Show pattern counts by type
            if pattern_report.pattern_counts:
                print("\n📊 Patterns by type:")
                for pattern_type, count in sorted(pattern_report.pattern_counts.items(), key=lambda x: x[1], reverse=True):
                    print(f"  • {pattern_type}: {count}")
            
            # Show critical patterns
            critical_patterns = [p for p in pattern_report.patterns if p.severity in ["critical", "error"]]
            if critical_patterns:
                print("\n⚠️ Critical patterns:")
                for pattern in critical_patterns[:3]:  # Show first 3
                    print(f"  • {pattern.pattern_id}: {pattern.description}")
            
            # Show recommendations
            if pattern_report.recommendations:
                print("\n💡 Top recommendations:")
                for rec in pattern_report.recommendations[:5]:  # Show first 5
                    print(f"  • {rec}")
            
        except Exception as e:
            logger.error("Pattern detection failed", error=str(e))
            raise
        
        print("✅ Pattern detection complete")
    
    async def demo_crossref_recommendations(self, project_id: int) -> None:
        """Demo cross-reference recommendations."""
        print("\n💡 Demo 5: Cross-Reference Recommendations")
        print("-" * 40)
        
        try:
            # Get full analysis
            content_results = await universal_analyzer.content_analyzer.analyze_project_files(project_id)
            relationships, dependency_graph, recommendations = await universal_analyzer.relationship_analyzer.analyze_project_relationships(
                project_id, content_results
            )
            
            print(f"✓ Recommendations generated: {len(recommendations)}")
            
            # Group recommendations by priority
            priority_groups = {}
            for rec in recommendations:
                priority = rec.priority
                if priority not in priority_groups:
                    priority_groups[priority] = []
                priority_groups[priority].append(rec)
            
            # Show recommendations by priority
            for priority in ["critical", "high", "medium", "low"]:
                if priority in priority_groups:
                    recs = priority_groups[priority]
                    print(f"\n🔥 {priority.upper()} priority ({len(recs)} recommendations):")
                    for rec in recs[:3]:  # Show first 3 of each priority
                        print(f"  • {rec.source_file}:")
                        print(f"    → Add references to: {', '.join(rec.target_files[:3])}")
                        print(f"    → Reason: {rec.reasoning}")
                        print(f"    → Confidence: {rec.confidence:.2f}")
            
        except Exception as e:
            logger.error("Cross-reference recommendations failed", error=str(e))
            raise
        
        print("✅ Cross-reference recommendations complete")
    
    async def demo_comprehensive_analysis(self, project_id: int) -> None:
        """Demo comprehensive analysis report."""
        print("\n📊 Demo 6: Comprehensive Analysis Report")
        print("-" * 40)
        
        try:
            print("🧠 Running comprehensive analysis...")
            report = await analyze_project(
                project_id=project_id,
                include_patterns=True,
                include_relationships=True,
                include_recommendations=True
            )
            
            # Show summary
            summary = report.get_summary()
            print("✓ Analysis complete! Summary:")
            print(f"  • Files analyzed: {summary['files_analyzed']}")
            print(f"  • Total imports: {summary['total_imports']}")
            print(f"  • Total exports: {summary['total_exports']}")
            print(f"  • Dependencies: {summary['total_dependencies']}")
            print(f"  • Relationships: {summary['relationships']}")
            print(f"  • Hub files: {summary['hub_files']}")
            print(f"  • Clusters: {summary['clusters']}")
            print(f"  • Patterns: {summary['patterns']}")
            print(f"  • Quality score: {summary['quality_score']:.2f}")
            print(f"  • Recommendations: {summary['recommendations']}")
            
            # Cross-reference insights
            insights = report.get_crossref_insights()
            print(f"\n🔗 Cross-reference insights:")
            print(f"  • Cross-ref coverage: {insights['crossref_coverage']:.1%}")
            print(f"  • Files with cross-refs: {insights['files_with_crossrefs']}")
            print(f"  • Files without cross-refs: {insights['files_without_crossrefs']}")
            print(f"  • Hub files: {len(insights['hub_files'])}")
            
            # Export to dict for inspection
            full_report = report.export_to_dict()
            logger.info("Full analysis report generated", 
                       report_size=len(str(full_report)),
                       sections=list(full_report.keys()))
            
        except Exception as e:
            logger.error("Comprehensive analysis failed", error=str(e))
            raise
        
        print("✅ Comprehensive analysis complete")
    
    async def cleanup(self) -> None:
        """Cleanup resources."""
        logger.info("🧹 Cleaning up resources...")
        
        try:
            await orchestrator.cleanup_all()
            await close_db()
        except Exception as e:
            logger.error("Cleanup error", error=str(e))


async def main():
    """Main demo function."""
    # Get project path from command line or use current directory
    project_path = sys.argv[1] if len(sys.argv) > 1 else "."
    
    demo = AnalysisDemo()
    await demo.run_demo(project_path)


if __name__ == "__main__":
    print("🧠 Universal Cross-Reference Content Analysis Demo")
    print("Step 1.4: Content Analysis & Pattern Detection")
    print("=" * 50)
    print()
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n🛑 Demo interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Demo failed: {e}")
        sys.exit(1) 