"""
Madde 33 Adım 1 — #91: her bağlam üretimde cevabı getiriyor mu? (Foundry + Ollama)

run_tests.py'nin kendi fonksiyonlarıyla (get_top_chunks -> build_context -> ask),
süreç içinde; varyantlar varyant.py ile src.retrieval modülüne uygulanır.
  V0   mevcut sistem (cevap paragrafı bağlamda yok)
  S    stemmer oracle (katman: P1 havuza giriyor, reranker 5. -> bağlam = V0)
  M    birleşik paragraf 1-2 (bağlamda 1.)
  G2   S'nin reranker engelini aşsaydı: V0 bağlamı, P1 AYRI chunk olarak 2. sıraya
       (P2'nin hemen arkası), son chunk düşer — iki paragraf ayrı ama ikisi de bağlamda
  G4   aynı, P1 4. sıraya (reranker'ın 5.'yi 4.'ye almasına en yakın durum)
Her biri 2 kez (temperature=0; tekrarlanabilirlik sağlaması).

Kullanım (kökten): python experiments/madde33_stemmer_chunk/uretim91.py
Çıktı: uretim91.jsonl, sonuc_uretim91.txt
"""
import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(HERE), str(ROOT / "evaluation"), str(ROOT / "src"), str(ROOT)]

SET, QID = "test_4", "91"
TEKRAR = 2


def main():
    import run_tests as T
    from benchmark_eval import classify_answer
    from gt_utils import load_ground_truth
    from varyant import P1, kur

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    R = sys.modules[T.get_top_chunks.__module__]
    gt = load_ground_truth()
    with open(ROOT / "evaluation/datasets" / f"{SET}.csv", encoding="utf-8-sig") as f:
        row = next(r for r in csv.DictReader(f) if r["id"] == QID)
    soru = row["soru"]
    llm = T.load_model()

    def zorla(pos):
        kur(R, "V0")
        base = R.retrieve(soru)
        n = len(R._cache.rows)
        p1 = next(c for c in R.retrieve(soru, top_k=n, rerank_top_n=n, use_reranker=False) if c["id"] == P1)
        chunks = [c for c in base if c["id"] != P1][:len(base) - 1]
        chunks.insert(pos - 1, p1)
        return chunks

    kayitlar, lines = [], [f"{SET}#{QID}: {soru}", f"GT: {row.get('referans_cevap', '')}", ""]
    for v in ["V0", "S", "M", "G2", "G4"]:
        if v in ("V0", "S", "M"):
            kur(R, v)
            chunks = R.retrieve(soru)
        else:
            chunks = zorla(int(v[1]))
        ctx = T.build_context(chunks, soru)
        cevaplar = [T.ask(llm, ctx, soru) for _ in range(TEKRAR)]
        siniflar = [classify_answer({**row, "set": SET, "cevap": c}, gt) for c in cevaplar]
        k = {"varyant": v, "baglam": [(c["id"], c["page_info"]) for c in chunks],
             "cevaplar": cevaplar, "siniflar": siniflar, "context": ctx}
        kayitlar.append(k)
        lines += [f"=== {v}  bağlam {k['baglam']}"]
        lines += [f"  [{i + 1}] {s}: {c[:220]!r}" for i, (s, c) in enumerate(zip(siniflar, cevaplar))]
        lines.append(f"  tekrarlar aynı: {len(set(cevaplar)) == 1}")
        lines.append("")
        print("\n".join(lines[-(TEKRAR + 3):]))
    kur(R, "V0")

    with open(HERE / "uretim91.jsonl", "w", encoding="utf-8") as f:
        for k in kayitlar:
            f.write(json.dumps(k, ensure_ascii=False) + "\n")
    (HERE / "sonuc_uretim91.txt").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
