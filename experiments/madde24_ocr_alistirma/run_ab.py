"""
Madde 24 Adım 2 — görev notu A/B, aynı oturumda (Foundry + Ollama + reranker).
Plan: docs/implementation_plan_madde24_ocr_isaret.md §4, §5.

Faz 1: Adım 0 etki kümesi (etkilenen_set.csv'de isaretli_sayfalar dolu 16 soru)
       × 3 tekrar × 2 kol (task_notes=True "acik" / False "kapali").
       Kol sırası tekrardan tekrara değişir (1: açık→kapalı, 2: kapalı→açık, ...)
       ki sabit sıra etkisi karışmasın.
Faz 2: Tam negatif set (32) × 1, kol "acik" (plan: prompt'a dokunan her
       değişiklik tam negatif setle doğrulanır).

run_tests fonksiyonları değiştirilmeden kullanılır (run_single_test,
task_notes parametresi Adım 1'de eklendi). Her satır üretilir üretilmez
ab_sonuclari.jsonl'a yazılır; yeniden başlatılırsa tamamlanan satırlar atlanır.

Kullanım:
    HF_HUB_OFFLINE=1 python -u experiments/madde24_ocr_alistirma/run_ab.py
"""
import csv
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "evaluation"))

import run_tests  # noqa: E402

OUT = HERE / "ab_sonuclari.jsonl"
REPS = 3
MAX_CONSECUTIVE_ERRORS = 3
DATASET_FIELDS = ("soru", "referans_cevap", "dokumanda_var_mi", "beklenen_kaynak")


def dataset(set_name):
    with open(ROOT / "evaluation" / "datasets" / f"{set_name}.csv", encoding="utf-8-sig") as f:
        return {r["id"]: r for r in csv.DictReader(f)}


def plan():
    with open(HERE / "etkilenen_set.csv", encoding="utf-8-sig") as f:
        affected = [(r["set"], r["id"]) for r in csv.DictReader(f) if r["isaretli_sayfalar"]]
    jobs = []
    for rep in range(1, REPS + 1):
        arms = ("acik", "kapali") if rep % 2 else ("kapali", "acik")
        for s, i in affected:
            for arm in arms:
                jobs.append(("faz1", s, i, rep, arm))
    for i in dataset("test_negative"):
        jobs.append(("faz2", "test_negative", i, 1, "acik"))
    return jobs


def done_keys():
    if not OUT.exists():
        return set()
    keys = set()
    for line in OUT.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        keys.add((r["faz"], r["set"], r["id"], r["tekrar"], r["kol"]))
    return keys


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    jobs = plan()
    done = done_keys()
    todo = [j for j in jobs if j not in done]
    print(f"Toplam is: {len(jobs)}  tamamlanan: {len(jobs) - len(todo)}  kalan: {len(todo)}")
    if not todo:
        return
    sets = {s: dataset(s) for s in {j[1] for j in todo}}
    print("Model yukleniyor...")
    llm = run_tests.load_model()
    t0, streak = time.perf_counter(), []
    with open(OUT, "a", encoding="utf-8") as f:
        for n, (faz, s, i, rep, arm) in enumerate(todo, 1):
            row = sets[s][i]
            print(f"[{n}/{len(todo)}] {faz} {s}#{i} tekrar={rep} kol={arm}: {row['soru'][:70]}")
            try:
                res = run_tests.run_single_test(llm, row["soru"], task_notes=(arm == "acik"))
                streak = []
            except Exception as e:
                res = {"cevap": f"HATA: {e}", "bulunan_kaynaklar": "", "sure_sn": 0,
                       "context": "", "dogrulama_durumu": ""}
                streak.append((s, i, run_tests.error_kind(str(e))))
            rec = {"faz": faz, "set": s, "id": i, "tekrar": rep, "kol": arm,
                   **{k: row.get(k, "") for k in DATASET_FIELDS},
                   "cevap": res["cevap"], "bulunan_kaynaklar": res["bulunan_kaynaklar"],
                   "not_var": "[Not: Bu parça okuyucuya" in (res.get("context") or ""),
                   "context": res.get("context", ""), "sure_sn": res["sure_sn"]}
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            print(f"    -> {res['sure_sn']} sn  not_var={rec['not_var']}  {res['cevap'][:90]!r}")
            if len(streak) >= MAX_CONSECUTIVE_ERRORS:
                sys.exit(f"{len(streak)} ardisik hata: {streak} — kosu durduruldu (devam icin yeniden calistir)")
            run_tests.free_gpu_memory()
            time.sleep(1)
    print(f"\nTamamlandi: {len(todo)} is, {(time.perf_counter() - t0) / 60:.1f} dk. Sonuclar: {OUT}")


if __name__ == "__main__":
    main()
