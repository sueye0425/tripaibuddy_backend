#!/usr/bin/env python3
"""
Comprehensive Test Runner for /complete-itinerary Endpoint

This script runs all test suites to validate:
1. Response format consistency with frontend expectations
2. Latency within 12s requirement
3. LLM and agentic system integration 
4. Edge cases and error scenarios
5. Theme park detection and handling
6. Restaurant guarantee mechanisms
7. Landmark expansion logic

Usage:
    python run_comprehensive_tests.py

Prerequisites:
    - Server running on http://127.0.0.1:8000
    - Environment variables set (OPENAI_API_KEY, GOOGLE_PLACES_API_KEY)
    - ENABLE_AGENTIC_SYSTEM=true
"""

import subprocess
import sys
import time
import requests
import os
from pathlib import Path


def check_server_status():
    """Check if the server is running"""
    try:
        response = requests.get("http://127.0.0.1:8000/", timeout=5)
        if response.status_code == 200:
            return True
    except requests.exceptions.RequestException:
        pass
    return False


def check_environment():
    """Check required environment variables"""
    required_vars = ["OPENAI_API_KEY", "GOOGLE_PLACES_API_KEY"]
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    # Check agentic system enabled
    agentic_enabled = os.getenv("ENABLE_AGENTIC_SYSTEM", "false").lower() == "true"
    
    return missing_vars, agentic_enabled


def run_test_file(test_file: str, description: str) -> bool:
    """Run a specific test file and return success status"""
    print(f"\n{'='*60}")
    print(f"🧪 Running {description}")
    print(f"📄 File: {test_file}")
    print(f"{'='*60}")
    
    start_time = time.time()
    
    try:
        # Run the test file directly with Python
        result = subprocess.run(
            [sys.executable, test_file],
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout per test suite
        )
        
        duration = time.time() - start_time
        
        if result.returncode == 0:
            print(f"✅ {description} - PASSED ({duration:.1f}s)")
            # Print the output for visibility
            if result.stdout:
                print(result.stdout)
            return True
        else:
            print(f"❌ {description} - FAILED ({duration:.1f}s)")
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)
            return False
            
    except subprocess.TimeoutExpired:
        print(f"⏰ {description} - TIMEOUT (exceeded 5 minutes)")
        return False
    except Exception as e:
        print(f"💥 {description} - ERROR: {e}")
        return False


def main():
    """Main test runner"""
    print("🧪 COMPREHENSIVE TEST SUITE FOR /complete-itinerary ENDPOINT")
    print("=" * 70)
    print()
    print("This test suite validates:")
    print("✓ Response format consistency with frontend expectations")
    print("✓ Latency within 12s requirement")
    print("✓ LLM and agentic system integration")
    print("✓ Edge cases and error scenarios")
    print("✓ Theme park detection and handling")
    print("✓ Restaurant guarantee mechanisms")
    print("✓ Landmark expansion logic")
    print()
    
    # Check prerequisites
    print("🔍 Checking Prerequisites...")
    print("-" * 30)
    
    # Check server
    if not check_server_status():
        print("❌ Server not running!")
        print("   Please start the server with:")
        print("   python -m uvicorn app.main:app --reload --port 8000")
        return False
    else:
        print("✅ Server is running")
    
    # Check environment
    missing_vars, agentic_enabled = check_environment()
    
    if missing_vars:
        print(f"❌ Missing environment variables: {', '.join(missing_vars)}")
        return False
    else:
        print("✅ Environment variables configured")
    
    if not agentic_enabled:
        print("❌ ENABLE_AGENTIC_SYSTEM not set to 'true'")
        print("   Please set: export ENABLE_AGENTIC_SYSTEM=true")
        return False
    else:
        print("✅ Agentic system enabled")
    
    print()
    
    # Define test suites to run
    test_suites = [
        {
            "file": "test_complete_itinerary_requirements.py",
            "description": "Core Requirements Tests",
            "priority": "HIGH"
        },
        {
            "file": "test_comprehensive_edge_cases.py", 
            "description": "Edge Cases & Response Format Tests",
            "priority": "HIGH"
        },
        {
            "file": "test_llm_agentic_integration.py",
            "description": "LLM & Agentic System Integration Tests",
            "priority": "MEDIUM"
        }
    ]
    
    # Track results
    total_tests = len(test_suites)
    passed_tests = 0
    failed_tests = []
    
    start_time = time.time()
    
    # Run each test suite
    for suite in test_suites:
        test_file = suite["file"]
        description = suite["description"]
        priority = suite["priority"]
        
        # Check if test file exists
        if not Path(test_file).exists():
            print(f"⚠️  Test file not found: {test_file}")
            failed_tests.append(f"{description} (file not found)")
            continue
        
        # Run the test
        success = run_test_file(test_file, description)
        
        if success:
            passed_tests += 1
        else:
            failed_tests.append(f"{description} ({priority} priority)")
            
            # For HIGH priority tests, consider stopping
            if priority == "HIGH":
                print(f"\n🚨 HIGH PRIORITY TEST FAILED: {description}")
                print("   This indicates a critical issue that should be addressed.")
    
    # Generate final report
    total_duration = time.time() - start_time
    
    print(f"\n{'='*70}")
    print("📊 COMPREHENSIVE TEST REPORT")
    print(f"{'='*70}")
    print(f"⏱️  Total Duration: {total_duration:.1f}s")
    print(f"📈 Test Suites: {passed_tests}/{total_tests} passed")
    print(f"✅ Success Rate: {(passed_tests/total_tests)*100:.1f}%")
    
    if failed_tests:
        print(f"\n❌ Failed Tests:")
        for failed_test in failed_tests:
            print(f"   • {failed_test}")
    
    print()
    
    # Overall assessment
    if passed_tests == total_tests:
        print("🎉 ALL TESTS PASSED!")
        print("   The /complete-itinerary endpoint meets all requirements.")
        print("   ✓ Response format consistent with frontend")
        print("   ✓ Latency within 12s requirement")
        print("   ✓ LLM and agentic system properly integrated")
        print("   ✓ Edge cases handled gracefully")
        return True
    elif passed_tests >= total_tests * 0.8:  # 80% pass rate
        print("⚠️  MOSTLY PASSING (some issues detected)")
        print(f"   {passed_tests}/{total_tests} test suites passed.")
        print("   Please review failed tests and address issues.")
        return False
    else:
        print("🚨 CRITICAL ISSUES DETECTED")
        print(f"   Only {passed_tests}/{total_tests} test suites passed.")
        print("   The endpoint has significant problems that need immediate attention.")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 