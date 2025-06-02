#!/usr/bin/env python3
"""Entry point to run the Universal Cross-Reference MCP Server"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.mcp_server.server import main

if __name__ == "__main__":
    import asyncio
    asyncio.run(main()) 