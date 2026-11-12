"""
A1 entegrasyon: yalniz CIKTISI DEGISEN sorulari judge'la (kaydedilmis context'e gore, evaluation/ DEGISMEZ).
Kullanim (kokten): python -u experiments/madde_grupA_sutun/entegrasyon_judge.py KOSUL ID1,ID2,... CIKTI_ADI
  KOSUL: kontrol | islem  (entegrasyon/<KOSUL>/sonuclari.csv); cikti: entegrasyon/judge_<CIKTI_ADI>.csv
"""
import csv, os, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT / "evaluation"), str(ROOT / "src"), str(ROOT)]
csv.field_size_limit(10**9)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
kosul, ids, ad = sys.argv[1], [i for i in sys.argv[2].split(",") if i], sys.argv[3]
import llm_as_judge as J

kaynak = HERE / "entegrasyon" / kosul / "sonuclari.csv"
with open(kaynak, encoding="utf-8-sig") as f:
    rd = csv.DictReader(f)
    alanlar, rows = rd.fieldnames, [r for r in rd if r["id"] in ids]
girdi = HERE / "entegrasyon" / f"_girdi_{ad}.csv"
with open(girdi, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=alanlar)
    w.writeheader()
    w.writerows(rows)
J.REBUILD_CONTEXT = False
J.run_judge_evaluation(sonuc_csv=str(girdi), output_csv=str(HERE / "entegrasyon" / f"judge_{ad}.csv"),
                       ground_truth_path=None, judge_model=J.JUDGE_MODEL, only_ids=ids)
