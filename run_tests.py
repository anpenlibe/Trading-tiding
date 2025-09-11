#!/usr/bin/env python3
"""Test runner with coverage reporting."""

import sys
import subprocess
import os


def run_tests():
    """Run all tests with coverage."""
    print("=" * 60)
    print("🧪 RUNNING AUTOMATED TEST SUITE")
    print("=" * 60)
    
    # Ensure we're in the right directory
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    success = True
    
    # Run unit tests
    print("\n📦 Running Unit Tests...")
    result = subprocess.run(
        ["python", "-m", "pytest", "tests/unit/", "-v", "--tb=short"],
        capture_output=True,
        text=True
    )
    print(result.stdout)
    if result.returncode != 0:
        print("❌ Unit tests failed!")
        print(result.stderr)
        success = False
    else:
        print("✅ Unit tests passed!")
    
    # Run integration tests
    print("\n🔗 Running Integration Tests...")
    result = subprocess.run(
        ["python", "-m", "pytest", "tests/integration/", "-v", "--tb=short"],
        capture_output=True,
        text=True
    )
    print(result.stdout)
    if result.returncode != 0:
        print("❌ Integration tests failed!")
        print(result.stderr)
        success = False
    else:
        print("✅ Integration tests passed!")
    
    # Run all tests with coverage
    print("\n📊 Generating Coverage Report...")
    result = subprocess.run(
        ["python", "-m", "pytest", "--cov=src", "--cov-report=term-missing", "--cov-report=html", "--tb=short"],
        capture_output=True,
        text=True
    )
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    
    if success:
        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("📊 Coverage report generated in htmlcov/index.html")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("❌ SOME TESTS FAILED!")
        print("📋 Check output above for details")
        print("=" * 60)
    
    return success


def run_quick_test():
    """Run a quick test to verify setup."""
    print("🚀 Running quick test verification...")
    result = subprocess.run(
        ["python", "-m", "pytest", "--co", "-q"],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        test_count = len([line for line in result.stdout.split('\n') if 'test_' in line])
        print(f"✅ Test setup verified! Found {test_count} tests")
        return True
    else:
        print("❌ Test setup failed!")
        print(result.stderr)
        return False


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--quick":
        success = run_quick_test()
    else:
        success = run_tests()
    
    sys.exit(0 if success else 1)