"""
Madde 27 kapsam ölçümü: kayıtlı koşulardaki benzersiz cevap + referans metinleri
bge-m3 (Ollama) ile embed edilir; NaN / hata üreten metinler sayılır.

benchmark_eval._embed_text ile aynı çağrı (ollama.embeddings, prompt=strip edilmiş
metin). Koşul etiketi (ör. "foundry_yok", "foundry_yuklu") sonuç dosyasına yazılır;
aynı tarama iki koşulda koşulup karşılaştırılır (madde 29 hipotezi).

Kullanım:
    python -u experiments/madde27_nan_embedding/nan_tarama.py KOSUL_ETIKETI
Çıktı: tarama_<etiket>.jsonl (metin başına sonuç), özet stdout'ta.
"""
import csv
import glob
import json
import math
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MODEL = "bge-m3"


def texts():
    csv.field_size_limit(10**9)
    seen = {}
    files = sorted(glob.glob(str(ROOT / "experiments" / "*" / "report*" / "genel_scored.csv"))
                   + glob.glob(str(ROOT / "experiments" / "madde25_ret_tespiti" / "yeniden_skor_*" / "genel_scored.csv")))
    for path in files:
        for r in csv.DictReader(open(path, encoding="utf-8-sig")):
            cands = [("cevap", r.get("cevap") or "")]
            cands += [("referans", t) for t in (r.get("referans_cevaplar") or "").split(" | ")]
            for kind, t in cands:
                t = t.strip()
                if t and not t.startswith("HATA") and t not in seen:
                    seen[t] = (kind, f"{Path(path).parent.parent.name}:{r['test_seti']}#{r['id']}")
    return seen


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    import ollama
    label = sys.argv[1]
    items = texts()
    out = HERE / f"tarama_{label}.jsonl"
    bad = []
    t0 = time.perf_counter()
    ps_logged = None
    with open(out, "w", encoding="utf-8") as f:
        for n, (t, (kind, where)) in enumerate(items.items(), 1):
            try:
                v = ollama.embeddings(model=MODEL, prompt=t, keep_alive="5m")["embedding"]
                status = "nan" if any(math.isnan(x) for x in v) else "ok"
                err = ""
            except Exception as e:
                status, err = "hata", f"{type(e).__name__}: {str(e)[:160]}"
            if ps_logged is None:
                ps_logged = subprocess.run(["ollama", "ps"], capture_output=True, text=True).stdout.strip()
            rec = {"kosul": label, "durum": status, "hata": err, "tur": kind, "ilk_gorulen": where,
                   "uzunluk": len(t), "metin": t}
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            if status != "ok":
                bad.append(rec)
                print(f"[{n}] {status} {where} len={len(t)} {err} {t[:80]!r}", flush=True)
    print(f"\nkosul={label}  metin={len(items)}  nan/hata={len(bad)}  sure={(time.perf_counter() - t0) / 60:.1f} dk")
    print(f"ollama ps (ilk embedding sonrasi):\n{ps_logged}")


if __name__ == "__main__":
    main()
