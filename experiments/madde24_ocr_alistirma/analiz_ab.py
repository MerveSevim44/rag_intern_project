"""
Madde 24 Adım 2 analizi: ab_sonuclari.jsonl → plan §4 başarı ölçütleri.

Sınıf: bugünkü skorlayıcı (check_is_not_found). Pozitif: TP/FN, negatif: TN/FP.
Tekrarlarda sınıf "3'te en az 2" ile raporlanır; F1 tekrar ortalamasıdır.
Referans cevaplar ve v8 sınıfı: experiments/v8_bm25_stopword/report/genel_scored.csv
(sınıf orada da bugünkü skorlayıcıyla yeniden hesaplanır).

Kullanım:
    python experiments/madde24_ocr_alistirma/analiz_ab.py > experiments/madde24_ocr_alistirma/sonuc_ab.txt
"""
import collections
import csv
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "evaluation")]
import evaluation.benchmark_eval as B  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "uzun_ret_tripwire", ROOT / "experiments" / "madde25_ret_tespiti" / "uzun_ret_tripwire.py")
tripwire = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tripwire)

NEG_SETS = {"test_negative", "test_5"}
OCR_FP = [("test_negative", "224"), ("test_5", "103")]           # ölçüt 1: FP -> TN
OCR_TN = [("test_negative", "217"), ("test_5", "102")]           # ölçüt 2: TN kalır
OUT_OF_SCOPE = [("test_5", "101")]


def load():
    csv.field_size_limit(10**9)
    v8 = {(r["test_seti"], r["id"]): r for r in
          csv.DictReader(open(ROOT / "experiments/v8_bm25_stopword/report/genel_scored.csv", encoding="utf-8-sig"))}
    rows = [json.loads(l) for l in (HERE / "ab_sonuclari.jsonl").read_text(encoding="utf-8").splitlines()]
    return v8, rows


def cls(set_name, answer, question):
    if B.is_run_error(answer):
        return "HATA"
    nf = B.check_is_not_found(answer, question)
    if set_name in NEG_SETS:
        return "TN" if nf else "FP"
    return "FN" if nf else "TP"


def f1(answer, refs):
    if B.is_run_error(answer) or not refs:
        return None
    return 100 * B.compute_token_f1(answer, refs)[0]


def majority(classes):
    c = collections.Counter(x for x in classes if x != "HATA")
    if not c:
        return "HATA"
    top, n = c.most_common(1)[0]
    return top if n >= 2 else "/".join(sorted(c))


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    v8, rows = load()
    refs = {k: [x for x in r["referans_cevaplar"].split(" | ") if x] for k, r in v8.items()}
    v8cls = {k: cls(k[0], r["cevap"], r["soru"]) for k, r in v8.items()}

    errors = [r for r in rows if B.is_run_error(r["cevap"])]
    print(f"Satir: {len(rows)}  HATA: {len(errors)}")
    for r in errors:
        print(f"   HATA {r['faz']} {r['set']}#{r['id']} t{r['tekrar']} {r['kol']}: {r['cevap'][:120]}")

    # --- Faz 1: A/B ---------------------------------------------------------
    f1rows = [r for r in rows if r["faz"] == "faz1"]
    by = collections.defaultdict(list)
    for r in f1rows:
        by[(r["set"], r["id"], r["kol"])].append(r)
    keys = sorted({(s, i) for s, i, _ in by}, key=lambda k: (k[0], int(k[1])))

    print("\n== Faz 1: ayni oturumda A/B (3 tekrar)")
    print(f"   {'soru':20} {'v8':4} | {'kapali (t1 t2 t3) -> cogunluk':34} | {'acik (t1 t2 t3) -> cogunluk':34} | F1 kapali / acik | not acik/kapali")
    summary = {}
    for k in keys:
        cells = {}
        for arm in ("kapali", "acik"):
            rs = sorted(by.get((k[0], k[1], arm), []), key=lambda r: r["tekrar"])
            cs = [cls(k[0], r["cevap"], r["soru"]) for r in rs]
            fs = [x for x in (f1(r["cevap"], refs.get(k)) for r in rs) if x is not None]
            notes = sum(r["not_var"] for r in rs)
            cells[arm] = (cs, majority(cs), (sum(fs) / len(fs)) if fs else None, notes, len(rs))
        summary[k] = cells
        fmt = lambda c: f"{' '.join(c[0]):14} -> {c[1]:5}"
        fk, fa = cells["kapali"][2], cells["acik"][2]
        f1s = "   -   " if fk is None else f"{fk:5.1f} / {fa:5.1f}"
        print(f"   {k[0]+'#'+k[1]:20} {v8cls.get(k, '?'):4} | {fmt(cells['kapali']):34} | {fmt(cells['acik']):34} | {f1s:16} | "
              f"{cells['acik'][3]}/{cells['acik'][4]} , {cells['kapali'][3]}/{cells['kapali'][4]}")

    # not satırı gerçekten bağlamda mı (retrieval kayması kontrolü)
    drift = [(r["set"], r["id"], r["tekrar"]) for r in f1rows if r["kol"] == "acik" and not r["not_var"]
             and not B.is_run_error(r["cevap"])]
    leak = [(r["set"], r["id"], r["tekrar"]) for r in f1rows if r["kol"] == "kapali" and r["not_var"]]
    print(f"\n   acik kolda notsuz baglam (retrieval kaymis): {drift or 0}")
    print(f"   kapali kolda notlu baglam (olmamali): {leak or 0}")

    # --- Faz 2: tam negatif set ---------------------------------------------
    f2 = [r for r in rows if r["faz"] == "faz2"]
    print(f"\n== Faz 2: tam negatif set, kol acik ({len(f2)} soru)")
    c_now = collections.Counter(cls(r["set"], r["cevap"], r["soru"]) for r in f2)
    c_v8 = collections.Counter(v8cls[k] for k in v8cls if k[0] == "test_negative")
    print(f"   simdi: {dict(c_now)}   v8 (bugunku skorlayici): {dict(c_v8)}")
    for r in f2:
        k = (r["set"], r["id"])
        now = cls(r["set"], r["cevap"], r["soru"])
        if now != v8cls.get(k) or now == "FP":
            print(f"   #{r['id']}: v8={v8cls.get(k)} simdi={now} not_var={r['not_var']}  {r['cevap'][:140]!r}")
    in_drift = [r["id"] for r in f2 if r["not_var"] and ("test_negative", r["id"]) not in OCR_FP + OCR_TN]
    print(f"   Adim 0 kumesi disinda notlu baglam alan negatif soru: {in_drift or 0}")

    # --- Tripwire -------------------------------------------------------------
    hits = [r for r in rows if r["set"] in NEG_SETS and not B.is_run_error(r["cevap"])
            and len(r["cevap"]) > tripwire.MIN_LEN and B.check_is_not_found(r["cevap"], r["soru"])]
    print(f"\n== Tripwire (madde 28): eslesme={len(hits)}")
    for r in hits:
        print(f"   {r['faz']} {r['set']}#{r['id']} t{r['tekrar']} {r['kol']} len={len(r['cevap'])}: {r['cevap'][:200]!r}")

    # --- Ölçütler ---------------------------------------------------------------
    maj = lambda k, arm: summary.get(k, {}).get(arm, (None, "?"))[1]
    print("\n== Plan §4 olcutleri (acik kol cogunluk sinifi)")
    ok1 = all(maj(k, "acik") == "TN" for k in OCR_FP)
    print(f"1. #224, test_5 #103 FP->TN: {'GECTI' if ok1 else 'KALDI'}  "
          + ", ".join(f"{k[0]}#{k[1]}: kapali={maj(k, 'kapali')} acik={maj(k, 'acik')}" for k in OCR_FP))
    ok2 = all(maj(k, "acik") == "TN" for k in OCR_TN)
    print(f"2. #217, test_5 #102 TN kalir: {'GECTI' if ok2 else 'KALDI'}  "
          + ", ".join(f"{k[0]}#{k[1]}: kapali={maj(k, 'kapali')} acik={maj(k, 'acik')}" for k in OCR_TN))
    pos = [k for k in keys if k[0] == "test_1"]
    worse = [k for k in pos if maj(k, "kapali") == "TP" and maj(k, "acik") != "TP"]
    better = [k for k in pos if maj(k, "kapali") != "TP" and maj(k, "acik") == "TP"]
    fdelta = [(k, summary[k]["acik"][2] - summary[k]["kapali"][2]) for k in pos
              if summary[k]["acik"][2] is not None and summary[k]["kapali"][2] is not None]
    mean_d = sum(d for _, d in fdelta) / len(fdelta) if fdelta else 0.0
    print(f"3. test_1 ({len(pos)} soru) bozulmaz: TP->baska {[k[1] for k in worse] or 0}, "
          f"baska->TP {[k[1] for k in better] or 0}, ortalama F1 farki (acik-kapali) {mean_d:+.1f}")
    for k, d in sorted(fdelta, key=lambda x: x[1])[:3]:
        print(f"      en buyuk F1 dususu: #{k[1]} {d:+.1f}")
    fp_now, fp_v8 = c_now.get("FP", 0), c_v8.get("FP", 0)
    print(f"4. tam negatif sette FP artmaz: simdi {fp_now}/32, v8 {fp_v8}/32 -> {'GECTI' if fp_now <= fp_v8 else 'KALDI'}; "
          f"tripwire {len(hits)} -> {'GECTI' if not hits else 'INCELE'}")
    for k in OUT_OF_SCOPE:
        print(f"   kapsam disi {k[0]}#{k[1]}: kapali={maj(k, 'kapali')} acik={maj(k, 'acik')}")


if __name__ == "__main__":
    main()
