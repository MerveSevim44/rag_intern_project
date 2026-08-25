"""
run_tests.py — RAG Test Seti Koşucu Wrapper

Bu modül, evaluation/run_tests.py modülüne yönlendirme yapar.

Kullanım:
  python run_tests.py
  python run_tests.py test_sorulari_json.csv
  python run_tests.py evaluation/datasets/test_sorulari.csv
"""

import sys
from pathlib import Path

_root_dir = Path(__file__).resolve().parent
_eval_dir = _root_dir / "evaluation"
_src_dir = _root_dir / "src"

for _p in [str(_eval_dir), str(_src_dir), str(_root_dir)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from evaluation.run_tests import *  # noqa: F401, F403
import evaluation.run_tests as _runner_module

if __name__ == "__main__":
    import runpy
    runpy.run_path(str(_eval_dir / "run_tests.py"), run_name="__main__")