"""
Madde 22 kapsam ölçümü — Örnek/Cevap sayfa birleştirmenin retrieval etkisi,
gerçek DB'ye dokunmadan (servis: Ollama + reranker; LLM gerekmez).

Birleştirme kuralı R (belgeye özel değil): bir PDF sayfası OCR'lanmışsa
(metin katmanı < OCR_MAX_TEXT_CHARS ve resim var) VE başlığındaki bölüm
numarası (ör. "4.5.2.") bir önceki sayfanınkiyle aynıysa, önceki sayfanın
chunk'ına eklenir. Bugünkü korpusta tam 5 çift: gramer PDF'i 22+23, 24+25,
26+27, 28+29, 30+31 (diğer PDF'lerde OCR sayfası yok; 18/19 aynı numaralı ama
OCR değil).

1. rag.db scratchpad'e kopyalanır (gerçek DB salt okunur kullanılır).
2. Kopyada her çiftin Cevap chunk'ı silinir, Örnek chunk'ının içeriği
   "Örnek\\nCevap" olur, page_info "sayfa N-M" olur, embedding ingest'in kendi
   get_embeddings fonksiyonuyla yeniden üretilir. Diğer 906 chunk ve
   embedding'leri aynen kalır.
3. 147 benchmark sorusu (test_1..5 + negatif) iki DB'de AYNI SÜREÇTE
   retrieve(top_k=5) ile koşulur (oturumlar arası kayma — madde 29 — karışmasın).
4. Hedef 5 soru (#24, #25, #26, #28, #29) için bugünkü DB'de doğru Cevap
   sayfasının hibrit sırası (rerank öncesi, ilk 40) ayrıca ölçülür.

Kullanım:
    HF_HUB_OFFLINE=1 python -u experiments/madde22_ornek_cevap/simulasyon.py SCRATCH_DIR
Çıktı: simulasyon.jsonl (soru × db), cevap_sirasi.txt; özet için analiz.py.
"""
import contextlib
import csv
import io
import json
import re
import shutil
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
# src ÖNCE: kökteki ingest.py / retrieval.py yönlendirme katmanları alt çizgili
# yardımcıları dışarı vermiyor (benchmark_eval ile aynı tuzak).
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]

import pdfplumber  # noqa: E402
from ingest import _page_text_with_subscripts, OCR_MAX_TEXT_CHARS, get_embeddings  # noqa: E402
import retrieval  # noqa: E402

SETS = ["test_1", "test_2", "test_3", "test_4", "test_5", "test_negative"]
SECTION_RE = re.compile(r"^\s*-?(\d+(?:\.\d+)+)\.?\s")
TARGETS = {"24": 23, "25": 27, "26": 25, "28": 29, "29": 31}   # test_1 id -> doğru Cevap sayfası


def merge_pairs(con):
    """Kural R'ye uyan (pdf, önceki sayfa, OCR sayfası) üçlüleri."""
    pairs = []
    for (src,) in con.execute("select distinct source from chunks where source like '%.pdf'"):
        pages = {}
        for p, t in con.execute("select page_info, content from chunks where source=? order by id", (src,)):
            pages.setdefault(p, t)
        with pdfplumber.open(ROOT / src) as doc:
            info = []
            for n, page in enumerate(doc.pages, 1):
                t = _page_text_with_subscripts(page)
                ocr = len(t.strip()) < OCR_MAX_TEXT_CHARS and bool(page.images)
                first = (pages.get(f"sayfa {n}") or "").strip().split("\n")[0]
                m = SECTION_RE.match(first)
                info.append((n, ocr, m.group(1) if m else None))
        for (a, _, sa), (b, ocr_b, sb) in zip(info, info[1:]):
            if ocr_b and sa and sa == sb:
                pairs.append((src, a, b))
    return pairs


def build_sim_db(scratch):
    sim = Path(scratch) / "rag_madde22_sim.db"
    shutil.copyfile(ROOT / "rag.db", sim)
    con = sqlite3.connect(sim)
    pairs = merge_pairs(con)
    merged = []
    for src, a, b in pairs:
        (ida, ta), = con.execute("select id, content from chunks where source=? and page_info=?", (src, f"sayfa {a}"))
        (idb, tb), = con.execute("select id, content from chunks where source=? and page_info=?", (src, f"sayfa {b}"))
        merged.append((ida, idb, f"{ta}\n{tb}", f"sayfa {a}-{b}"))
    embs = get_embeddings([m[2] for m in merged])
    for (ida, idb, text, page), emb in zip(merged, embs):
        con.execute("update chunks set content=?, page_info=?, embedding=? where id=?",
                    (text, page, json.dumps(emb), ida))
        con.execute("delete from chunks where id=?", (idb,))
    con.commit()
    n = con.execute("select count(*) from chunks").fetchone()[0]
    con.close()
    print(f"Sim DB: {sim}  birlesen cift: {[(Path(s).name, a, b) for s, a, b in pairs]}  chunk: {n}")
    return sim, pairs


def answer_page_ranks(questions):
    """Bugünkü DB'de hedef sorular için doğru Cevap sayfasının hibrit sırası (ilk 40)."""
    lines = []
    for i, cevap in TARGETS.items():
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            retrieval.retrieve(questions[("test_1", i)], top_k=40, use_reranker=False, debug=True)
        rows = [l for l in buf.getvalue().splitlines() if re.match(r"\s*\d+\s+\d+\s+sayfa", l)]
        rank = next((int(l.split()[0]) for l in rows if re.search(rf"\bsayfa {cevap}\b", l)), None)
        lines.append(f"test_1 #{i}: Cevap sayfasi {cevap} hibrit sirasi = {rank or '>40'}")
        if rank:
            lines.append("   " + rows[rank - 1].strip())
    return lines


def run_all(db, label, questions, out):
    retrieval.invalidate_cache()
    for (s, i), q in questions.items():
        chunks = retrieval.retrieve(q, db_path=str(db), top_k=5)
        rec = {"db": label, "set": s, "id": i,
               "route": ",".join(sorted({str(c.get("route")) for c in chunks})),
               "kaynaklar": [f"{Path(c['source']).name} ({c.get('page_info', '')})" for c in chunks],
               "rerank": [round(c.get("rerank_score", float("nan")), 4) for c in chunks]}
        out.write(json.dumps(rec, ensure_ascii=False) + "\n")
        out.flush()
        print(f"[{label}] {s}#{i} {rec['kaynaklar']}", flush=True)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    scratch = sys.argv[1]
    questions = {}
    for s in SETS:
        with open(ROOT / "evaluation" / "datasets" / f"{s}.csv", encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                questions[(s, r["id"])] = r["soru"]
    sim, _ = build_sim_db(scratch)
    ranks = answer_page_ranks(questions)
    (HERE / "cevap_sirasi.txt").write_text("\n".join(ranks) + "\n", encoding="utf-8")
    print("\n".join(ranks))
    with open(HERE / "simulasyon.jsonl", "w", encoding="utf-8") as out:
        run_all(ROOT / "rag.db", "bugun", questions, out)
        run_all(sim, "birlesik", questions, out)


if __name__ == "__main__":
    main()
