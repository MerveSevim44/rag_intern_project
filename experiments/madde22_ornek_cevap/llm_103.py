"""
Madde 22 × madde 24 kesişimi: test_5 #103'ün cevabı birleşik DB ile değişiyor mu?
Bugünkü ve birleşik (simülasyon) DB ile aynı oturumda birer LLM çağrısı.

run_tests fonksiyonları değiştirilmeden kullanılır; yalnız run_tests'in
get_top_chunks adı db_path sabitlenmiş bir sarmalayıcıyla değiştirilir.

Kullanım:
    HF_HUB_OFFLINE=1 python -u experiments/madde22_ornek_cevap/llm_103.py SIM_DB
Çıktı: llm_103.jsonl
"""
import csv
import functools
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "evaluation"))

import run_tests  # noqa: E402
sys.path[:0] = [str(ROOT)]
import evaluation.benchmark_eval as B  # noqa: E402

_orig = run_tests.get_top_chunks


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    sim = sys.argv[1]
    q = next(r for r in csv.DictReader(open(ROOT / "evaluation/datasets/test_5.csv", encoding="utf-8-sig"))
             if r["id"] == "103")
    llm = run_tests.load_model()
    with open(HERE / "llm_103.jsonl", "w", encoding="utf-8") as f:
        for label, db in (("bugun", str(ROOT / "rag.db")), ("birlesik", sim)):
            run_tests.get_top_chunks = functools.partial(_orig, db_path=db)
            res = run_tests.run_single_test(llm, q["soru"])
            nf = B.check_is_not_found(res["cevap"], q["soru"])
            rec = {"db": label, "soru": q["soru"], "cevap": res["cevap"], "sinif": "TN" if nf else "FP",
                   "bulunan_kaynaklar": res["bulunan_kaynaklar"], "context": res.get("context", "")}
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            print(f"[{label}] {rec['sinif']} {res['bulunan_kaynaklar']}\n   {res['cevap']!r}\n", flush=True)
            run_tests.free_gpu_memory()


if __name__ == "__main__":
    main()
