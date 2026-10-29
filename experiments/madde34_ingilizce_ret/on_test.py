"""
Madde 34 Adım 3 ön-test — (a) bağıl rerank eşiği #82'de işe yarar mı? (sweep değil)

Bağıl eşik: rerank_score / ilk chunk'ın rerank_score'u < ESIK olan chunk bağlamdan
çıkar (madde 24'teki bağıl eşik fikri; src/ değişmez, süreç içi).
#82, N=1 bağlamı: 4185 (cevap, 1.), 4187, 4333 (zararlı, Adım 1), 4184. 4333'ün oranı
4184'ünkünden büyük olduğu için 4333'ü eleyen her eşik 4184'ü de eler; bu script
bunu canlı skorlarla doğrular ve kalan bağlamla üretimi 2 kez koşar.
Doğruluk elle, GT referansıyla (sonuc_on_test.txt'ye GT de basılır).

Kullanım (kökten): python experiments/madde34_ingilizce_ret/on_test.py
Çıktı: on_test.jsonl, sonuc_on_test.txt
"""
import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(HERE), str(ROOT / "evaluation"), str(ROOT / "src"), str(ROOT)]

SET, QID = "test_3", "82"
ESIK = 0.25
ZARARLI, YAN = 4333, 4184
TEKRAR = 2


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

    base = R.retrieve(row["soru"], dense_force_n=1)
    top = base[0]["rerank_score"]
    oran = {c["id"]: c["rerank_score"] / top for c in base}
    kalan = [c for c in base if oran[c["id"]] >= ESIK]
    lines = [f"{SET}#{QID}: {row['soru']}",
             "GT: " + json.dumps(gt[QID]["referans_cevaplar"], ensure_ascii=False),
             f"eşik={ESIK}  oranlar: " + ", ".join(f"{i}={o:.3f}" for i, o in oran.items()),
             f"elenen: {[c['id'] for c in base if c not in kalan]}  kalan: {[c['id'] for c in kalan]}", ""]
    assert ZARARLI not in [c["id"] for c in kalan] and YAN not in [c["id"] for c in kalan]

    llm = T.load_model()
    ctx = T.build_context(kalan, row["soru"])
    cevaplar = [T.ask(llm, ctx, row["soru"]) for _ in range(TEKRAR)]
    siniflar = [classify_answer({**row, "set": SET, "cevap": c}, gt) for c in cevaplar]
    lines += [f"  [{i + 1}] {s}: {c!r}" for i, (s, c) in enumerate(zip(siniflar, cevaplar))]
    lines.append(f"  tekrarlar aynı: {len(set(cevaplar)) == 1}")
    print("\n".join(lines))
    with open(HERE / "on_test.jsonl", "w", encoding="utf-8") as f:
        f.write(json.dumps({"esik": ESIK, "oran": oran, "kalan": [c["id"] for c in kalan],
                            "cevaplar": cevaplar, "siniflar": siniflar, "context": ctx},
                           ensure_ascii=False) + "\n")
    (HERE / "sonuc_on_test.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
