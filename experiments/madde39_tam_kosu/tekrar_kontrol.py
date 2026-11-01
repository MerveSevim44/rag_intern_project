"""
Madde 39 kapanış — iki yeni FN (test_2#48, test_3#90; v8'de TP, bugün FN) bağlam
değişikliğiyle açıklanmıyor (Ön-ölçüm A bu sorularda 0 fark bulmuştu). Üretim-zamanı
(generation) kararsızlığı mı diye, retrieve() ile kurulan GÜNCEL bağlamla 2 kez
yeniden soruluyor (temperature=0; aynı bağlam, LLM tekrar denendiğinde kararlı mı?).

Kullanım (kökten): python -u experiments/madde39_tam_kosu/tekrar_kontrol.py
"""
import csv
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(HERE), str(ROOT / "evaluation"), str(ROOT / "src"), str(ROOT)]

SORULAR = [("test_2", "48"), ("test_3", "90")]
TEKRAR = 3


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
    satirlar = {}
    for s, i in SORULAR:
        with open(ROOT / "evaluation/datasets" / f"{s}.csv", encoding="utf-8-sig") as f:
            satirlar[(s, i)] = next(r for r in csv.DictReader(f) if r["id"] == i)

    baglamlar = {(s, i): R.retrieve(satirlar[(s, i)]["soru"]) for s, i in SORULAR}
    llm = T.load_model()
    for s, i in SORULAR:
        row = satirlar[(s, i)]
        chunks = baglamlar[(s, i)]
        ctx = T.build_context(chunks, row["soru"])
        print(f"=== {s}#{i}  bağlam {[(c['id'], c['page_info']) for c in chunks]}")
        for n in range(TEKRAR):
            cevap = T.ask(llm, ctx, row["soru"])
            sinif = classify_answer({**row, "set": s, "cevap": cevap}, gt)
            print(f"  [{n + 1}] {sinif}: {cevap[:200]!r}")


if __name__ == "__main__":
    main()
