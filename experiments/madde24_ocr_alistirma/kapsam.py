"""
Madde 24 ölçümü: OCR'lı alıştırma sayfaları negatif sorularda bağlama giriyor mu,
girince sınıf ne oluyor. Kayıtlı koşu sonuçlarından okur; servis gerektirmez.

Sınıf, kayıtlı değer değil BUGÜNKÜ skorlayıcıyla (check_is_not_found) yeniden
hesaplanır — koşular arası karşılaştırma aynı ölçütle yapılsın diye.

OCR sayfaları: dffb6a5 ile OCR'lanan 8-Baglamdan_bagimsiz_dilbilgisi.pdf sayfa
22–31 (Örnek/Cevap 2, 5, 6, 7, 8). DB'de OCR işareti olmadığı için sayfa
numarasıyla tanımlı; çözüm bir işaret eklerse buradan okunmalı.

Sonda madde 28 tripwire'ı (experiments/madde25_ret_tespiti/uzun_ret_tripwire.py)
her koşu için çalıştırılır.

Kullanım:
    python experiments/madde24_ocr_alistirma/kapsam.py [RESULTS_DIR ...]
    (argümansız: v7 ve v8)
"""
import csv
import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "evaluation")]
import evaluation.benchmark_eval as B  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "uzun_ret_tripwire", ROOT / "experiments" / "madde25_ret_tespiti" / "uzun_ret_tripwire.py")
tripwire = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tripwire)

PDF = "8-Baglamdan_bagimsiz_dilbilgisi.pdf"
OCR_PAGES = set(range(22, 32))
_PAGE_RE = re.compile(re.escape(PDF) + r" \(sayfa (\d+)\)")

DEFAULT_RUNS = [ROOT / "experiments" / "v7_refusal_clarity" / "results",
                ROOT / "experiments" / "v8_bm25_stopword" / "results"]


def rows(results_dir):
    csv.field_size_limit(10**9)
    for name in tripwire.NEGATIVE_FILES:
        path = Path(results_dir) / name
        if path.exists():
            for r in csv.DictReader(open(path, encoding="utf-8-sig")):
                yield name.replace("_sonuclari.csv", ""), r


def classify(r):
    if (r.get("cevap") or "").startswith("HATA"):
        return "HATA"
    return "TN" if B.check_is_not_found(r["cevap"], r["soru"]) else "FP"


if __name__ == "__main__":
    runs = [Path(p) for p in sys.argv[1:]] or DEFAULT_RUNS
    for d in runs:
        total = pdf_q = ocr_q = 0
        fp_all = fp_ocr = 0
        print(f"== {d.parent.name}")
        for f, r in rows(d):
            total += 1
            cls = classify(r)
            fp_all += cls == "FP"
            pages = [int(p) for p in _PAGE_RE.findall(r.get("bulunan_kaynaklar") or "")]
            if not pages:
                continue
            pdf_q += 1
            ocr = sorted(OCR_PAGES & set(pages))
            ocr_q += bool(ocr)
            fp_ocr += bool(ocr) and cls == "FP"
            print(f"   {f:13} #{r['id']:3} {cls:4} sayfalar={pages} ocr={ocr or '-'}  {r['soru'][:70]}")
        print(f"   negatif soru={total}  gramer PDF'i baglamda={pdf_q}  OCR sayfasi baglamda={ocr_q}  "
              f"FP toplam={fp_all}  FP (OCR baglamda)={fp_ocr}")
        hits = tripwire.scan(d)
        print(f"   tripwire (madde 28): eslesme={len(hits)}")
        for f, i, n, ans in hits:
            print(f"      {f}#{i} len={n}: {ans[:200]!r}")
        print()
