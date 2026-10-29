"""
Madde 33 — production duman testi: ingest'e alınan MIN=500 birleştirmesi
(src/ingest.py, .txt yeniden ingest) deneydeki simülasyonla aynı şeyi mi üretiyor?

  retrieval: 147 sorunun nihai bağlam imzası, yeni rag.db ile; havuz2.jsonl'deki
             MIN=500 (bağlamı değişen 13 soru) ve MIN=0 (= madde 32 n0; kalan 134)
             kaydıyla karşılaştırılır. LLM yok.
  uretim:    (1) Faz B'nin 13 sorusu yeni DB ile → uretim2_min500.csv ile aynı cevap mı
             (2) tam negatif set (32) yedek DB ve yeni DB ile, soru soru sırası
                 değişerek aynı oturumda → yeni FP var mı (madde 22 Adım 3 disiplini)

Kullanım (kökten; uretim için Foundry + Ollama):
  python -u experiments/madde33_stemmer_chunk/duman_prod.py retrieval
  python -u experiments/madde33_stemmer_chunk/duman_prod.py uretim
  python experiments/madde33_stemmer_chunk/duman_prod.py rapor
"""
import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(HERE), str(ROOT / "evaluation"), str(ROOT / "src"), str(ROOT)]

YEDEK = str(ROOT / "rag.db.bak_madde33_2026-10-29")
YENI = str(ROOT / "rag.db")
SETS = ["test_1", "test_2", "test_3", "test_4", "test_5", "test_negative"]
FIELDS = ["db", "set", "id", "soru", "cevap", "bulunan_kaynaklar", "sure_sn", "context", "dogrulama_durumu"]


def _sorular():
    out = {}
    for s in SETS:
        with open(ROOT / "evaluation/datasets" / f"{s}.csv", encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                out[(s, r["id"])] = {**r, "set": s}
    return out


def _havuz2():
    k = {}
    with open(HERE / "havuz2.jsonl", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            k[(r["set"], r["id"], r["min"])] = r["imza"]
    return k


def _degisen(h):
    return sorted({(s, i) for s, i, m in h if m == 500 and h[(s, i, 500)] != h[(s, i, 0)]},
                  key=lambda q: (q[0], int(q[1])))


def retrieval():
    import retrieval as R
    from havuz2 import _imza

    h, sorular = _havuz2(), _sorular()
    R._cache.invalidate()
    deg = set(_degisen(h))
    L, fark = [], []
    with open(HERE / "duman_prod_retrieval.jsonl", "w", encoding="utf-8") as out:
        for q in sorular:
            imza = _imza(R.retrieve(sorular[q]["soru"], db_path=YENI))
            beklenen = h[(*q, 500)]
            out.write(json.dumps({"set": q[0], "id": q[1], "imza": imza}, ensure_ascii=False) + "\n")
            if imza != beklenen:
                fark.append(q)
                L.append(f"   FARK {q[0]}#{q[1]} ({'değişen' if q in deg else 'değişmemesi gereken'}):"
                         f" beklenen {beklenen} | yeni {imza}")
    n_deg = len(deg)
    L.insert(0, f"Yeni DB nihai bağlam == havuz2 MIN=500 kaydı: {len(sorular) - len(fark)}/{len(sorular)}"
                f" (bağlamı değişen {n_deg}: {n_deg - sum(q in deg for q in fark)}/{n_deg}; "
                f"değişmemesi gereken {len(sorular) - n_deg}: "
                f"{len(sorular) - n_deg - sum(q not in deg for q in fark)}/{len(sorular) - n_deg})")
    text = "\n".join(L) + "\n"
    (HERE / "sonuc_duman_prod_retrieval.txt").write_text(text, encoding="utf-8")
    print(text)


def uretim():
    import run_tests as T

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    R = sys.modules[T.get_top_chunks.__module__]
    db = [YENI]
    orijinal_load = R._cache.load
    R._cache.load = lambda _p: orijinal_load(db[0])

    sorular = _sorular()
    isler = [("yeni", q) for q in _degisen(_havuz2())]
    neg = [q for q in sorular if q[0] == "test_negative"]
    for n, q in enumerate(neg):
        sira = ["yedek", "yeni"] if n % 2 == 0 else ["yeni", "yedek"]
        isler += [(d, q) for d in sira]

    yol = HERE / "duman_prod_uretim.csv"
    yapildi = set()
    if yol.exists():
        with open(yol, encoding="utf-8-sig") as f:
            yapildi = {(r["db"], r["set"], r["id"]) for r in csv.DictReader(f)}
    llm = T.load_model()
    with open(yol, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        if not yapildi:
            w.writeheader()
        for d, q in isler:
            if (d, *q) in yapildi:
                continue
            db[0] = YENI if d == "yeni" else YEDEK
            row = sorular[q]
            try:
                res = T.run_single_test(llm, row["soru"])
            except Exception as e:
                res = {"cevap": f"HATA: {e}", "bulunan_kaynaklar": "", "sure_sn": 0, "context": "",
                       "dogrulama_durumu": ""}
            w.writerow({**row, **res, "db": d})
            f.flush()
            print(f"  {d} {q[0]}#{q[1]} ({res['sure_sn']} sn): {res['cevap'][:80]!r}", flush=True)
    R._cache.load = orijinal_load


def rapor():
    from benchmark_eval import classify_answer
    from gt_utils import load_ground_truth

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    gt, sorular = load_ground_truth(), _sorular()
    with open(HERE / "duman_prod_uretim.csv", encoding="utf-8-sig") as f:
        res = {(r["db"], r["set"], r["id"]): r for r in csv.DictReader(f)}
    with open(HERE / "uretim2_min500.csv", encoding="utf-8-sig") as f:
        faz_b = {(r["set"], r["id"]): r for r in csv.DictReader(f)}

    def sinif(q, r):
        return classify_answer({**sorular[q], **r}, gt)

    L = ["(1) Faz B'nin bağlamı değişen soruları, yeni DB vs uretim2_min500.csv"]
    ayni = 0
    for q in _degisen(_havuz2()):
        a, b = faz_b[q], res[("yeni", *q)]
        esit = a["cevap"] == b["cevap"]
        ayni += esit
        L.append(f"   {q[0]}#{q[1]}: sınıf {sinif(q, a)} -> {sinif(q, b)} | cevap metni "
                 + ("AYNI" if esit else f"FARKLI\n      Faz B: {a['cevap'][:200]!r}\n      yeni : {b['cevap'][:200]!r}"))
    L.insert(1, f"   cevap metni birebir aynı: {ayni}/{len(faz_b)}")

    neg = [q for q in sorular if q[0] == "test_negative"]
    gec = {}
    satir = []
    for q in neg:
        a, b = sinif(q, res[("yedek", *q)]), sinif(q, res[("yeni", *q)])
        gec[f"{a}->{b}"] = gec.get(f"{a}->{b}", 0) + 1
        esit = res[("yedek", *q)]["cevap"] == res[("yeni", *q)]["cevap"]
        if a != b or not esit:
            satir.append(f"   {q[0]}#{q[1]}: {a} -> {b} | cevap {'AYNI' if esit else 'FARKLI'}\n"
                         f"      yedek: {res[('yedek', *q)]['cevap'][:200]!r}\n"
                         f"      yeni : {res[('yeni', *q)]['cevap'][:200]!r}")
    fp = lambda d: sorted(int(q[1]) for q in neg if sinif(q, res[(d, *q)]) == "FP")
    L += ["", f"(2) Tam negatif set ({len(neg)}), aynı oturum, yedek DB vs yeni DB",
          "   geçişler: " + ", ".join(f"{k}={v}" for k, v in sorted(gec.items())),
          f"   FP yedek: {len(fp('yedek'))}/{len(neg)} {fp('yedek')}",
          f"   FP yeni : {len(fp('yeni'))}/{len(neg)} {fp('yeni')}",
          f"   yeni FP: {sorted(set(fp('yeni')) - set(fp('yedek')))}"]
    L += satir
    text = "\n".join(L) + "\n"
    (HERE / "sonuc_duman_prod.txt").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    {"retrieval": retrieval, "uretim": uretim, "rapor": rapor}[sys.argv[1]]()
