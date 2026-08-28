#!/usr/bin/env python3

# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Script to run functional tests using pytest.

This script runs the end-to-end functional tests using pytest,
which provides better test discovery, reporting, and execution.
"""

import subprocess
import sys
from pathlib import Path


def main():
    """Run functional tests using pytest."""
    print("=" * 60)
    print("RUNNING FUNCTIONAL TESTS WITH PYTEST")
    print("=" * 60)

    # Get the functional_tests directory
    functional_tests_dir = Path(__file__).parent
    project_root = functional_tests_dir.parent

    if not functional_tests_dir.exists():
        print(f"Functional tests directory not found: {functional_tests_dir}")
        return 1

    # Check if pytest is available
    try:
        import pytest
    except ImportError:
        print("pytest is not installed. Please install it with: pip install pytest")
        return 1

    # Run pytest on the functional_tests directory
    # Use relative path and run from project root for better test discovery
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "functional_tests",
        "-v",
        "--tb=short",
        "--color=yes",
    ]

    print(f"Running: {' '.join(cmd)}")
    print(f"Working directory: {project_root}")
    print()

    try:
        result = subprocess.run(cmd, cwd=project_root, check=False)
        return result.returncode
    except KeyboardInterrupt:
        print("\nTests interrupted by user")
        return 1
    except FileNotFoundError:
        print("pytest command not found. Please ensure pytest is installed.")
        return 1
    except Exception as e:
        print(f"Failed to run tests: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
