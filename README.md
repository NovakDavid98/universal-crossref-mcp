# 🔗 Universal Cross-Reference MCP Server

**Intelligent cross-reference system for any codebase via Model Context Protocol**

## Overview

The Universal Cross-Reference MCP Server applies a comprehensive cross-reference methodology to ANY project, ensuring complete understanding across all files and codebases. This system enforces "forced comprehensive understanding" for your entire development workflow.

## Features

- 🌐 **Universal**: Works with any project type, any file structure
- ⚡ **Async**: High-performance scanning for large codebases
- 🧠 **Intelligent**: Learns your cross-reference patterns
- 🔗 **Automated**: Maintains cross-references as you develop
- 📊 **PostgreSQL**: Robust database backend for scalability
- 🎯 **MCP Native**: Direct integration with Cursor IDE and other MCP-compatible tools

## Project Structure

```
universal-crossref-mcp/
├── src/
│   ├── mcp_server/          # Main MCP server implementation
│   ├── scanner/             # Async file scanning engine
│   ├── analyzer/            # Content analysis and pattern detection
│   ├── database/            # PostgreSQL models and operations
│   └── utils/               # Shared utilities
├── config/                  # Configuration templates and schemas
├── migrations/              # Database migrations
├── tests/                   # Test suite
├── docs/                    # Documentation
└── examples/                # Example configurations
```

## Quick Start

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Setup Database**
   ```bash
   python -m src.database.init_db
   ```

3. **Configure for Your Project**
   ```bash
   python -m src.mcp_server.setup
   ```

4. **Add to Cursor IDE**
   ```json
   {
     "mcpServers": {
       "universal-crossref": {
         "command": "python",
         "args": ["-m", "src.mcp_server.main"]
       }
     }
   }
   ```

## Development Status

🔨 **In Development** - Following step-by-step implementation plan

## License

MIT License - See LICENSE file for details 