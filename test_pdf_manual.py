#!/usr/bin/env python3
"""Manual test script for PDF extraction functionality"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_pdf_extraction():
    """Test PDF extraction manually"""
    
    # Import the functions
    try:
        from mcp_server.simple_server import extract_pdf_text, chunk_pdf_content, generate_chunk_filenames
        print('✅ PDF extraction functions imported successfully')
    except ImportError as e:
        print(f'❌ Failed to import functions: {e}')
        return
    
    # Test with the Walter Russell PDF
    pdf_path = Path('../TheUniversalOne1926WalterRussell.pdf')
    
    if not pdf_path.exists():
        print(f'❌ PDF not found: {pdf_path}')
        return
    
    print(f'📖 Testing with PDF: {pdf_path}')
    print(f'📊 PDF size: {pdf_path.stat().st_size / 1024 / 1024:.1f} MB')
    
    # Step 1: Extract text
    print('\n🔧 Step 1: Extracting text...')
    try:
        extraction_result = extract_pdf_text(pdf_path)
        
        if not extraction_result["success"]:
            print(f'❌ Text extraction failed: {extraction_result.get("error")}')
            return
        
        text = extraction_result["text"]
        quality = extraction_result["quality"]
        strategy = extraction_result["strategy_used"]
        
        print(f'✅ Text extracted successfully')
        print(f'   Strategy used: {strategy}')
        print(f'   Quality score: {quality:.2f}')
        print(f'   Text length: {len(text):,} characters')
        print(f'   Sample: {text[:200]}...')
        
    except Exception as e:
        print(f'❌ Exception during text extraction: {e}')
        return
    
    # Step 2: Chunk content
    print('\n🔧 Step 2: Chunking content...')
    try:
        chunks = chunk_pdf_content(text, pdf_path.name, max_chunks=10)
        print(f'✅ Content chunked into {len(chunks)} pieces')
        
        for i, chunk in enumerate(chunks[:3]):  # Show first 3 chunks
            print(f'   Chunk {i+1}: {len(chunk):,} characters')
        
    except Exception as e:
        print(f'❌ Exception during chunking: {e}')
        return
    
    # Step 3: Generate filenames
    print('\n🔧 Step 3: Generating filenames...')
    try:
        filenames = generate_chunk_filenames(pdf_path.name, chunks)
        print(f'✅ Generated {len(filenames)} filenames')
        
        for i, filename in enumerate(filenames[:5]):  # Show first 5 filenames
            print(f'   File {i+1}: {filename}')
        
    except Exception as e:
        print(f'❌ Exception during filename generation: {e}')
        return
    
    print('\n🎉 All PDF extraction components working correctly!')
    print(f'📋 Ready to create {len(chunks)} markdown files')

if __name__ == "__main__":
    test_pdf_extraction() 