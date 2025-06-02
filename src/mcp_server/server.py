#!/usr/bin/env python3
"""Universal Cross-Reference MCP Server

A Model Context Protocol server that provides cross-reference analysis capabilities
for any codebase using the proven cross-reference methodology.
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Resource,
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
)
from mcp.server.models import InitializationOptions
import structlog

from src.analyzer import universal_analyzer, analyze_project, quick_file_analysis
from src.scanner import orchestrator
from src.database.connection import init_db, close_db
from src.database.models import Base
from src.database.connection import db_manager
from src.utils.config import get_settings

logger = structlog.get_logger(__name__)

# Initialize MCP server
app = Server("universal-crossref")

# Global state
_initialized = False

async def initialize_server():
    """Initialize the cross-reference server"""
    global _initialized
    if _initialized:
        return
    
    try:
        logger.info("🔗 Initializing Universal Cross-Reference MCP Server")
        
        # Initialize database
        await init_db()
        
        # Create tables
        async with db_manager.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        _initialized = True
        logger.info("✅ Universal Cross-Reference MCP Server initialized successfully")
        
    except Exception as e:
        logger.error("❌ Failed to initialize server", error=str(e))
        raise

@app.list_resources()
async def list_resources() -> List[Resource]:
    """List available cross-reference resources"""
    await initialize_server()
    
    return [
        Resource(
            uri="crossref://analysis/help",
            name="Cross-Reference Analysis Help",
            description="Guide to using the Universal Cross-Reference system",
            mimeType="text/markdown"
        ),
        Resource(
            uri="crossref://analysis/capabilities",
            name="System Capabilities",
            description="Comprehensive list of cross-reference analysis capabilities",
            mimeType="text/markdown"
        )
    ]

@app.read_resource()
async def read_resource(uri: str) -> str:
    """Read cross-reference resources"""
    await initialize_server()
    
    if uri == "crossref://analysis/help":
        return """# Universal Cross-Reference Analysis Help

## 🎯 Available Tools

### `analyze_file`
Analyze a single file for cross-reference patterns, imports, and relationships.
- **Parameters**: `file_path` (string), `content` (optional string)
- **Returns**: Detailed analysis including imports, exports, patterns, cross-references

### `analyze_project`
Perform comprehensive analysis of an entire project.
- **Parameters**: `project_path` (string), `project_name` (optional string)
- **Returns**: Full project analysis with relationships, patterns, and recommendations

### `get_crossref_recommendations`
Get intelligent cross-reference recommendations for improving documentation.
- **Parameters**: `project_path` (string)
- **Returns**: Prioritized recommendations for adding cross-references

### `detect_hub_files`
Identify hub files (central documentation) in a project.
- **Parameters**: `project_path` (string)
- **Returns**: List of detected hub files with confidence scores

### `analyze_relationships`
Analyze relationships and dependencies between files.
- **Parameters**: `project_path` (string)
- **Returns**: Dependency graph, cycles, clusters, and relationship types

## 🚀 Quick Start

1. **Analyze a single file**: Use `analyze_file` with just the file path
2. **Analyze entire project**: Use `analyze_project` with your project directory
3. **Get recommendations**: Use `get_crossref_recommendations` for improvement suggestions

## 📋 Cross-Reference Methodology

This system implements the proven cross-reference methodology:
- **Hub file detection**: Identifies central documentation files
- **Mandatory reading patterns**: Detects existing cross-reference requirements
- **Quality scoring**: Measures documentation completeness
- **Intelligent recommendations**: Suggests improvements based on relationships

"""
    
    elif uri == "crossref://analysis/capabilities":
        return """# Universal Cross-Reference System Capabilities

## 🔍 Content Analysis
- **Multi-language support**: Python, JavaScript/TypeScript, Markdown, and more
- **Import/Export detection**: AST parsing for code, regex for others
- **Pattern recognition**: Cross-reference headers, hub files, documentation patterns
- **Quality assessment**: Comprehensive scoring based on coverage and patterns

## 🔗 Relationship Detection
- **Import relationships**: Direct and relative imports between files
- **Hub file mapping**: Central documentation and high-connectivity files
- **Semantic similarity**: Content-based relationships between files
- **Shared dependencies**: Files with common external dependencies
- **Explicit cross-references**: Existing documentation links and references

## 📊 Dependency Analysis
- **Dependency graphs**: Visual representation of file relationships
- **Cycle detection**: Identifies circular dependencies
- **Cluster analysis**: Groups of strongly related files
- **Depth mapping**: Distance from hub files

## 💡 Intelligent Recommendations
- **Missing hub references**: Files that should reference central documentation
- **Import-based suggestions**: Cross-references based on code dependencies
- **Semantic recommendations**: Suggestions based on content similarity
- **Quality improvements**: Actionable steps to improve documentation

## 🎯 Use Cases
- **Documentation audits**: Assess cross-reference coverage
- **Onboarding preparation**: Ensure complete understanding paths
- **Refactoring guidance**: Understand impact of changes
- **Quality assurance**: Maintain documentation standards

"""
    
    else:
        raise Exception(f"Unknown resource: {uri}")

@app.list_tools()
async def list_tools() -> List[Tool]:
    """List available cross-reference tools"""
    await initialize_server()
    
    return [
        Tool(
            name="analyze_file",
            description="Analyze a single file for cross-reference patterns, imports, exports, and relationships",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the file to analyze"
                    },
                    "content": {
                        "type": "string",
                        "description": "File content (optional, will read from file if not provided)"
                    }
                },
                "required": ["file_path"]
            }
        ),
        Tool(
            name="analyze_project",
            description="Perform comprehensive cross-reference analysis of an entire project",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": "Path to the project directory"
                    },
                    "project_name": {
                        "type": "string",
                        "description": "Name for the project (optional, uses directory name if not provided)"
                    }
                },
                "required": ["project_path"]
            }
        ),
        Tool(
            name="get_crossref_recommendations",
            description="Get intelligent recommendations for improving cross-reference coverage",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": "Path to the project directory"
                    }
                },
                "required": ["project_path"]
            }
        ),
        Tool(
            name="detect_hub_files",
            description="Identify hub files (central documentation) in a project",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": "Path to the project directory"
                    }
                },
                "required": ["project_path"]
            }
        ),
        Tool(
            name="analyze_relationships",
            description="Analyze relationships and dependencies between files in a project",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": "Path to the project directory"
                    }
                },
                "required": ["project_path"]
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle tool calls for cross-reference analysis"""
    await initialize_server()
    
    try:
        if name == "analyze_file":
            file_path = arguments["file_path"]
            content = arguments.get("content")
            
            # Read file content if not provided
            if content is None:
                file_path_obj = Path(file_path)
                if not file_path_obj.exists():
                    return [TextContent(type="text", text=f"❌ File not found: {file_path}")]
                
                try:
                    content = file_path_obj.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    try:
                        content = file_path_obj.read_text(encoding="latin-1")
                    except Exception as e:
                        return [TextContent(type="text", text=f"❌ Could not read file: {e}")]
            
            # Determine language from file extension
            language = None
            if file_path.endswith('.py'):
                language = 'python'
            elif file_path.endswith('.js') or file_path.endswith('.jsx'):
                language = 'javascript'
            elif file_path.endswith('.ts') or file_path.endswith('.tsx'):
                language = 'typescript'
            elif file_path.endswith('.md'):
                language = 'markdown'
            
            # Perform analysis
            result = await quick_file_analysis(file_path, content, language)
            
            # Format results
            response = f"""# 📄 File Analysis: {file_path}

## 📊 Summary
- **Language**: {result.language or 'Unknown'}
- **Imports**: {len(result.imports)}
- **Exports**: {len(result.exports)}
- **Dependencies**: {len(result.dependencies)}
- **Patterns**: {len(result.patterns)}
- **Cross-references**: {len(result.cross_references)}

## 📥 Imports Detected
"""
            if result.imports:
                for imp in result.imports:
                    response += f"- `{imp.module}` ({imp.import_type})\n"
            else:
                response += "No imports detected.\n"
            
            response += "\n## 📤 Exports Detected\n"
            if result.exports:
                for exp in result.exports:
                    response += f"- `{exp}`\n"
            else:
                response += "No exports detected.\n"
            
            response += "\n## 🔍 Patterns Detected\n"
            if result.patterns:
                for pattern in result.patterns:
                    response += f"- **{pattern.pattern_type}**: {pattern.content[:100]}...\n"
            else:
                response += "No patterns detected.\n"
            
            response += "\n## 🔗 Cross-references\n"
            if result.cross_references:
                for ref in result.cross_references:
                    response += f"- {ref.source_file} → {ref.target_file} ({ref.reference_type})\n"
            else:
                response += "No cross-references detected.\n"
            
            return [TextContent(type="text", text=response)]
        
        elif name == "analyze_project":
            project_path = arguments["project_path"]
            project_name = arguments.get("project_name", Path(project_path).name)
            
            if not Path(project_path).exists():
                return [TextContent(type="text", text=f"❌ Project path not found: {project_path}")]
            
            # Perform project analysis
            try:
                # Set up scanner
                scanner_config = {
                    "include_patterns": ["*.py", "*.js", "*.jsx", "*.ts", "*.tsx", "*.md", "*.txt"],
                    "exclude_patterns": ["__pycache__/", "node_modules/", "dist/", "build/", ".git/"]
                }
                
                scanner = await orchestrator.add_project(
                    project_name=project_name,
                    root_path=Path(project_path),
                    enable_monitoring=False,
                    enable_performance_management=False,
                    config=scanner_config
                )
                
                # Scan project
                await scanner.initialize()
                stats = await scanner.scan_project()
                project_id = scanner.project_id
                
                # Analyze content
                analysis_results = await universal_analyzer.content_analyzer.analyze_project_files(project_id)
                
                # Detect relationships
                relationships, dependency_graph, recommendations = await universal_analyzer.relationship_analyzer.analyze_project_relationships(
                    project_id, analysis_results
                )
                
                # Detect patterns
                pattern_report = universal_analyzer.pattern_detector.detect_all_patterns(analysis_results)
                
                # Format comprehensive report
                response = f"""# 🔗 Project Analysis: {project_name}

## 📊 Project Overview
- **Files Scanned**: {stats.files_processed}
- **Files Analyzed**: {len(analysis_results)}
- **Total Imports**: {sum(len(r.imports) for r in analysis_results.values())}
- **Total Exports**: {sum(len(r.exports) for r in analysis_results.values())}
- **Relationships**: {len(relationships)}
- **Hub Files**: {len(dependency_graph.hub_files)}
- **Quality Score**: {pattern_report.quality_score:.2f}

## 🏛️ Hub Files Detected
"""
                if dependency_graph.hub_files:
                    for hub in dependency_graph.hub_files[:10]:  # Show top 10
                        response += f"- `{hub}`\n"
                else:
                    response += "No hub files detected.\n"
                
                response += f"\n## 📊 Language Breakdown\n"
                languages = {}
                for result in analysis_results.values():
                    if result.language:
                        languages[result.language] = languages.get(result.language, 0) + 1
                
                for lang, count in sorted(languages.items(), key=lambda x: x[1], reverse=True):
                    response += f"- **{lang}**: {count} files\n"
                
                response += f"\n## 🔗 Relationship Types\n"
                rel_types = {}
                for rel in relationships:
                    rel_types[rel.relationship_type] = rel_types.get(rel.relationship_type, 0) + 1
                
                for rel_type, count in sorted(rel_types.items(), key=lambda x: x[1], reverse=True):
                    response += f"- **{rel_type}**: {count}\n"
                
                response += f"\n## 🔍 Patterns Detected\n"
                if pattern_report.pattern_counts:
                    for pattern_type, count in sorted(pattern_report.pattern_counts.items(), key=lambda x: x[1], reverse=True):
                        response += f"- **{pattern_type}**: {count}\n"
                else:
                    response += "No patterns detected.\n"
                
                response += f"\n## 💡 Top Recommendations\n"
                if recommendations:
                    for rec in recommendations[:5]:  # Show top 5
                        response += f"- **{rec.source_file}**: {rec.reasoning} (Priority: {rec.priority})\n"
                else:
                    response += "No recommendations generated.\n"
                
                # Cleanup
                await scanner.cleanup()
                
                return [TextContent(type="text", text=response)]
                
            except Exception as e:
                return [TextContent(type="text", text=f"❌ Analysis failed: {str(e)}")]
        
        elif name == "get_crossref_recommendations":
            project_path = arguments["project_path"]
            
            if not Path(project_path).exists():
                return [TextContent(type="text", text=f"❌ Project path not found: {project_path}")]
            
            try:
                # Quick project setup for recommendations
                scanner_config = {
                    "include_patterns": ["*.py", "*.js", "*.jsx", "*.ts", "*.tsx", "*.md", "*.txt"],
                    "exclude_patterns": ["__pycache__/", "node_modules/", "dist/", "build/", ".git/"]
                }
                
                scanner = await orchestrator.add_project(
                    project_name=f"recommendations_{Path(project_path).name}",
                    root_path=Path(project_path),
                    enable_monitoring=False,
                    enable_performance_management=False,
                    config=scanner_config
                )
                
                await scanner.initialize()
                await scanner.scan_project()
                
                analysis_results = await universal_analyzer.content_analyzer.analyze_project_files(scanner.project_id)
                relationships, dependency_graph, recommendations = await universal_analyzer.relationship_analyzer.analyze_project_relationships(
                    scanner.project_id, analysis_results
                )
                
                response = f"# 💡 Cross-Reference Recommendations\n\n"
                
                if recommendations:
                    # Group by priority
                    priority_groups = {}
                    for rec in recommendations:
                        if rec.priority not in priority_groups:
                            priority_groups[rec.priority] = []
                        priority_groups[rec.priority].append(rec)
                    
                    for priority in ["critical", "high", "medium", "low"]:
                        if priority in priority_groups:
                            recs = priority_groups[priority]
                            response += f"## 🔥 {priority.upper()} Priority ({len(recs)} recommendations)\n\n"
                            
                            for rec in recs[:5]:  # Show top 5 per priority
                                response += f"### `{rec.source_file}`\n"
                                response += f"- **Recommendation**: {rec.reasoning}\n"
                                response += f"- **Target Files**: {', '.join(rec.target_files[:3])}\n"
                                response += f"- **Confidence**: {rec.confidence:.2f}\n\n"
                else:
                    response += "No recommendations generated. Project may already have good cross-reference coverage.\n"
                
                await scanner.cleanup()
                return [TextContent(type="text", text=response)]
                
            except Exception as e:
                return [TextContent(type="text", text=f"❌ Recommendation generation failed: {str(e)}")]
        
        elif name == "detect_hub_files":
            project_path = arguments["project_path"]
            
            if not Path(project_path).exists():
                return [TextContent(type="text", text=f"❌ Project path not found: {project_path}")]
            
            try:
                scanner_config = {
                    "include_patterns": ["*.py", "*.js", "*.jsx", "*.ts", "*.tsx", "*.md", "*.txt"],
                    "exclude_patterns": ["__pycache__/", "node_modules/", "dist/", "build/", ".git/"]
                }
                
                scanner = await orchestrator.add_project(
                    project_name=f"hubdetect_{Path(project_path).name}",
                    root_path=Path(project_path),
                    enable_monitoring=False,
                    enable_performance_management=False,
                    config=scanner_config
                )
                
                await scanner.initialize()
                await scanner.scan_project()
                
                analysis_results = await universal_analyzer.content_analyzer.analyze_project_files(scanner.project_id)
                relationships, dependency_graph, _ = await universal_analyzer.relationship_analyzer.analyze_project_relationships(
                    scanner.project_id, analysis_results
                )
                
                response = f"# 🏛️ Hub Files Analysis\n\n"
                
                if dependency_graph.hub_files:
                    response += f"Found **{len(dependency_graph.hub_files)}** hub files:\n\n"
                    
                    # Calculate hub file scores based on in-degree
                    in_degree = {}
                    for rel in relationships:
                        in_degree[rel.target_file] = in_degree.get(rel.target_file, 0) + 1
                    
                    hub_scores = [(hub, in_degree.get(hub, 0)) for hub in dependency_graph.hub_files]
                    hub_scores.sort(key=lambda x: x[1], reverse=True)
                    
                    for hub, score in hub_scores:
                        response += f"## `{hub}`\n"
                        response += f"- **Connections**: {score}\n"
                        
                        # Check if it has hub patterns
                        if hub in analysis_results:
                            result = analysis_results[hub]
                            hub_patterns = [p for p in result.patterns if p.pattern_type in ["hub_file", "cross_ref_header"]]
                            if hub_patterns:
                                response += f"- **Hub Patterns**: {len(hub_patterns)} detected\n"
                            else:
                                response += f"- **Hub Patterns**: None detected\n"
                        response += "\n"
                else:
                    response += "No hub files detected. Consider creating central documentation files.\n"
                
                await scanner.cleanup()
                return [TextContent(type="text", text=response)]
                
            except Exception as e:
                return [TextContent(type="text", text=f"❌ Hub file detection failed: {str(e)}")]
        
        elif name == "analyze_relationships":
            project_path = arguments["project_path"]
            
            if not Path(project_path).exists():
                return [TextContent(type="text", text=f"❌ Project path not found: {project_path}")]
            
            try:
                scanner_config = {
                    "include_patterns": ["*.py", "*.js", "*.jsx", "*.ts", "*.tsx", "*.md", "*.txt"],
                    "exclude_patterns": ["__pycache__/", "node_modules/", "dist/", "build/", ".git/"]
                }
                
                scanner = await orchestrator.add_project(
                    project_name=f"relationships_{Path(project_path).name}",
                    root_path=Path(project_path),
                    enable_monitoring=False,
                    enable_performance_management=False,
                    config=scanner_config
                )
                
                await scanner.initialize()
                await scanner.scan_project()
                
                analysis_results = await universal_analyzer.content_analyzer.analyze_project_files(scanner.project_id)
                relationships, dependency_graph, _ = await universal_analyzer.relationship_analyzer.analyze_project_relationships(
                    scanner.project_id, analysis_results
                )
                
                response = f"# 🔗 Relationship Analysis\n\n"
                response += f"## 📊 Graph Overview\n"
                response += f"- **Nodes**: {len(dependency_graph.nodes)}\n"
                response += f"- **Edges**: {len(dependency_graph.edges)}\n"
                response += f"- **Hub Files**: {len(dependency_graph.hub_files)}\n"
                response += f"- **Cycles**: {len(dependency_graph.cycles)}\n"
                response += f"- **Clusters**: {len(dependency_graph.clusters)}\n\n"
                
                # Relationship types
                rel_types = {}
                for rel in relationships:
                    rel_types[rel.relationship_type] = rel_types.get(rel.relationship_type, 0) + 1
                
                response += f"## 🔗 Relationship Types\n"
                for rel_type, count in sorted(rel_types.items(), key=lambda x: x[1], reverse=True):
                    response += f"- **{rel_type}**: {count}\n"
                
                # Cycles
                if dependency_graph.cycles:
                    response += f"\n## 🔄 Dependency Cycles\n"
                    for i, cycle in enumerate(dependency_graph.cycles[:5], 1):
                        response += f"{i}. {' → '.join(cycle)}\n"
                else:
                    response += f"\n## ✅ No Dependency Cycles\nGreat! No circular dependencies detected.\n"
                
                # Clusters
                if dependency_graph.clusters:
                    response += f"\n## 🎯 File Clusters\n"
                    for i, cluster in enumerate(dependency_graph.clusters[:5], 1):
                        response += f"{i}. **Cluster {i}** ({len(cluster)} files): {', '.join(cluster[:3])}{'...' if len(cluster) > 3 else ''}\n"
                else:
                    response += f"\n## 📁 No Strong Clusters\nFiles are well-distributed without tight clustering.\n"
                
                await scanner.cleanup()
                return [TextContent(type="text", text=response)]
                
            except Exception as e:
                return [TextContent(type="text", text=f"❌ Relationship analysis failed: {str(e)}")]
        
        else:
            return [TextContent(type="text", text=f"❌ Unknown tool: {name}")]
    
    except Exception as e:
        logger.error("Tool execution failed", tool=name, error=str(e))
        return [TextContent(type="text", text=f"❌ Tool execution failed: {str(e)}")]

async def cleanup():
    """Cleanup server resources"""
    try:
        await orchestrator.cleanup_all()
        await close_db()
        logger.info("🧹 Server cleanup completed")
    except Exception as e:
        logger.error("Cleanup error", error=str(e))

async def main():
    """Main server entry point"""
    try:
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
        
        logger.info("🚀 Starting Universal Cross-Reference MCP Server")
        
        # Run the server with initialization options
        async with stdio_server() as streams:
            initialization_options = {
                "server_name": "universal-crossref",
                "server_version": "1.0.0"
            }
            await app.run(streams[0], streams[1], initialization_options)
            
    except KeyboardInterrupt:
        logger.info("👋 Server stopped by user")
    except Exception as e:
        logger.error("💥 Server error", error=str(e))
        raise
    finally:
        await cleanup()

if __name__ == "__main__":
    asyncio.run(main()) 