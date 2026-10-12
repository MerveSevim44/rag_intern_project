"""
Madde 22 simülasyon analizi: simulasyon.jsonl (bugün / birleşik DB, aynı süreç).

Raporlar:
  A) Hedef 5 soru (test_1 #24, #25, #26, #28, #29): doğru Cevap sayfası
     bağlama giriyor mu (birleşik DB'de "sayfa N-M" chunk'ı = Örnek+Cevap).
  B) Madde 24 kesişimi — test_5 #103'ün dolgu sayfaları ve rerank skorları.
  C) Etki alanı: kaynak listesi değişen tüm sorular (gramer PDF'i dışı dahil;
     birleştirme BM25 IDF'ini ve doküman sayısını değiştirir).

Kullanım:
    python experiments/madde22_ornek_cevap/analiz.py > experiments/madde22_ornek_cevap/sonuc_simulasyon.txt
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGETS = {"24": 23, "25": 27, "26": 25, "28": 29, "29": 31}
PDF = "8-Baglamdan_bagimsiz_dilbilgisi.pdf"


def pages(srcs):
    out = []
    for s in srcs:
        m = re.match(re.escape(PDF) + r" \(sayfa ([\d-]+)\)", s)
        if m:
            out.append(m.group(1))
    return out


def has_page(srcs, n):
    for p in pages(srcs):
        a, _, b = p.partition("-")
        if int(a) == n or (b and int(b) == n):
            return True
    return False


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    rows = [json.loads(l) for l in (HERE / "simulasyon.jsonl").read_text(encoding="utf-8").splitlines()]
    by = {(r["db"], r["set"], r["id"]): r for r in rows}
    keys = sorted({(r["set"], r["id"]) for r in rows}, key=lambda k: (k[0], int(k[1])))
    print(f"Satir: {len(rows)} (soru: {len(keys)})")

    print("\n== A) Hedef sorular — dogru Cevap sayfasi baglamda mi")
    for i, cev in TARGETS.items():
        b, m = by[("bugun", "test_1", i)], by[("birlesik", "test_1", i)]
        print(f"   #{i} (Cevap s.{cev}): bugun {'VAR' if has_page(b['kaynaklar'], cev) else 'yok'} {pages(b['kaynaklar'])} "
              f"rerank={b['rerank']}")
        print(f"   {'':16} birlesik {'VAR' if has_page(m['kaynaklar'], cev) else 'yok'} {pages(m['kaynaklar'])} "
              f"rerank={m['rerank']}")

    print("\n== B) Madde 24 kesisimi — test_5 #103 (pompalama lemmasi, belgede yok)")
    for db in ("bugun", "birlesik"):
        r = by[(db, "test_5", "103")]
        print(f"   {db:9} {r['kaynaklar']}\n   {'':9} rerank={r['rerank']}")

    print("\n== C) Etki alani — kaynak listesi degisen sorular")
    changed = [k for k in keys if by[("bugun", *k)]["kaynaklar"] != by[("birlesik", *k)]["kaynaklar"]]
    pdf_q = [k for k in changed if any(PDF in s for s in by[("bugun", *k)]["kaynaklar"] + by[("birlesik", *k)]["kaynaklar"])]
    other = [k for k in changed if k not in pdf_q]
    print(f"   degisen: {len(changed)} / {len(keys)}  (gramer PDF'i iceren: {len(pdf_q)}, digerleri: {len(other)})")
    for k in changed:
        b, m = by[("bugun", *k)], by[("birlesik", *k)]
        only_merge = [p for p in pages(m["kaynaklar"]) if "-" in p]
        print(f"   {k[0]:13} #{k[1]:3} bugun={pages(b['kaynaklar']) or b['kaynaklar']}")
        print(f"   {'':18} birlesik={pages(m['kaynaklar']) or m['kaynaklar']}"
              + ("" if k in pdf_q else "   <-- PDF DISI"))
    same_route = all(by[("bugun", *k)]["route"] == by[("birlesik", *k)]["route"] for k in keys)
    print(f"\n   rota degisen soru: {'0' if same_route else [k for k in keys if by[('bugun', *k)]['route'] != by[('birlesik', *k)]['route']]}")


if __name__ == "__main__":
    main()
