"""
Madde 32 Adım 1 — kaba kapsam: "doğru dosya, doğru chunk yok" kaç pozitif soruda?

İki ölçüt, tam benchmark (test_1..test_5) POZİTİF soruları (benchmark_eval
question_polarity) üzerinde, yalnız semantic_rag rotasında:

A) GT terimi (madde 20 kapsam_topk.py ile aynı çağrı: retrieve(soru), varsayılan
   parametreler): nihai bağlamda beklenen dosya var mı ve GT 'anahtar_kelimeler'
   alanından kaçı nihai chunk metinlerinde geçiyor? "Dosya var, terim 0" =
   şüpheli. Gürültülü: GT terimleri Türkçe parafraz olabilir, doküman İngilizce
   olabilir (#79).
B) RRF mekanizması (GT'den bağımsız; #79/#82'de bulunan): dense sıralamasında
   1. olan chunk'ın BM25 skoru 0 mı ve bu yüzden TOP_K aday havuzunun dışında
   mı kalıyor? (BM25=0 chunk'ın normalize RRF tavanı 0.5.)

LLM/Groq/Foundry yok; Ollama + reranker gerekir. DB'ye yazmaz.
Kullanım (kökten): python -u experiments/madde32_chunk_kacirma/kapsam.py
Çıktı: kapsam.jsonl, sonuc_kapsam.txt
"""
import ast
import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT / "evaluation"), str(ROOT / "src"), str(ROOT)]

SETS = ["test_1", "test_2", "test_3", "test_4", "test_5"]


def _terimler(entry):
    kw = entry.get("anahtar_kelimeler") or []
    if isinstance(kw, str):
        try:
            kw = ast.literal_eval(kw)
        except (ValueError, SyntaxError):
            kw = [kw]
    return [k for k in kw if str(k).strip()]


def main():
    from benchmark_eval import question_polarity
    from gt_utils import load_ground_truth
    from retrieval import retrieve, TOP_K, _cache

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

    gt = load_ground_truth()
    kayitlar = []
    for set_name in SETS:
        with open(ROOT / "evaluation/datasets" / f"{set_name}.csv", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                is_negative, _ = question_polarity(row, gt)
                if is_negative:
                    continue
                soru, beklenen = row["soru"], row["beklenen_kaynak"].strip()
                nihai = retrieve(soru)
                rota = (nihai[0].get("route") if nihai else None) or ""
                rec = {"set": set_name, "id": row["id"], "soru": soru, "beklenen": beklenen, "rota": rota}
                if rota != "semantic_rag":
                    kayitlar.append(rec)
                    print(f"{set_name}#{row['id']}: rota={rota} (atlandı)")
                    continue
                # A) GT terimi
                metin = "\n".join(c["content"] for c in nihai).lower()
                terimler = _terimler(gt.get(row["id"], {}))
                gecen = [t for t in terimler if str(t).lower() in metin]
                dosya_var = any(Path(c["source"]).name == beklenen for c in nihai)
                # B) dense #1 chunk havuz dışında mı?
                n = len(_cache.rows)
                tum = retrieve(soru, top_k=n, rerank_top_n=n, use_reranker=False)
                d1 = min(tum, key=lambda c: c["score_debug"]["dense_rank"])
                d1_sira = next(i for i, c in enumerate(tum, 1) if c["id"] == d1["id"])
                rec.update({
                    "dosya_var": dosya_var, "terim_sayisi": len(terimler), "terim_gecen": len(gecen),
                    "nihai": [[Path(c["source"]).name, c["page_info"]] for c in nihai],
                    "dense1_id": d1["id"], "dense1_kaynak": Path(d1["source"]).name,
                    "dense1_page": d1["page_info"], "dense1_bm25": d1["score_debug"]["bm25_raw"],
                    "dense1_hibrit_sira": d1_sira, "dense1_havuz_disi": d1_sira > TOP_K,
                    "dense1_nihaide": any(c["id"] == d1["id"] for c in nihai),
                })
                kayitlar.append(rec)
                print(f"{set_name}#{row['id']}: dosya={'+' if dosya_var else '-'} "
                      f"terim {len(gecen)}/{len(terimler)} | dense#1 {rec['dense1_kaynak'][:24]} "
                      f"{rec['dense1_page']} bm25={rec['dense1_bm25']:.2f} hibrit#{d1_sira}"
                      f"{' HAVUZ DIŞI' if rec['dense1_havuz_disi'] else ''}")

    with open(HERE / "kapsam.jsonl", "w", encoding="utf-8") as f:
        for k in kayitlar:
            f.write(json.dumps(k, ensure_ascii=False) + "\n")

    sem = [k for k in kayitlar if k["rota"] == "semantic_rag"]
    a = [k for k in sem if k["dosya_var"] and k["terim_sayisi"] and k["terim_gecen"] == 0]
    b = [k for k in sem if k["dense1_havuz_disi"]]
    b0 = [k for k in b if k["dense1_bm25"] == 0]
    b_dosya = [k for k in b0 if k["dense1_kaynak"] == k["beklenen"]]
    lines = [
        f"Pozitif soru: {len(kayitlar)} | semantic_rag: {len(sem)} | diğer rota (atlandı): {len(kayitlar) - len(sem)}",
        "",
        f"A) Beklenen dosya nihai bağlamda AMA GT terimlerinin hiçbiri yok: {len(a)}",
        *[f"   {k['set']}#{k['id']} (0/{k['terim_sayisi']}) {k['soru'][:70]!r}" for k in a],
        "",
        f"B) Dense #1 chunk TOP_K havuzu dışında: {len(b)} (BM25=0 olan: {len(b0)}; "
        f"bunlardan dense #1 beklenen dosyadan: {len(b_dosya)})",
        *[f"   {k['set']}#{k['id']} dense#1={k['dense1_kaynak'][:28]} {k['dense1_page']} "
          f"bm25={k['dense1_bm25']:.2f} hibrit#{k['dense1_hibrit_sira']} | {k['soru'][:60]!r}" for k in b],
        "",
        "A ∩ B: " + ", ".join(f"{k['set']}#{k['id']}" for k in a if k in b),
    ]
    text = "\n".join(lines) + "\n"
    (HERE / "sonuc_kapsam.txt").write_text(text, encoding="utf-8")
    print("\n" + text)


if __name__ == "__main__":
    main()
