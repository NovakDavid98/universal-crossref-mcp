#!/usr/bin/env python3
"""Simple test of PDF extraction creating basic markdown files"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_simple_extraction():
    """Test simple PDF extraction with file creation"""
    
    # Import the core extraction functions
    try:
        from mcp_server.simple_server import (
            extract_pdf_text, 
            chunk_pdf_content, 
            generate_chunk_filenames
        )
        print('✅ PDF extraction functions imported successfully')
    except ImportError as e:
        print(f'❌ Failed to import functions: {e}')
        return
    
    # Test parameters
    pdf_path = Path('../TheUniversalOne1926WalterRussell.pdf')
    output_dir = Path('./TheUniversalOne_simple_extracted')
    max_chunks = 8  # Smaller number for faster processing
    
    if not pdf_path.exists():
        print(f'❌ PDF not found: {pdf_path}')
        return
    
    print(f'📖 Starting simple extraction of: {pdf_path}')
    print(f'📂 Output directory: {output_dir}')
    
    try:
        # Create output directory
        output_dir.mkdir(exist_ok=True)
        print(f'✅ Created output directory: {output_dir}')
        
        # Step 1: Extract text
        print('\n🔧 Step 1: Extracting text...')
        extraction_result = extract_pdf_text(pdf_path)
        
        if not extraction_result["success"]:
            print(f'❌ Text extraction failed: {extraction_result.get("error")}')
            return
        
        text = extraction_result["text"]
        print(f'✅ Extracted {len(text):,} characters with quality {extraction_result["quality"]:.2f}')
        
        # Step 2: Chunk content
        print('\n🔧 Step 2: Chunking content...')
        chunks = chunk_pdf_content(text, pdf_path.name, max_chunks)
        print(f'✅ Created {len(chunks)} chunks')
        
        # Step 3: Generate filenames
        print('\n🔧 Step 3: Generating filenames...')
        filenames = generate_chunk_filenames(pdf_path.name, chunks)
        print(f'✅ Generated {len(filenames)} filenames')
        
        # Step 4: Create markdown files
        print('\n🔧 Step 4: Creating markdown files...')
        created_files = []
        
        for i, (chunk_content, filename) in enumerate(zip(chunks, filenames)):
            chunk_file_path = output_dir / filename
            
            markdown_content = f"""# {filename.replace('.md', '').replace('_', ' ').title()}

**Extracted from PDF**: {pdf_path.name}
**Chunk**: {i+1} of {len(chunks)}
**Words**: ~{len(chunk_content.split()):,}
**Quality Score**: {extraction_result["quality"]:.2f}
**Extraction Strategy**: {extraction_result["strategy_used"]}

---

{chunk_content}
"""
            
            # Write file
            chunk_file_path.write_text(markdown_content, encoding="utf-8")
            created_files.append(str(chunk_file_path))
            print(f'   ✅ Created: {filename} ({len(chunk_content):,} chars)')
        
        # Step 5: Create simple index file
        print('\n🔧 Step 5: Creating index file...')
        index_filename = f"{pdf_path.stem}_index.md"
        index_file_path = output_dir / index_filename
        
        index_content = f"""# {pdf_path.stem} - Extracted Content Index

**Source PDF**: {pdf_path.name}
**Extraction Date**: {extraction_result.get('timestamp', 'Unknown')}
**Quality Score**: {extraction_result["quality"]:.2f}
**Strategy Used**: {extraction_result["strategy_used"]}
**Total Characters**: {len(text):,}
**Total Chunks**: {len(chunks)}

## 📚 Available Chapters

"""
        
        for i, (filename, chunk) in enumerate(zip(filenames, chunks), 1):
            word_count = len(chunk.split())
            index_content += f"{i}. [{filename.replace('.md', '').replace('_', ' ').title()}](./{filename}) (~{word_count:,} words)\\n"
        
        index_content += f"""

## 📖 Reading Instructions

This content was extracted from "{pdf_path.name}" and divided into {len(chunks)} manageable chapters. 
Each chapter contains approximately {len(text.split()) // len(chunks):,} words.

**Quality Assessment**: {extraction_result["quality"]:.2f}/1.0 - {"Excellent" if extraction_result["quality"] > 0.8 else "Good" if extraction_result["quality"] > 0.6 else "Fair"}

**Extraction Method**: {extraction_result["strategy_used"]}
"""
        
        index_file_path.write_text(index_content, encoding="utf-8")
        print(f'   ✅ Created index file: {index_filename}')
        
        # Final summary
        print('\n🎉 SIMPLE EXTRACTION COMPLETE!')
        print(f'📊 Summary:')
        print(f'   📖 PDF processed: {pdf_path.name}')
        print(f'   📂 Output directory: {output_dir}')
        print(f'   📄 Markdown files: {len(created_files)}')
        print(f'   📋 Index file: {index_filename}')
        print(f'   ⭐ Quality score: {extraction_result["quality"]:.2f}')
        print(f'   📏 Total content: {len(text):,} characters')
        print(f'   🔧 Strategy used: {extraction_result["strategy_used"]}')
        
        # List all created files
        print('\n📁 Created files:')
        for file_path in created_files:
            file_size = Path(file_path).stat().st_size
            print(f'   - {Path(file_path).name} ({file_size:,} bytes)')
        print(f'   - {index_filename} (index file)')
        
        print('\n🎯 Next steps:')
        print(f'   1. Review the extracted content in: {output_dir}')
        print(f'   2. Start with the index file: {index_filename}')
        print(f'   3. Use MCP tools to add cross-references if needed')
        
    except Exception as e:
        print(f'❌ Error during extraction: {e}')
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_simple_extraction() 