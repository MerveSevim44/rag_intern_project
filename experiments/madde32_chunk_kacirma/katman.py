"""
Madde 32 Adım 1 — cevap chunk'ı hangi katmanda kayboluyor? (yalnız ölçüm)

Sorular: test_3 #79, test_3 #82, test_4 #91. Cevap chunk'ları GT referansı ve
anahtar kelimeleriyle elle belirlendi (chunk düzeyinde GT yok):
  #79 -> id 4183  Fourier sayfa 10 "Ölçekleme (Scaling)": "Extent in time
                  domain is inversely proportional to extent in freq…"
  #82 -> id 4185  Fourier sayfa 12 "Sinuzoidal Genlik Modülasyonu":
                  "Multiplication in the time domain is convolution in the
                  frequency domain"
  #91 -> id 4227  test1.txt paragraf 1: "… devasa bir kütüphane yükselirdi:
                  Gümüş Yaprak."

Yöntem (src/ değişmez, DB'ye yazılmaz):
1. retrieve(top_k=tüm korpus, use_reranker=False) -> her chunk'ın score_debug'ı
   (dense cosine + sıra, BM25 ham + sıra, RRF, boost'lar) ve nihai hibrit skor.
   Hibrit sıralama retrieve()'ün kendi sıralaması; ilk TOP_K = gerçek aday havuzu.
2. Reranker (cross-encoder, çift başına bağımsız skor) yalnız havuz + cevap
   chunk'ı + aynı dosyanın diğer chunk'ları üzerinde çağrılır. Sağlama: havuzun
   rerank sonrası ilk RERANK_TOP_N'i, normal retrieve() çıktısıyla aynı olmalı.

LLM/Groq/Foundry yok; Ollama (bge-m3) + reranker modeli gerekir.
Kullanım (kökten): python experiments/madde32_chunk_kacirma/katman.py
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]

HEDEF = {
    "79": ("test_3", 4183),
    "82": ("test_3", 4185),
    "91": ("test_4", 4227),
}


def soru_metni(set_name, qid):
    import csv
    with open(ROOT / "evaluation/datasets" / f"{set_name}.csv", encoding="utf-8-sig") as f:
        return next(r["soru"] for r in csv.DictReader(f) if r["id"] == qid)


def main():
    from retrieval import retrieve, TOP_K, RERANK_TOP_N, _cache, _tokenize
    from embedder import rerank_indices

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

    kayitlar = []
    for qid, (set_name, hedef_id) in HEDEF.items():
        soru = soru_metni(set_name, qid)
        normal = retrieve(soru)  # gerçek davranış (sağlama için)
        n = len(_cache.rows)
        tum = retrieve(soru, top_k=n, rerank_top_n=n, use_reranker=False)
        assert len(tum) == n, (len(tum), n)
        hibrit_sira = {c["id"]: i + 1 for i, c in enumerate(tum)}
        hedef = next(c for c in tum if c["id"] == hedef_id)
        havuz = tum[:TOP_K]
        hedef_kaynak = hedef["source"]
        ayni_dosya = [c for c in tum if c["source"] == hedef_kaynak]

        # Reranker: havuz + hedef (havuzda değilse) + aynı dosyanın chunk'ları
        aday = {c["id"]: c for c in havuz + [hedef] + ayni_dosya}
        aday_list = list(aday.values())
        rr = {aday_list[i]["id"]: float(s) for s, i in rerank_indices(soru, [c["content"] for c in aday_list])}

        havuz_rr = sorted(havuz, key=lambda c: rr[c["id"]], reverse=True)
        sagla = [c["id"] for c in havuz_rr[:RERANK_TOP_N]] == [c["id"] for c in normal]
        hedef_havuzda = hedef_id in {c["id"] for c in havuz}
        # Hedef havuzda olsaydı / olduğunda havuz içi rerank sırası
        hedef_rr_havuz_sira = 1 + sum(1 for c in havuz if c["id"] != hedef_id and rr[c["id"]] > rr[hedef_id])
        dosya_rr_sira = 1 + sum(1 for c in ayni_dosya if c["id"] != hedef_id and rr[c["id"]] > rr[hedef_id])
        dosya_hibrit_sira = 1 + sum(1 for c in ayni_dosya if c["id"] != hedef_id and c["score"] > hedef["score"])
        d = hedef["score_debug"]
        q_tokens = _tokenize(soru)
        hedef_tokens = set(_tokenize(hedef["content"]))

        kayit = {
            "set": set_name, "id": qid, "soru": soru, "hedef_chunk": hedef_id,
            "hedef_page_info": hedef["page_info"], "korpus": n,
            "bm25_sorgu_tokenlari": q_tokens,
            "bm25_hedefte_gecen": sorted(set(q_tokens) & hedef_tokens),
            "dense_cosine": d["dense_raw"], "dense_sira": d["dense_rank"],
            "bm25_ham": d["bm25_raw"], "bm25_sira": d["bm25_rank"],
            "rrf": d["rrf"], "boost": d["keyword_boost"] + d["meta_boost"] + d["hint_boost"],
            "hibrit_skor": hedef["score"], "hibrit_sira": hibrit_sira[hedef_id],
            "hibrit_esik_skor_TOPK": havuz[-1]["score"],
            "havuzda": hedef_havuzda,
            "rerank_skor": rr[hedef_id],
            "rerank_havuz_ici_sira": hedef_rr_havuz_sira,
            "rerank_esik_skor_TOPN": rr[havuz_rr[RERANK_TOP_N - 1]["id"]],
            "dosya_chunk_sayisi": len(ayni_dosya),
            "dosya_ici_hibrit_sira": dosya_hibrit_sira,
            "dosya_ici_rerank_sira": dosya_rr_sira,
            "sagla_normal_retrieve_ile_ayni": sagla,
            "havuz": [{"id": c["id"], "kaynak": Path(c["source"]).name, "page_info": c["page_info"],
                       "hibrit": round(c["score"], 4), "dense_sira": c["score_debug"]["dense_rank"],
                       "bm25_sira": c["score_debug"]["bm25_rank"], "rerank": round(rr[c["id"]], 4)}
                      for c in havuz],
            "dosya_ici": [{"id": c["id"], "page_info": c["page_info"], "hibrit_sira": hibrit_sira[c["id"]],
                           "dense_sira": c["score_debug"]["dense_rank"], "bm25_sira": c["score_debug"]["bm25_rank"],
                           "rerank": round(rr[c["id"]], 4)} for c in ayni_dosya],
        }
        kayitlar.append(kayit)

        print(f"\n=== {set_name}#{qid}: {soru}")
        print(f"  hedef chunk {hedef_id} ({hedef['page_info']}) — korpus {n}, dosyada {len(ayni_dosya)} chunk")
        print(f"  BM25 sorgu token'ları: {q_tokens}")
        print(f"  hedefte geçen token'lar: {kayit['bm25_hedefte_gecen']}")
        print(f"  dense : cosine {d['dense_raw']:.4f}  sıra {d['dense_rank']}/{n}")
        print(f"  BM25  : ham {d['bm25_raw']:.3f}  sıra {d['bm25_rank'] or '— (skor 0, RRF katkısı yok)'}")
        print(f"  hibrit: skor {hedef['score']:.4f}  sıra {hibrit_sira[hedef_id]}/{n}  "
              f"(havuz eşiği = {TOP_K}. aday {havuz[-1]['score']:.4f}) -> "
              f"{'HAVUZDA' if hedef_havuzda else 'HAVUZA GİRMİYOR'}")
        print(f"  rerank: skor {rr[hedef_id]:.4f}  havuz içi sıra {hedef_rr_havuz_sira}"
              f"{'' if hedef_havuzda else ' (havuzda olsaydı)'}  "
              f"(nihai eşik = {RERANK_TOP_N}. {kayit['rerank_esik_skor_TOPN']:.4f})")
        print(f"  dosya içi: hibrit sıra {dosya_hibrit_sira}/{len(ayni_dosya)}, "
              f"rerank sıra {dosya_rr_sira}/{len(ayni_dosya)}")
        print(f"  sağlama (havuz rerank ilk {RERANK_TOP_N} == normal retrieve): {sagla}")
        print("  havuz:")
        for h in kayit["havuz"]:
            print(f"    {h['id']:>5} {h['kaynak'][:32]:<32} {str(h['page_info'])[:16]:<16} "
                  f"hibrit {h['hibrit']:.4f} d#{h['dense_sira']:<4} b#{str(h['bm25_sira']):<4} rr {h['rerank']:.4f}")

    with open(HERE / "katman.jsonl", "w", encoding="utf-8") as f:
        for k in kayitlar:
            f.write(json.dumps(k, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
