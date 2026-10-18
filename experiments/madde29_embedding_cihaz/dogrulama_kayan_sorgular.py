# pyrefly: ignore[missing-import]
"""
Madde 29 Adım 2 — kayan sorguların kararlılık doğrulaması
(docs/implementation_plan_madde29_embedding_cihaz.md §6).

Madde 24 Adım 0'da kaydığı bilinen 3 sınır sorusu (test_2 #36, test_4 #93,
negatif #217) embedder.py'deki EMBED_NUM_GPU sabitlemesinden SONRA, iki ayrı
Python SÜRECİNDE retrieval ile çalıştırılır. Amaç: her iki süreçte de Ollama
sorgu embedding'ini aynı cihaza (GPU) yüklediğini ve bunun sonucunda aday
listesi + skorların 0 fark ile birebir aynı çıktığını doğrulamak.

Kullanım (aynı makinede, Ollama + rag.db ile, İKİ AYRI terminalde/süreçte):
    python -u experiments/madde29_embedding_cihaz/dogrulama_kayan_sorgular.py --run a
    python -u experiments/madde29_embedding_cihaz/dogrulama_kayan_sorgular.py --run b
    python -u experiments/madde29_embedding_cihaz/dogrulama_kayan_sorgular.py --compare

DB'ye yazmaz. retrieve() sadece sorgu embedding'i üretir (EMBED_NUM_GPU ile
sabitlenmiş); rag.db'deki doküman embedding'lerine dokunulmaz.
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]

SORULAR = [
    ("test_2", "36"),
    ("test_4", "93"),
    ("test_negative", "217"),
]

OUT = HERE / "kayan_sorgular_sonuclari.jsonl"


def _soru_metni(set_name, qid):
    import csv
    with open(ROOT / "evaluation" / "datasets" / f"{set_name}.csv", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if row["id"] == qid:
                return row["soru"]
    raise KeyError(f"{set_name}#{qid} datasette bulunamadi")


def _calistir():
    from retrieval import retrieve  # noqa: E402

    out = []
    for set_name, qid in SORULAR:
        soru = _soru_metni(set_name, qid)
        sonuclar = retrieve(soru)
        out.append({
            "set": set_name, "id": qid, "soru": soru,
            "adaylar": [
                {"source": r["source"], "page_info": r.get("page_info"),
                 "score": r["score"], "rerank_score": r.get("rerank_score")}
                for r in sonuclar
            ],
        })
    return out


def _karsilastir():
    if not OUT.exists():
        sys.exit(f"{OUT} yok — once --run a ve --run b ile iki sureci calistirin.")
    runs = {}
    for line in OUT.read_text(encoding="utf-8").splitlines():
        rec = json.loads(line)
        runs.setdefault(rec["run"], []).append(rec)
    etiketler = sorted(runs)
    if len(etiketler) < 2:
        sys.exit(f"Yalnizca {etiketler} calistirilmis — ikinci sureci de calistirin (--run <diger_etiket>).")
    a, b = runs[etiketler[0]], runs[etiketler[1]]
    print(f"Karsilastirma: run={etiketler[0]!r} vs run={etiketler[1]!r}\n")
    tum_ayni = True
    for ra, rb in zip(a, b):
        ayni = ra["adaylar"] == rb["adaylar"]
        tum_ayni &= ayni
        print(f"{ra['set']}#{ra['id']}: {'AYNI' if ayni else 'FARKLI'}  "
              f"({len(ra['adaylar'])} vs {len(rb['adaylar'])} aday)")
        if not ayni:
            for i, (ca, cb) in enumerate(zip(ra["adaylar"], rb["adaylar"])):
                if ca != cb:
                    print(f"   sira {i}: {ca}  !=  {cb}")
    print(f"\nSonuc: {'0 FARK — determinist' if tum_ayni else 'FARK VAR — hala kayiyor'}")
    return tum_ayni


def main():
    parser = argparse.ArgumentParser()
    grp = parser.add_mutually_exclusive_group(required=True)
    grp.add_argument("--run", type=str, help="Bu surecin etiketi (ör. 'a', 'b'); sonuclari OUT'a ekler.")
    grp.add_argument("--compare", action="store_true", help="OUT'taki iki (veya daha fazla) run'i karsilastirir.")
    args = parser.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

    if args.compare:
        ok = _karsilastir()
        sys.exit(0 if ok else 1)

    kayitlar = _calistir()
    with open(OUT, "a", encoding="utf-8") as f:
        for rec in kayitlar:
            f.write(json.dumps({"run": args.run, **rec}, ensure_ascii=False) + "\n")
    print(f"run={args.run!r}: {len(kayitlar)} soru calistirildi, {OUT}'a eklendi.")


if __name__ == "__main__":
    main()
