"""
app.py — RAG Soru-Cevap Uygulaması (Streamlit Giriş Noktası)

Bu dosya, src/app.py altındaki ana Streamlit uygulamasını çalıştıran kök giriş noktasıdır.

Çalıştırma:
  streamlit run app.py
"""

import sys
import runpy
from pathlib import Path

_root_dir = Path(__file__).resolve().parent
_src_dir = _root_dir / "src"

for _p in [str(_src_dir), str(_root_dir)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

if __name__ == "__main__":
    app_target = _src_dir / "app.py"
    runpy.run_path(str(app_target), run_name="__main__")
