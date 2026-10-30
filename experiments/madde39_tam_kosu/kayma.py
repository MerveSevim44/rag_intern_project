"""
Madde 39 — embedding kayması: aynı metnin vektörü LLM (Foundry) GPU'dayken ve değilken
aynı mı? kosu.py'nin nöbet özeti set öncesi/sonrası farklı çıktı (d16e… / 5b82…).

Kullanım (kökten): python -u experiments/madde39_tam_kosu/kayma.py ETIKET
  ETIKET altında vektörleri kayma_ETIKET.json'a yazar; önceki etiketlerle kosinüsü basar.
"""
import json
import re
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "src"))
METINLER = ["Bağlamdan bağımsız dilbilgisi için türetme ağacı nedir?",
            "Zamanda çarpımın frekansta konvolüsyona karşılık geldiği özellik hangi türetme ile gösterilmiştir?",
            "Bağlamdan bağımsız dilbilgisi için pompalama (pumping) lemması nasıl ifade edilir?",
            "Alis'in çalıştığı kütüphanenin adı nedir?"]


def main():
    from embedder import EMBED_NUM_GPU, get_embedding

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    etiket = sys.argv[1]
    vek = [[get_embedding(m) for m in METINLER] for _ in range(2)]
    print(f"{etiket}: num_gpu={EMBED_NUM_GPU}  kendi içinde bayt bayt aynı: {vek[0] == vek[1]}")
    (HERE / f"kayma_{etiket}.json").write_text(json.dumps(vek[0]), encoding="utf-8")
    a = np.array(vek[0])
    for p in HERE.glob("kayma_*.json"):
        if p.stem == f"kayma_{etiket}":
            continue
        b = np.array(json.loads(p.read_text(encoding="utf-8")))
        cos = (a * b).sum(1) / (np.linalg.norm(a, axis=1) * np.linalg.norm(b, axis=1))
        print(f"  {etiket} vs {p.stem[6:]}: bayt aynı={a.tolist() == b.tolist()} "
              f"kosinüs min={cos.min():.6f} max={cos.max():.6f}")
    log = Path.home() / "AppData/Local/Ollama/server.log"
    if log.exists():
        satir = log.read_text(encoding="utf-8", errors="replace").splitlines()[-400:]
        for s in satir:
            if re.search(r"offload|layers\.model|graph splits", s) or "n_gpu_layers" in s:
                son = s
        print("  son log:", son[:200] if "son" in dir() else "-")


if __name__ == "__main__":
    main()
