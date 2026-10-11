"""
v8 koşu sürücüsü — v7 ile aynı yaklaşım (experiments/v7_refusal_clarity/PROVENANCE.md "Koşu biçimi").

run_tests.py'nin KENDİ fonksiyonları (load_model, run_single_test,
free_gpu_memory, error_kind) değiştirilmeden kullanılır. Sürücüdeki iki fark:
  1. her satır üretilir üretilmez diske yazılır (servis çökmesinde kayıp olmasın),
  2. --min-id/--max-id ile id aralığı (negatif setin segmentleri için).
RAG davranışı değişmez. `python -u` ile koşulur.

Kullanım:
    python -u experiments/v8_bm25_stopword/run_set.py test_1
    python -u experiments/v8_bm25_stopword/run_set.py test_negative --min-id 201 --max-id 215 --out neg_seg_A.csv
"""
import argparse
import csv
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "evaluation"))

import run_tests  # noqa: E402

FIELDS_EXTRA = ["cevap", "bulunan_kaynaklar", "sure_sn", "context", "dogrulama_durumu"]


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("set")
    ap.add_argument("--min-id", type=int)
    ap.add_argument("--max-id", type=int)
    ap.add_argument("--out")
    ap.add_argument("--max-consecutive-errors", type=int, default=run_tests.DEFAULT_MAX_CONSECUTIVE_ERRORS)
    args = ap.parse_args()

    src = ROOT / "evaluation" / "datasets" / f"{args.set}.csv"
    with open(src, encoding="utf-8-sig") as f:
        rows = [r for r in csv.DictReader(f) if r.get("id", "").strip().isdigit()]
    rows = [r for r in rows
            if (args.min_id is None or int(r["id"]) >= args.min_id)
            and (args.max_id is None or int(r["id"]) <= args.max_id)]
    out = HERE / "results" / (args.out or f"{args.set}_sonuclari.csv")
    out.parent.mkdir(parents=True, exist_ok=True)

    print(f"Soru seti: {src}  ({len(rows)} soru)")
    print("Model yukleniyor...")
    llm = run_tests.load_model()
    fields = list(rows[0].keys()) + FIELDS_EXTRA
    t0, streak = time.perf_counter(), []
    with open(out, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            print(f"[{row['id']}] Soruluyor: {row['soru']}")
            try:
                res = run_tests.run_single_test(llm, row["soru"])
                streak = []
            except Exception as e:
                res = {"cevap": f"HATA: {e}", "bulunan_kaynaklar": "", "sure_sn": 0,
                       "context": "", "dogrulama_durumu": ""}
                streak.append((row["id"], run_tests.error_kind(str(e))))
            writer.writerow({**row, **res})
            f.flush()
            print(f"    -> {res['sure_sn']} sn\n")
            if args.max_consecutive_errors and len(streak) >= args.max_consecutive_errors:
                sys.exit(f"{len(streak)} ardışık hata: {streak} — koşu durduruldu ({out})")
            run_tests.free_gpu_memory()
            time.sleep(1)
    print(f"\nTamamlandi. {len(rows)} soru, {(time.perf_counter() - t0) / 60:.1f} dk. Sonuclar: {out}")


if __name__ == "__main__":
    main()
