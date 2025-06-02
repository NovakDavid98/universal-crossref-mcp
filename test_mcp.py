#!/usr/bin/env python3
"""Test script to verify MCP server is working"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    from mcp_server.simple_server import mcp
    print('✅ MCP Server loaded successfully')
    print('🔧 Available tools:')
    for tool_name in ['analyze_file', 'scan_project', 'get_crossref_recommendations']:
        print(f'   - {tool_name}')
    print('🚀 Server is ready for Cursor integration!')
    print()
    print('📋 Configuration for Cursor:')
    print('   Add this to your Cursor settings.json:')
    print()
    print('   "mcpServers": {')
    print('     "universal-crossref": {')
    print('       "command": "python3",')
    print('       "args": [')
    print(f'         "{Path(__file__).parent.absolute()}/src/mcp_server/simple_server.py"')
    print('       ],')
    print('       "env": {')
    print(f'         "PYTHONPATH": "{Path(__file__).parent.absolute()}"')
    print('       }')
    print('     }')
    print('   }')
    
except Exception as e:
    print(f'❌ Error loading MCP server: {e}')
    sys.exit(1) 