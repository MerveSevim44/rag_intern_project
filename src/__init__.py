"""
src package — RAG & Data Engine Core System
"""

import sys
from pathlib import Path

# Add src and root directories to sys.path so modules can import seamlessly
_src_dir = Path(__file__).resolve().parent
_root_dir = _src_dir.parent

if str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))
if str(_root_dir) not in sys.path:
    sys.path.insert(0, str(_root_dir))
