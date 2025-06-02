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

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Initialize the MCP server
mcp = FastMCP("universal-crossref")

# In-memory storage for demonstration
projects = {}
current_project = None

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
            "purpose": "Automates the cross-referencing methodology for Markdown documentation",
            "key_concepts": {
                "hub_file": "Central documentation file (e.g., SYSTEM.md) that lists ALL mandatory reading requirements",
                "cross_reference_headers": "Headers added to each Markdown file pointing back to hub and related files",
                "mandatory_reading": "The principle that readers MUST read all linked files for complete understanding",
                "auto_watcher": "Background monitoring that automatically updates cross-references when files change"
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
            }
        },
        
        "best_practices": {
            "recommended_workflow": [
                "1. Start with scan_project to understand current state",
                "2. For new projects: create_hub_file + start_auto_crossref_watcher",
                "3. For existing projects: implement_crossref_methodology + start_auto_crossref_watcher", 
                "4. Use get_crossref_recommendations periodically for improvements",
                "5. Use manual tools (add_crossref_header, update_hub_mandatory_reading) for fine-tuning"
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
            ]
        },
        
        "troubleshooting": {
            "common_issues": {
                "watcher_not_updating": "Ensure watcher is started and monitoring correct directory path",
                "duplicate_headers": "Use add_crossref_header - it now detects and avoids duplicates",
                "hub_file_not_found": "Verify hub file name and path, or let start_auto_crossref_watcher create one",
                "json_parsing_errors": "Avoid debug print statements in server code - use PM2 logs for debugging"
            }
        }
    }
    
    return {
        "success": True,
        "documentation": documentation,
        "total_tools": 9,
        "server_version": "1.0.0",
        "summary": "Universal Cross-Reference MCP Server - Complete tool documentation and usage guide"
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

@mcp.tool()
def create_hub_file(file_path: str, title: str, description: str, related_files: list = None) -> dict:
    """Create a hub file with mandatory cross-reference reading requirements in standard format."""
    try:
        file_path_obj = Path(file_path)
        
        if file_path_obj.exists():
            return {"error": f"File already exists: {file_path}"}
        
        if related_files is None:
            related_files = []
        
        # Create the hub file content with methodology format
        content = f"""# 📄 **{title}**

*{description}*

---

# 📋 **CROSS-REFERENCE READING REQUIREMENT**

> **⚠️ IMPORTANT: When reading this file you HAVE TO (I repeat HAVE TO) read files {', '.join([f'`{f}`' for f in related_files])}**  
> **This is my system of cross-referencing MD files. When we make new MD files from now on, we will cross-reference like this to this main hub file**

---

## 🎯 **System Overview**

{description}

### **Core Principle**
> **Every person reading this documentation MUST read ALL related files to get the complete picture**

---

## 📋 **Document Hierarchy & Structure**

### **1. Central Hub Document**
**File**: `{file_path_obj.name}`
**Role**: **Primary system documentation** - the main entry point
**Contains**: 
- Complete system overview
- Core components and features
- **MANDATORY reading requirements** for all supplementary files

### **2. Supplementary Technical Documents**
**Files**: {', '.join([f'`{f}`' for f in related_files])}
**Role**: **Deep-dive technical analysis** and specific system aspects

---

## 🔧 **Implementation Rules**

When creating **ANY** new MD file in this project:

1. **Add cross-reference at the top** pointing back to this hub file
2. **Update this hub file** to include the new file in the mandatory reading list
3. **Update related files** if the new document relates to their content
4. **Follow the established formatting** with warning icons and strong language

---

## 📊 **Current Documentation Ecosystem**

### **Active Cross-Reference Network**
```
{file_path_obj.name} (CENTRAL HUB)
{chr(10).join([f'├── MUST READ: {f}' for f in related_files])}
└── Future files will be added here
```

---

*Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
*Cross-reference system ensures complete understanding across all documentation.*
"""
        
        # Write the file
        file_path_obj.write_text(content, encoding="utf-8")
        
        return {
            "success": True,
            "file_created": str(file_path_obj),
            "related_files": related_files,
            "summary": f"Created hub file {file_path_obj.name} with {len(related_files)} cross-references"
        }
        
    except Exception as e:
        return {"error": f"Failed to create hub file: {str(e)}"}

@mcp.tool()
def add_crossref_header(file_path: str, hub_file: str, related_files: list = None) -> dict:
    """Add cross-reference header to an existing file in standard format."""
    try:
        file_path_obj = Path(file_path)
        
        if not file_path_obj.exists():
            return {"error": f"File not found: {file_path}"}
        
        if related_files is None:
            related_files = []
        
        # Read existing content
        try:
            existing_content = file_path_obj.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            existing_content = file_path_obj.read_text(encoding="latin-1")
        
        # Check if cross-reference header already exists
        if "Cross-reference:" in existing_content:
            return {
                "success": True,
                "status": "already_exists",
                "file_updated": str(file_path_obj),
                "summary": f"File {file_path_obj.name} already contains a cross-reference header. No changes made."
            }
        
        # Extract title from first line if it's a markdown header
        lines = existing_content.split('\n')
        title_line = ""
        content_start = 0
        
        for i, line in enumerate(lines):
            if line.strip().startswith('#'):
                title_line = line.strip()
                content_start = i + 1
                break
        
        # Create cross-reference header
        other_files_text = ""
        if related_files:
            other_files_text = f" Also read with {', '.join([f'`{f}`' for f in related_files])} for complete understanding."
        
        crossref_header = f"""
**Cross-reference**: This document supplements the main system documentation in `{hub_file}`.{other_files_text}

---

"""
        
        # Reconstruct the file with cross-reference header
        if title_line:
            # Insert after title
            new_content = title_line + "\n\n"
            if content_start < len(lines) and lines[content_start].strip():
                # Add description line if it exists
                description_line = lines[content_start].strip()
                if description_line and not description_line.startswith('#'):
                    new_content += f"*{description_line}*\n\n"
                    content_start += 1
            
            new_content += crossref_header
            new_content += '\n'.join(lines[content_start:])
        else:
            # No title found, add at the beginning
            new_content = crossref_header + existing_content
        
        # Write the updated content
        file_path_obj.write_text(new_content, encoding="utf-8")
        
        return {
            "success": True,
            "file_updated": str(file_path_obj),
            "hub_file": hub_file,
            "related_files": related_files,
            "summary": f"Added cross-reference header to {file_path_obj.name}"
        }
        
    except Exception as e:
        return {"error": f"Failed to add cross-reference header: {str(e)}"}

@mcp.tool()
def update_hub_mandatory_reading(hub_file_path: str, new_files: list = None, files_to_remove: list = None) -> dict:
    """Update the mandatory reading list in a hub file with new files or remove existing ones."""
    try:
        hub_path_obj = Path(hub_file_path)
        
        if not hub_path_obj.exists():
            return {"error": f"Hub file not found: {hub_file_path}"}

        if new_files is None:
            new_files = []
        if files_to_remove is None:
            files_to_remove = []
        
        # Read the hub file
        try:
            content = hub_path_obj.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = hub_path_obj.read_text(encoding="latin-1")
        
        lines = content.split('\n')
        updated_lines = list(lines) # Work on a mutable copy
        
        # Part 1: Update the main cross-reference reading requirement line
        main_crossref_line_updated = False
        in_crossref_section = False
        
        temp_updated_lines_part1 = []
        for line_idx, line in enumerate(updated_lines):
            if "CROSS-REFERENCE READING REQUIREMENT" in line:
                in_crossref_section = True
                temp_updated_lines_part1.append(line)
            elif in_crossref_section and line.strip().startswith("> **⚠️ IMPORTANT:"):
                existing_files = []
                if 'read files' in line:
                    files_part = line.split('read files')[1].split('**')[0]
                    existing_files = re.findall(r'`([^`]+)`', files_part)
                
                current_files_set = set(existing_files)
                for new_file in new_files: current_files_set.add(new_file)
                for old_file in files_to_remove: current_files_set.discard(old_file)
                all_files_list = sorted(list(current_files_set))
                
                files_text = ', '.join([f'`{f}`' for f in all_files_list]) if all_files_list else "[no other files currently]"
                new_line_content = f"> **⚠️ IMPORTANT: When reading this file you HAVE TO (I repeat HAVE TO) read files {files_text}**"
                
                original_line_parts = line.split('**', 1)
                if len(original_line_parts) > 1 and 'This is my system' in original_line_parts[1]:
                    # Preserve the descriptive part of the line
                    descriptive_part_match = re.search(r'(\*\*\\s*This is my system.*)', line)
                    if descriptive_part_match:
                         new_line = new_line_content + "  \\n> " + descriptive_part_match.group(1).replace("** ","",1) # Keep original formatting
                    else: # Fallback if regex fails
                         new_line = new_line_content + original_line_parts[1][original_line_parts[1].find("This is my system")-len("**  \\n> "):]
                else:
                    new_line = new_line_content

                temp_updated_lines_part1.append(new_line)
                if line != new_line: # Check if actual change happened
                    main_crossref_line_updated = True
            elif in_crossref_section and line.strip().startswith("---"):
                in_crossref_section = False
                temp_updated_lines_part1.append(line)
            else:
                temp_updated_lines_part1.append(line)
        
        if main_crossref_line_updated : # only assign if an update truly happened
             updated_lines = temp_updated_lines_part1
        elif not any("CROSS-REFERENCE READING REQUIREMENT" in l for l in updated_lines): # section not found
             pass # main_crossref_line_updated remains false
        else: # section found but no changes made to the line itself.
             main_crossref_line_updated = True # still count as "processed" if files were already there or list became empty as requested


        # Part 2: Update the Active Cross-Reference Network diagram
        ecosystem_diagram_updated = False
        # Use 'updated_lines' from Part 1 for further modifications
        
        diagram_section_start_idx = -1
        for i, line_content in enumerate(updated_lines):
            if "Active Cross-Reference Network" in line_content:
                diagram_section_start_idx = i
                break
        
        if diagram_section_start_idx != -1:
            code_block_start_idx = -1
            code_block_end_idx = -1
            
            # Find the ``` start after the "Active Cross-Reference Network" header
            for i in range(diagram_section_start_idx + 1, len(updated_lines)):
                if updated_lines[i].strip().startswith("```"):
                    code_block_start_idx = i
                    break
            
            if code_block_start_idx != -1:
                # Find the ``` end
                for i in range(code_block_start_idx + 1, len(updated_lines)):
                    if updated_lines[i].strip() == "```":
                        code_block_end_idx = i
                        break

                if code_block_end_idx != -1:
                    # Extract existing files from the current diagram (within updated_lines)
                    existing_files_in_diagram = set()
                    hub_name_line = ""
                    for i in range(code_block_start_idx + 1, code_block_end_idx):
                        diag_line = updated_lines[i].strip()
                        if "(CENTRAL HUB)" in diag_line and not hub_name_line:
                             hub_name_line = updated_lines[i] # Keep the hub line
                        elif diag_line.startswith("├── MUST READ:"):
                            existing_files_in_diagram.add(diag_line.replace("├── MUST READ:", "").strip())
                    
                    current_diag_files_set = existing_files_in_diagram.copy()
                    for new_file in new_files: current_diag_files_set.add(new_file)
                    for old_file in files_to_remove: current_diag_files_set.discard(old_file)
                    sorted_diag_files = sorted(list(current_diag_files_set))
                    
                    new_diagram_lines = [updated_lines[code_block_start_idx]] # Start with ```
                    if hub_name_line: # Add hub line if found
                        new_diagram_lines.append(hub_name_line)
                    elif updated_lines[code_block_start_idx+1].strip().endswith("(CENTRAL HUB)"): # Fallback for hub line
                         new_diagram_lines.append(updated_lines[code_block_start_idx+1])


                    for f_diag in sorted_diag_files:
                        new_diagram_lines.append(f'├── MUST READ: {f_diag}')
                    new_diagram_lines.append("└── Future files will be added here")
                    new_diagram_lines.append(updated_lines[code_block_end_idx]) # End with ```
                    
                    # Check if the diagram content actually changed
                    original_diagram_lines = updated_lines[code_block_start_idx : code_block_end_idx + 1]
                    if original_diagram_lines != new_diagram_lines:
                        updated_lines = updated_lines[:code_block_start_idx] + new_diagram_lines + updated_lines[code_block_end_idx+1:]
                        ecosystem_diagram_updated = True
                    else: # No change in diagram content
                         ecosystem_diagram_updated = True # Count as "processed"

        if not main_crossref_line_updated and not ecosystem_diagram_updated:
            return {"error": "Could not find or update cross-reference section or ecosystem diagram"}

        # Write the updated content
        new_content = '\n'.join(updated_lines)
        hub_path_obj.write_text(new_content, encoding="utf-8")
        
        return {
            "success": True,
            "hub_file_updated": str(hub_path_obj),
            "files_added": new_files,
            "files_removed": files_to_remove,
            "summary": f"Updated mandatory reading list in {hub_path_obj.name}. Added: {len(new_files)}, Removed: {len(files_to_remove)}"
        }
        
    except Exception as e:
        return {"error": f"Failed to update hub file: {str(e)}"}

@mcp.tool()
def implement_crossref_methodology(project_path: str, hub_file_name: str = "SYSTEM.md", project_title: str = None) -> dict:
    """Implement the complete cross-reference methodology for a project."""
    try:
        project_path_obj = Path(project_path)
        
        if not project_path_obj.exists():
            return {"error": f"Project path not found: {project_path}"}
        
        if not project_title:
            project_title = f"{project_path_obj.name} System Documentation"
        
        # Find markdown files
        md_files = []
        for md_file in project_path_obj.rglob("*.md"):
            if not any(ignore_dir in md_file.parts for ignore_dir in {".git", "node_modules", "__pycache__"}):
                relative_path = md_file.relative_to(project_path_obj)
                md_files.append(str(relative_path))
        
        # Remove the hub file from the list if it exists
        md_files = [f for f in md_files if not f.endswith(hub_file_name)]
        
        hub_file_path = project_path_obj / hub_file_name
        
        operations = []
        
        # Step 1: Create or update hub file
        if not hub_file_path.exists():
            hub_result = create_hub_file(
                str(hub_file_path),
                project_title,
                f"Comprehensive system documentation for {project_path_obj.name}",
                md_files
            )
            operations.append({"operation": "create_hub", "result": hub_result})
        else:
            # Update existing hub file
            update_result = update_hub_mandatory_reading(str(hub_file_path), md_files)
            operations.append({"operation": "update_hub", "result": update_result})
        
        # Step 2: Add cross-reference headers to all markdown files
        for md_file in md_files:
            full_md_path = project_path_obj / md_file
            other_files = [f for f in md_files if f != md_file][:3]  # Limit to 3 related files
            
            header_result = add_crossref_header(
                str(full_md_path),
                hub_file_name,
                other_files
            )
            operations.append({"operation": "add_header", "file": md_file, "result": header_result})
        
        # Count successful operations
        successful_ops = sum(1 for op in operations if op["result"].get("success", False))
        
        return {
            "success": True,
            "project_path": str(project_path_obj),
            "hub_file": hub_file_name,
            "markdown_files_processed": len(md_files),
            "operations_completed": successful_ops,
            "total_operations": len(operations),
            "operations": operations,
            "summary": f"Implemented cross-reference methodology for {project_path_obj.name}: {successful_ops}/{len(operations)} operations successful"
        }
        
    except Exception as e:
        return {"error": f"Failed to implement cross-reference methodology: {str(e)}"}

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
        '.yml': 'yaml'
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

if __name__ == "__main__":
    # Run the server using stdio transport
    mcp.run(transport="stdio") 