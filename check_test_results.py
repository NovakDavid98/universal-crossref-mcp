#!/usr/bin/env python3
"""Check test results to validate fixes"""

import sys
from pathlib import Path

def check_results():
    """Check the test results"""
    print("🔍 Checking PDF Extraction Fix Results")
    print("=" * 50)
    
    # Check async extraction output
    async_dir = Path("/tmp/quick_test_async")
    
    if async_dir.exists():
        print(f"✅ Async extraction directory found: {async_dir}")
        
        # Find markdown files
        md_files = list(async_dir.glob("*.md"))
        print(f"📄 Markdown files created: {len(md_files)}")
        
        if md_files:
            # Check first file header
            first_file = md_files[0]
            print(f"🔍 Checking header in: {first_file.name}")
            
            try:
                with open(first_file, 'r', encoding='utf-8') as f:
                    content = f.read(1000)  # First 1000 chars
                
                print("\n📋 Header Content:")
                header_lines = content.split('\n')[:10]  # First 10 lines
                for i, line in enumerate(header_lines, 1):
                    print(f"  {i:2d}: {line}")
                
                # Check critical elements
                print("\n🎯 Critical Fix Validation:")
                
                # 1. Cross-reference format
                if "Cross-reference: SYSTEM.md" in content:
                    print("✅ Hub Reference Fix: RESOLVED - References SYSTEM.md correctly")
                elif "Cross-reference:" in content:
                    # Extract wrong reference
                    for line in header_lines:
                        if "Cross-reference:" in line:
                            wrong_ref = line.split(':', 1)[1].strip()
                            print(f"❌ Hub Reference Fix: FAILED - Still references '{wrong_ref}'")
                            break
                else:
                    print("❌ Hub Reference Fix: FAILED - No Cross-reference field found")
                
                # 2. Quality score (check if it's not 0.00)
                if "Quality Score:" in content:
                    for line in header_lines:
                        if "Quality Score:" in line:
                            quality_str = line.split(':', 1)[1].strip()
                            try:
                                quality = float(quality_str)
                                if quality > 0.1:
                                    print(f"✅ Quality Score Fix: RESOLVED - Score: {quality:.3f}")
                                else:
                                    print(f"❌ Quality Score Fix: FAILED - Still showing: {quality:.3f}")
                            except:
                                print(f"⚠️ Quality Score Fix: UNCLEAR - Value: {quality_str}")
                            break
                else:
                    print("❌ Quality Score Fix: FAILED - No quality score found")
                
                # 3. Header structure
                if content.startswith('---\nMANDATORY READING:'):
                    print("✅ Header Structure: CORRECT - Proper YAML format")
                else:
                    print("❌ Header Structure: INCORRECT - Wrong format")
                
                return True
                
            except Exception as e:
                print(f"❌ Error reading file: {str(e)}")
                return False
        
        else:
            print("❌ No markdown files found - extraction may have failed")
            return False
    
    else:
        print("❌ Async extraction directory not found - test didn't complete")
        return False

if __name__ == "__main__":
    success = check_results()
    print(f"\n🎯 Results check: {'PASSED' if success else 'FAILED'}") 