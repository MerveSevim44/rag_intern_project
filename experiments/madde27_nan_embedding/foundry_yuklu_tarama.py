"""
nan_tarama.py'yi Foundry Local modeli GPU'da YÜKLÜYKEN koşar (madde 29 hipotezi:
LLM GPU'dayken bge-m3 farklı cihaz/bölüşümde koşup farklı — NaN dahil — sonuç veriyor mu?).

run_tests.load_model() ile model yüklenir ve bir kez çağrılarak GPU'da sıcak tutulur;
ardından aynı süreçte tarama koşulur. `ollama ps` ve Foundry'nin yüklü modelleri
sonuç dosyasına/ekrana yazılır.

Kullanım:
    HF_HUB_OFFLINE=1 python -u experiments/madde27_nan_embedding/foundry_yuklu_tarama.py
"""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "evaluation"))

import run_tests  # noqa: E402

_spec = importlib.util.spec_from_file_location("nan_tarama", HERE / "nan_tarama.py")
T = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(T)

if __name__ == "__main__":
    llm = run_tests.load_model()
    print("LLM isinma cevabi:", llm.invoke("Merhaba, tek kelimeyle cevap ver: hazir misin?").content[:60])
    sys.argv = [sys.argv[0], "foundry_yuklu"]
    T.main()
