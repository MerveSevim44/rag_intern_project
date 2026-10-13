"""
Madde 22 Adım 3 — LLM ölçümü: yedek DB vs yeniden ingest edilmiş rag.db, aynı oturum.
Plan: docs/implementation_plan_madde22_ornek_cevap.md §4, §5 Adım 3.

Faz 1: Adım 2'de kaynak listesi değişen 18 soru × 2 DB × 1 tekrar (üretim
       deterministik — madde 24 Adım 2). DB sırası sorudan soruya değişir.
Faz 2: tam negatif set (32) × yeni DB.

run_tests fonksiyonları değiştirilmeden kullanılır; yalnız run_tests'in
get_top_chunks adı db_path sabitlenmiş bir sarmalayıcıyla değiştirilir
(llm_103.py yöntemi). Satır satır adim3_sonuclari.jsonl'a yazılır; yeniden
başlatılırsa tamamlanan işler atlanır. 3 ardışık hatada durur.

Kullanım:
    HF_HUB_OFFLINE=1 python -u experiments/madde22_ornek_cevap/run_adim3.py
"""
import csv
import functools
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "evaluation"))

import run_tests  # noqa: E402

OUT = HERE / "adim3_sonuclari.jsonl"
DBS = {"yedek": str(ROOT / "rag.db.bak_madde22_2026-10-12"), "yeni": str(ROOT / "rag.db")}
MAX_CONSECUTIVE_ERRORS = 3
DATASET_FIELDS = ("soru", "referans_cevap", "dokumanda_var_mi", "beklenen_kaynak")
_orig_get_top_chunks = run_tests.get_top_chunks


def dataset(set_name):
    with open(ROOT / "evaluation" / "datasets" / f"{set_name}.csv", encoding="utf-8-sig") as f:
        return {r["id"]: r for r in csv.DictReader(f)}


def plan():
    rows = [json.loads(l) for l in (HERE / "adim2_retrieval.jsonl").read_text(encoding="utf-8").splitlines()]
    by = {(r["db"], r["set"], r["id"]): r["kaynaklar"] for r in rows}
    keys = []
    for r in rows:
        k = (r["set"], r["id"])
        if r["db"] == "yedek" and by[("yedek", *k)] != by[("yeni", *k)]:
            keys.append(k)
    jobs = []
    for n, (s, i) in enumerate(keys):
        for db in (("yedek", "yeni") if n % 2 == 0 else ("yeni", "yedek")):
            jobs.append(("faz1", s, i, db))
    jobs += [("faz2", "test_negative", i, "yeni") for i in dataset("test_negative")]
    return jobs


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    jobs = plan()
    done = set()
    if OUT.exists():
        for line in OUT.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            done.add((r["faz"], r["set"], r["id"], r["db"]))
    todo = [j for j in jobs if j not in done]
    print(f"Is: {len(jobs)} (faz1 {sum(j[0] == 'faz1' for j in jobs)}, faz2 {sum(j[0] == 'faz2' for j in jobs)}) "
          f"kalan: {len(todo)}")
    if not todo:
        return
    sets = {s: dataset(s) for s in {j[1] for j in todo}}
    llm = run_tests.load_model()
    t0, streak = time.perf_counter(), 0
    with open(OUT, "a", encoding="utf-8") as f:
        for n, (faz, s, i, db) in enumerate(todo, 1):
            row = sets[s][i]
            run_tests.get_top_chunks = functools.partial(_orig_get_top_chunks, db_path=DBS[db])
            print(f"[{n}/{len(todo)}] {faz} {s}#{i} db={db}: {row['soru'][:70]}")
            try:
                res = run_tests.run_single_test(llm, row["soru"])
                streak = 0
            except Exception as e:
                res = {"cevap": f"HATA: {e}", "bulunan_kaynaklar": "", "sure_sn": 0, "context": ""}
                streak += 1
            rec = {"faz": faz, "set": s, "id": i, "db": db, **{k: row.get(k, "") for k in DATASET_FIELDS},
                   "cevap": res["cevap"], "bulunan_kaynaklar": res["bulunan_kaynaklar"],
                   "context": res.get("context", ""), "sure_sn": res["sure_sn"]}
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            print(f"    -> {res['sure_sn']} sn {res['bulunan_kaynaklar'][:80]!r} {res['cevap'][:80]!r}")
            if streak >= MAX_CONSECUTIVE_ERRORS:
                sys.exit(f"{streak} ardisik hata — kosu durduruldu (servisleri kontrol et, yeniden calistir)")
            run_tests.free_gpu_memory()
            time.sleep(1)
    print(f"\nTamamlandi: {len(todo)} is, {(time.perf_counter() - t0) / 60:.1f} dk.")


if __name__ == "__main__":
    main()
