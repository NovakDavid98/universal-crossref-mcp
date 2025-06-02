#!/usr/bin/env python3
"""Quick Demo of Universal Cross-Reference Analysis

This script demonstrates the power of the cross-reference system
by analyzing any project you specify.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.analyzer import universal_analyzer, quick_file_analysis
from src.scanner import orchestrator
from src.database.connection import init_db, close_db, db_manager
from src.database.models import Base

async def quick_demo(project_path: str):
    """Run a quick demonstration of cross-reference analysis"""
    
    print("🔗 Universal Cross-Reference Analysis Demo")
    print("=" * 50)
    
    # Initialize
    print("🔧 Initializing system...")
    await init_db()
    async with db_manager.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    project_path = Path(project_path)
    if not project_path.exists():
        print(f"❌ Project path not found: {project_path}")
        return
    
    print(f"📂 Analyzing project: {project_path.name}")
    
    try:
        # Set up scanner
        scanner_config = {
            "include_patterns": ["*.py", "*.js", "*.jsx", "*.ts", "*.tsx", "*.md", "*.txt"],
            "exclude_patterns": ["__pycache__/", "node_modules/", "dist/", "build/", ".git/"]
        }
        
        scanner = await orchestrator.add_project(
            project_name=f"demo_{project_path.name}",
            root_path=project_path,
            enable_monitoring=False,
            enable_performance_management=False,
            config=scanner_config
        )
        
        # Scan and analyze
        print("🔍 Scanning files...")
        await scanner.initialize()
        stats = await scanner.scan_project()
        
        print(f"✅ Scanned {stats.files_processed} files")
        
        if stats.files_processed == 0:
            print("⚠️  No files found to analyze. Check include/exclude patterns.")
            await scanner.cleanup()
            return
        
        # Content analysis
        print("🧠 Analyzing content...")
        analysis_results = await universal_analyzer.content_analyzer.analyze_project_files(scanner.project_id)
        
        # Relationship analysis
        print("🔗 Detecting relationships...")
        relationships, dependency_graph, recommendations = await universal_analyzer.relationship_analyzer.analyze_project_relationships(
            scanner.project_id, analysis_results
        )
        
        # Pattern analysis
        print("🔍 Detecting patterns...")
        pattern_report = universal_analyzer.pattern_detector.detect_all_patterns(analysis_results)
        
        # Results
        print("\n📊 ANALYSIS RESULTS")
        print("=" * 30)
        
        print(f"📁 Files Analyzed: {len(analysis_results)}")
        print(f"🔗 Relationships: {len(relationships)}")
        print(f"🏛️  Hub Files: {len(dependency_graph.hub_files)}")
        print(f"📈 Quality Score: {pattern_report.quality_score:.2f}/10")
        print(f"💡 Recommendations: {len(recommendations)}")
        
        # Language breakdown
        languages = {}
        for result in analysis_results.values():
            if result.language:
                languages[result.language] = languages.get(result.language, 0) + 1
        
        if languages:
            print(f"\n🗣️  Languages Detected:")
            for lang, count in sorted(languages.items(), key=lambda x: x[1], reverse=True):
                print(f"   • {lang}: {count} files")
        
        # Hub files
        if dependency_graph.hub_files:
            print(f"\n🏛️  Hub Files:")
            for hub in dependency_graph.hub_files[:5]:
                print(f"   • {hub}")
            if len(dependency_graph.hub_files) > 5:
                print(f"   ... and {len(dependency_graph.hub_files) - 5} more")
        
        # Top recommendations
        if recommendations:
            print(f"\n💡 Top Recommendations:")
            for rec in recommendations[:3]:
                print(f"   • {rec.source_file}: {rec.reasoning}")
        
        # Patterns
        if pattern_report.pattern_counts:
            print(f"\n🔍 Patterns Detected:")
            for pattern_type, count in sorted(pattern_report.pattern_counts.items(), key=lambda x: x[1], reverse=True)[:5]:
                print(f"   • {pattern_type}: {count}")
        
        print(f"\n✅ Analysis complete! Use Cursor MCP integration for detailed analysis.")
        
        # Cleanup
        await scanner.cleanup()
        
    except Exception as e:
        print(f"❌ Analysis failed: {e}")
    
    finally:
        await close_db()

def main():
    """Main entry point"""
    if len(sys.argv) != 2:
        print("Usage: python quick_demo.py <project_path>")
        print("\nExample:")
        print("  python quick_demo.py /path/to/your/project")
        print("  python quick_demo.py .")
        return
    
    project_path = sys.argv[1]
    asyncio.run(quick_demo(project_path))

if __name__ == "__main__":
    main() 