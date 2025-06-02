# 🔗 Universal Cross-Reference MCP Server

A powerful cross-reference documentation management system for Markdown files, integrated with [Cursor IDE](https://cursor.sh/) via the Model Context Protocol (MCP).

## 🌟 Overview

Universal Cross-Reference MCP Server automates the cross-referencing methodology for documentation, creating bidirectional links between related files and ensuring readers have access to all necessary context.

The system:
- Creates and maintains a central "hub" file that lists all related documentation
- Automatically adds cross-reference headers to Markdown files
- Watches for file changes and updates references in real-time
- Provides tooling for analysis and implementing the methodology in existing projects

## 🚀 Features

- **Automated Cross-Referencing**: Automatically manage links between related documentation files
- **Real-time Watching**: File system monitoring that updates cross-references when files are created, deleted, or moved
- **Comprehensive Tools**: 9 specialized tools for managing cross-reference documentation
- **Cursor IDE Integration**: Seamless integration with Cursor IDE via Model Context Protocol
- **LLM-Friendly**: Designed to be easily used by Large Language Models for documentation management

## 📋 Requirements

- Python 3.8+
- FastAPI
- Watchdog (for file system monitoring)
- MCP library (for Cursor integration)
- PM2 (for process management)

## 🛠️ Installation

1. Clone this repository:
```bash
git clone https://github.com/yourusername/universal-crossref-mcp.git
cd universal-crossref-mcp
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Install PM2 (if not already installed):
```bash
npm install -g pm2
```

4. Configure your environment:
```bash
cp env.example .env
# Edit .env with your configuration
```

5. Create the PM2 configuration:
```bash
cp ecosystem.config.example.js ecosystem.config.js
# Edit ecosystem.config.js as needed
```

## 🚀 Running the Server

Start the server using PM2:

```bash
pm2 start ecosystem.config.js
```

To stop the server:

```bash
pm2 stop ecosystem.config.js
```

## 🔌 Cursor IDE Integration

1. Open Cursor IDE
2. Go to Settings
3. Navigate to MCP settings
4. Add the following configuration:

```json
{
  "universal-crossref": {
    "command": "python3 /path/to/universal-crossref-mcp/src/mcp_server/simple_server.py",
    "enabled": true,
    "metadata": {
      "description": "Universal Cross-Reference Documentation System"
    }
  }
}
```

## 🧰 Available Tools

The server provides 9 tools for managing cross-references:

1. **analyze_file**: Analyze a single file for cross-reference patterns
2. **scan_project**: Scan a project directory for files and basic analysis
3. **get_crossref_recommendations**: Get recommendations for improving cross-reference coverage
4. **create_hub_file**: Create a hub file with mandatory cross-reference reading requirements
5. **add_crossref_header**: Add cross-reference header to an existing file
6. **update_hub_mandatory_reading**: Update the mandatory reading list in a hub file
7. **implement_crossref_methodology**: Apply the complete methodology to a project
8. **start_auto_crossref_watcher**: Start automatic cross-reference monitoring
9. **stop_auto_crossref_watcher**: Stop automatic cross-reference monitoring
10. **get_tool_documentation**: Get comprehensive documentation for all tools

For detailed documentation on each tool, use the `get_tool_documentation` tool.

## 📖 Usage Example

### Starting with a New Project

```python
# 1. Create a hub file for your project
mcp_universal-crossref_create_hub_file(
    file_path="/path/to/project/SYSTEM.md",
    title="Project Documentation Hub",
    description="Central documentation for the project",
    related_files=["api.md", "architecture.md"]
)

# 2. Start the automatic watcher
mcp_universal-crossref_start_auto_crossref_watcher(
    project_path="/path/to/project",
    hub_file_name="SYSTEM.md"
)

# Now when you create new Markdown files, they'll be automatically cross-referenced
# The hub file will be updated, and headers will be added to new files
```

### Working with an Existing Project

```python
# 1. Scan your project to analyze its structure
mcp_universal-crossref_scan_project(
    project_path="/path/to/existing/project",
    project_name="MyProject"
)

# 2. Implement cross-reference methodology across all files
mcp_universal-crossref_implement_crossref_methodology(
    project_path="/path/to/existing/project",
    hub_file_name="README.md",
    project_title="Existing Project Documentation"
)

# 3. Start automatic watcher for ongoing management
mcp_universal-crossref_start_auto_crossref_watcher(
    project_path="/path/to/existing/project",
    hub_file_name="README.md"
)
```

## 📋 The Cross-Reference Methodology

This system implements a specific documentation methodology with these key principles:

1. **Central Hub**: A main documentation file that lists all related files
2. **Mandatory Reading**: Explicit requirement that readers must read all related files
3. **Bidirectional Links**: Each file references the hub and other related files
4. **Standardized Headers**: Consistent cross-reference format at the top of each file
5. **Network Visualization**: Clear diagram showing how files relate to each other

## 📄 License

This project is licensed under the Mozilla Public License 2.0 (MPL-2.0) - see the [LICENSE](LICENSE) file for details.

The MPL-2.0 is a copyleft license that allows for commercial use, modification, distribution, and private use, while ensuring that modifications to the code remain open source.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📬 Contact

For questions or support, please open an issue on this repository. 