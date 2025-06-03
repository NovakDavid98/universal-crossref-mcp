#!/usr/bin/env python3
"""Quick test for async PDF extraction fixes"""

import asyncio
import sys
from pathlib import Path

# Add the src path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from mcp_server.simple_server import (
    extract_pdf_to_markdown_async,
    check_pdf_extraction_status
)

async def quick_test():
    """Quick test of async extraction"""
    print("🚀 Quick Async PDF Extraction Test")
    print("=" * 50)
    
    # Test with Walter Russell PDF
    pdf_path = "/home/frontalneuralcortex/crossrefference/TheUniversalOne1926WalterRussell.pdf"
    output_dir = "/tmp/quick_test_async"
    
    print(f"📄 Testing with: {pdf_path}")
    print(f"📁 Output: {output_dir}")
    
    try:
        # Start async extraction
        result = extract_pdf_to_markdown_async(
            pdf_path=pdf_path,
            output_dir=output_dir,
            max_chunks=3,  # Small for quick test
            create_hub=True,
            hub_file_name="SYSTEM.md"
        )
        
        if result.get("success"):
            task_id = result["task_id"]
            print(f"✅ Async extraction started: {task_id}")
            
            # Monitor progress briefly
            for i in range(30):  # Max 60 seconds
                await asyncio.sleep(2)
                status = check_pdf_extraction_status(task_id)
                
                current_status = status.get("status", "unknown")
                progress = status.get("progress", 0)
                
                print(f"📊 {progress:.1f}% - {current_status}")
                
                if current_status == "completed":
                    final_result = status.get("result", {})
                    quality = final_result.get("quality_score", 0)
                    files = len(final_result.get("files_created", []))
                    
                    print(f"🎉 SUCCESS!")
                    print(f"   Quality Score: {quality:.3f}")
                    print(f"   Files Created: {files}")
                    print(f"   Hub Used: {final_result.get('hub_file_used', 'unknown')}")
                    
                    # Check first file header
                    first_file = final_result.get("files_created", [])
                    if first_file:
                        with open(first_file[0], 'r') as f:
                            header = f.read(500)
                        
                        if "Cross-reference: SYSTEM.md" in header:
                            print("✅ Header format: CORRECT - References SYSTEM.md")
                        else:
                            print("❌ Header format: INCORRECT - Wrong hub reference")
                    
                    return True
                    
                elif current_status == "failed":
                    error = status.get("error", "Unknown")
                    print(f"❌ FAILED: {error}")
                    
                    # Check for specific AttributeError
                    if "'str' object has no attribute 'name'" in error:
                        print("🐛 CRITICAL: AttributeError bug still present!")
                    
                    return False
            
            print("⏰ Test timed out")
            return False
            
        else:
            print(f"❌ Failed to start: {result.get('error')}")
            return False
            
    except Exception as e:
        print(f"💥 Exception: {str(e)}")
        return False

if __name__ == "__main__":
    success = asyncio.run(quick_test())
    print(f"\n🎯 Quick test result: {'PASSED' if success else 'FAILED'}") 