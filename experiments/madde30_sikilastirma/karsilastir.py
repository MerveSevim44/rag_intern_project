"""
Madde 30 — (a2) istisnalı tam koşunun madde 39'un taze tabanıyla (6c60f60)
set bazlı ve soru bazlı karşılaştırması.

Kullanım (kökten): python -u experiments/madde30_sikilastirma/karsilastir.py
"""
import csv
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT / "evaluation"), str(ROOT)]

from benchmark_eval import classify_answer  # noqa: E402
from gt_utils import load_ground_truth  # noqa: E402

SETS = ["test_1", "test_2", "test_3", "test_4", "test_5", "test_negative"]
BASE_DIR = ROOT / "experiments" / "madde39_tam_kosu"
NEW_DIR = HERE


def satirlar(yol):
    with open(yol, encoding="utf-8-sig") as f:
        return {r["id"]: r for r in csv.DictReader(f)}


def hata_duzeltilmis(klasor, satir_dict):
    """sonuclari.csv'deki HATA satırlarını, varsa hata_tekrar.csv'deki tekrar
    sonucuyla değiştirir (kosu.py'nin kendi mantığı; asıl dosya değişmez, burada
    yalnızca sınıflandırma için birleştiriyoruz)."""
    tekrar_yolu = klasor / "hata_tekrar.csv"
    if not tekrar_yolu.exists():
        return satir_dict
    tekrar = satirlar(tekrar_yolu)
    birlesik = dict(satir_dict)
    for id_, row in tekrar.items():
        if id_ in birlesik:
            birlesik[id_] = row
    return birlesik


def main():
    gt = load_ground_truth()
    toplam = {"base": {"TP": 0, "TN": 0, "FN": 0, "FP": 0, "HATA": 0},
              "new": {"TP": 0, "TN": 0, "FN": 0, "FP": 0, "HATA": 0}}
    farklar = []

    for s in SETS:
        base_csv = BASE_DIR / s / "sonuclari.csv"
        new_csv = NEW_DIR / s / "sonuclari.csv"
        if not base_csv.exists() or not new_csv.exists():
            print(f"[ATLA] {s}: eksik dosya (base={base_csv.exists()}, new={new_csv.exists()})")
            continue
        base_rows = hata_duzeltilmis(BASE_DIR / s, satirlar(base_csv))
        new_rows = hata_duzeltilmis(NEW_DIR / s, satirlar(new_csv))
        set_sonuc = {"base": {"TP": 0, "TN": 0, "FN": 0, "FP": 0, "HATA": 0},
                     "new": {"TP": 0, "TN": 0, "FN": 0, "FP": 0, "HATA": 0}}
        for id_ in sorted(base_rows, key=int):
            if id_ not in new_rows:
                continue
            b_row, n_row = {**base_rows[id_], "set": s}, {**new_rows[id_], "set": s}
            b_sinif = classify_answer(b_row, gt)
            n_sinif = classify_answer(n_row, gt)
            set_sonuc["base"][b_sinif] += 1
            set_sonuc["new"][n_sinif] += 1
            toplam["base"][b_sinif] += 1
            toplam["new"][n_sinif] += 1
            if b_sinif != n_sinif:
                farklar.append((s, id_, b_sinif, n_sinif, b_row["soru"][:70]))

        print(f"{s}: base={set_sonuc['base']}  new={set_sonuc['new']}")

    print()
    print(f"GENEL base={toplam['base']}")
    print(f"GENEL new ={toplam['new']}")
    print()
    print(f"Fark eden sorular ({len(farklar)}):")
    for s, id_, b, n, soru in farklar:
        print(f"  {s}#{id_}: {b} -> {n}   {soru}")


if __name__ == "__main__":
    main()
