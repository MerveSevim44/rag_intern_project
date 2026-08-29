"""
make_ground_truth.py — Test seti başına ayrı ground truth dosyası üretir/günceller.

Tek bir dev `ground_truth.json` yerine her test seti için ayrı dosya tutulur:

    evaluation/ground_truth/test_1.json   (id 1-30   — Bağlamdan bağımsız dilbilgisi PDF)
    evaluation/ground_truth/test_2.json   (id 31-60  — 728_profiles.json)
    evaluation/ground_truth/test_3.json   (id 61-90  — Fourier Transform PDF)
    evaluation/ground_truth/test_4.json   (id 91-100 — test1.txt / test2.txt)

Bu script iskeleti CSV'den üretir; `referans_cevaplar` ve `anahtar_kelimeler`
alanları elle (ya da dokümandan) doldurulur. Tekrar çalıştırıldığında MEVCUT
cevaplar KORUNUR — soru metni değişmediyse üzerine yazılmaz.

Kullanım:
    python evaluation/make_ground_truth.py            # 4 seti de üret/güncelle
    python evaluation/make_ground_truth.py test_2     # tek set
    python evaluation/make_ground_truth.py --status   # doldurulma durumunu raporla
"""
import csv
import json
import sys
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
DATASET_DIR = EVAL_DIR / "datasets"
GT_DIR = EVAL_DIR / "ground_truth"

DEFAULT_SETS = ["test_1", "test_2", "test_3", "test_4"]


def dataset_path(name: str) -> Path:
    return DATASET_DIR / f"{name}.csv"


def gt_path(name: str) -> Path:
    return GT_DIR / f"{name}.json"


def load_existing(name: str) -> dict:
    """Var olan GT dosyasını, yoksa eski tekil ground_truth.json'ı okur."""
    p = gt_path(name)
    if p.exists():
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    legacy = EVAL_DIR / "ground_truth.json"
    if legacy.exists():
        with open(legacy, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def build(name: str) -> dict:
    csv_file = dataset_path(name)
    if not csv_file.exists():
        raise FileNotFoundError(f"Veri seti bulunamadı: {csv_file}")

    existing = load_existing(name)
    with open(csv_file, "r", encoding="utf-8-sig") as f:
        rows = [r for r in csv.DictReader(f) if (r.get("soru") or "").strip()]

    out = {}
    for row in rows:
        q_id = (row.get("id") or "").strip()
        question = (row.get("soru") or "").strip()
        old = existing.get(q_id, {})
        # Eski kayıt YALNIZCA soru metni birebir aynıysa devralınır; aksi
        # halde bayat referanslar yanlış soruya bağlanıp EM/F1'i bozar.
        reusable = old.get("soru", "").strip() == question
        out[q_id] = {
            "soru": question,
            "zorluk": (row.get("zorluk") or "Orta").strip(),
            "beklenen_kaynak": (row.get("beklenen_kaynak") or "").strip(),
            "dokumanda_var_mi": (row.get("dokumanda_var_mi") or "Evet").strip(),
            "referans_cevaplar": old.get("referans_cevaplar", []) if reusable else [],
            "anahtar_kelimeler": old.get("anahtar_kelimeler", []) if reusable else [],
        }
    return out


def write(name: str, data: dict) -> Path:
    GT_DIR.mkdir(parents=True, exist_ok=True)
    p = gt_path(name)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return p


def status(names) -> None:
    print("=" * 72)
    print("GROUND TRUTH DURUMU")
    print("=" * 72)
    grand_total = grand_filled = 0
    for name in names:
        p = gt_path(name)
        if not p.exists():
            print(f"  {name:8s}: dosya yok — önce `python evaluation/make_ground_truth.py` çalıştırın")
            continue
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        total = len(data)
        # Negatif sorularda (dokumanda_var_mi=Hayır) referans cevap gerekmez;
        # başarı ölçütü modelin "bulunamadı" demesidir.
        negatives = sum(1 for v in data.values()
                        if str(v.get("dokumanda_var_mi", "")).strip().lower() in ("hayır", "hayir", "no"))
        filled = sum(1 for v in data.values() if v.get("referans_cevaplar"))
        needed = total - negatives
        grand_total += needed
        grand_filled += filled
        pct = (filled / needed * 100) if needed else 100.0
        print(f"  {name:8s}: {total:3d} soru | {negatives:2d} negatif | "
              f"referans dolu {filled:3d}/{needed:3d} (%{pct:.0f})")
    pct = (grand_filled / grand_total * 100) if grand_total else 100.0
    print("-" * 72)
    print(f"  TOPLAM  : referans dolu {grand_filled}/{grand_total} (%{pct:.0f})")
    print("=" * 72)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    only_status = "--status" in argv
    argv = [a for a in argv if not a.startswith("--")]
    names = argv or DEFAULT_SETS

    if not only_status:
        for name in names:
            data = build(name)
            p = write(name, data)
            print(f"✔ {name}: {len(data)} soru → {p}")
        print()
    status(names)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    main()
