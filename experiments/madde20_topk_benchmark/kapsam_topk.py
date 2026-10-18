"""
Madde 20 (2. alt konu) — kapsam ölçümü: benchmark `top_k=5`
(`evaluation/run_tests.py::run_single_test`) ile arayüz `TOP_K=8`
(`src/retrieval.py`, `src/app.py` slider varsayılanı) arasındaki fark
kaç soruda retrieval çıktısını gerçekten değiştiriyor?

DB'ye yazmaz. Her soru için `retrieve()` iki kez çağrılır (top_k=5 ve
top_k=8), reranker ve rerank_top_n (4) her ikisinde de aynı — tek değişken
hibrit aday havuzu boyutu. Nihai (reranker sonrası) 4 chunk'lık liste
(kaynak + page_info sırasıyla) karşılaştırılır.

Kapsam: tam benchmark (test_1..test_5, 115 soru) + test_negative (32) = 147.

Kullanım (yerel ortamda, Ollama + rag.db + reranker modeli hazırken):
    python -u experiments/madde20_topk_benchmark/kapsam_topk.py
Çıktı: kapsam_topk.jsonl (soru başına), sonuc_kapsam_topk.txt (özet).
"""
import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]

SETS = ["test_1", "test_2", "test_3", "test_4", "test_5", "test_negative"]


def _sorular():
    out = []
    for set_name in SETS:
        with open(ROOT / "evaluation" / "datasets" / f"{set_name}.csv", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                out.append((set_name, row["id"], row["soru"]))
    return out


def _imza(chunks):
    """Karsilastirma icin sade imza: (kaynak, page_info) sirali listesi."""
    return [(Path(c["source"]).name, c.get("page_info")) for c in chunks]


def main():
    from retrieval import retrieve  # noqa: E402

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

    sorular = _sorular()
    print(f"Toplam soru: {len(sorular)}")

    farkli = []
    with open(HERE / "kapsam_topk.jsonl", "w", encoding="utf-8") as f:
        for n, (set_name, qid, soru) in enumerate(sorular, 1):
            r5 = retrieve(soru, top_k=5)
            r8 = retrieve(soru, top_k=8)
            sig5, sig8 = _imza(r5), _imza(r8)
            ayni = sig5 == sig8
            rec = {"set": set_name, "id": qid, "soru": soru,
                   "top_k5": sig5, "top_k8": sig8, "ayni": ayni}
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            print(f"[{n}/{len(sorular)}] {set_name}#{qid}: {'AYNI' if ayni else 'FARKLI'}")
            if not ayni:
                farkli.append(rec)

    lines = [f"Toplam soru: {len(sorular)}", f"Farkli sonuc veren: {len(farkli)}", ""]
    for rec in farkli:
        lines.append(f"{rec['set']}#{rec['id']}: {rec['soru'][:70]!r}")
        lines.append(f"   top_k=5: {rec['top_k5']}")
        lines.append(f"   top_k=8: {rec['top_k8']}")
    text = "\n".join(lines) + "\n"
    (HERE / "sonuc_kapsam_topk.txt").write_text(text, encoding="utf-8")
    print("\n" + text)


if __name__ == "__main__":
    main()
