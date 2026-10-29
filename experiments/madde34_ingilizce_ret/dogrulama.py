"""
Madde 34 Adım 2b — genelleme taramasının adaylarında X / XR izolasyonu (Foundry).

Adım 1'deki #82 testinin aynısı:
  V0   bugünkü N=0 bağlamı (sınıf bugün hâlâ FN mi?)
  X    şüpheli chunk(lar) çıkarılır (bağlam kısalır)        -> TP mi?
  XR   şüpheli chunk(lar)ın yerine aynı havuzun rerank sırasındaki sonraki
       chunk'ları (bağlam uzunluğu aynı)                       -> hâlâ TP mi?
Yalnız X ve XR'nin ikisi de TP ise aday "doğrulanmış" sayılır.

Adaylar (sonuc_genelleme.txt):
  test_4 #100  cevap 4358 1.; 3./4. sırada test1.txt chunk'ları (ortak: merak, sayfa)
  test_2 #56   cevap 4112 ($.metadata) 1.; 2–4. sırada profil chunk'ları
               (aynı kaynak, konu dışı; ortak: alan, ver)
Her biri 2 tekrar, temperature=0. Bağlamlar LLM yüklenmeden önce kurulur
(uretim82.py'deki VRAM notu).

Kullanım (kökten): python experiments/madde34_ingilizce_ret/dogrulama.py
Çıktı: dogrulama.jsonl, sonuc_dogrulama.txt
"""
import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(HERE), str(ROOT / "evaluation"), str(ROOT / "src"), str(ROOT)]

TEKRAR = 2
HAVUZ = 8  # TOP_K: reranker'a giren havuz
ADAYLAR = [
    # (set, id, cevap chunk'ı, şüpheli chunk kümeleri — her küme ayrı bir X/XR)
    ("test_4", "100", 4358, [[4353], [4355], [4353, 4355]]),
    ("test_2", "56", 4112, [[3777, 3773, 3775]]),
]


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
    for set_ in {a[0] for a in ADAYLAR}:
        with open(ROOT / "evaluation/datasets" / f"{set_}.csv", encoding="utf-8-sig") as f:
            satirlar.update({(set_, r["id"]): r for r in csv.DictReader(f)})

    isler = []
    for set_, qid, cevap_id, kumeler in ADAYLAR:
        soru = satirlar[(set_, qid)]["soru"]
        havuz = R.retrieve(soru, dense_force_n=0, rerank_top_n=HAVUZ)
        base = R.retrieve(soru, dense_force_n=0)
        assert [c["id"] for c in havuz[:len(base)]] == [c["id"] for c in base]
        assert base[0]["id"] == cevap_id, f"{set_}#{qid}: cevap chunk'ı 1. değil"
        isler.append((set_, qid, "V0", base))
        yedek = havuz[len(base):]
        for kume in kumeler:
            assert set(kume) <= {c["id"] for c in base}, (qid, kume)
            etiket = "+".join(map(str, kume))
            isler.append((set_, qid, f"X[{etiket}]", [c for c in base if c["id"] not in kume]))
            yerine = iter(yedek)
            isler.append((set_, qid, f"XR[{etiket}]",
                          [next(yerine) if c["id"] in kume else c for c in base]))

    llm = T.load_model()
    kayitlar, lines = [], []
    for set_, qid, v, chunks in isler:
        row = satirlar[(set_, qid)]
        ctx = T.build_context(chunks, row["soru"])
        cevaplar = [T.ask(llm, ctx, row["soru"]) for _ in range(TEKRAR)]
        siniflar = [classify_answer({**row, "set": set_, "cevap": c}, gt) for c in cevaplar]
        k = {"set": set_, "id": qid, "varyant": v,
             "baglam": [(c["id"], Path(c["source"]).name, c["page_info"], round(c.get("rerank_score", 0), 5))
                        for c in chunks],
             "cevaplar": cevaplar, "siniflar": siniflar, "context": ctx}
        kayitlar.append(k)
        lines += [f"=== {set_}#{qid} {v}  bağlam {k['baglam']}"]
        lines += [f"  [{i + 1}] {s}: {c[:300]!r}" for i, (s, c) in enumerate(zip(siniflar, cevaplar))]
        lines.append(f"  tekrarlar aynı: {len(set(cevaplar)) == 1}")
        lines.append("")
        print("\n".join(lines[-(TEKRAR + 3):]), flush=True)

    with open(HERE / "dogrulama.jsonl", "w", encoding="utf-8") as f:
        for k in kayitlar:
            f.write(json.dumps(k, ensure_ascii=False) + "\n")
    (HERE / "sonuc_dogrulama.txt").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
