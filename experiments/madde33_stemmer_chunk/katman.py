"""
Madde 33 Adım 1 — #91: stemmer ve chunk birleştirme ayrı ayrı ne kazandırıyor?
(retrieval katmanları; LLM yok)

Her varyantta (V0, S, M, SM — bkz. varyant.py) madde 32 katman.py ile aynı ölçüm:
cevap chunk'ı (P1 = 4227; M/SM'de birleşik 4227) için dense / BM25 / hibrit
sıra, havuza girip girmediği, reranker skoru ve sırası, nihai bağlamda olup
olmadığı; ayrıca "Alis" paragrafının (4228; M/SM'de birleşik chunk'ın içinde)
nihai bağlamda olup olmadığı.

Kullanım (kökten): python experiments/madde33_stemmer_chunk/katman.py
Çıktı: katman.jsonl, sonuc_katman.txt
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(HERE), str(ROOT / "src"), str(ROOT)]

SET, QID = "test_4", "91"


def main():
    import csv
    import retrieval as R
    from embedder import rerank_indices
    from varyant import VARYANTLAR, P1, P2, kur, saglama_embedding

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

    with open(ROOT / "evaluation/datasets" / f"{SET}.csv", encoding="utf-8-sig") as f:
        soru = next(r["soru"] for r in csv.DictReader(f) if r["id"] == QID)

    lines = [f"{SET}#{QID}: {soru}",
             f"Yöntem sağlaması: P1 metni yeniden gömüldü, DB vektörüyle cosine = {saglama_embedding(R):.6f}", ""]
    kayitlar = []
    for v in VARYANTLAR:
        kur(R, v)
        normal = R.retrieve(soru)
        n = len(R._cache.rows)
        tum = R.retrieve(soru, top_k=n, rerank_top_n=n, use_reranker=False)
        sira = {c["id"]: i + 1 for i, c in enumerate(tum)}
        hedef = next(c for c in tum if c["id"] == P1)
        havuz = tum[:R.TOP_K]
        aday = {c["id"]: c for c in havuz + [hedef]}
        al = list(aday.values())
        rr = {al[i]["id"]: float(s) for s, i in rerank_indices(soru, [c["content"] for c in al])}
        havuz_rr = sorted(havuz, key=lambda c: rr[c["id"]], reverse=True)
        sagla = [c["id"] for c in havuz_rr[:R.RERANK_TOP_N]] == [c["id"] for c in normal]
        rr_sira = 1 + sum(1 for c in havuz if c["id"] != P1 and rr[c["id"]] > rr[P1])
        d = hedef["score_debug"]
        q_tok = R._tokenize(soru)
        nihai = [c["id"] for c in normal]
        k = {
            "varyant": v, "korpus": n, "sorgu_tokenlari": q_tok,
            "hedefte_gecen": sorted(set(q_tok) & set(R._tokenize(hedef["content"]))),
            "dense_cosine": d["dense_raw"], "dense_sira": d["dense_rank"],
            "bm25_ham": d["bm25_raw"], "bm25_sira": d["bm25_rank"],
            "hibrit_skor": hedef["score"], "hibrit_sira": sira[P1],
            "havuzda": P1 in {c["id"] for c in havuz},
            "rerank_skor": rr[P1], "rerank_havuz_ici_sira": rr_sira,
            "rerank_esik_TOPN": rr[havuz_rr[R.RERANK_TOP_N - 1]["id"]],
            "nihai": nihai, "nihai_page_info": [c["page_info"] for c in normal],
            "P1_nihaide": P1 in nihai,
            "alis_nihaide": (P2 in nihai) or ("M" in v and P1 in nihai),
            "sagla": sagla,
        }
        kayitlar.append(k)
        lines += [
            f"=== {v}  (korpus {n})",
            f"  sorgu token'ları: {q_tok} | hedefte geçen: {k['hedefte_gecen']}",
            f"  dense  cosine {k['dense_cosine']:.4f}  sıra {k['dense_sira']}",
            f"  BM25   ham {k['bm25_ham']:.3f}  sıra {k['bm25_sira'] or '— (0)'}",
            f"  hibrit sıra {k['hibrit_sira']}  -> {'HAVUZDA' if k['havuzda'] else 'havuz dışı'} (TOP_K={R.TOP_K})",
            f"  rerank skor {k['rerank_skor']:.4f}  havuz içi sıra {rr_sira}"
            f"{'' if k['havuzda'] else ' (havuzda olsaydı)'}  eşik ({R.RERANK_TOP_N}.) {k['rerank_esik_TOPN']:.4f}",
            f"  nihai bağlam: {list(zip(nihai, k['nihai_page_info']))}",
            f"  cevap paragrafı nihaide: {k['P1_nihaide']} | 'Alis' paragrafı nihaide: {k['alis_nihaide']}"
            f" | sağlama: {sagla}",
            "",
        ]
    kur(R, "V0")

    with open(HERE / "katman.jsonl", "w", encoding="utf-8") as f:
        for k in kayitlar:
            f.write(json.dumps(k, ensure_ascii=False) + "\n")
    text = "\n".join(lines)
    (HERE / "sonuc_katman.txt").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
