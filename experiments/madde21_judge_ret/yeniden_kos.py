"""
Madde 21 Adım 3 — v8'in 5 FN sorusunu güncel sistemde yeniden koş + judge'la.

Sorular: test_2 #50, #56; test_3 #79, #82; test_4 #91 (v8'de benchmark FN;
#50 skorlayıcının yanlış FN'si). Güncel sistem: madde 19 + madde 22 sonrası
DB, madde 29 GPU embedding, madde 20 benchmark top_k = retrieval.TOP_K.
(2b hâlâ açık; bu 5 sorunun hiçbiri router 2b'ye bağlı değil.)

Her koşu AYRI süreçlerde: evaluation/run_tests.py (Foundry) ->
evaluation/llm_as_judge.py (Groq). Cevap üretiminde örnekleme olduğu için en
az 2 bağımsız koşu: `python experiments/madde21_judge_ret/yeniden_kos.py 1`
ve `... 2`. Çıktılar kosu_N/ altına; sınıf sütunu judge CSV'sinde.
"""
import csv
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
HEDEF = {"test_2": ["50", "56"], "test_3": ["79", "82"], "test_4": ["91"]}
FIELDS = ["id", "zorluk", "soru", "beklenen_kaynak", "dokumanda_var_mi"]


def soru_csv(path):
    rows = []
    for s, ids in HEDEF.items():
        with open(ROOT / "evaluation/datasets" / f"{s}.csv", encoding="utf-8-sig") as f:
            rows += [{k: r[k] for k in FIELDS} for r in csv.DictReader(f) if r["id"] in ids]
    assert len(rows) == 5, rows
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)


def main(kosu):
    out = HERE / f"kosu_{kosu}"
    out.mkdir(exist_ok=True)
    sorular = HERE / "sorular_5.csv"
    if not sorular.exists():
        soru_csv(sorular)
    sonuc, judge = out / "sonuclari.csv", out / "sonuclari_judge.csv"
    for cmd, log in (
        ([sys.executable, "evaluation/run_tests.py", str(sorular), str(sonuc)], out / "log_run_tests.txt"),
        ([sys.executable, "evaluation/llm_as_judge.py", str(sonuc), "--output", str(judge)], out / "log_judge.txt"),
    ):
        with open(log, "w", encoding="utf-8") as f:
            subprocess.run(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT, check=True,
                           env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"})


if __name__ == "__main__":
    main(sys.argv[1])
