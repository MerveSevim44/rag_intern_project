"""
Madde 27 + 29: bge-m3 embedding'i CPU (num_gpu=0) ve GPU (num_gpu=99) yolunda
aynı metinler için karşılaştırılır — NaN hangi yolda çıkıyor, iki yolun
vektörleri ne kadar farklı (oturumlar arası kayma hipotezi).

Gözlem (2026-10-13): Ollama 0.21.2 varsayılan çağrıda bge-m3'ü "100% CPU"
yüklüyor (8 GB VRAM'in 1.7 GB'ı doluyken bile); 11 Ekim'deki NaN'ın hangi
yolda oluştuğu bilinmiyor.

Metinler: nan_tarama.py ile aynı küme (kayıtlı koşulların benzersiz cevap +
referans metinleri). Her yol için model yeniden yüklenir; `ollama ps` kaydedilir.

Kullanım:
    python -u experiments/madde27_nan_embedding/gpu_cpu_karsilastirma.py
Çıktı: gpu_cpu.jsonl, sonuc_gpu_cpu.txt
"""
import importlib.util
import json
import math
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("nan_tarama", HERE / "nan_tarama.py")
T = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(T)


def embed_all(ollama, items, num_gpu):
    # Önce modeli boşalt ki yeni num_gpu ile yeniden yüklensin.
    ollama.embeddings(model=T.MODEL, prompt="x", keep_alive=0)
    vecs, ps = {}, None
    for t in items:
        try:
            v = ollama.embeddings(model=T.MODEL, prompt=t, keep_alive="5m",
                                  options={"num_gpu": num_gpu})["embedding"]
            vecs[t] = ("nan", v) if any(math.isnan(x) for x in v) else ("ok", v)
        except Exception as e:
            vecs[t] = ("hata", f"{type(e).__name__}: {str(e)[:160]}")
        if ps is None:
            ps = subprocess.run(["ollama", "ps"], capture_output=True, text=True).stdout.strip()
    return vecs, ps


def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    import ollama
    items = T.texts()
    cpu, ps_cpu = embed_all(ollama, items, 0)
    gpu, ps_gpu = embed_all(ollama, items, 99)
    lines = [f"metin: {len(items)}", f"ollama ps (CPU yolu):\n{ps_cpu}", f"ollama ps (GPU yolu):\n{ps_gpu}"]
    cos, worst = [], []
    with open(HERE / "gpu_cpu.jsonl", "w", encoding="utf-8") as f:
        for t, (kind, where) in items.items():
            (sc, vc), (sg, vg) = cpu[t], gpu[t]
            c = cosine(vc, vg) if sc == sg == "ok" else None
            if c is not None:
                cos.append(c)
                worst.append((c, where, t))
            f.write(json.dumps({"ilk_gorulen": where, "tur": kind, "uzunluk": len(t), "cpu": sc, "gpu": sg,
                                "cosine_cpu_gpu": c, "metin": t}, ensure_ascii=False) + "\n")
    for label, d in (("CPU", cpu), ("GPU", gpu)):
        bad = [(t, s) for t, (s, _) in d.items() if s != "ok"]
        lines.append(f"{label}: nan/hata {len(bad)}")
        lines += [f"   {s} {items[t][1]} len={len(t)} {t[:80]!r}" for t, s in bad[:20]]
    if cos:
        cos_sorted = sorted(cos)
        lines.append(f"cosine(CPU, GPU): min={cos_sorted[0]:.6f} medyan={cos_sorted[len(cos) // 2]:.6f} "
                     f"max={cos_sorted[-1]:.6f}; < 0.9999: {sum(c < 0.9999 for c in cos)}, "
                     f"< 0.999: {sum(c < 0.999 for c in cos)}")
        for c, where, t in sorted(worst)[:5]:
            lines.append(f"   en farkli: {c:.6f} {where} {t[:70]!r}")
    text = "\n".join(lines) + "\n"
    (HERE / "sonuc_gpu_cpu.txt").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
