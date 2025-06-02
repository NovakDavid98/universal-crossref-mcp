#!/usr/bin/env python3
"""Simple Universal Cross-Reference MCP Server using FastMCP"""

from mcp.server.fastmcp import FastMCP
from pathlib import Path
import json
import sys
import os
import re
from datetime import datetime
import time # For watchdog
import threading # For watchdog
from watchdog.observers import Observer # For watchdog
from watchdog.events import FileSystemEventHandler # For watchdog

# PDF Processing imports (Phase 2)
import PyPDF2
import pdfplumber
try:
    import pytesseract
    from pdf2image import convert_from_path
    from PIL import Image
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

# Async processing imports (Phase 5)
import asyncio
import aiofiles
from concurrent.futures import ThreadPoolExecutor
import uuid

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Initialize the MCP server
mcp = FastMCP("universal-crossref")

# In-memory storage for demonstration
projects = {}
current_project = None

# Async task tracking system (Phase 5)
active_tasks = {}
task_executor = ThreadPoolExecutor(max_workers=2)

class PDFExtractionTask:
    def __init__(self, task_id: str, pdf_path: str, params: dict):
        self.task_id = task_id
        self.pdf_path = pdf_path
        self.params = params
        self.status = "starting"
        self.progress = 0.0
        self.result = None
        self.error = None
        self.start_time = datetime.now()
        
    def update_status(self, status: str, progress: float = None):
        self.status = status
        if progress is not None:
            self.progress = progress
            
    def complete(self, result: dict):
        self.status = "completed"
        self.progress = 100.0
        self.result = result
        
    def fail(self, error: str):
        self.status = "failed"
        self.error = error

# --- Watchdog Implementation ---
active_observers = {}

class CrossRefEventHandler(FileSystemEventHandler):
    def __init__(self, project_path: Path, hub_file_name: str):
        self.project_path = project_path
        self.hub_file_name = hub_file_name
        self.hub_file_path = self.project_path / self.hub_file_name

    def _is_relevant_md_file(self, file_path_str: str) -> bool:
        file_path = Path(file_path_str)
        return file_path.suffix.lower() == ".md" and file_path.name != self.hub_file_name

    def on_created(self, event):
        if event.is_directory or not self._is_relevant_md_file(event.src_path):
            return
        created_file_path = Path(event.src_path)
        relative_path = str(created_file_path.relative_to(self.project_path))
        
        all_md_in_project = [str(p.relative_to(self.project_path)) for p in self.project_path.rglob("*.md") 
                               if p.name != self.hub_file_name and p != created_file_path and not p.is_dir()]
        
        add_crossref_header_result = add_crossref_header(str(created_file_path), self.hub_file_name, all_md_in_project[:2])

        update_result = update_hub_mandatory_reading(str(self.hub_file_path), new_files=[relative_path])

    def on_deleted(self, event):
        if event.is_directory or not self._is_relevant_md_file(event.src_path):
            if Path(event.src_path).name == self.hub_file_name:
                pass
            return
        
        deleted_file_path = Path(event.src_path)
        relative_path = str(deleted_file_path.relative_to(self.project_path))
        update_result = update_hub_mandatory_reading(str(self.hub_file_path), files_to_remove=[relative_path])

    def on_moved(self, event):
        if event.is_directory:
            return
        
        src_is_relevant = self._is_relevant_md_file(event.src_path)
        dest_is_relevant = self._is_relevant_md_file(event.dest_path)

        src_path_obj = Path(event.src_path)
        dest_path_obj = Path(event.dest_path)
        relative_src_path = str(src_path_obj.relative_to(self.project_path))
        relative_dest_path = str(dest_path_obj.relative_to(self.project_path))

        files_to_add_to_hub = []
        files_to_remove_from_hub = []

        if src_is_relevant:
            files_to_remove_from_hub.append(relative_src_path)
        
        if dest_is_relevant:
            files_to_add_to_hub.append(relative_dest_path)
            all_md_in_project = [str(p.relative_to(self.project_path)) for p in self.project_path.rglob("*.md") 
                                   if p.name != self.hub_file_name and p != dest_path_obj and not p.is_dir()]
            add_crossref_header(str(dest_path_obj), self.hub_file_name, all_md_in_project[:2])

        if files_to_add_to_hub or files_to_remove_from_hub:
            update_result = update_hub_mandatory_reading(str(self.hub_file_path), 
                                         new_files=files_to_add_to_hub, 
                                         files_to_remove=files_to_remove_from_hub)

@mcp.tool()
def start_auto_crossref_watcher(project_path: str, hub_file_name: str = "SYSTEM.md") -> dict:
    """Start automatic cross-reference monitoring for a project using watchdog."""
    try:
        project_path_obj = Path(project_path)
        if not project_path_obj.exists() or not project_path_obj.is_dir():
            return {"error": f"Project path not found or not a directory: {project_path}"}

        if project_path in active_observers:
            return {"warning": f"Watcher already active for project: {project_path}"}

        if current_project != project_path_obj.name or project_path_obj.name not in projects:
            scan_result = scan_project(project_path=project_path, project_name=project_path_obj.name)
            if scan_result.get("error"):
                 return {"error": f"Initial project scan failed: {scan_result['error']}. Cannot start watcher."}

        hub_file_abs_path = project_path_obj / hub_file_name
        if not hub_file_abs_path.exists():
            related_md_files = [str(p.relative_to(project_path_obj)) for p in project_path_obj.rglob("*.md") if p.name != hub_file_name and not p.is_dir()]
            create_hub_result = create_hub_file(
                file_path=str(hub_file_abs_path), 
                title=f"{project_path_obj.name} System Hub", 
                description=f"Central documentation hub for the {project_path_obj.name} project.",
                related_files=related_md_files
            )
            if create_hub_result.get("error"):
                return {"error": f"Failed to create initial hub file {hub_file_name}: {create_hub_result['error']}"}

        event_handler = CrossRefEventHandler(project_path_obj, hub_file_name)
        observer = Observer()
        observer.schedule(event_handler, str(project_path_obj), recursive=True)
        
        observer_thread = threading.Thread(target=observer.start, daemon=True)
        observer_thread.start()
        
        active_observers[project_path] = observer
        return {
            "success": True, 
            "project_path": project_path, 
            "status": "Watcher started",
            "hub_file": hub_file_name
        }

    except Exception as e:
        return {"error": f"Failed to start watcher: {str(e)}"}

@mcp.tool()
def stop_auto_crossref_watcher(project_path: str) -> dict:
    """Stop automatic cross-reference monitoring for a project."""
    try:
        if project_path in active_observers:
            observer = active_observers.pop(project_path)
            observer.stop()
            observer.join()
            return {"success": True, "project_path": project_path, "status": "Watcher stopped"}
        else:
            return {"warning": f"No active watcher found for project: {project_path}"}
    except Exception as e:
        return {"error": f"Failed to stop watcher: {str(e)}"}

@mcp.tool()
def get_tool_documentation() -> dict:
    """Get comprehensive documentation for all available MCP tools with usage instructions."""
    
    documentation = {
        "system_overview": {
            "name": "Universal Cross-Reference MCP Server",
            "version": "2.0.0 - Universal Content-Aware Edition",
            "purpose": "Automates intelligent cross-referencing methodology for any type of documentation or book content",
            "key_innovations": {
                "universal_genre_detection": "Automatically detects content type (fiction, technical, historical, etc.) and adapts analysis accordingly",
                "content_aware_cross_referencing": "Creates meaningful relationships based on actual content analysis, not just file proximity",
                "adaptive_analysis_strategies": "Different cross-referencing logic for different content types (characters for fiction, concepts for technical, etc.)",
                "intelligent_concept_extraction": "Genre-aware concept identification with semantic weighting",
                "named_entity_recognition": "Extracts people, places, organizations from content for better relationships"
            },
            "key_concepts": {
                "hub_file": "Central documentation file (e.g., SYSTEM.md) that lists ALL mandatory reading requirements",
                "cross_reference_headers": "Headers added to each file pointing back to hub and related files with intelligent reasoning",
                "mandatory_reading": "The principle that readers MUST read all linked files for complete understanding",
                "auto_watcher": "Background monitoring that automatically updates cross-references when files change",
                "content_aware_analysis": "Deep content understanding that goes beyond simple file relationships",
                "genre_adaptive_logic": "Different cross-referencing strategies based on detected content type"
            }
        },
        
        "universal_content_analysis": {
            "supported_genres": {
                "fiction": {
                    "detection_keywords": ["novel", "story", "character", "plot", "romance", "mystery", "fantasy", "drama"],
                    "analysis_features": ["Character relationship mapping", "Plot thread connections", "Dialogue density analysis", "Setting relationships"],
                    "cross_reference_strategy": "Links based on shared characters, similar themes, narrative connections",
                    "relationship_types": ["narrative_connection", "character_relationship", "thematic_similarity"]
                },
                "philosophical": {
                    "detection_keywords": ["philosophy", "metaphysics", "consciousness", "existence", "reality", "truth"],
                    "analysis_features": ["Concept density analysis", "Metaphysical theme extraction", "Philosophical argument mapping"],
                    "cross_reference_strategy": "Links based on shared philosophical concepts, building arguments, related ideas",
                    "relationship_types": ["conceptual_dependency", "philosophical_connection", "idea_progression"]
                },
                "scientific": {
                    "detection_keywords": ["science", "research", "experiment", "theory", "physics", "chemistry", "biology"],
                    "analysis_features": ["Theory dependency analysis", "Research methodology connections", "Scientific concept hierarchies"],
                    "cross_reference_strategy": "Links based on theoretical foundations, experimental relationships, concept building",
                    "relationship_types": ["theoretical_dependency", "experimental_connection", "concept_hierarchy"]
                },
                "technical": {
                    "detection_keywords": ["programming", "software", "computer", "algorithm", "code", "system", "technical"],
                    "analysis_features": ["Procedure step detection", "Code density analysis", "Technical dependency mapping"],
                    "cross_reference_strategy": "Links based on prerequisite knowledge, procedure dependencies, system relationships",
                    "relationship_types": ["prerequisite_dependency", "procedural_connection", "system_relationship"]
                },
                "historical": {
                    "detection_keywords": ["history", "historical", "century", "war", "empire", "civilization", "ancient"],
                    "analysis_features": ["Temporal reference extraction", "Historical figure identification", "Event chronology mapping"],
                    "cross_reference_strategy": "Links based on chronological relationships, shared figures, cause-effect chains",
                    "relationship_types": ["chronological_relationship", "causal_connection", "temporal_proximity"]
                },
                "business": {
                    "detection_keywords": ["business", "management", "strategy", "leadership", "marketing", "sales", "profit"],
                    "analysis_features": ["Strategy term detection", "Quantitative content analysis", "Business concept mapping"],
                    "cross_reference_strategy": "Links based on strategic connections, case study relationships, methodology similarities",
                    "relationship_types": ["strategic_connection", "methodology_relationship", "case_study_link"]
                },
                "selfhelp": {
                    "detection_keywords": ["self-help", "improve", "success", "habit", "motivation", "achievement", "personal"],
                    "analysis_features": ["Goal progression tracking", "Habit building sequences", "Improvement methodology mapping"],
                    "cross_reference_strategy": "Links based on goal relationships, habit building progressions, improvement sequences",
                    "relationship_types": ["goal_progression", "habit_sequence", "improvement_chain"]
                },
                "medical": {
                    "detection_keywords": ["medical", "health", "medicine", "disease", "treatment", "patient", "clinical"],
                    "analysis_features": ["Treatment protocol analysis", "Symptom relationship mapping", "Medical research connections"],
                    "cross_reference_strategy": "Links based on treatment protocols, symptom relationships, research connections",
                    "relationship_types": ["treatment_protocol", "symptom_relationship", "clinical_connection"]
                },
                "religious": {
                    "detection_keywords": ["religion", "spiritual", "faith", "god", "prayer", "scripture", "sacred"],
                    "analysis_features": ["Scriptural reference detection", "Doctrinal connection mapping", "Spiritual theme analysis"],
                    "cross_reference_strategy": "Links based on scriptural references, doctrinal connections, spiritual themes",
                    "relationship_types": ["scriptural_reference", "doctrinal_connection", "spiritual_theme"]
                }
            },
            "analysis_methods": {
                "concept_extraction": "TF-IDF weighted concept identification with genre-specific boosting",
                "named_entity_recognition": "Heuristic-based extraction of people, places, organizations",
                "similarity_calculation": "Multi-factor similarity using Jaccard similarity, weighted concept overlap, and genre-specific bonuses",
                "relationship_reasoning": "Human-readable explanations for why chapters are related",
                "quality_assessment": "Content quality scoring based on readability, concept density, and coherence"
            }
        },
        
        "workflow_guide": {
            "new_project_setup": [
                "1. Use create_hub_file to create your central hub file (or let start_auto_crossref_watcher create one)",
                "2. Use start_auto_crossref_watcher to enable automatic cross-reference management",
                "3. Create your Markdown files - they'll be automatically cross-referenced",
                "4. The hub file will automatically update as you add/remove/rename files"
            ],
            "existing_project_setup": [
                "1. Use scan_project to analyze your current project structure",
                "2. Use implement_crossref_methodology to apply cross-referencing to all existing files",
                "3. Use start_auto_crossref_watcher for ongoing automatic management"
            ],
            "pdf_book_processing": [
                "1. Use extract_pdf_to_markdown for small-medium PDFs (< 500KB)",
                "2. Use extract_pdf_to_markdown_async for large PDFs to avoid timeouts",
                "3. System automatically detects book genre and adapts cross-referencing strategy",
                "4. Generated files include intelligent content-based relationships",
                "5. Hub file provides genre-appropriate navigation and reading guidance"
            ]
        },
        
        "tools": {
            "analyze_file": {
                "description": "Analyze a single file for cross-reference patterns, imports, and dependencies",
                "parameters": {
                    "file_path": {"required": True, "type": "string", "description": "Path to the file to analyze"}
                },
                "returns": {
                    "file": "File path",
                    "lines": "Number of lines",
                    "size_bytes": "File size",
                    "language": "Detected programming language",
                    "imports": "List of import statements",
                    "exports": "List of export statements", 
                    "cross_references": "Detected cross-reference patterns"
                },
                "use_cases": ["Understanding file dependencies", "Checking existing cross-references", "File analysis before modification"],
                "example": "analyze_file('/path/to/document.md')"
            },
            
            "scan_project": {
                "description": "Scan a project directory for files and provide basic analysis statistics",
                "parameters": {
                    "project_path": {"required": True, "type": "string", "description": "Path to the project directory"},
                    "project_name": {"required": False, "type": "string", "description": "Name for the project (defaults to directory name)"}
                },
                "returns": {
                    "project_name": "Project identifier",
                    "files_found": "Total number of relevant files",
                    "languages": "Programming languages detected",
                    "total_lines": "Total lines of code/documentation",
                    "sample_files": "List of example files found"
                },
                "use_cases": ["Initial project assessment", "Understanding project structure", "Prerequisites for other tools"],
                "example": "scan_project('/path/to/project', 'MyProject')"
            },
            
            "get_crossref_recommendations": {
                "description": "Get recommendations for improving cross-reference coverage in a project",
                "parameters": {
                    "project_name": {"required": False, "type": "string", "description": "Project name (uses current project if not specified)"}
                },
                "returns": {
                    "recommendations": "List of suggested improvements with priority levels",
                    "types": "hub_file, documentation coverage suggestions"
                },
                "use_cases": ["Project improvement planning", "Documentation coverage assessment", "Identifying missing hub files"],
                "example": "get_crossref_recommendations('MyProject')",
                "note": "Run scan_project first to establish current project context"
            },
            
            "create_hub_file": {
                "description": "Create a new hub file with mandatory cross-reference reading requirements in standard format",
                "parameters": {
                    "file_path": {"required": True, "type": "string", "description": "Path where the hub file should be created"},
                    "title": {"required": True, "type": "string", "description": "Title for the hub file"},
                    "description": {"required": True, "type": "string", "description": "Description of the project/system"},
                    "related_files": {"required": False, "type": "list", "description": "List of initial files to cross-reference"}
                },
                "returns": {
                    "file_created": "Path to created hub file",
                    "related_files": "List of files linked in the hub",
                    "success": "Boolean indicating creation success"
                },
                "use_cases": ["Starting new project documentation", "Creating central documentation hub", "Establishing cross-reference methodology"],
                "example": "create_hub_file('/project/SYSTEM.md', 'My System Hub', 'Central system documentation', ['readme.md', 'api.md'])",
                "notes": ["File must not already exist", "Creates comprehensive hub with mandatory reading sections"]
            },
            
            "add_crossref_header": {
                "description": "Add cross-reference header to an existing file in standard format",
                "parameters": {
                    "file_path": {"required": True, "type": "string", "description": "Path to the file to modify"},
                    "hub_file": {"required": True, "type": "string", "description": "Name of the hub file to reference"},
                    "related_files": {"required": False, "type": "list", "description": "List of other related files to mention"}
                },
                "returns": {
                    "file_updated": "Path to updated file",
                    "status": "Update status (success, already_exists, etc.)",
                    "summary": "Description of changes made"
                },
                "use_cases": ["Adding cross-references to existing files", "Ensuring file follows methodology", "Manual header management"],
                "example": "add_crossref_header('/project/feature.md', 'SYSTEM.md', ['api.md', 'config.md'])",
                "notes": ["Detects existing headers and avoids duplicates", "Preserves existing file structure"]
            },
            
            "update_hub_mandatory_reading": {
                "description": "Update the mandatory reading list in a hub file by adding or removing files",
                "parameters": {
                    "hub_file_path": {"required": True, "type": "string", "description": "Path to the hub file to update"},
                    "new_files": {"required": False, "type": "list", "description": "List of files to add to mandatory reading"},
                    "files_to_remove": {"required": False, "type": "list", "description": "List of files to remove from mandatory reading"}
                },
                "returns": {
                    "hub_file_updated": "Path to updated hub file",
                    "files_added": "List of files that were added",
                    "files_removed": "List of files that were removed",
                    "success": "Boolean indicating update success"
                },
                "use_cases": ["Manual hub file maintenance", "Correcting cross-reference links", "Managing large documentation changes"],
                "example": "update_hub_mandatory_reading('/project/SYSTEM.md', ['new_feature.md'], ['old_deprecated.md'])",
                "notes": ["Updates both mandatory reading section and network diagram", "Handles file addition and removal in single operation"]
            },
            
            "implement_crossref_methodology": {
                "description": "Apply the complete cross-reference methodology to an entire project in one operation",
                "parameters": {
                    "project_path": {"required": True, "type": "string", "description": "Path to the project directory"},
                    "hub_file_name": {"required": False, "type": "string", "description": "Name for hub file (default: SYSTEM.md)"},
                    "project_title": {"required": False, "type": "string", "description": "Title for the project documentation"}
                },
                "returns": {
                    "operations": "Detailed list of all operations performed",
                    "operations_completed": "Number of successful operations",
                    "markdown_files_processed": "Number of files that received headers",
                    "success": "Overall success status"
                },
                "use_cases": ["Retrofitting existing projects", "Bulk application of methodology", "One-time setup for established projects"],
                "example": "implement_crossref_methodology('/existing/project', 'README.md', 'My Existing Project')",
                "notes": ["Creates or updates hub file", "Adds headers to all existing Markdown files", "Comprehensive but potentially disruptive operation"]
            },
            
            "start_auto_crossref_watcher": {
                "description": "Start automatic cross-reference monitoring using file system watcher",
                "parameters": {
                    "project_path": {"required": True, "type": "string", "description": "Path to project directory to monitor"},
                    "hub_file_name": {"required": False, "type": "string", "description": "Name of hub file (default: SYSTEM.md)"}
                },
                "returns": {
                    "status": "Watcher start status",
                    "project_path": "Path being monitored",
                    "hub_file": "Hub file being managed",
                    "success": "Boolean indicating successful start"
                },
                "use_cases": ["Enabling automatic cross-reference management", "Ongoing project maintenance", "Hands-off documentation management"],
                "example": "start_auto_crossref_watcher('/my/project', 'hub.md')",
                "notes": [
                    "Monitors file creation, deletion, and movement events",
                    "Automatically updates hub file when files change",
                    "Adds headers to newly created Markdown files",
                    "Creates hub file if it doesn't exist",
                    "Runs in background until stopped"
                ],
                "automatic_behaviors": {
                    "on_file_created": "Adds cross-reference header, updates hub mandatory reading list and network diagram",
                    "on_file_deleted": "Removes file from hub mandatory reading list and network diagram", 
                    "on_file_moved": "Updates hub file links from old name to new name, ensures moved file has header"
                }
            },
            
            "stop_auto_crossref_watcher": {
                "description": "Stop automatic cross-reference monitoring for a project",
                "parameters": {
                    "project_path": {"required": True, "type": "string", "description": "Path to project directory to stop monitoring"}
                },
                "returns": {
                    "status": "Watcher stop status",
                    "project_path": "Path no longer being monitored",
                    "success": "Boolean indicating successful stop"
                },
                "use_cases": ["Disabling automatic management", "Preparing for manual editing", "Cleaning up watchers"],
                "example": "stop_auto_crossref_watcher('/my/project')",
                "notes": ["Safe to call even if no watcher is active", "Cleanly shuts down background monitoring"]
            },
            
            "extract_pdf_to_markdown": {
                "description": "Extract PDF content to cross-referenced markdown files with universal intelligent cross-referencing for any book type",
                "parameters": {
                    "pdf_path": {"required": True, "type": "string", "description": "Path to the PDF file to extract"},
                    "output_dir": {"required": False, "type": "string", "description": "Output directory for extracted files (defaults to same as PDF location)"},
                    "max_chunks": {"required": False, "type": "integer", "description": "Maximum number of chunks to create (default: 20)"},
                    "extraction_strategy": {"required": False, "type": "string", "description": "Extraction strategy (default: 'auto')"},
                    "create_hub": {"required": False, "type": "boolean", "description": "Create hub file if true (default: True)"}
                },
                "returns": {
                    "success": "Boolean indicating success",
                    "pdf_processed": "Path to processed PDF",
                    "output_directory": "Path to output directory",
                    "chunks_created": "Number of chunks created",
                    "files_generated": "List of generated file paths",
                    "hub_file": "Path to created hub file",
                    "extraction_quality": "Extraction quality score (0-1)",
                    "extraction_strategy": "Used extraction strategy (PyPDF2, pdfplumber, OCR)",
                    "cross_reference_headers_added": "Number of cross-reference headers added",
                    "detected_genres": "Automatically detected book genres with confidence scores",
                    "intelligent_cross_references": "Number of content-aware cross-references created",
                    "content_analysis": "Summary of genre-specific analysis performed",
                    "summary": "Summary of operation"
                },
                "use_cases": [
                    "Extracting any type of PDF book or document", 
                    "Creating intelligent cross-referenced knowledge bases", 
                    "Converting books to navigable markdown with content-aware relationships",
                    "Academic research document processing",
                    "Business document conversion with strategic relationship mapping"
                ],
                "universal_capabilities": {
                    "fiction": "Character relationships, plot connections, thematic links, dialogue analysis",
                    "non_fiction": "Conceptual dependencies, topic relationships, learning progression mapping",
                    "technical": "Procedure dependencies, concept building chains, system relationships",
                    "historical": "Chronological relationships, figure connections, cause-effect chains",
                    "business": "Strategic connections, case study links, methodology relationships",
                    "scientific": "Theory dependencies, research connections, concept hierarchies",
                    "self_help": "Goal relationships, habit building sequences, improvement progressions",
                    "medical": "Treatment protocols, symptom relationships, research connections",
                    "religious": "Scriptural references, doctrinal connections, spiritual themes",
                    "philosophical": "Concept dependencies, argument progressions, metaphysical connections"
                },
                "content_analysis_features": {
                    "automatic_genre_detection": "Analyzes content to determine primary genre(s) and adapts processing accordingly",
                    "concept_extraction": "TF-IDF weighted extraction of key concepts with genre-specific boosting",
                    "named_entity_recognition": "Identifies people, places, organizations relevant to the content",
                    "similarity_scoring": "Multi-factor similarity calculation including conceptual overlap and genre-specific features",
                    "relationship_reasoning": "Generates human-readable explanations for why chapters are related",
                    "quality_assessment": "Scores extraction quality based on readability, concept density, and coherence"
                },
                "example": "extract_pdf_to_markdown('/path/to/any_book.pdf', '/output/directory', 20, 'auto', True)",
                "notes": [
                    "🎯 Automatically detects book genre and adapts cross-referencing strategy accordingly",
                    "🧠 Creates meaningful content-based relationships, not just sequential file links",
                    "📚 Works equally well with novels, textbooks, manuals, histories, biographies, and more",
                    "🔗 Generates genre-specific cross-reference reasons and relationship types",
                    "⚡ Uses multiple extraction strategies (PyPDF2, pdfplumber, OCR) for best results",
                    "📊 Provides detailed content analysis and quality scoring",
                    "🎨 Creates beautiful, navigable hub files with genre-appropriate organization"
                ]
            },

            "extract_pdf_to_markdown_async": {
                "description": "Start asynchronous PDF extraction with universal content-aware cross-referencing for any book type - ideal for large documents",
                "parameters": {
                    "pdf_path": {"required": True, "type": "string", "description": "Path to the PDF file to extract"},
                    "output_dir": {"required": False, "type": "string", "description": "Output directory for extracted files (defaults to same as PDF location)"},
                    "max_chunks": {"required": False, "type": "integer", "description": "Maximum number of chunks to create (default: 50)"},
                    "create_hub": {"required": False, "type": "boolean", "description": "Create hub file with universal cross-reference methodology (default: True)"}
                },
                "returns": {
                    "success": "Boolean indicating successful task start",
                    "task_id": "Unique identifier for tracking the extraction task",
                    "status": "Task status ('started')",
                    "pdf_path": "Path to the PDF being processed",
                    "estimated_time": "Estimated processing time based on file size",
                    "instructions": "How to monitor progress using check_pdf_extraction_status",
                    "message": "Confirmation message about background processing with automatic genre detection"
                },
                "use_cases": [
                    "Processing large PDFs of any genre without blocking the system", 
                    "Background extraction with automatic genre detection and appropriate cross-referencing", 
                    "Handling multiple diverse PDF extractions concurrently",
                    "Academic textbook processing",
                    "Large technical manual conversion"
                ],
                "processing_phases": {
                    "starting_extraction": "0-10% - Initializing and validating PDF file",
                    "extracting_text": "10-25% - Running multiple extraction strategies for best quality",
                    "analyzing_content": "25-55% - Detecting genre and analyzing content structure",
                    "generating_cross_references": "55-75% - Creating intelligent content-based relationships",
                    "creating_files": "75-90% - Writing markdown files with cross-reference headers",
                    "creating_hub": "90-100% - Generating comprehensive hub file with navigation"
                },
                "example": "extract_pdf_to_markdown_async('/path/to/large_book.pdf', '/output/directory', 50, True)",
                "notes": [
                    "🔄 Runs in background with real-time progress tracking",
                    "🎯 Adapts cross-referencing strategy based on detected content type",
                    "📚 Works with novels, textbooks, manuals, histories, biographies, and more",
                    "🏠 Creates comprehensive hub file with genre-appropriate navigation",
                    "⚡ Ideal for any book type - system automatically adapts its analysis approach",
                    "📊 Provides detailed progress updates and final content analysis",
                    "🛡️ Handles timeouts and large files gracefully"
                ]
            },

            "check_pdf_extraction_status": {
                "description": "Monitor the progress and results of an ongoing asynchronous PDF extraction task with detailed content analysis",
                "parameters": {
                    "task_id": {"required": True, "type": "string", "description": "Task ID returned by extract_pdf_to_markdown_async"}
                },
                "returns": {
                    "task_id": "The task identifier",
                    "status": "Current status (starting_extraction, extracting_text, analyzing_content, generating_cross_references, creating_files, creating_hub, completed, failed)",
                    "progress": "Progress percentage (0-100)",
                    "pdf_path": "Path to the PDF being processed",
                    "start_time": "When the task started",
                    "elapsed_time": "How long the task has been running",
                    "result": "Complete extraction results including content analysis (only when status is 'completed')",
                    "error": "Error details (only when status is 'failed')"
                },
                "status_meanings": {
                    "starting_extraction": "Initializing task and validating inputs",
                    "extracting_text": "Running multiple extraction strategies (PyPDF2, pdfplumber, OCR)",
                    "analyzing_content": "Detecting genre and analyzing content structure with AI",
                    "generating_cross_references": "Creating intelligent content-based relationships",
                    "creating_files": "Writing markdown files with cross-reference headers",
                    "creating_hub": "Generating comprehensive hub file with navigation",
                    "completed": "All processing finished successfully",
                    "failed": "An error occurred during processing"
                },
                "use_cases": ["Monitoring async PDF extraction progress", "Getting results when extraction completes", "Troubleshooting failed extractions"],
                "example": "check_pdf_extraction_status('abc123-def456-789')",
                "notes": [
                    "📊 Provides real-time progress updates with detailed status information",
                    "🎯 Shows genre detection and content analysis progress",
                    "✅ Task is automatically cleaned up after returning final results",
                    "🔄 Call periodically to monitor progress (recommended every 10-30 seconds)",
                    "📋 Returns complete extraction results including content analysis when finished"
                ]
            },

            "list_pdf_extraction_tasks": {
                "description": "List all currently active PDF extraction tasks with their status and content analysis progress",
                "parameters": {
                    "random_string": {"required": True, "type": "string", "description": "Dummy parameter (use any string)"}
                },
                "returns": {
                    "success": "Boolean indicating successful listing",
                    "active_tasks": "Number of currently running tasks",
                    "tasks": "Array of task objects with id, status, progress, pdf_path, start_time, and detected_genre"
                },
                "use_cases": ["Monitoring multiple concurrent extractions", "Checking system load", "Debugging extraction queue", "Managing batch PDF processing"],
                "example": "list_pdf_extraction_tasks('show_tasks')",
                "notes": [
                    "📋 Only shows currently running or pending tasks",
                    "🗑️ Completed and failed tasks are automatically removed from the list",
                    "🔄 Useful for managing multiple concurrent PDF extractions",
                    "📊 Shows progress and genre detection status for each task"
                ]
            }
        },
        
        "best_practices": {
            "recommended_workflow": [
                "1. Start with scan_project to understand current state",
                "2. For new projects: create_hub_file + start_auto_crossref_watcher",
                "3. For existing projects: implement_crossref_methodology + start_auto_crossref_watcher", 
                "4. Use get_crossref_recommendations periodically for improvements",
                "5. Use manual tools (add_crossref_header, update_hub_mandatory_reading) for fine-tuning",
                "6. For PDF processing: Use extract_pdf_to_markdown for small files, extract_pdf_to_markdown_async for large files"
            ],
            "file_naming": [
                "Use descriptive hub file names (SYSTEM.md, README.md, docs_hub.md)",
                "Keep Markdown file names consistent and descriptive",
                "Avoid special characters that might break cross-reference parsing"
            ],
            "project_organization": [
                "Place hub file at project root or in main docs directory",
                "Keep related Markdown files in same directory tree as hub",
                "Use consistent directory structure for multi-module projects"
            ],
            "pdf_extraction_guidelines": [
                "Use synchronous extraction for PDFs < 500KB or < 20 pages",
                "Use asynchronous extraction for larger PDFs to avoid timeouts",
                "Let the system auto-detect genre and create appropriate cross-references",
                "Review extraction quality scores - values > 0.8 indicate excellent extraction",
                "Trust the content-aware analysis - it creates better relationships than manual linking",
                "Use generated hub files as navigation starting points"
            ],
            "content_analysis_optimization": [
                "Provide clear, descriptive PDF titles for better genre detection",
                "For mixed-genre documents, the system will detect primary genre and adapt",
                "Review generated cross-reference reasons to understand content relationships",
                "Use the hub file's content analysis summary to understand document structure",
                "For technical documents, ensure clear procedure/step formatting for better analysis"
            ]
        },
        
        "troubleshooting": {
            "common_issues": {
                "watcher_not_updating": "Ensure watcher is started and monitoring correct directory path",
                "duplicate_headers": "Use add_crossref_header - it now detects and avoids duplicates",
                "hub_file_not_found": "Verify hub file name and path, or let start_auto_crossref_watcher create one",
                "json_parsing_errors": "Avoid debug print statements in server code - use PM2 logs for debugging",
                "pdf_extraction_timeout": "Use extract_pdf_to_markdown_async for large PDFs instead of synchronous version",
                "low_extraction_quality": "Try different extraction strategies or check if PDF is scanned (OCR required)",
                "async_task_not_found": "Task may have completed and been cleaned up - check task status immediately after completion",
                "poor_cross_references": "Check if content has clear structure - system works best with well-structured text",
                "genre_detection_incorrect": "For mixed-genre documents, system picks dominant genre - this is usually correct",
                "missing_relationships": "System only creates high-quality relationships (similarity > 0.2) - low similarity indicates genuinely unrelated content"
            },
            "performance_optimization": [
                "For large PDF batches, use async extraction to prevent system overload",
                "Monitor active task count to avoid overwhelming the system",
                "Quality scores below 0.5 may indicate scanned PDFs requiring OCR",
                "Genre detection accuracy improves with longer, more structured content"
            ]
        }
    }
    
    return {
        "success": True,
        "documentation": documentation,
        "total_tools": 12,
        "server_version": "2.0.0 - Universal Content-Aware Edition",
        "major_features": [
            "Universal genre detection for 9+ content types",
            "Content-aware cross-referencing with intelligent relationship analysis",
            "Named entity recognition and concept extraction",
            "Adaptive analysis strategies based on content type",
            "Multi-strategy PDF extraction with quality assessment",
            "Async processing for large documents",
            "Real-time progress tracking and content analysis"
        ],
        "summary": "Universal Cross-Reference MCP Server - Complete tool documentation with revolutionary content-aware analysis that works intelligently with any type of book or document"
    }

# --- End Watchdog Implementation ---

@mcp.tool()
def analyze_file(file_path: str) -> dict:
    """Analyze a single file for cross-reference patterns, imports, and dependencies."""
    try:
        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            return {"error": f"File not found: {file_path}"}
        
        # Read file content
        try:
            content = file_path_obj.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            try:
                content = file_path_obj.read_text(encoding="latin-1")
            except Exception as e:
                return {"error": f"Could not read file: {e}"}
        
        # Basic analysis
        lines = content.split('\n')
        analysis = {
            "file": str(file_path_obj),
            "lines": len(lines),
            "size_bytes": len(content),
            "language": _detect_language(file_path_obj),
            "imports": _extract_imports(content, file_path_obj),
            "exports": _extract_exports(content, file_path_obj),
            "cross_references": _detect_cross_references(content),
            "summary": f"Analyzed {file_path_obj.name}: {len(lines)} lines, {len(content)} bytes"
        }
        
        return analysis
        
    except Exception as e:
        return {"error": f"Analysis failed: {str(e)}"}

@mcp.tool()
def scan_project(project_path: str, project_name: str = None) -> dict:
    """Scan a project directory for files and basic analysis."""
    try:
        project_path_obj = Path(project_path)
        if not project_path_obj.exists():
            return {"error": f"Project path not found: {project_path}"}
        
        if not project_name:
            project_name = project_path_obj.name
        
        # Find relevant files
        file_patterns = ["*.py", "*.js", "*.jsx", "*.ts", "*.tsx", "*.md", "*.txt", "*.json"]
        files_found = []
        
        for pattern in file_patterns:
            files_found.extend(project_path_obj.rglob(pattern))
        
        # Filter out common directories to ignore
        ignore_dirs = {".git", "__pycache__", "node_modules", "dist", "build", ".venv", "venv"}
        filtered_files = []
        
        for file_path in files_found:
            if not any(ignore_dir in file_path.parts for ignore_dir in ignore_dirs):
                filtered_files.append(file_path)
        
        # Basic project statistics
        total_files = len(filtered_files)
        languages = {}
        total_lines = 0
        
        for file_path in filtered_files[:50]:  # Limit to first 50 files for demo
            try:
                lang = _detect_language(file_path)
                languages[lang] = languages.get(lang, 0) + 1
                
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                total_lines += len(content.split('\n'))
            except Exception:
                continue
        
        # Store project info
        global current_project
        current_project = project_name
        projects[project_name] = {
            "path": str(project_path_obj),
            "files": [str(f) for f in filtered_files],
            "stats": {
                "total_files": total_files,
                "languages": languages,
                "total_lines": total_lines
            }
        }
        
        result = {
            "project_name": project_name,
            "project_path": str(project_path_obj),
            "files_found": total_files,
            "languages": languages,
            "total_lines": total_lines,
            "sample_files": [str(f) for f in filtered_files[:10]],
            "summary": f"Scanned {project_name}: {total_files} files, {len(languages)} languages"
        }
        
        return result
        
    except Exception as e:
        return {"error": f"Project scan failed: {str(e)}"}

@mcp.tool()
def get_crossref_recommendations(project_name: str = None) -> dict:
    """Get recommendations for improving cross-reference coverage in a project."""
    try:
        if not project_name:
            project_name = current_project
        
        if not project_name or project_name not in projects:
            return {"error": "No project specified or project not found. Run scan_project first."}
        
        project = projects[project_name]
        recommendations = []
        
        # Check for hub files
        has_readme = any("readme" in Path(f).name.lower() for f in project["files"])
        has_system_md = any("system.md" in Path(f).name.lower() for f in project["files"])
        
        if not has_readme:
            recommendations.append({
                "priority": "high",
                "type": "hub_file",
                "suggestion": "Create a README.md file to serve as the main project hub",
                "reasoning": "README files help establish clear project documentation structure"
            })
        
        if not has_system_md:
            recommendations.append({
                "priority": "medium", 
                "type": "hub_file",
                "suggestion": "Consider creating a SYSTEM.md file for comprehensive system documentation",
                "reasoning": "SYSTEM.md files provide central technical documentation following cross-reference methodology"
            })
        
        # Check for documentation coverage
        md_files = [f for f in project["files"] if f.endswith('.md')]
        code_files = [f for f in project["files"] if any(f.endswith(ext) for ext in ['.py', '.js', '.jsx', '.ts', '.tsx'])]
        
        if len(md_files) < len(code_files) * 0.1:  # Less than 10% documentation ratio
            recommendations.append({
                "priority": "medium",
                "type": "documentation",
                "suggestion": "Increase documentation coverage - consider adding more .md files",
                "reasoning": f"Found {len(md_files)} documentation files for {len(code_files)} code files"
            })
        
        return {
            "project": project_name,
            "recommendations": recommendations,
            "summary": f"Generated {len(recommendations)} recommendations for {project_name}"
        }
        
    except Exception as e:
        return {"error": f"Recommendation generation failed: {str(e)}"}

# --- End PDF Extraction Engine ---

@mcp.tool()
def extract_pdf_text(pdf_path: Path) -> dict:
    """Extract text using multiple strategies for best results"""
    try:
        strategies_tried = []
        best_result = {"text": "", "quality": 0.0, "strategy": "none"}
        
        # Strategy 1: Direct text extraction with PyPDF2 (fastest)
        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                text = ""
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n\n"
                
                quality = assess_extraction_quality(text)
                strategies_tried.append({"strategy": "PyPDF2", "quality": quality})
                
                if quality > best_result["quality"]:
                    best_result = {"text": text, "quality": quality, "strategy": "PyPDF2"}
                    
        except Exception as e:
            strategies_tried.append({"strategy": "PyPDF2", "error": str(e)})
        
        # Strategy 2: PDFPlumber (better for structured text)
        try:
            with pdfplumber.open(pdf_path) as pdf:
                text = ""
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n\n"
                
                quality = assess_extraction_quality(text)
                strategies_tried.append({"strategy": "pdfplumber", "quality": quality})
                
                if quality > best_result["quality"]:
                    best_result = {"text": text, "quality": quality, "strategy": "pdfplumber"}
                    
        except Exception as e:
            strategies_tried.append({"strategy": "pdfplumber", "error": str(e)})
        
        # Strategy 3: OCR with Tesseract (slowest, for scanned PDFs)
        if OCR_AVAILABLE and best_result["quality"] < 0.5:  # Only if other methods failed
            try:
                images = convert_from_path(pdf_path, first_page=1, last_page=min(5, 10))  # Limit to first few pages for speed
                text = ""
                for image in images:
                    text += pytesseract.image_to_string(image) + "\n\n"
                
                quality = assess_extraction_quality(text)
                strategies_tried.append({"strategy": "OCR", "quality": quality})
                
                if quality > best_result["quality"]:
                    best_result = {"text": text, "quality": quality, "strategy": "OCR"}
                    
            except Exception as e:
                strategies_tried.append({"strategy": "OCR", "error": str(e)})
        
        return {
            "success": True,
            "text": best_result["text"],
            "quality": best_result["quality"], 
            "strategy_used": best_result["strategy"],
            "strategies_tried": strategies_tried,
            "page_count": get_pdf_page_count(pdf_path)
        }
        
    except Exception as e:
        return {"success": False, "error": f"PDF extraction failed: {str(e)}"}

def assess_extraction_quality(text: str) -> float:
    """Score extraction quality (0-1) based on text patterns"""
    if not text or len(text.strip()) < 10:
        return 0.0
    
    # Basic quality indicators
    total_chars = len(text)
    if total_chars == 0:
        return 0.0
    
    # Count readable characters vs garbled
    readable_chars = sum(1 for c in text if c.isalnum() or c.isspace() or c in '.,!?;:"()[]{}')
    readable_ratio = readable_chars / total_chars
    
    # Check for common OCR/extraction errors
    garbled_patterns = ['â€™', 'â€œ', 'â€', 'Â', 'ï¿½']
    garbled_count = sum(text.count(pattern) for pattern in garbled_patterns)
    garbled_penalty = min(garbled_count / 100, 0.5)  # Max 50% penalty
    
    # Check for reasonable word distribution
    words = text.split()
    if len(words) == 0:
        return 0.0
    
    avg_word_length = sum(len(word) for word in words) / len(words)
    word_length_score = min(avg_word_length / 6, 1.0)  # Ideal around 6 chars per word
    
    # Final quality score
    quality = readable_ratio * word_length_score - garbled_penalty
    return max(0.0, min(1.0, quality))

def get_pdf_page_count(pdf_path: Path) -> int:
    """Get number of pages in PDF"""
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            return len(pdf_reader.pages)
    except:
        return 0

def chunk_pdf_content(text: str, pdf_name: str, max_chunks: int = 50) -> dict:
    """Chunk PDF content into manageable markdown files (Phase 3)"""
    if not text or not text.strip():
        return {"success": False, "error": "No text content to chunk", "chunks": []}
    
    # Simple chunking by word count (MVP approach)
    words = text.split()
    if len(words) == 0:
        return {"success": False, "error": "No words found in text", "chunks": []}
    
    # Calculate target words per chunk
    target_words_per_chunk = max(500, len(words) // max_chunks)  # At least 500 words per chunk
    
    chunk_texts = []
    current_chunk = []
    current_word_count = 0
    
    for word in words:
        current_chunk.append(word)
        current_word_count += 1
        
        # Check for natural break points (sentence endings)
        if (current_word_count >= target_words_per_chunk and 
            word.endswith(('.', '!', '?')) and 
            len(chunk_texts) < max_chunks - 1):
            
            chunk_text = ' '.join(current_chunk).strip()
            if chunk_text:
                chunk_texts.append(chunk_text)
            current_chunk = []
            current_word_count = 0
    
    # Add remaining content as final chunk
    if current_chunk:
        chunk_text = ' '.join(current_chunk).strip()
        if chunk_text:
            chunk_texts.append(chunk_text)
    
    # Convert to expected chunk format with metadata
    chunks = []
    for i, chunk_text in enumerate(chunk_texts, 1):
        # Try to extract a meaningful title from first line/sentence
        lines = chunk_text.split('\n')
        first_line = next((line.strip() for line in lines if line.strip()), "")
        
        if len(first_line) > 5 and len(first_line) < 60:
            # Use first line as title
            title = first_line[:50]
        else:
            # Fallback to generic title
            title = f"Chapter {i}"
        
        chunk_data = {
            "content": chunk_text,
            "title": title,
            "word_count": len(chunk_text.split()),
            "chunk_number": i
        }
        chunks.append(chunk_data)
    
    return {
        "success": True,
        "chunks": chunks,
        "total_chunks": len(chunks),
        "total_words": sum(chunk["word_count"] for chunk in chunks)
    }

def generate_chunk_filenames(pdf_name: str, chunks: list) -> list:
    """Generate meaningful filenames for chunks (Phase 3)"""
    base_name = pdf_name.replace('.pdf', '').replace(' ', '_').lower()
    
    filenames = []
    for i, chunk in enumerate(chunks, 1):
        # Try to extract a meaningful title from first line/sentence
        lines = chunk.split('\n')
        first_line = next((line.strip() for line in lines if line.strip()), "")
        
        if len(first_line) > 5 and len(first_line) < 60:
            # Use first line as basis for filename
            title = re.sub(r'[^\w\s-]', '', first_line)
            title = re.sub(r'\s+', '_', title.strip()).lower()
            filename = f"{base_name}_{i:02d}_{title[:30]}.md"
        else:
            # Fallback to sequential naming
            filename = f"{base_name}_chapter_{i:02d}.md"
        
        filenames.append(filename)
    
    return filenames

# --- End PDF Extraction Engine ---

# --- Async PDF Extraction Engine (Phase 5) ---

async def extract_pdf_text_async(pdf_path: Path, task: PDFExtractionTask) -> dict:
    """Async version of PDF text extraction with progress tracking"""
    try:
        task.update_status("starting_extraction", 5)
        await asyncio.sleep(0)  # Yield control
        
        # Use thread pool for CPU-intensive operations
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(task_executor, extract_pdf_text, pdf_path)
        
        task.update_status("text_extracted", 15)
        await asyncio.sleep(0)  # Yield control
        
        return result
        
    except Exception as e:
        task.fail(f"Async text extraction failed: {str(e)}")
        return {"success": False, "error": str(e)}

async def process_pdf_async(task_id: str, pdf_path: str, params: dict) -> dict:
    """Process PDF extraction asynchronously with content-aware cross-referencing"""
    task = active_tasks.get(task_id)
    if not task:
        return {"error": "Task not found", "success": False}
    
    try:
        task.update_status("starting_extraction", 5)
        await asyncio.sleep(0)  # Yield control
        
        pdf_path_obj = Path(pdf_path)
        if not pdf_path_obj.exists():
            task.fail(f"PDF file not found: {pdf_path}")
            return {"error": f"PDF file not found: {pdf_path}", "success": False}
        
        # Extract text from PDF
        task.update_status("extracting_text", 15)
        result = await extract_pdf_text_async(pdf_path_obj, task)
        if not result["success"]:
            task.fail(result.get("error", "Text extraction failed"))
            return result
        
        text = result["text"]
        page_count = result.get("page_count", 0)
        quality_score = result.get("quality_score", 0.0)
        strategy_used = result.get("strategy", "auto")
        
        task.update_status("text_extracted", 25)
        await asyncio.sleep(0)
        
        # Set output directory
        output_dir = params.get("output_dir")
        if output_dir is None:
            base_name = pdf_path_obj.stem
            output_dir = pdf_path_obj.parent / f"{base_name}_extracted"
        else:
            output_dir = Path(output_dir)
        
        # Create output directory
        output_dir.mkdir(exist_ok=True)
        
        # Chunk the content
        task.update_status("chunking_content", 35)
        max_chunks = params.get("max_chunks", 50)
        chunk_result = chunk_pdf_content(text, pdf_path.name, max_chunks)
        if not chunk_result["success"]:
            task.fail(chunk_result.get("error", "Chunking failed"))
            return chunk_result
        
        chunks = chunk_result["chunks"]
        task.update_status("content_chunked", 45)
        await asyncio.sleep(0)
        
        # **NEW: Analyze content for intelligent cross-referencing**
        task.update_status("analyzing_content", 55)
        
        # Prepare content for analysis (filename -> content mapping)
        content_map = {}
        for i, chunk in enumerate(chunks, 1):
            filename = f"{pdf_path_obj.stem.lower().replace(' ', '').replace('-', '').replace('_', '')}_chapter_{i:02d}.md"
            content_map[filename] = chunk["content"]
        
        # Generate intelligent cross-references
        smart_cross_refs = analyze_pdf_content_for_crossref_universal(content_map, pdf_path_obj.name)
        
        task.update_status("cross_references_generated", 65)
        await asyncio.sleep(0)
        
        # Create individual chapter files with smart cross-references
        task.update_status("creating_files", 75)
        created_files = []
        hub_file_name = f"{pdf_path_obj.stem}_index.md"
        
        for i, chunk in enumerate(chunks, 1):
            filename = f"{pdf_path_obj.stem.lower().replace(' ', '').replace('-', '').replace('_', '')}_chapter_{i:02d}.md"
            file_path = output_dir / filename
            
            # Get smart cross-references for this chapter
            related_files = smart_cross_refs.get(filename, [])
            
            # Create proper cross-reference header with intelligent relationships
            cross_ref_header = f"""---
MANDATORY READING: You HAVE TO read {hub_file_name} first, then this file.
Cross-reference: {hub_file_name}
Related files: {related_files}
Chapter: {i} of {len(chunks)}
Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
---

"""
            
            # Create chapter content
            chapter_content = f"""# {chunk['title']}

**Extracted from PDF**: {pdf_path_obj.name}
**Chunk**: {i} of {len(chunks)}
**Words**: ~{chunk['word_count']:,}
**Quality Score**: {quality_score:.2f}
**Extraction Strategy**: {strategy_used}

---

{chunk['content']}
"""
            
            # Write the file asynchronously
            async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                await f.write(cross_ref_header + chapter_content)
            
            created_files.append(str(file_path))
            
            # Update progress for each file
            file_progress = 75 + ((i / len(chunks)) * 15)
            task.update_status(f"created_file_{i}", file_progress)
            await asyncio.sleep(0)  # Yield control
        
        # Create hub/index file if requested
        create_hub = params.get("create_hub", True)
        if create_hub:
            task.update_status("creating_hub", 90)
            hub_path = output_dir / hub_file_name
            
            # Generate hub content with content analysis
            hub_content = f"""# {pdf_path_obj.stem} - Complete Cross-Referenced Knowledge Base

**Source**: {pdf_path_obj.name}  
**Extracted**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  
**Total Pages**: {page_count}  
**Quality Score**: {quality_score:.2f}/1.0  
**Extraction Strategy**: {strategy_used}  
**Chapters**: {len(chunks)}

## 📚 Reading Guide

This knowledge base uses **intelligent content-aware cross-referencing** that analyzes:
- **Conceptual relationships** between chapters
- **Thematic connections** and shared ideas  
- **Learning progression** from foundational to advanced concepts
- **Semantic similarity** between topics

### 🎯 Suggested Reading Path

"""
            
            # Add chapters with word counts and smart navigation
            for i, chunk in enumerate(chunks, 1):
                filename = f"{pdf_path_obj.stem.lower().replace(' ', '').replace('-', '').replace('_', '')}_chapter_{i:02d}.md"
                related_count = len(smart_cross_refs.get(filename, []))
                
                hub_content += f"""
#### Chapter {i}: [{chunk['title']}]({filename})
- **Words**: ~{chunk['word_count']:,}
- **Related chapters**: {related_count} intelligent connections
- **Preview**: {chunk['content'][:200].replace('\n', ' ')}...

"""
            
            hub_content += f"""
## 📊 Content Analysis Summary

- **Total chapters**: {len(chunks)}
- **Total words**: ~{sum(chunk['word_count'] for chunk in chunks):,}
- **Average chapter length**: ~{sum(chunk['word_count'] for chunk in chunks) // len(chunks):,} words
- **Cross-reference density**: {sum(len(refs) for refs in smart_cross_refs.values())} intelligent connections

## 🔗 Cross-Reference Methodology

This extraction uses **content-aware cross-referencing** that goes beyond simple sequential linking:

1. **Concept Extraction**: Identifies key philosophical, scientific, and metaphysical concepts
2. **Thematic Analysis**: Groups chapters by shared themes and ideas
3. **Semantic Similarity**: Calculates meaningful relationships between content
4. **Learning Progression**: Suggests optimal reading sequences based on concept dependencies

Each chapter's "Related files" are selected based on actual content analysis, not just proximity!

---
*Generated by Universal Cross-Reference MCP Server with Content-Aware PDF Analysis*
"""
            
            async with aiofiles.open(hub_path, 'w', encoding='utf-8') as f:
                await f.write(hub_content)
            
            created_files.append(str(hub_path))
        
        await asyncio.sleep(0)
        
        total_files = len(created_files)
        total_words = sum(chunk['word_count'] for chunk in chunks)
        
        result = {
            "success": True,
            "message": f"Successfully extracted PDF to {total_files} cross-referenced markdown files",
            "files_created": created_files,
            "output_directory": str(output_dir),
            "total_chapters": len(chunks),
            "total_words": total_words,
            "average_words_per_chapter": total_words // len(chunks),
            "quality_score": quality_score,
            "extraction_strategy": strategy_used,
            "intelligent_cross_references": len([refs for refs in smart_cross_refs.values() if refs])
        }
        
        task.complete(result)
        return result
        
    except Exception as e:
        task.fail(f"PDF extraction failed: {str(e)}")
        return {"error": f"PDF extraction failed: {str(e)}", "success": False}

@mcp.tool()
def extract_pdf_to_markdown_async(
    pdf_path: str,
    output_dir: str = None,
    max_chunks: int = 50,
    create_hub: bool = True
) -> dict:
    """Start async PDF extraction to cross-referenced markdown files"""
    try:
        pdf_path_obj = Path(pdf_path)
        if not pdf_path_obj.exists():
            return {"error": f"PDF file not found: {pdf_path}"}
        
        if not pdf_path_obj.suffix.lower() == '.pdf':
            return {"error": f"File is not a PDF: {pdf_path}"}
        
        # Generate unique task ID
        task_id = str(uuid.uuid4())
        
        # Create task
        params = {
            'output_dir': output_dir,
            'max_chunks': max_chunks,
            'create_hub': create_hub
        }
        
        task = PDFExtractionTask(task_id, pdf_path, params)
        active_tasks[task_id] = task
        
        # Start async processing
        asyncio.create_task(process_pdf_async(task_id, pdf_path, params))
        
        return {
            "success": True,
            "task_id": task_id,
            "status": "started",
            "pdf_path": pdf_path,
            "estimated_time": "2-5 minutes for large PDFs",
            "instructions": f"Use check_pdf_extraction_status('{task_id}') to monitor progress",
            "message": "PDF extraction started in background with automatic cross-referencing"
        }
        
    except Exception as e:
        return {"error": f"Failed to start async extraction: {str(e)}"}

@mcp.tool()
def check_pdf_extraction_status(task_id: str) -> dict:
    """Check the status of an ongoing PDF extraction task"""
    try:
        task = active_tasks.get(task_id)
        if not task:
            return {"error": f"Task {task_id} not found"}
        
        result = {
            "task_id": task_id,
            "status": task.status,
            "progress": task.progress,
            "pdf_path": task.pdf_path,
            "start_time": task.start_time.strftime('%Y-%m-%d %H:%M:%S'),
            "elapsed_time": str(datetime.now() - task.start_time)
        }
        
        if task.status == "completed" and task.result:
            result["result"] = task.result
            # Clean up completed task after returning result
            del active_tasks[task_id]
        elif task.status == "failed" and task.error:
            result["error"] = task.error
            # Clean up failed task
            del active_tasks[task_id]
        
        return result
        
    except Exception as e:
        return {"error": f"Failed to check status: {str(e)}"}

@mcp.tool()
def list_pdf_extraction_tasks() -> dict:
    """List all active PDF extraction tasks"""
    try:
        tasks = []
        for task_id, task in active_tasks.items():
            tasks.append({
                "task_id": task_id,
                "status": task.status,
                "progress": task.progress,
                "pdf_path": task.pdf_path,
                "start_time": task.start_time.strftime('%Y-%m-%d %H:%M:%S')
            })
        
        return {
            "success": True,
            "active_tasks": len(tasks),
            "tasks": tasks
        }
        
    except Exception as e:
        return {"error": f"Failed to list tasks: {str(e)}"}

# --- End Async PDF Extraction Engine ---

# Modify the existing extract_pdf_to_markdown function to include automatic cross-referencing
@mcp.tool()
def extract_pdf_to_markdown(pdf_path: str, output_dir: str = None, max_chunks: int = 20, 
                           create_hub: bool = True, extraction_strategy: str = "auto") -> dict:
    """Extract PDF content to cross-referenced markdown files with intelligent cross-referencing"""
    try:
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            return {"error": f"PDF file not found: {pdf_path}", "success": False}
        
        # Extract text from PDF
        result = extract_pdf_text(pdf_path)
        if not result["success"]:
            return result
        
        text = result["text"]
        page_count = result.get("page_count", 0)
        quality_score = result.get("quality_score", 0.0)
        strategy_used = result.get("strategy", extraction_strategy)
        
        print(f"✅ PDF extraction completed. Quality: {quality_score:.2f}, Strategy: {strategy_used}")
        
        # Set output directory
        if output_dir is None:
            base_name = pdf_path.stem
            output_dir = pdf_path.parent / f"{base_name}_extracted"
        else:
            output_dir = Path(output_dir)
        
        # Create output directory
        output_dir.mkdir(exist_ok=True)
        
        # Chunk the content
        chunk_result = chunk_pdf_content(text, pdf_path.name, max_chunks)
        if not chunk_result["success"]:
            return chunk_result
        
        chunks = chunk_result["chunks"]
        
        print(f"✅ Content chunked into {len(chunks)} chapters")
        
        # **NEW: Analyze content for intelligent cross-referencing**
        print("🧠 Analyzing content for intelligent cross-referencing...")
        
        # Prepare content for analysis (filename -> content mapping)
        content_map = {}
        for i, chunk in enumerate(chunks, 1):
            filename = f"{pdf_path.stem.lower().replace(' ', '').replace('-', '').replace('_', '')}_chapter_{i:02d}.md"
            content_map[filename] = chunk["content"]
        
        # Generate intelligent cross-references
        smart_cross_refs = analyze_pdf_content_for_crossref_universal(content_map, pdf_path.name)
        
        print(f"🎯 Generated intelligent cross-references for {len(smart_cross_refs)} chapters")
        
        # Create individual chapter files with smart cross-references
        created_files = []
        hub_file_name = f"{pdf_path.stem}_index.md"
        
        for i, chunk in enumerate(chunks, 1):
            filename = f"{pdf_path.stem.lower().replace(' ', '').replace('-', '').replace('_', '')}_chapter_{i:02d}.md"
            file_path = output_dir / filename
            
            # Get smart cross-references for this chapter
            related_files = smart_cross_refs.get(filename, [])
            
            # Create proper cross-reference header with intelligent relationships
            cross_ref_header = f"""---
MANDATORY READING: You HAVE TO read {hub_file_name} first, then this file.
Cross-reference: {hub_file_name}
Related files: {related_files}
Chapter: {i} of {len(chunks)}
Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
---

"""
            
            # Create chapter content
            chapter_content = f"""# {chunk['title']}

**Extracted from PDF**: {pdf_path.name}
**Chunk**: {i} of {len(chunks)}
**Words**: ~{chunk['word_count']:,}
**Quality Score**: {quality_score:.2f}
**Extraction Strategy**: {strategy_used}

---

{chunk['content']}
"""
            
            # Write the file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(cross_ref_header + chapter_content)
            
            created_files.append(str(file_path))
            print(f"📄 Created: {filename} with {len(related_files)} intelligent cross-references")
        
        # Create hub/index file if requested
        if create_hub:
            hub_path = output_dir / hub_file_name
            
            # Generate hub content with content analysis
            hub_content = f"""# {pdf_path.stem} - Complete Cross-Referenced Knowledge Base

**Source**: {pdf_path.name}  
**Extracted**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  
**Total Pages**: {page_count}  
**Quality Score**: {quality_score:.2f}/1.0  
**Extraction Strategy**: {strategy_used}  
**Chapters**: {len(chunks)}

## 📚 Reading Guide

This knowledge base uses **intelligent content-aware cross-referencing** that analyzes:
- **Conceptual relationships** between chapters
- **Thematic connections** and shared ideas  
- **Learning progression** from foundational to advanced concepts
- **Semantic similarity** between topics

### 🎯 Suggested Reading Path

"""
            
            # Add chapters with word counts and smart navigation
            for i, chunk in enumerate(chunks, 1):
                filename = f"{pdf_path.stem.lower().replace(' ', '').replace('-', '').replace('_', '')}_chapter_{i:02d}.md"
                related_count = len(smart_cross_refs.get(filename, []))
                
                hub_content += f"""
#### Chapter {i}: [{chunk['title']}]({filename})
- **Words**: ~{chunk['word_count']:,}
- **Related chapters**: {related_count} intelligent connections
- **Preview**: {chunk['content'][:200].replace('\n', ' ')}...

"""
            
            hub_content += f"""
## 📊 Content Analysis Summary

- **Total chapters**: {len(chunks)}
- **Total words**: ~{sum(chunk['word_count'] for chunk in chunks):,}
- **Average chapter length**: ~{sum(chunk['word_count'] for chunk in chunks) // len(chunks):,} words
- **Cross-reference density**: {sum(len(refs) for refs in smart_cross_refs.values())} intelligent connections

## 🔗 Cross-Reference Methodology

This extraction uses **content-aware cross-referencing** that goes beyond simple sequential linking:

1. **Concept Extraction**: Identifies key philosophical, scientific, and metaphysical concepts
2. **Thematic Analysis**: Groups chapters by shared themes and ideas
3. **Semantic Similarity**: Calculates meaningful relationships between content
4. **Learning Progression**: Suggests optimal reading sequences based on concept dependencies

Each chapter's "Related files" are selected based on actual content analysis, not just proximity!

---
*Generated by Universal Cross-Reference MCP Server with Content-Aware PDF Analysis*
"""
            
            with open(hub_path, 'w', encoding='utf-8') as f:
                f.write(hub_content)
            
            created_files.append(str(hub_path))
            print(f"🏠 Created hub file: {hub_file_name}")
        
        total_files = len(created_files)
        total_words = sum(chunk['word_count'] for chunk in chunks)
        
        return {
            "success": True,
            "message": f"Successfully extracted PDF to {total_files} cross-referenced markdown files",
            "files_created": created_files,
            "output_directory": str(output_dir),
            "total_chapters": len(chunks),
            "total_words": total_words,
            "average_words_per_chapter": total_words // len(chunks),
            "quality_score": quality_score,
            "extraction_strategy": strategy_used,
            "intelligent_cross_references": len([refs for refs in smart_cross_refs.values() if refs])
        }
        
    except Exception as e:
        return {"error": f"PDF extraction failed: {str(e)}", "success": False}

# --- End PDF Extraction Engine ---

def _detect_language(file_path: Path) -> str:
    """Detect programming language from file extension."""
    ext = file_path.suffix.lower()
    language_map = {
        '.py': 'python',
        '.js': 'javascript', 
        '.jsx': 'javascript',
        '.ts': 'typescript',
        '.tsx': 'typescript',
        '.md': 'markdown',
        '.txt': 'text',
        '.json': 'json',
        '.yaml': 'yaml',
        '.yml': 'yaml',
        '.pdf': 'pdf'  # Add PDF detection
    }
    return language_map.get(ext, 'unknown')

def _extract_imports(content: str, file_path: Path) -> list:
    """Extract import statements from code."""
    imports = []
    lines = content.split('\n')
    
    lang = _detect_language(file_path)
    
    if lang == 'python':
        for line in lines:
            line = line.strip()
            if line.startswith('import ') or line.startswith('from '):
                imports.append(line)
    elif lang in ['javascript', 'typescript']:
        for line in lines:
            line = line.strip()
            if 'import ' in line and 'from ' in line:
                imports.append(line)
    
    return imports[:10]  # Limit to first 10 imports

def _extract_exports(content: str, file_path: Path) -> list:
    """Extract export statements from code."""
    exports = []
    lines = content.split('\n')
    
    lang = _detect_language(file_path)
    
    if lang in ['javascript', 'typescript']:
        for line in lines:
            line = line.strip()
            if line.startswith('export '):
                exports.append(line)
    elif lang == 'python':
        # Look for __all__ definitions
        for line in lines:
            line = line.strip()
            if '__all__' in line:
                exports.append(line)
    
    return exports[:10]  # Limit to first 10 exports

def _detect_cross_references(content: str) -> list:
    """Detect cross-reference patterns in content."""
    cross_refs = []
    lines = content.split('\n')
    
    # Look for common cross-reference patterns
    patterns = [
        'Cross-reference:',
        'See also:',
        'Related:',
        'MUST READ',
        'HAVE TO',
        'Also read'
    ]
    
    for i, line in enumerate(lines):
        for pattern in patterns:
            if pattern.lower() in line.lower():
                cross_refs.append({
                    "line": i + 1,
                    "pattern": pattern,
                    "text": line.strip()
                })
    
    return cross_refs[:5]  # Limit to first 5 cross-references

# --- Universal Content-Aware PDF Cross-Referencing Engine (Enhanced for All Book Types) ---

import re
from collections import Counter, defaultdict
from typing import Dict, List, Tuple, Set
import math

class UniversalPDFContentAnalyzer:
    """Universal content-aware cross-referencing for all types of books and documents"""
    
    def __init__(self):
        # Comprehensive concept patterns for different genres
        self.concept_patterns = {
            # Fiction & Literature
            'fiction': [
                r'\b(character|protagonist|hero|villain|narrator)\b',
                r'\b(plot|story|narrative|chapter|scene|dialogue)\b',
                r'\b(love|romance|relationship|family|friendship)\b',
                r'\b(conflict|tension|drama|mystery|adventure)\b',
                r'\b(setting|world|place|location|time|era)\b'
            ],
            
            # Philosophy & Metaphysics  
            'philosophical': [
                r'\b(mind|consciousness|thinking|thought|idea|concept)\b',
                r'\b(being|existence|reality|truth|essence|meaning)\b', 
                r'\b(universal|omnipresent|infinite|eternal|absolute)\b',
                r'\b(god|divine|spirit|soul|transcendent)\b',
                r'\b(wisdom|knowledge|understanding|awareness)\b'
            ],
            
            # Science & Technical
            'scientific': [
                r'\b(energy|force|motion|gravity|radiation|electromagnetic)\b',
                r'\b(atom|molecule|element|particle|quantum|wave)\b',
                r'\b(theory|hypothesis|experiment|research|data)\b',
                r'\b(analysis|measurement|calculation|formula|equation)\b',
                r'\b(system|process|mechanism|function|structure)\b'
            ],
            
            # Business & Economics
            'business': [
                r'\b(strategy|management|leadership|organization|team)\b',
                r'\b(market|customer|product|service|brand|sales)\b',
                r'\b(profit|revenue|cost|investment|growth|value)\b',
                r'\b(competition|advantage|innovation|efficiency)\b',
                r'\b(goal|objective|performance|success|achievement)\b'
            ],
            
            # History & Biography
            'historical': [
                r'\b(war|battle|conflict|revolution|empire|kingdom)\b',
                r'\b(century|decade|year|period|era|age|epoch)\b',
                r'\b(king|queen|president|leader|ruler|government)\b',
                r'\b(culture|society|civilization|tradition|custom)\b',
                r'\b(event|happening|occurrence|incident|development)\b'
            ],
            
            # Self-Help & Psychology
            'selfhelp': [
                r'\b(habit|behavior|practice|routine|discipline)\b',
                r'\b(goal|success|achievement|improvement|growth)\b',
                r'\b(emotion|feeling|mood|attitude|mindset)\b',
                r'\b(relationship|communication|interaction|social)\b',
                r'\b(confidence|motivation|inspiration|determination)\b'
            ],
            
            # Technical & Programming
            'technical': [
                r'\b(function|method|algorithm|process|procedure)\b',
                r'\b(data|information|input|output|result|value)\b',
                r'\b(system|application|software|program|code)\b',
                r'\b(requirement|specification|implementation|design)\b',
                r'\b(error|bug|debug|test|validation|verification)\b'
            ],
            
            # Medical & Health
            'medical': [
                r'\b(health|disease|treatment|therapy|medicine|drug)\b',
                r'\b(patient|doctor|nurse|hospital|clinic|care)\b',
                r'\b(symptom|diagnosis|condition|syndrome|disorder)\b',
                r'\b(body|organ|cell|tissue|blood|brain|heart)\b',
                r'\b(research|study|trial|evidence|effectiveness)\b'
            ],
            
            # Religious & Spiritual
            'religious': [
                r'\b(god|divine|sacred|holy|spiritual|prayer)\b',
                r'\b(faith|belief|religion|worship|devotion)\b',
                r'\b(soul|spirit|heaven|salvation|enlightenment)\b',
                r'\b(church|temple|mosque|synagogue|cathedral)\b',
                r'\b(scripture|bible|quran|torah|teaching|doctrine)\b'
            ]
        }
        
        # Genre indicators for automatic detection
        self.genre_indicators = {
            'fiction': ['novel', 'story', 'character', 'plot', 'romance', 'mystery', 'fantasy', 'drama'],
            'philosophical': ['philosophy', 'metaphysics', 'consciousness', 'existence', 'reality', 'truth'],
            'scientific': ['science', 'research', 'experiment', 'theory', 'physics', 'chemistry', 'biology'],
            'business': ['business', 'management', 'strategy', 'leadership', 'marketing', 'sales', 'profit'],
            'historical': ['history', 'historical', 'century', 'war', 'empire', 'civilization', 'ancient'],
            'selfhelp': ['self-help', 'improve', 'success', 'habit', 'motivation', 'achievement', 'personal'],
            'technical': ['programming', 'software', 'computer', 'algorithm', 'code', 'system', 'technical'],
            'medical': ['medical', 'health', 'medicine', 'disease', 'treatment', 'patient', 'clinical'],
            'religious': ['religion', 'spiritual', 'faith', 'god', 'prayer', 'scripture', 'sacred']
        }
    
    def detect_genre(self, full_text: str, title: str = "") -> List[Tuple[str, float]]:
        """Detect the primary genre(s) of the book based on content analysis"""
        text_lower = (full_text + " " + title).lower()
        genre_scores = defaultdict(float)
        
        # Score based on genre indicators
        for genre, indicators in self.genre_indicators.items():
            score = 0
            for indicator in indicators:
                # Count occurrences, weighted by indicator importance
                count = text_lower.count(indicator)
                score += count * (1.0 + len(indicator) / 10.0)  # Longer indicators get slight boost
            
            # Normalize by text length
            genre_scores[genre] = score / max(len(text_lower.split()), 1000)
        
        # Also score based on concept patterns
        for genre, patterns in self.concept_patterns.items():
            pattern_score = 0
            for pattern in patterns:
                matches = len(re.findall(pattern, text_lower, re.IGNORECASE))
                pattern_score += matches
            
            genre_scores[genre] += pattern_score / max(len(text_lower.split()), 1000)
        
        # Return sorted genres by score
        sorted_genres = sorted(genre_scores.items(), key=lambda x: x[1], reverse=True)
        return [(genre, score) for genre, score in sorted_genres if score > 0]
    
    def extract_concepts_universal(self, text: str, title: str = "", detected_genres: List[str] = None) -> Dict[str, float]:
        """Extract concepts with genre-aware weighting"""
        text_lower = text.lower()
        concept_counts = Counter()
        
        # Use detected genres or fall back to all patterns
        if detected_genres:
            active_patterns = {}
            for genre in detected_genres[:3]:  # Use top 3 genres
                if genre in self.concept_patterns:
                    active_patterns[genre] = self.concept_patterns[genre]
        else:
            active_patterns = self.concept_patterns
        
        # Extract concepts by category with genre weighting
        for genre, patterns in active_patterns.items():
            genre_weight = 1.0
            if detected_genres and genre in detected_genres:
                # Higher weight for primary detected genres
                genre_weight = 2.0 / (detected_genres.index(genre) + 1)
            
            for pattern in patterns:
                matches = re.findall(pattern, text_lower, re.IGNORECASE)
                for match in matches:
                    concept_counts[match] += genre_weight
        
        # Add title-based concepts (higher weight)
        title_words = re.findall(r'\b\w{4,}\b', title.lower())
        for word in title_words:
            if word not in ['chapter', 'contents', 'page', 'book', 'part']:
                concept_counts[word] += 3
        
        # Add named entities (simple extraction)
        entities = self.extract_named_entities(text)
        for entity in entities:
            concept_counts[entity.lower()] += 2
        
        # Weight by frequency and context importance
        weighted_concepts = {}
        total_words = len(text.split())
        
        for concept, count in concept_counts.items():
            # TF-IDF style weighting
            frequency = count / max(total_words, 1)
            importance = math.log(1 + count)
            weighted_concepts[concept] = frequency * importance
            
        return weighted_concepts
    
    def extract_named_entities(self, text: str) -> List[str]:
        """Simple named entity extraction (people, places, organizations)"""
        # Simple heuristic-based approach (could be enhanced with NLP libraries)
        entities = []
        
        # Capitalized words that aren't at sentence start
        sentences = re.split(r'[.!?]+', text)
        for sentence in sentences:
            words = sentence.split()
            for i, word in enumerate(words):
                if (i > 0 and  # Not first word of sentence
                    word[0].isupper() and  # Capitalized
                    len(word) > 3 and  # Reasonable length
                    word.isalpha()):  # Only letters
                    entities.append(word)
        
        # Remove duplicates and common false positives
        common_words = {'The', 'This', 'That', 'These', 'Those', 'When', 'Where', 'What', 'Why', 'How'}
        entities = list(set([e for e in entities if e not in common_words]))
        
        return entities[:20]  # Limit to top 20
    
    def analyze_content_structure(self, chapters: Dict[str, str], detected_genres: List[str]) -> Dict[str, Dict]:
        """Genre-aware content structure analysis"""
        chapter_analysis = {}
        primary_genre = detected_genres[0] if detected_genres else 'general'
        
        for chapter_id, content in chapters.items():
            # Extract title from content
            title_match = re.search(r'# (.+)', content)
            title = title_match.group(1) if title_match else chapter_id
            
            # Extract concepts with genre awareness
            concepts = self.extract_concepts_universal(content, title, detected_genres)
            
            # Identify primary themes (top concepts)
            primary_themes = dict(sorted(concepts.items(), 
                                       key=lambda x: x[1], reverse=True)[:5])
            
            # Genre-specific analysis
            special_features = self.extract_genre_specific_features(content, primary_genre)
            
            chapter_analysis[chapter_id] = {
                'title': title,
                'concepts': concepts,
                'primary_themes': primary_themes,
                'primary_genre': primary_genre,
                'word_count': len(content.split()),
                'concept_density': len(concepts) / max(len(content.split()), 1),
                'special_features': special_features,
                'entities': self.extract_named_entities(content)
            }
            
        return chapter_analysis
    
    def extract_genre_specific_features(self, content: str, genre: str) -> Dict:
        """Extract genre-specific features for better cross-referencing"""
        features = {}
        
        if genre == 'fiction':
            # Character extraction
            characters = [e for e in self.extract_named_entities(content) 
                         if not any(word in e.lower() for word in ['chapter', 'book', 'part'])]
            features['characters'] = characters[:10]
            
            # Dialogue density
            dialogue_lines = len(re.findall(r'"[^"]*"', content))
            features['dialogue_density'] = dialogue_lines / max(len(content.split()), 1)
            
        elif genre == 'technical':
            # Procedure/step detection
            steps = re.findall(r'\b(?:step|first|second|third|\d+\.)\b.*?(?:\.|$)', content, re.IGNORECASE)
            features['procedures'] = len(steps)
            
            # Code/formula detection
            code_blocks = len(re.findall(r'```|`[^`]+`|\b[A-Z_]+\([^)]*\)', content))
            features['code_density'] = code_blocks / max(len(content.split()), 1)
            
        elif genre == 'historical':
            # Date/year extraction
            dates = re.findall(r'\b(?:19|20)\d{2}\b|\b\d{1,2}(?:st|nd|rd|th)?\s+century\b', content, re.IGNORECASE)
            features['temporal_references'] = len(set(dates))
            
            # Historical figures (capitalized names)
            historical_figures = [e for e in self.extract_named_entities(content)]
            features['historical_figures'] = historical_figures[:10]
            
        elif genre == 'business':
            # Metrics/numbers detection
            metrics = len(re.findall(r'\$[\d,]+|\b\d+%|\b\d+\.\d+\b', content))
            features['quantitative_content'] = metrics / max(len(content.split()), 1)
            
            # Strategy terms
            strategy_terms = len(re.findall(r'\b(?:strategy|goal|objective|kpi|roi|growth)\b', content, re.IGNORECASE))
            features['strategy_density'] = strategy_terms / max(len(content.split()), 1)
        
        return features
    
    def calculate_universal_similarity(self, chapter1: Dict, chapter2: Dict) -> float:
        """Universal similarity calculation that adapts to genre"""
        genre = chapter1.get('primary_genre', 'general')
        
        # Base conceptual similarity
        concepts1 = set(chapter1['concepts'].keys())
        concepts2 = set(chapter2['concepts'].keys())
        
        if not concepts1 or not concepts2:
            return 0.0
            
        # Jaccard similarity for concept overlap
        intersection = len(concepts1.intersection(concepts2))
        union = len(concepts1.union(concepts2))
        jaccard = intersection / union if union > 0 else 0
        
        # Weighted similarity by concept importance
        weighted_sim = 0.0
        shared_concepts = concepts1.intersection(concepts2)
        
        for concept in shared_concepts:
            weight1 = chapter1['concepts'].get(concept, 0)
            weight2 = chapter2['concepts'].get(concept, 0)
            weighted_sim += min(weight1, weight2)
        
        # Normalize by average concept count
        avg_concepts = (len(concepts1) + len(concepts2)) / 2
        normalized_weighted = weighted_sim / max(avg_concepts, 1)
        
        # Genre-specific similarity adjustments
        genre_bonus = self.calculate_genre_specific_similarity(chapter1, chapter2, genre)
        
        # Combined similarity score
        base_similarity = (jaccard * 0.4) + (normalized_weighted * 0.4)
        return min(1.0, base_similarity + genre_bonus * 0.2)
    
    def calculate_genre_specific_similarity(self, chapter1: Dict, chapter2: Dict, genre: str) -> float:
        """Calculate genre-specific similarity bonuses"""
        features1 = chapter1.get('special_features', {})
        features2 = chapter2.get('special_features', {})
        
        if genre == 'fiction':
            # Character overlap
            chars1 = set(features1.get('characters', []))
            chars2 = set(features2.get('characters', []))
            char_overlap = len(chars1.intersection(chars2)) / max(len(chars1.union(chars2)), 1)
            return char_overlap * 0.5
            
        elif genre == 'technical':
            # Similar procedure density
            proc1 = features1.get('procedures', 0)
            proc2 = features2.get('procedures', 0)
            if proc1 > 0 and proc2 > 0:
                return min(proc1, proc2) / max(proc1, proc2) * 0.3
                
        elif genre == 'historical':
            # Temporal proximity or figure overlap
            figs1 = set(features1.get('historical_figures', []))
            figs2 = set(features2.get('historical_figures', []))
            fig_overlap = len(figs1.intersection(figs2)) / max(len(figs1.union(figs2)), 1)
            return fig_overlap * 0.4
        
        return 0.0
    
    def generate_universal_cross_references(self, analysis: Dict[str, Dict], 
                                          chapter_id: str, max_refs: int = 3) -> List[Dict[str, str]]:
        """Generate intelligent cross-references adapted to content genre"""
        if chapter_id not in analysis:
            return []
            
        current_chapter = analysis[chapter_id]
        genre = current_chapter.get('primary_genre', 'general')
        similarities = []
        
        # Calculate similarity with all other chapters
        for other_id, other_data in analysis.items():
            if other_id != chapter_id:
                similarity = self.calculate_universal_similarity(current_chapter, other_data)
                similarities.append((other_id, similarity, other_data))
        
        # Sort by similarity and select top references
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        cross_refs = []
        for other_id, similarity, other_data in similarities[:max_refs]:
            if similarity > 0.2:  # Minimum threshold for meaningful relationships
                # Generate descriptive reason for the relationship
                reason = self.generate_relationship_reason(current_chapter, other_data, genre)
                
                cross_refs.append({
                    'file': other_id,
                    'similarity_score': round(similarity, 3),
                    'reason': reason,
                    'genre': genre,
                    'relationship_type': self.classify_relationship_type(current_chapter, other_data, genre)
                })
        
        return cross_refs
    
    def generate_relationship_reason(self, chapter1: Dict, chapter2: Dict, genre: str) -> str:
        """Generate human-readable reasons for cross-references"""
        shared_concepts = set(chapter1['concepts'].keys()).intersection(
            set(chapter2['concepts'].keys())
        )
        
        if not shared_concepts:
            return "Thematic connection"
        
        # Get top shared concepts
        top_shared = sorted(shared_concepts, 
                          key=lambda c: chapter1['concepts'].get(c, 0) + chapter2['concepts'].get(c, 0),
                          reverse=True)[:3]
        
        if genre == 'fiction':
            # Check for character overlap
            chars1 = set(chapter1.get('special_features', {}).get('characters', []))
            chars2 = set(chapter2.get('special_features', {}).get('characters', []))
            char_overlap = chars1.intersection(chars2)
            
            if char_overlap:
                return f"Shared characters: {', '.join(list(char_overlap)[:2])}"
            else:
                return f"Related themes: {', '.join(top_shared)}"
                
        elif genre == 'technical':
            return f"Related concepts: {', '.join(top_shared)}"
            
        elif genre == 'historical':
            return f"Connected topics: {', '.join(top_shared)}"
            
        else:
            return f"Shared concepts: {', '.join(top_shared)}"
    
    def classify_relationship_type(self, chapter1: Dict, chapter2: Dict, genre: str) -> str:
        """Classify the type of relationship between chapters"""
        if genre == 'fiction':
            return "narrative_connection"
        elif genre == 'technical':
            return "conceptual_dependency"
        elif genre == 'historical':
            return "chronological_relationship"
        elif genre == 'business':
            return "strategic_connection"
        else:
            return "thematic_relationship"

def analyze_pdf_content_for_crossref_universal(chunks: Dict[str, str], pdf_title: str = "") -> Dict[str, List[str]]:
    """Universal function to analyze PDF content and generate cross-references for any book type"""
    analyzer = UniversalPDFContentAnalyzer()
    
    # Combine all text for genre detection
    full_text = " ".join(chunks.values())
    
    # Detect genres
    detected_genres = analyzer.detect_genre(full_text, pdf_title)
    primary_genres = [genre for genre, score in detected_genres[:3]]
    
    print(f"🎯 Detected genres: {primary_genres}")
    
    # Analyze all chapters with genre awareness
    analysis = analyzer.analyze_content_structure(chunks, primary_genres)
    
    # Generate cross-references for each chapter
    cross_references = {}
    for chapter_id in chunks.keys():
        smart_refs = analyzer.generate_universal_cross_references(analysis, chapter_id)
        cross_references[chapter_id] = [ref['file'] for ref in smart_refs]
        
        # Debug output
        if smart_refs:
            print(f"📚 {chapter_id}: {len(smart_refs)} intelligent connections")
            for ref in smart_refs:
                print(f"   → {ref['file']}: {ref['reason']} (similarity: {ref['similarity_score']})")
    
    return cross_references

if __name__ == "__main__":
    # Run the server using stdio transport
    mcp.run(transport="stdio") 