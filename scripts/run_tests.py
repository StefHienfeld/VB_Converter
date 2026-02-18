#!/usr/bin/env python
"""
Test runner script with optional coverage reporting.

Usage:
    python scripts/run_tests.py              # Run all tests
    python scripts/run_tests.py --coverage   # Run with coverage report
    python scripts/run_tests.py --unit       # Run only unit tests
    python scripts/run_tests.py --quick      # Skip slow tests

Prerequisites:
    pip install pytest pytest-cov pytest-mock
"""

import subprocess
import sys
import argparse
from pathlib import Path

# Get project root
PROJECT_ROOT = Path(__file__).parent.parent


def run_tests(
    with_coverage: bool = False,
    unit_only: bool = False,
    quick: bool = False,
    verbose: bool = True
) -> int:
    """
    Run pytest with the specified options.

    Args:
        with_coverage: Include coverage reporting
        unit_only: Only run unit tests (skip integration)
        quick: Skip slow tests
        verbose: Verbose output

    Returns:
        Exit code from pytest
    """
    cmd = [sys.executable, "-m", "pytest"]

    # Test selection
    if unit_only:
        cmd.append("tests/unit/")
    else:
        cmd.append("tests/")

    # Coverage options
    if with_coverage:
        cmd.extend([
            "--cov=hienfeld",
            "--cov=hienfeld_api",
            "--cov-report=term-missing",
            "--cov-report=html:coverage_html",
            "--cov-fail-under=10"
        ])

    # Skip slow tests if quick mode
    if quick:
        cmd.extend(["-m", "not slow"])

    # Verbosity
    if verbose:
        cmd.append("-v")

    # Show short traceback
    cmd.append("--tb=short")

    print(f"Running: {' '.join(cmd)}")
    print("=" * 60)

    result = subprocess.run(cmd, cwd=PROJECT_ROOT)
    return result.returncode


def check_coverage_installed() -> bool:
    """Check if pytest-cov is installed."""
    try:
        import pytest_cov
        return True
    except ImportError:
        return False


def main():
    parser = argparse.ArgumentParser(description="Run tests for VB Converter")
    parser.add_argument("--coverage", "-c", action="store_true",
                        help="Generate coverage report")
    parser.add_argument("--unit", "-u", action="store_true",
                        help="Run only unit tests")
    parser.add_argument("--quick", "-q", action="store_true",
                        help="Skip slow tests")
    parser.add_argument("--quiet", action="store_true",
                        help="Less verbose output")

    args = parser.parse_args()

    # Check if coverage is requested but not installed
    if args.coverage and not check_coverage_installed():
        print("WARNING: pytest-cov is not installed. Running without coverage.")
        print("Install with: pip install pytest-cov")
        print()
        args.coverage = False

    exit_code = run_tests(
        with_coverage=args.coverage,
        unit_only=args.unit,
        quick=args.quick,
        verbose=not args.quiet
    )

    if args.coverage and exit_code == 0:
        print()
        print("=" * 60)
        print("Coverage report generated in: coverage_html/index.html")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
