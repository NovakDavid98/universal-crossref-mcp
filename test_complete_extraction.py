#!/usr/bin/env python3
"""Complete test of PDF extraction creating actual markdown files"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_complete_extraction():
    """Test complete PDF extraction with file creation"""
    
    # Import the main extraction function
    try:
        # Import the required components
        from mcp_server.simple_server import (
            extract_pdf_text, 
            chunk_pdf_content, 
            generate_chunk_filenames,
            create_hub_file,
            add_crossref_header
        )
        print('✅ All PDF functions imported successfully')
    except ImportError as e:
        print(f'❌ Failed to import functions: {e}')
        return
    
    # Test parameters
    pdf_path = Path('../TheUniversalOne1926WalterRussell.pdf')
    output_dir = Path('./TheUniversalOne_extracted')
    max_chunks = 8  # Smaller number for faster processing
    
    if not pdf_path.exists():
        print(f'❌ PDF not found: {pdf_path}')
        return
    
    print(f'📖 Starting complete extraction of: {pdf_path}')
    print(f'📂 Output directory: {output_dir}')
    
    try:
        # Create output directory
        output_dir.mkdir(exist_ok=True)
        print(f'✅ Created output directory: {output_dir}')
        
        # Step 1: Extract text
        print('\\n🔧 Step 1: Extracting text...')
        extraction_result = extract_pdf_text(pdf_path)
        
        if not extraction_result["success"]:
            print(f'❌ Text extraction failed: {extraction_result.get("error")}')
            return
        
        text = extraction_result["text"]
        print(f'✅ Extracted {len(text):,} characters with quality {extraction_result["quality"]:.2f}')
        
        # Step 2: Chunk content
        print('\\n🔧 Step 2: Chunking content...')
        chunks = chunk_pdf_content(text, pdf_path.name, max_chunks)
        print(f'✅ Created {len(chunks)} chunks')
        
        # Step 3: Generate filenames
        print('\\n🔧 Step 3: Generating filenames...')
        filenames = generate_chunk_filenames(pdf_path.name, chunks)
        print(f'✅ Generated {len(filenames)} filenames')
        
        # Step 4: Create markdown files
        print('\\n🔧 Step 4: Creating markdown files...')
        created_files = []
        
        for i, (chunk_content, filename) in enumerate(zip(chunks, filenames)):
            chunk_file_path = output_dir / filename
            
            markdown_content = f"""# {filename.replace('.md', '').replace('_', ' ').title()}

**Extracted from PDF**: {pdf_path.name}
**Chunk**: {i+1} of {len(chunks)}
**Words**: ~{len(chunk_content.split()):,}

---

{chunk_content}
"""
            
            # Write file
            chunk_file_path.write_text(markdown_content, encoding="utf-8")
            created_files.append(str(chunk_file_path))
            print(f'   ✅ Created: {filename}')
        
        # Step 5: Create hub file
        print('\\n🔧 Step 5: Creating hub file...')
        hub_filename = f"{pdf_path.stem}_hub.md"
        hub_file_path = output_dir / hub_filename
        
        # Get relative filenames for hub
        relative_files = [Path(f).name for f in created_files]
        
        hub_result = create_hub_file(
            str(hub_file_path),
            f"{pdf_path.stem} Knowledge Hub",
            f"Cross-referenced content extracted from {pdf_path.name}",
            relative_files
        )
        
        if hub_result.get("success"):
            print(f'   ✅ Created hub file: {hub_filename}')
        else:
            print(f'   ❌ Hub creation failed: {hub_result.get("error")}')
        
        # Step 6: Add cross-reference headers
        print('\\n🔧 Step 6: Adding cross-reference headers...')
        headers_added = 0
        
        for chunk_file in created_files:
            # Get other files as related (limit to 3)
            other_files = [Path(f).name for f in created_files if f != chunk_file][:3]
            
            header_result = add_crossref_header(
                chunk_file,
                hub_filename,
                other_files
            )
            
            if header_result.get("success"):
                headers_added += 1
                print(f'   ✅ Added header to: {Path(chunk_file).name}')
        
        # Final summary
        print(f'\\n🎉 EXTRACTION COMPLETE!')
        print(f'📊 Summary:')
        print(f'   📖 PDF processed: {pdf_path.name}')
        print(f'   📂 Output directory: {output_dir}')
        print(f'   📄 Files created: {len(created_files)}')
        print(f'   🔗 Cross-reference headers: {headers_added}')
        print(f'   📋 Hub file: {hub_filename}')
        print(f'   ⭐ Quality score: {extraction_result["quality"]:.2f}')
        print(f'   📏 Total content: {len(text):,} characters')
        
        # List all created files
        print(f'\\n📁 Created files:')
        for file_path in created_files:
            file_size = Path(file_path).stat().st_size
            print(f'   - {Path(file_path).name} ({file_size:,} bytes)')
        print(f'   - {hub_filename} (hub file)')
        
    except Exception as e:
        print(f'❌ Error during extraction: {e}')
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_complete_extraction() 