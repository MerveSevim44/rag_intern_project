"""
Madde 34 Adım 1b — #82: cevap chunk'ı (4185) bağlamda 1. sırada; hangi değişiklik
reti kaldırıyor? (Foundry, run_tests.py'nin kendi build_context / ask yolu)

Bağlam: retrieve(soru, dense_force_n=1) — madde 32 Adım 2 N=1 bağlamı (4185 1.).
Yalnız 4185'in metni değişir (varyant.py), diğer chunk'lar ve sıra aynı:
  V0 / A1 / A2 / B / C   bkz. varyant.py
Ek (plan dışı, ayrı etiketli):
  A1T  mekanik sembol eşlemesi bağlamdaki TÜM chunk'lara (gerçekçi politika)
  X3   V0, bağlamın 3. chunk'ı (dilbilgisi PDF'i "4.2 Türetme Ağacı" — sorudaki
       "türetme" ile sözcük eşleşmesi, konu dışı) çıkarılmış (bağlam 3 chunk)
  X3R  X3'ün kontrolü: dikkat dağıtıcının yerine aynı havuzun rerank 5.'si
       (bağlam yine 4 chunk) — "dikkat dağıtıcı" ile "daha az chunk"ı ayırır
Kontrol: aynı chunk'ı bağlamında taşıyan #83 / #84 / #89, bugünkü N=1 bağlamıyla.
Her biri 2 kez (temperature=0; tekrarlanabilirlik sağlaması).

Kullanım (kökten): python experiments/madde34_ingilizce_ret/uretim82.py [VARYANT ...]
  Varyant verilirse yalnız onlar (#82'de) koşulur; çıktı adına varyantlar eklenir.
Çıktı: uretim82[_VARYANT].jsonl, sonuc_uretim82[_VARYANT].txt
"""
import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(HERE), str(ROOT / "evaluation"), str(ROOT / "src"), str(ROOT)]

SET, QID = "test_3", "82"
KONTROL = ["83", "84", "89"]
DISTRAKTOR = ("8-Baglamdan_bagimsiz_dilbilgisi.pdf", "sayfa 7")
TEKRAR = 2


def main():
    import run_tests as T
    from benchmark_eval import classify_answer
    from gt_utils import load_ground_truth
    from varyant import CEVAP_ID, metin, pua_esle

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    R = sys.modules[T.get_top_chunks.__module__]
    gt = load_ground_truth()
    with open(ROOT / "evaluation/datasets" / f"{SET}.csv", encoding="utf-8-sig") as f:
        sorular = {r["id"]: r for r in csv.DictReader(f)}
    def baglam(qid, varyant):
        chunks = [dict(c) for c in R.retrieve(sorular[qid]["soru"], dense_force_n=1)]
        if varyant == "X3":
            assert (Path(chunks[2]["source"]).name, chunks[2]["page_info"]) == DISTRAKTOR
            return chunks[:2] + chunks[3:]
        if varyant == "X3R":
            bes = R.retrieve(sorular[qid]["soru"], dense_force_n=1, rerank_top_n=5)
            assert [c["id"] for c in bes[:4]] == [c["id"] for c in chunks]
            assert (Path(chunks[2]["source"]).name, chunks[2]["page_info"]) == DISTRAKTOR
            return chunks[:2] + chunks[3:] + [dict(bes[4])]
        if varyant == "A1T":
            for c in chunks:
                c["content"] = pua_esle(c["content"])
            return chunks
        if varyant != "V0":
            c = next(c for c in chunks if c["id"] == CEVAP_ID)
            c["content"] = metin(varyant, c["content"])
        return chunks

    isler = [(QID, v) for v in ["V0", "A1", "A2", "B", "C", "A1T", "X3"]]
    isler += [(q, "V0") for q in KONTROL]
    ek = sys.argv[1:]
    if ek:
        isler = [(QID, v) for v in ek]
    ad = "uretim82" + "".join(f"_{v}" for v in ek)
    # Embedding (Ollama, GPU) LLM yüklenmeden önce: ikisi aynı anda VRAM'de olunca
    # embedding runner'ı çöküyor; num_gpu=0 ise vektörleri değiştiriyor (madde 29).
    baglamlar = {(qid, v): baglam(qid, v) for qid, v in isler}
    llm = T.load_model()

    kayitlar, lines = [], [f"{SET}#{QID}: {sorular[QID]['soru']}", ""]
    for qid, v in isler:
        row = sorular[qid]
        chunks = baglamlar[(qid, v)]
        if qid == QID:
            assert chunks[0]["id"] == CEVAP_ID, "4185 bağlamda 1. değil"
        ctx = T.build_context(chunks, row["soru"])
        cevaplar = [T.ask(llm, ctx, row["soru"]) for _ in range(TEKRAR)]
        siniflar = [classify_answer({**row, "set": SET, "cevap": c}, gt) for c in cevaplar]
        k = {"soru_id": qid, "varyant": v, "baglam": [(c["id"], c["page_info"]) for c in chunks],
             "cevaplar": cevaplar, "siniflar": siniflar, "context": ctx}
        kayitlar.append(k)
        lines += [f"=== #{qid} {v}  bağlam {k['baglam']}"]
        lines += [f"  [{i + 1}] {s}: {c[:300]!r}" for i, (s, c) in enumerate(zip(siniflar, cevaplar))]
        lines.append(f"  tekrarlar aynı: {len(set(cevaplar)) == 1}")
        lines.append("")
        print("\n".join(lines[-(TEKRAR + 3):]), flush=True)

    with open(HERE / f"{ad}.jsonl", "w", encoding="utf-8") as f:
        for k in kayitlar:
            f.write(json.dumps(k, ensure_ascii=False) + "\n")
    (HERE / f"sonuc_{ad}.txt").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
