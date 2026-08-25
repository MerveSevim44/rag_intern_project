"""
tests package — Unit & Integration Test Suite
"""

import sys
from pathlib import Path

# Add src and root directories to sys.path for test runners
_tests_dir = Path(__file__).resolve().parent
_root_dir = _tests_dir.parent
_src_dir = _root_dir / "src"

for p in [str(_src_dir), str(_root_dir)]:
    if p not in sys.path:
        sys.path.insert(0, p)
