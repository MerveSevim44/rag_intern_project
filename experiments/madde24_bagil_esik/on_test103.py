"""
Madde 24 ön-test — bağıl rerank eşiği #103 FP'sini kaldırabilir mi? (sweep değil)

Bağıl eşik: rerank_score / en yüksek rerank_score < ESIK olan chunk elenir. En yüksek
skorlu chunk her zaman kalır (oran 1), yani bağıl eşik bağlamı boşaltamaz. Tek
senaryo = bağıl eşiğin #103'teki ÜST SINIRI: yalnız en yüksek chunk'ın kaldığı eşik
(ESIK = 2. chunk'ın oranının hemen üstü). Burada FP sürüyorsa hiçbir bağıl eşik
#103'ü çözmez.
Ayrıca (LLM yok): madde 34'teki 0.25 eşiği #103 bağlamını değiştiriyor mu.
--tarama: üst sınır eşiği 115 pozitifin kaçının bağlamını değiştiriyor (TP feda
riski; uzun sürer, yalnız kapı geçilirse; LLM testi tekrar koşulmaz).

Kullanım (kökten): python -u experiments/madde24_bagil_esik/on_test103.py [--tarama]
Çıktı: on_test103.jsonl, sonuc_on_test103.txt (--tarama: sonuc_tarama103.txt)
"""
import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(HERE), str(ROOT / "evaluation"), str(ROOT / "src"), str(ROOT)]

SET, QID = "test_5", "103"
ESIK_M34 = 0.25
TEKRAR = 2


def oranlar(chunks):
    top = chunks[0]["rerank_score"]
    return [c["rerank_score"] / top if top > 0 else 0.0 for c in chunks]


def main():
    import run_tests as T
    from benchmark_eval import classify_answer
    from gt_utils import load_ground_truth

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    R = sys.modules[T.get_top_chunks.__module__]
    gt = load_ground_truth()
    with open(ROOT / "evaluation/datasets" / f"{SET}.csv", encoding="utf-8-sig") as f:
        row = next(r for r in csv.DictReader(f) if r["id"] == QID)

    base = R.retrieve(row["soru"])
    o = oranlar(base)
    esik = (o[1] + 1.0) / 2 if len(o) > 1 else 1.0  # yalnız 1. chunk kalır
    lines = [f"{SET}#{QID}: {row['soru']}",
             "bağlam: " + ", ".join(f"{c['id']} {Path(c['source']).name} {c['page_info']} "
                                    f"rerank={c['rerank_score']:.5f} oran={r:.3f}" for c, r in zip(base, o)),
             f"madde 34 eşiği {ESIK_M34}: elenen {[c['id'] for c, r in zip(base, o) if r < ESIK_M34]}",
             f"üst sınır eşiği {esik:.3f}: kalan {[base[0]['id']]}", ""]

    if "--tarama" in sys.argv:
        degisen, toplam = [], 0
        for s in range(1, 5):
            with open(ROOT / "evaluation/datasets" / f"test_{s}.csv", encoding="utf-8-sig") as f:
                for r in csv.DictReader(f):
                    if r["dokumanda_var_mi"] != "Evet":
                        continue
                    toplam += 1
                    ch = R.retrieve(r["soru"])
                    if ch and "rerank_score" in ch[0]:
                        n = sum(x < esik for x in oranlar(ch))
                        if n:
                            degisen.append((f"test_{s}#{r['id']}", n))
                    print(f"tarama {toplam}: test_{s}#{r['id']}", flush=True)
        ozet = chr(10).join([f"üst sınır eşiği {esik:.3f} ile bağlamı değişen pozitif: {len(degisen)}/{toplam}",
                          "   " + ", ".join(f"{q}(-{n})" for q, n in degisen), ""])
        print(ozet)
        (HERE / "sonuc_tarama103.txt").write_text(ozet, encoding="utf-8")
        return

    print(chr(10).join(lines), flush=True)
    llm = T.load_model()
    sonuc = []
    for ad, chunks in (("V0", base), ("UST_SINIR", base[:1])):
        ctx = T.build_context(chunks, row["soru"])
        cevaplar = [T.ask(llm, ctx, row["soru"]) for _ in range(TEKRAR)]
        siniflar = [classify_answer({**row, "set": SET, "cevap": c}, gt) for c in cevaplar]
        sonuc.append({"varyant": ad, "baglam": [c["id"] for c in chunks], "cevaplar": cevaplar,
                      "siniflar": siniflar, "context": ctx})
        lines.append(f"=== {ad} bağlam {[c['id'] for c in chunks]}")
        lines += [f"  [{i + 1}] {s}: {c[:400]!r}" for i, (s, c) in enumerate(zip(siniflar, cevaplar))]
        lines.append(f"  tekrarlar aynı: {len(set(cevaplar)) == 1}")
        lines.append("")
    print("\n".join(lines))
    with open(HERE / "on_test103.jsonl", "w", encoding="utf-8") as f:
        f.write(json.dumps({"esik": esik, "oran": o, "sonuc": sonuc},
                           ensure_ascii=False) + "\n")
    (HERE / "sonuc_on_test103.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
