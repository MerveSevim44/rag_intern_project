"""
ingest.py — Doküman İndeksleme Wrapper

Bu modül, src/ingest.py modülüne yönlendirme yapar ve hem CLI hem de import olarak kullanılabilir.

Kullanım:
  python ingest.py
  python ingest.py --data_dir data --db_path rag.db --model bge-m3
"""

import sys
from pathlib import Path

_root_dir = Path(__file__).resolve().parent
_src_dir = _root_dir / "src"

for _p in [str(_src_dir), str(_root_dir)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from src.ingest import *  # noqa: F401, F403
import src.ingest as _ingest_module

if __name__ == "__main__":
    import runpy
    runpy.run_path(str(_src_dir / "ingest.py"), run_name="__main__")
