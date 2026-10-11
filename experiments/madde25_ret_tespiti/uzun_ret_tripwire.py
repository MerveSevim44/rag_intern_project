"""
Madde 28 tripwire'ı: negatif sette ret sayılan ama uzun olan cevaplar.

Ret tespitinin ikinci aşaması içerik miktarına bakmadığı için (backlog madde
28), "bilgi bulunmamaktadır, ancak genel olarak şu adımlar…" gibi melez bir
cevap sayı / özel isim taşımıyorsa TN sayılır ve negatif FP sayısı yapay olarak
iyileşir. Bu script o adayları listeler; eşleşmeler elle incelenir.

Taban çizgisi (2026-10-11, 7 koşu): tek eşleşme v5 #231 (dürüst ret).

Kullanım:
    python experiments/madde25_ret_tespiti/uzun_ret_tripwire.py [RESULTS_DIR ...]
    (argümansız: experiments/*/results altındaki tüm koşular)
"""
import csv
import glob
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "evaluation")]
import evaluation.benchmark_eval as B  # noqa: E402

MIN_LEN = 120
NEGATIVE_FILES = ("test_negative_sonuclari.csv", "test_5_sonuclari.csv")


def scan(results_dir, min_len=MIN_LEN):
    """(dosya, id, uzunluk, cevap) — ret sayılan ve min_len'den uzun negatif cevaplar."""
    csv.field_size_limit(10**9)
    hits = []
    for name in NEGATIVE_FILES:
        path = Path(results_dir) / name
        if not path.exists():
            continue
        for r in csv.DictReader(open(path, encoding="utf-8-sig")):
            ans = r.get("cevap") or ""
            if ans.startswith("HATA") or len(ans) <= min_len:
                continue
            if B.check_is_not_found(ans, r["soru"]):
                hits.append((name.replace("_sonuclari.csv", ""), r["id"], len(ans), ans))
    return hits


if __name__ == "__main__":
    dirs = sys.argv[1:] or sorted(glob.glob(str(ROOT / "experiments" / "*" / "results")))
    for d in dirs:
        hits = scan(d)
        print(f"{Path(d).parent.name:28} eslesme={len(hits)}")
        for f, i, n, ans in hits:
            print(f"    {f}#{i} len={n}: {ans[:200]!r}")
