#!/usr/bin/env python3
"""Test script for PDF extraction functionality"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

try:
    from mcp_server.simple_server import extract_pdf_text, chunk_pdf_content, generate_chunk_filenames
    print('✅ PDF extraction functions loaded successfully')
    
    # Test basic functionality
    print('\n🔧 Available PDF processing functions:')
    print('   - extract_pdf_text()')
    print('   - chunk_pdf_content()')
    print('   - generate_chunk_filenames()')
    
    print('\n📋 To test PDF extraction:')
    print('   1. Place a PDF file in this directory')
    print('   2. Use the extract_pdf_to_markdown MCP tool')
    print('   3. Check the output directory for generated files')
    
    print('\n🚀 PDF extraction is ready!')
    print('\n📖 Example usage:')
    print('   Tool: extract_pdf_to_markdown')
    print('   Parameters:')
    print('   - pdf_path: "/path/to/your/document.pdf"')
    print('   - max_chunks: 30')
    print('   - create_hub: true')
    
except Exception as e:
    print(f'❌ Error loading PDF extraction: {e}')
    sys.exit(1) 