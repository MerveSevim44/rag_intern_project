"""
benchmark_eval.py — Benchmark & Skorlama Wrapper

Bu modül, evaluation/benchmark_eval.py modülüne yönlendirme yapar.

Kullanım:
  python benchmark_eval.py test_sonuclari.csv ground_truth.json --output-dir report
  python benchmark_eval.py evaluation/datasets/test_sonuclari.csv
"""

import sys
from pathlib import Path

_root_dir = Path(__file__).resolve().parent
_eval_dir = _root_dir / "evaluation"
_src_dir = _root_dir / "src"

for _p in [str(_eval_dir), str(_src_dir), str(_root_dir)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from evaluation.benchmark_eval import *  # noqa: F401, F403
import evaluation.benchmark_eval as _bench_module

if __name__ == "__main__":
    import runpy
    runpy.run_path(str(_eval_dir / "benchmark_eval.py"), run_name="__main__")
