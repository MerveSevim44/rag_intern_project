"""
Madde 24 Adım 0 — "görev/talimat" işaretinin etki alanı (kod değişikliği yok).
Plan: docs/implementation_plan_madde24_ocr_isaret.md §3, §5.

A) Korpus taraması: rag.db'deki HER chunk tespit kuralından geçirilir; işaretlenen
   chunk'ların tam listesi (id, kaynak, sayfa, bulunan fiil) basılır. Beklenen 5
   Örnek sayfası dışındaki her eşleşme BEKLENMEYEN diye ayrıca raporlanır.
B) Benchmark soruları (test_1..5 + test_negative): retrieve(top_k=5) ile nihai
   bağlam alınır; bağlamında işaretli chunk olan sorular listelenir. Bu küme
   dışındaki sorularda Adım 1 sonrası LLM prompt'u bayt bayt aynı kalır.
   Kontrol: her sorunun kaynak listesi v8 kayıtlı `bulunan_kaynaklar` ile
   karşılaştırılır (src/ v8'den beri değişmedi; fark çıkarsa raporlanır).

Tespit kuralı: llm_client.task_instruction_verbs (bağlamdaki notun kullandığı
fonksiyonun aynısı). Adım 0'da script kuralın kendi kopyasıyla koşmuştu; Adım
1'de bu fonksiyona geçildi ve A listesi `--korpus` ile yeniden üretilip aynı
çıktığı doğrulandı (sonuc_etkilenen_set_korpus.txt).

Servis: Ollama (bge-m3) + reranker. LLM gerekmez; llm=None ile tablosal rotada
kod üretimi yapılamazsa satır `route` sütununda görünür.

Kullanım:
    python -u experiments/madde24_ocr_alistirma/etkilenen_set.py            # A + B
    python -u experiments/madde24_ocr_alistirma/etkilenen_set.py --korpus   # yalnız A (servis gerekmez)
Çıktı: sonuc_etkilenen_set.txt (özet) ve etkilenen_set.csv (tüm sorular);
--korpus ile sonuc_etkilenen_set_korpus.txt.
"""
import csv
import sqlite3
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src"), str(ROOT / "evaluation")]
from llm_client import task_instruction_verbs as task_verbs  # noqa: E402

SETS = ["test_1", "test_2", "test_3", "test_4", "test_5", "test_negative"]
V8_RESULTS = ROOT / "experiments" / "v8_bm25_stopword" / "results"
PDF = "8-Baglamdan_bagimsiz_dilbilgisi.pdf"
# Yalnız RAPORLAMA için (kural bunu kullanmaz): bugün işaretlenmesi beklenen sayfalar.
EXPECTED = {(PDF, f"sayfa {n}") for n in (22, 24, 26, 28, 30)}


def corpus_scan(log):
    con = sqlite3.connect(ROOT / "rag.db")
    rows = con.execute("select id, source, page_info, content from chunks order by id").fetchall()
    marked = []
    for cid, src, page, content in rows:
        verbs = task_verbs(content)
        if verbs:
            marked.append((cid, Path(src).name, page, verbs))
    log(f"== A) Korpus taramasi: isaretlenen {len(marked)} / {len(rows)} chunk")
    for cid, src, page, verbs in marked:
        flag = "" if (src, page) in EXPECTED else "   <-- BEKLENMEYEN"
        log(f"   id={cid} {src} | {page} | fiiller={verbs}{flag}")
    unexpected = [m for m in marked if (m[1], m[2]) not in EXPECTED]
    missing = EXPECTED - {(m[1], m[2]) for m in marked}
    log(f"   beklenmeyen (yanlis pozitif adayi): {len(unexpected)}")
    log(f"   beklenip isaretlenmeyen: {sorted(missing) or 0}")
    return {cid for cid, *_ in marked}


def v8_sources(set_name):
    path = V8_RESULTS / f"{set_name}_sonuclari.csv"
    if not path.exists():
        return {}
    csv.field_size_limit(10**9)
    return {r["id"]: r["bulunan_kaynaklar"] for r in csv.DictReader(open(path, encoding="utf-8-sig"))}


def fmt_sources(chunks):
    # run_tests.py'deki `bulunan_kaynaklar` biçimi: "dosya (page_info)"
    return "; ".join(f"{Path(c['source']).name} ({c.get('page_info', '')})" for c in chunks)


def question_scan(log, marked_ids):
    from retrieval import retrieve
    out_rows, affected, mismatch = [], [], []
    for set_name in SETS:
        v8 = v8_sources(set_name)
        qs = list(csv.DictReader(open(ROOT / "evaluation" / "datasets" / f"{set_name}.csv", encoding="utf-8-sig")))
        for q in qs:
            t0 = time.perf_counter()
            try:
                chunks = retrieve(q["soru"], top_k=5)
                err = ""
            except Exception as e:  # servis hatası: satır belirsiz kalır, sessizce düşmez
                chunks, err = [], f"{type(e).__name__}: {e}"
            route = ",".join(sorted({str(c.get("route")) for c in chunks})) or "-"
            hit = [c for c in chunks if c.get("id") in marked_ids]
            srcs = fmt_sources(chunks)
            same = "" if q["id"] not in v8 else ("evet" if v8[q["id"]] == srcs else "HAYIR")
            row = {"set": set_name, "id": q["id"], "route": route, "hata": err,
                   "isaretli_sayfalar": "; ".join(c["page_info"] for c in hit),
                   "kaynaklar": srcs, "v8_ile_ayni": same,
                   "sure_sn": f"{time.perf_counter() - t0:.1f}", "soru": q["soru"]}
            out_rows.append(row)
            if hit:
                affected.append(row)
            if same == "HAYIR" or err:
                mismatch.append(row)
            print(f"[{set_name} #{q['id']}] route={route} isaretli={row['isaretli_sayfalar'] or '-'} "
                  f"v8={same or '?'} {err}", flush=True)
    with open(HERE / "etkilenen_set.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
        w.writeheader()
        w.writerows(out_rows)

    log(f"\n== B) Benchmark sorulari: {len(out_rows)} soru, baglaminda isaretli chunk olan {len(affected)}")
    for r in affected:
        log(f"   {r['set']:13} #{r['id']:3} isaretli=[{r['isaretli_sayfalar']}]  {r['soru'][:80]}")
    log(f"\n   v8 kaynak listesinden farkli ya da hatali: {len(mismatch)}")
    for r in mismatch:
        log(f"   {r['set']:13} #{r['id']:3} route={r['route']} hata={r['hata'] or '-'}")
        log(f"      simdi: {r['kaynaklar']}")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    lines = []

    def log(s):
        print(s, flush=True)
        lines.append(s)

    marked_ids = corpus_scan(log)
    if "--korpus" in sys.argv[1:]:
        (HERE / "sonuc_etkilenen_set_korpus.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
        sys.exit(0)
    question_scan(log, marked_ids)
    (HERE / "sonuc_etkilenen_set.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
