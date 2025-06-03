#!/usr/bin/env python3
"""
Comprehensive Test Suite for Universal Cross-Reference MCP Server PDF Extraction Fixes

This test validates the critical fixes implemented for:
1. AttributeError in async extraction
2. Quality score calculation (0.00 -> proper scores)
3. Hub file references (wrong index files -> correct SYSTEM.md)
4. Auto-watcher integration conflicts
5. Header format consistency between sync and async

Usage: python test_pdf_extraction_fixes.py
"""

import asyncio
import json
import time
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
import sys
import os

# Add the src path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from mcp_server.simple_server import (
    extract_pdf_to_markdown,
    extract_pdf_to_markdown_async,
    check_pdf_extraction_status,
    start_auto_crossref_watcher,
    stop_auto_crossref_watcher,
    verify_project_sync,
    get_system_status,
    get_operation_logs
)

class PDFExtractionTestSuite:
    """Comprehensive test suite for PDF extraction fixes"""
    
    def __init__(self):
        self.test_results = {}
        self.test_dir = None
        self.test_pdf_path = None
        
    def setup_test_environment(self):
        """Create test environment with sample PDF"""
        print("🔧 Setting up test environment...")
        
        # Create temporary test directory
        self.test_dir = Path(tempfile.mkdtemp(prefix="crossref_test_"))
        print(f"📁 Test directory: {self.test_dir}")
        
        # Use the Walter Russell PDF if available, otherwise create a mock
        russell_pdf = Path("/home/frontalneuralcortex/crossrefference/TheUniversalOne1926WalterRussell.pdf")
        
        if russell_pdf.exists():
            self.test_pdf_path = russell_pdf
            print(f"📄 Using existing PDF: {self.test_pdf_path}")
        else:
            print("⚠️ Walter Russell PDF not found, creating mock PDF for testing")
            self.test_pdf_path = self.create_mock_pdf()
        
        return True
    
    def create_mock_pdf(self):
        """Create a simple mock PDF for testing if real PDF not available"""
        # This would require reportlab or similar, for now just use text file
        mock_pdf = self.test_dir / "mock_test.pdf"
        with open(mock_pdf, 'w') as f:
            f.write("Mock PDF content for testing purposes")
        return mock_pdf
    
    async def test_sync_extraction(self):
        """Test synchronous PDF extraction"""
        print("\n🔄 Testing SYNCHRONOUS PDF extraction...")
        
        start_time = time.time()
        try:
            result = extract_pdf_to_markdown(
                pdf_path=str(self.test_pdf_path),
                output_dir=str(self.test_dir / "sync_extraction"),
                max_chunks=5,  # Small for testing
                create_hub=True,
                hub_file_name="SYSTEM.md"
            )
            
            duration = time.time() - start_time
            
            # Analyze results
            success = result.get("success", False)
            quality_score = result.get("quality_score", 0.0)
            files_created = result.get("files_created", [])
            hub_file_used = result.get("hub_file_used", "")
            
            self.test_results["sync_extraction"] = {
                "success": success,
                "duration": duration,
                "quality_score": quality_score,
                "files_created": len(files_created),
                "hub_file_used": hub_file_used,
                "result": result,
                "timestamp": datetime.now().isoformat()
            }
            
            print(f"✅ Sync extraction completed in {duration:.2f}s")
            print(f"📊 Quality score: {quality_score}")
            print(f"📄 Files created: {len(files_created)}")
            print(f"🏠 Hub file: {hub_file_used}")
            
            return True
            
        except Exception as e:
            print(f"❌ Sync extraction failed: {str(e)}")
            self.test_results["sync_extraction"] = {
                "success": False,
                "error": str(e),
                "duration": time.time() - start_time,
                "timestamp": datetime.now().isoformat()
            }
            return False
    
    async def test_async_extraction(self):
        """Test asynchronous PDF extraction"""
        print("\n🔄 Testing ASYNCHRONOUS PDF extraction...")
        
        start_time = time.time()
        try:
            # Start async extraction
            result = extract_pdf_to_markdown_async(
                pdf_path=str(self.test_pdf_path),
                output_dir=str(self.test_dir / "async_extraction"),
                max_chunks=5,  # Small for testing
                create_hub=True,
                hub_file_name="SYSTEM.md"
            )
            
            if not result.get("success"):
                raise Exception(f"Failed to start async extraction: {result.get('error')}")
            
            task_id = result["task_id"]
            print(f"🚀 Async extraction started, task ID: {task_id}")
            
            # Monitor progress
            max_wait = 120  # 2 minutes max
            check_interval = 2  # Check every 2 seconds
            checks = 0
            
            while checks < max_wait // check_interval:
                await asyncio.sleep(check_interval)
                checks += 1
                
                status_result = check_pdf_extraction_status(task_id)
                status = status_result.get("status", "unknown")
                progress = status_result.get("progress", 0)
                
                print(f"📊 Progress: {progress:.1f}% - Status: {status}")
                
                if status == "completed":
                    final_result = status_result.get("result", {})
                    duration = time.time() - start_time
                    
                    # Analyze results
                    success = final_result.get("success", False)
                    quality_score = final_result.get("quality_score", 0.0)
                    files_created = final_result.get("files_created", [])
                    hub_file_used = final_result.get("hub_file_used", "")
                    
                    self.test_results["async_extraction"] = {
                        "success": success,
                        "duration": duration,
                        "quality_score": quality_score,
                        "files_created": len(files_created),
                        "hub_file_used": hub_file_used,
                        "final_result": final_result,
                        "task_id": task_id,
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    print(f"✅ Async extraction completed in {duration:.2f}s")
                    print(f"📊 Quality score: {quality_score}")
                    print(f"📄 Files created: {len(files_created)}")
                    print(f"🏠 Hub file: {hub_file_used}")
                    
                    return True
                    
                elif status == "failed":
                    error = status_result.get("error", "Unknown error")
                    raise Exception(f"Async extraction failed: {error}")
            
            # Timeout
            raise Exception("Async extraction timed out")
            
        except Exception as e:
            print(f"❌ Async extraction failed: {str(e)}")
            self.test_results["async_extraction"] = {
                "success": False,
                "error": str(e),
                "duration": time.time() - start_time,
                "timestamp": datetime.now().isoformat()
            }
            return False
    
    def validate_header_format(self, extraction_dir: Path, extraction_type: str):
        """Validate that headers reference SYSTEM.md correctly"""
        print(f"\n🔍 Validating {extraction_type} header formats...")
        
        issues = []
        correct_headers = 0
        
        for md_file in extraction_dir.rglob("*.md"):
            if md_file.name == "SYSTEM.md":
                continue
                
            try:
                with open(md_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Check header format
                if not content.startswith('---\nMANDATORY READING:'):
                    issues.append(f"❌ {md_file.name}: Missing cross-reference header")
                    continue
                
                # Check hub reference
                if 'Cross-reference: SYSTEM.md' in content:
                    correct_headers += 1
                    print(f"✅ {md_file.name}: Correct SYSTEM.md reference")
                else:
                    if 'Cross-reference:' in content:
                        # Extract the wrong reference
                        lines = content.split('\n')
                        for line in lines:
                            if line.startswith('Cross-reference:'):
                                wrong_ref = line.split(':', 1)[1].strip()
                                issues.append(f"❌ {md_file.name}: Wrong hub reference '{wrong_ref}' (should be SYSTEM.md)")
                                break
                    else:
                        issues.append(f"❌ {md_file.name}: Missing Cross-reference field")
                        
            except Exception as e:
                issues.append(f"❌ {md_file.name}: Error reading file - {str(e)}")
        
        self.test_results[f"{extraction_type}_header_validation"] = {
            "correct_headers": correct_headers,
            "issues": issues,
            "total_files": correct_headers + len(issues)
        }
        
        if issues:
            print(f"⚠️ Found {len(issues)} header issues:")
            for issue in issues:
                print(f"  {issue}")
        else:
            print(f"✅ All {correct_headers} headers are correctly formatted!")
        
        return len(issues) == 0
    
    async def test_auto_watcher_integration(self):
        """Test auto-watcher integration with PDF extraction"""
        print("\n🔍 Testing auto-watcher integration...")
        
        try:
            # Create a separate directory for watcher testing
            watcher_dir = self.test_dir / "watcher_test"
            watcher_dir.mkdir(exist_ok=True)
            
            # Start auto-watcher
            watcher_result = start_auto_crossref_watcher(str(watcher_dir))
            if not watcher_result.get("success"):
                raise Exception(f"Failed to start auto-watcher: {watcher_result.get('error')}")
            
            print("✅ Auto-watcher started successfully")
            
            # Test extraction with watcher active
            extraction_result = extract_pdf_to_markdown(
                pdf_path=str(self.test_pdf_path),
                output_dir=str(watcher_dir),
                max_chunks=3,  # Small for testing
                create_hub=True,
                hub_file_name="SYSTEM.md"
            )
            
            # Give watcher time to process
            await asyncio.sleep(2)
            
            # Check system status
            status_result = get_system_status(str(watcher_dir))
            
            # Stop watcher
            stop_result = stop_auto_crossref_watcher(str(watcher_dir))
            
            self.test_results["auto_watcher_integration"] = {
                "watcher_start": watcher_result.get("success", False),
                "extraction_with_watcher": extraction_result.get("success", False),
                "system_status": status_result,
                "watcher_stop": stop_result.get("success", False),
                "timestamp": datetime.now().isoformat()
            }
            
            print("✅ Auto-watcher integration test completed")
            return True
            
        except Exception as e:
            print(f"❌ Auto-watcher integration test failed: {str(e)}")
            self.test_results["auto_watcher_integration"] = {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
            return False
    
    def compare_sync_vs_async(self):
        """Compare sync vs async results for consistency"""
        print("\n📊 Comparing sync vs async extraction results...")
        
        sync_results = self.test_results.get("sync_extraction", {})
        async_results = self.test_results.get("async_extraction", {})
        
        if not sync_results.get("success") or not async_results.get("success"):
            print("⚠️ Cannot compare - one or both extractions failed")
            return False
        
        # Compare key metrics
        comparison = {
            "both_successful": True,
            "quality_score_diff": abs(sync_results.get("quality_score", 0) - async_results.get("quality_score", 0)),
            "file_count_diff": abs(sync_results.get("files_created", 0) - async_results.get("files_created", 0)),
            "hub_file_match": sync_results.get("hub_file_used") == async_results.get("hub_file_used"),
            "performance_ratio": async_results.get("duration", 1) / sync_results.get("duration", 1)
        }
        
        self.test_results["sync_vs_async_comparison"] = comparison
        
        print(f"📊 Quality score difference: {comparison['quality_score_diff']:.3f}")
        print(f"📄 File count difference: {comparison['file_count_diff']}")
        print(f"🏠 Hub file match: {comparison['hub_file_match']}")
        print(f"⚡ Performance ratio (async/sync): {comparison['performance_ratio']:.2f}x")
        
        # Validate header consistency
        sync_dir = self.test_dir / "sync_extraction"
        async_dir = self.test_dir / "async_extraction"
        
        sync_headers_ok = self.validate_header_format(sync_dir, "sync") if sync_dir.exists() else False
        async_headers_ok = self.validate_header_format(async_dir, "async") if async_dir.exists() else False
        
        comparison["header_consistency"] = sync_headers_ok and async_headers_ok
        
        return comparison["both_successful"] and comparison["header_consistency"]
    
    def generate_test_report(self):
        """Generate comprehensive test report"""
        print("\n" + "="*80)
        print("📋 COMPREHENSIVE TEST REPORT")
        print("="*80)
        
        # Test summary
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results.values() 
                          if isinstance(result, dict) and result.get("success", False))
        
        print(f"📊 Test Summary: {passed_tests}/{total_tests} tests passed")
        print(f"🕐 Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # Critical fixes validation
        print("🔧 CRITICAL FIXES VALIDATION:")
        
        # 1. AttributeError fix
        async_result = self.test_results.get("async_extraction", {})
        if async_result.get("success"):
            print("✅ AttributeError fix: RESOLVED - Async extraction completed without errors")
        else:
            error = async_result.get("error", "Unknown")
            if "'str' object has no attribute 'name'" in error:
                print("❌ AttributeError fix: FAILED - Original bug still present")
            else:
                print(f"⚠️ AttributeError fix: PARTIAL - Different error occurred: {error}")
        
        # 2. Quality score fix
        sync_quality = self.test_results.get("sync_extraction", {}).get("quality_score", 0)
        async_quality = self.test_results.get("async_extraction", {}).get("quality_score", 0)
        
        if sync_quality > 0.1 and async_quality > 0.1:
            print(f"✅ Quality score fix: RESOLVED - Sync: {sync_quality:.2f}, Async: {async_quality:.2f}")
        else:
            print(f"❌ Quality score fix: FAILED - Sync: {sync_quality:.2f}, Async: {async_quality:.2f}")
        
        # 3. Hub reference fix
        sync_headers = self.test_results.get("sync_header_validation", {})
        async_headers = self.test_results.get("async_header_validation", {})
        
        if (sync_headers.get("issues", []) == [] and async_headers.get("issues", []) == []):
            print("✅ Hub reference fix: RESOLVED - All headers reference SYSTEM.md correctly")
        else:
            sync_issues = len(sync_headers.get("issues", []))
            async_issues = len(async_headers.get("issues", []))
            print(f"❌ Hub reference fix: FAILED - Sync issues: {sync_issues}, Async issues: {async_issues}")
        
        # 4. Integration fix
        integration_result = self.test_results.get("auto_watcher_integration", {})
        if integration_result.get("extraction_with_watcher"):
            print("✅ Auto-watcher integration: RESOLVED - No conflicts detected")
        else:
            print("❌ Auto-watcher integration: FAILED - Conflicts still present")
        
        print()
        print("📄 Detailed Results:")
        print(json.dumps(self.test_results, indent=2, default=str))
        
        # Save report to file
        report_file = self.test_dir / "test_report.json"
        with open(report_file, 'w') as f:
            json.dump(self.test_results, f, indent=2, default=str)
        
        print(f"\n💾 Full report saved to: {report_file}")
        
        return self.test_results
    
    def cleanup(self):
        """Clean up test environment"""
        if self.test_dir and self.test_dir.exists():
            print(f"\n🧹 Cleaning up test directory: {self.test_dir}")
            # Keep the test directory for analysis
            print(f"📁 Test files preserved for analysis at: {self.test_dir}")

async def main():
    """Run the complete test suite"""
    print("🚀 Universal Cross-Reference MCP Server - PDF Extraction Fix Test Suite")
    print("=" * 80)
    
    test_suite = PDFExtractionTestSuite()
    
    try:
        # Setup
        test_suite.setup_test_environment()
        
        # Run tests
        await test_suite.test_sync_extraction()
        await test_suite.test_async_extraction()
        await test_suite.test_auto_watcher_integration()
        
        # Analysis
        test_suite.compare_sync_vs_async()
        test_suite.generate_test_report()
        
        print("\n🎯 Test suite completed! Check the report above for detailed results.")
        
    except Exception as e:
        print(f"\n💥 Test suite failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
    
    finally:
        test_suite.cleanup()

if __name__ == "__main__":
    asyncio.run(main()) 