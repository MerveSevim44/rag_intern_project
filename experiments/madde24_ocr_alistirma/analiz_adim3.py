"""
Madde 24 Adım 3 izole testi analizi: adim3_sonuclari.jsonl → plan §4 ölçüt 1–3
(ölçüt 4, tam negatif set, yalnız kural işe yararsa tam benchmark'ta ölçülür).

Kullanım:
    python experiments/madde24_ocr_alistirma/analiz_adim3.py > experiments/madde24_ocr_alistirma/sonuc_adim3.txt
"""
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("analiz_ab", HERE / "analiz_ab.py")
A = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(A)
B, tripwire = A.B, A.tripwire


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    v8, _ = A.load()
    refs = {k: [x for x in r["referans_cevaplar"].split(" | ") if x] for k, r in v8.items()}
    rows = [json.loads(l) for l in (HERE / "adim3_sonuclari.jsonl").read_text(encoding="utf-8").splitlines()]
    by = {(r["set"], r["id"], r["kol"]): r for r in rows}
    keys = sorted({(r["set"], r["id"]) for r in rows}, key=lambda k: (k[0], int(k[1])))

    bad = [r for r in rows if B.is_run_error(r["cevap"])]
    wrong_prompt = [(r["set"], r["id"], r["kol"]) for r in rows
                    if not B.is_run_error(r["cevap"]) and r["kural_promptta"] != (r["kol"] == "acik")]
    no_note = [(r["set"], r["id"], r["kol"]) for r in rows if not B.is_run_error(r["cevap"]) and not r["not_var"]]
    print(f"Satir: {len(rows)}  HATA: {len(bad)}  kural/kol uyumsuz: {wrong_prompt or 0}  notsuz baglam: {no_note or 0}")

    print(f"\n   {'soru':20} {'kural kapali':12} {'kural acik':12} {'F1 kapali/acik':16} ayni cevap")
    res = {}
    for k in keys:
        a, c = by.get((*k, "kapali")), by.get((*k, "acik"))
        ca = A.cls(k[0], a["cevap"], a["soru"]) if a else "?"
        cc = A.cls(k[0], c["cevap"], c["soru"]) if c else "?"
        fa = A.f1(a["cevap"], refs.get(k)) if a else None
        fc = A.f1(c["cevap"], refs.get(k)) if c else None
        res[k] = (ca, cc, fa, fc)
        f1s = "-" if fa is None or fc is None else f"{fa:5.1f} / {fc:5.1f}"
        same = "evet" if a and c and a["cevap"] == c["cevap"] else "hayir"
        print(f"   {k[0]+'#'+k[1]:20} {ca:12} {cc:12} {f1s:16} {same}")

    for k in A.OCR_FP + A.OUT_OF_SCOPE:
        r = by.get((*k, "acik"))
        if r:
            print(f"\n   {k[0]}#{k[1]} kural acik cevap: {r['cevap'][:500]!r}")

    hits = [r for r in rows if r["set"] in A.NEG_SETS and not B.is_run_error(r["cevap"])
            and len(r["cevap"]) > tripwire.MIN_LEN and B.check_is_not_found(r["cevap"], r["soru"])]
    print(f"\n== Tripwire (madde 28): eslesme={len(hits)}")
    for r in hits:
        print(f"   {r['set']}#{r['id']} {r['kol']} len={len(r['cevap'])}: {r['cevap'][:200]!r}")

    print("\n== Plan §4 olcutleri (kural acik kol)")
    ok1 = all(res.get(k, ("?", "?"))[1] == "TN" for k in A.OCR_FP)
    print(f"1. #224, test_5 #103 FP->TN: {'GECTI' if ok1 else 'KALDI'}  "
          + ", ".join(f"{k[0]}#{k[1]}: {res[k][0]}->{res[k][1]}" for k in A.OCR_FP if k in res))
    ok2 = all(res.get(k, ("?", "?"))[1] == "TN" for k in A.OCR_TN)
    print(f"2. #217, test_5 #102 TN kalir: {'GECTI' if ok2 else 'KALDI'}  "
          + ", ".join(f"{k[0]}#{k[1]}: {res[k][0]}->{res[k][1]}" for k in A.OCR_TN if k in res))
    pos = [k for k in keys if k[0] == "test_1"]
    worse = [k[1] for k in pos if res[k][0] == "TP" and res[k][1] != "TP"]
    d = [res[k][3] - res[k][2] for k in pos if res[k][2] is not None and res[k][3] is not None]
    print(f"3. test_1 ({len(pos)} soru) bozulmaz: TP->baska {worse or 0}, ort. F1 farki (acik-kapali) "
          f"{(sum(d) / len(d)) if d else 0:+.1f} -> {'GECTI' if not worse else 'KALDI'}")
    for k in A.OUT_OF_SCOPE:
        if k in res:
            print(f"   kapsam disi {k[0]}#{k[1]}: {res[k][0]}->{res[k][1]}")
    print(f"   tripwire: {len(hits)}")


if __name__ == "__main__":
    main()
