#!/usr/bin/env python3
"""Simple sync test for PDF extraction"""

import sys
from pathlib import Path

# Add the src path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from mcp_server.simple_server import extract_pdf_to_markdown

def sync_test():
    """Test sync extraction with small chunk count"""
    print("🔄 Quick Sync PDF Extraction Test")
    print("=" * 50)
    
    # Test with Walter Russell PDF
    pdf_path = "/home/frontalneuralcortex/crossrefference/TheUniversalOne1926WalterRussell.pdf"
    output_dir = "/tmp/quick_test_sync"
    
    print(f"📄 Testing with: {pdf_path}")
    print(f"📁 Output: {output_dir}")
    
    try:
        result = extract_pdf_to_markdown(
            pdf_path=pdf_path,
            output_dir=output_dir,
            max_chunks=2,  # Very small for quick test
            create_hub=True,
            hub_file_name="SYSTEM.md"
        )
        
        if result.get("success"):
            quality = result.get("quality_score", 0)
            files = len(result.get("files_created", []))
            hub_used = result.get("hub_file_used", "unknown")
            
            print(f"🎉 SYNC SUCCESS!")
            print(f"   Quality Score: {quality:.3f}")
            print(f"   Files Created: {files}")
            print(f"   Hub Used: {hub_used}")
            
            # Check first file header
            first_file = result.get("files_created", [])
            if first_file:
                with open(first_file[0], 'r') as f:
                    header = f.read(500)
                
                print(f"\n📋 First 3 header lines:")
                for i, line in enumerate(header.split('\n')[:3], 1):
                    print(f"  {i}: {line}")
                
                if "Cross-reference: SYSTEM.md" in header:
                    print("✅ Sync Header: CORRECT - References SYSTEM.md")
                else:
                    print("❌ Sync Header: INCORRECT - Wrong hub reference")
                    
                if f"Quality Score: {quality:.2f}" in header:
                    print(f"✅ Sync Quality: CORRECT - Shows {quality:.3f}")
                else:
                    print("⚠️ Sync Quality: Check manually")
            
            return True
            
        else:
            print(f"❌ SYNC FAILED: {result.get('error')}")
            return False
            
    except Exception as e:
        print(f"💥 SYNC Exception: {str(e)}")
        return False

if __name__ == "__main__":
    success = sync_test()
    print(f"\n🎯 Sync test result: {'PASSED' if success else 'FAILED'}") 