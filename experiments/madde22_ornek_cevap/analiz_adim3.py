"""
Madde 22 Adım 3 analizi: adim3_sonuclari.jsonl → plan §4 ölçüt 2–5.

Sınıf/F1: madde 24'ün analiz_ab.py yardımcıları (bugünkü skorlayıcı; v8
referansları). Hedef 5 sorunun cevapları referansla yan yana basılır — elle
inceleme için (F1 tek başına yetmez).

Kullanım:
    python experiments/madde22_ornek_cevap/analiz_adim3.py > experiments/madde22_ornek_cevap/sonuc_adim3.txt
"""
import collections
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
_spec = importlib.util.spec_from_file_location(
    "analiz_ab", ROOT / "experiments" / "madde24_ocr_alistirma" / "analiz_ab.py")
A = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(A)
B, tripwire = A.B, A.tripwire

TARGETS = {"24": 23, "25": 27, "26": 25, "28": 29, "29": 31}
PDF = "8-Baglamdan_bagimsiz_dilbilgisi.pdf"


def merged_in(srcs):
    return [s for s in srcs.split("; ") if PDF in s and "-" in s.rsplit("(", 1)[-1]]


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    v8, _ = A.load()
    refs = {k: [x for x in r["referans_cevaplar"].split(" | ") if x] for k, r in v8.items()}
    rows = [json.loads(l) for l in (HERE / "adim3_sonuclari.jsonl").read_text(encoding="utf-8").splitlines()]
    errs = [r for r in rows if B.is_run_error(r["cevap"])]
    print(f"Satir: {len(rows)}  HATA: {len(errs)}")
    for r in errs:
        print(f"   HATA {r['faz']} {r['set']}#{r['id']} {r['db']}: {r['cevap'][:120]}")

    f1rows = {(r["set"], r["id"], r["db"]): r for r in rows if r["faz"] == "faz1"}
    keys = sorted({(s, i) for s, i, _ in f1rows}, key=lambda k: (k[0], int(k[1])))
    res = {}
    print("\n== Faz 1: 18 soru, yedek vs yeni DB (ayni oturum, tek tekrar)")
    print(f"   {'soru':20} {'yedek':6} {'yeni':6} {'F1 yedek/yeni':16} ayni_cevap")
    for k in keys:
        a, b = f1rows.get((*k, "yedek")), f1rows.get((*k, "yeni"))
        ca, cb = A.cls(k[0], a["cevap"], a["soru"]), A.cls(k[0], b["cevap"], b["soru"])
        fa, fb = A.f1(a["cevap"], refs.get(k)), A.f1(b["cevap"], refs.get(k))
        res[k] = (ca, cb, fa, fb)
        f1s = "-" if fa is None or fb is None else f"{fa:5.1f} / {fb:5.1f}"
        print(f"   {k[0]+'#'+k[1]:20} {ca:6} {cb:6} {f1s:16} {'evet' if a['cevap'] == b['cevap'] else 'hayir'}")

    print("\n== Olcut 2: hedef 5 soru (elle inceleme icin cevap + referans)")
    up = 0
    for i, cev in TARGETS.items():
        k = ("test_1", i)
        ca, cb, fa, fb = res[k]
        up += fb is not None and fa is not None and fb > fa
        b = f1rows[(*k, "yeni")]
        print(f"\n   #{i} (Cevap s.{cev}) yedek={ca} F1 {fa:.1f} -> yeni={cb} F1 {fb:.1f}  "
              f"Cevap baglamda (yeni): {any(str(cev) in s for s in merged_in(b['bulunan_kaynaklar']))}")
        print(f"      soru : {b['soru'][:160]}")
        print(f"      yedek: {f1rows[(*k, 'yedek')]['cevap'][:400]!r}")
        print(f"      yeni : {b['cevap'][:400]!r}")
        print(f"      ref  : {(refs.get(k) or [''])[0][:300]}")
    worse_t = [i for i in TARGETS if res[("test_1", i)][0] == "TP" and res[("test_1", i)][1] != "TP"]
    print(f"\n   TP->baska: {worse_t or 0}; F1 artan: {up}/5 -> "
          f"{'GECTI' if not worse_t and up >= 3 else 'KALDI'} (elle inceleme ayrica)")

    print("\n== Olcut 3: 18 sorunun regresyonu")
    pos_bad = [k for k in keys if k[0] not in A.NEG_SETS and res[k][0] == "TP" and res[k][1] != "TP"]
    neg_bad = [k for k in keys if k[0] in A.NEG_SETS and res[k][0] == "TN" and res[k][1] != "TN"]
    known = {("test_5", "103"), ("test_negative", "224"), ("test_5", "101")}
    print(f"   pozitif TP->baska: {pos_bad or 0}")
    print(f"   negatif TN->FP: {neg_bad or 0}")
    for k in sorted(known):
        if k in res:
            print(f"   bilinen/kapsam disi {k[0]}#{k[1]}: {res[k][0]} -> {res[k][1]}")
    gained = [k for k in keys if res[k][0] != res[k][1] and k not in pos_bad + neg_bad]
    print(f"   diger sinif degisimi: {[(k, res[k][0], res[k][1]) for k in gained] or 0}")

    print("\n== Olcut 4: yeni dolgu — beklenen kaynagi baska dokuman olup birlesik chunk alan sorular")
    fill = []
    for (s, i, db), r in f1rows.items():
        exp = (r["beklenen_kaynak"] or "").strip()
        # Negatif sorular ("-") hariç: orada her kaynak "yanlış", dolgu ölçütü pozitifler için.
        if db == "yeni" and exp not in ("", "-") and PDF not in exp and merged_in(r["bulunan_kaynaklar"]):
            fill.append((s, i))
            print(f"   {s}#{i} beklenen={r['beklenen_kaynak'] or '-'} birlesik={merged_in(r['bulunan_kaynaklar'])} "
                  f"sinif {res[(s, i)][0]}->{res[(s, i)][1]}")
            print(f"      cevap: {r['cevap'][:300]!r}")
    print(f"   toplam: {len(fill)}")

    f2 = [r for r in rows if r["faz"] == "faz2"]
    c = collections.Counter(A.cls(r["set"], r["cevap"], r["soru"]) for r in f2)
    print(f"\n== Olcut 5: tam negatif set (yeni DB, {len(f2)} soru): {dict(c)}  (taban FP 2/32: #224, #232)")
    for r in f2:
        if A.cls(r["set"], r["cevap"], r["soru"]) == "FP":
            print(f"   FP #{r['id']}: {r['cevap'][:140]!r}")
    hits = [r for r in rows if r["set"] in A.NEG_SETS and not B.is_run_error(r["cevap"])
            and len(r["cevap"]) > tripwire.MIN_LEN and B.check_is_not_found(r["cevap"], r["soru"])]
    print(f"   tripwire: {len(hits)}")
    for r in hits:
        print(f"      {r['faz']} {r['set']}#{r['id']} {r['db']}: {r['cevap'][:200]!r}")


if __name__ == "__main__":
    main()
