"""
gt_utils.py — Ground truth (referans cevap) yükleme ve sonuç satırı yardımcıları.

benchmark_eval.py ve llm_as_judge.py ortak kullanır. Eskiden her script
ground truth dosyasını kendi seçiyordu: llm_as_judge sabit
evaluation/ground_truth.json'ı, benchmark_eval ise sonuç dosyasının adından
türettiği ground_truth/<set>.json'ı okuyor, adı tanıyamazsa (örn. *_ctx.csv)
sessizce eski ground_truth.json'a düşüyordu — o dosya aynı id'lerde (1-30)
FARKLI, eski soruların referanslarını taşıyor.

Artık ground_truth/ altındaki tüm dosyalar tek sözlükte birleştirilir ve
referans soru id'si ile bulunur. Id'ler setler arasında benzersizdir
(test_1: 1-30, test_2: 31-60, ...); çakışma olursa script durur.
"""

import json
import sys
from pathlib import Path

# Test bazlı ground truth dosyalarının dizini (test_1.json ... test_5.json).
GROUND_TRUTH_DIR = Path(__file__).resolve().parent / "ground_truth"


def load_ground_truth(path=None):
    """
    Ground truth'u {id: kayıt} olarak yükler.

    `path` verilirse yalnızca o dosya okunur (dosya yoksa FileNotFoundError).
    Verilmezse GROUND_TRUTH_DIR altındaki tüm JSON'lar birleştirilir; aynı id
    birden fazla dosyada varsa hangi dosyalarda çakıştığı yazılıp durulur.
    """
    if path:
        gt_path = Path(path)
        if not gt_path.exists():
            raise FileNotFoundError(f"Ground truth bulunamadı: {gt_path}")
        with open(gt_path, "r", encoding="utf-8") as f:
            return json.load(f)

    merged, origin, conflicts = {}, {}, {}
    for gt_path in sorted(GROUND_TRUTH_DIR.glob("*.json")):
        with open(gt_path, "r", encoding="utf-8") as f:
            for soru_id, entry in json.load(f).items():
                if soru_id in origin:
                    conflicts.setdefault(soru_id, [origin[soru_id]]).append(gt_path.name)
                    continue
                merged[soru_id] = entry
                origin[soru_id] = gt_path.name
    if conflicts:
        lines = "\n".join(f"  id {soru_id}: {', '.join(files)}"
                          for soru_id, files in sorted(conflicts.items(),
                                                       key=lambda kv: int(kv[0]) if kv[0].isdigit() else 0))
        sys.exit(f"Ground truth dosyalarında çakışan id'ler var ({GROUND_TRUTH_DIR}):\n{lines}")
    return merged


# run_tests.py bir soruda LLM/retrieval hatası alınca cevap sütununa
# f"HATA: {e}" yazar. Bu satırlar bir cevap değildir: skorlanmaz, ayrıca raporlanır.
RUN_ERROR_PREFIX = "HATA:"


def is_run_error(answer):
    """Cevap, run_tests.py'nin yazdığı bir çalışma hatası mı?"""
    return (answer or "").lstrip().startswith(RUN_ERROR_PREFIX)


def resolve_reference(row, gt, csv_fallback=True):
    """
    Satırın referans cevap(lar)ını bulur: önce ground truth (id ile).
    `csv_fallback` açıksa ve GT'de yoksa sonuç CSV'sindeki 'referans_cevap'
    sütunu kullanılır (test_negative gibi GT dosyası olmayan setler).
    Bulunamazsa boş liste döner.
    """
    soru_id = str(row.get("id", "")).strip()
    references = gt.get(soru_id, {}).get("referans_cevaplar") or []
    if references or not csv_fallback:
        return references
    csv_reference = (row.get("referans_cevap") or "").strip()
    return [csv_reference] if csv_reference else []
