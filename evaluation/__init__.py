"""
evaluation package — Benchmark, scoring, and retrieval evaluation tools
"""

import sys
from pathlib import Path

# Add src and root directories to sys.path
_eval_dir = Path(__file__).resolve().parent
_root_dir = _eval_dir.parent
_src_dir = _root_dir / "src"

for p in [str(_src_dir), str(_root_dir), str(_eval_dir)]:
    if p not in sys.path:
        sys.path.insert(0, p)
