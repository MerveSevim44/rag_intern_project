"""Madde 41 ön şart ölçümü — zorla D5 (madde 14 d5_gercek.py ile aynı enjeksiyon) + önerilen davranış
(sim_run_tests.kur) birlikte: 4 pozitif (test_2 #32/#35/#39/#42) ve 3 toplulaştırma sorusu (A1-A3,
madde 41 gözlemleri). Bugünkü davranış (fallback) sonuçları d5_gercek*.jsonl'da kayıtlı.
Kullanım (kökten): python -u experiments/madde41_simulasyon/d5_zorla_sim.py"""
import csv, json, os, sys
from pathlib import Path
os.environ.setdefault("RAG_EMBED_NUM_GPU", "99"); os.environ.setdefault("RAG_DENSE_FORCE_TOP_N", "0")
HERE = Path(__file__).resolve().parent; ROOT = HERE.parents[1]
sys.path[:0] = [str(HERE), str(ROOT / "evaluation"), str(ROOT / "src"), str(ROOT)]
os.environ["SIM_LOG"] = str(HERE / "d5_zorla_olaylar.jsonl")
EK = {"A1": "728_profiles.json veri setinde profillerin ortalama deneyim yılı (experience.years) kaçtır?",
      "A2": "728_profiles.json veri setinde kaç profil business türündedir?",
      "A3": "728_profiles.json veri setinde profillerin ortalama minimumNoticeHours değeri kaçtır?"}
GT = {"A1": "11.9986", "A2": "129", "A3": "9.75"}
BOZUK = "result = df['olmayan_sutun'].mean()"
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import sim_run_tests
import run_tests as T
from benchmark_eval import classify_answer
from gt_utils import load_ground_truth
gt = load_ground_truth()
rows = {r["id"]: r for r in csv.DictReader(open(ROOT / "evaluation/datasets/test_2.csv", encoding="utf-8-sig"))}
llm = T.load_model()
import code_interpreter as CI
gercek = CI.call_llm_text
sim_run_tests.kur()
kayit = []
for qid, soru in [(q, rows[q]["soru"]) for q in ("32", "35", "39", "42")] + list(EK.items()):
    CI.call_llm_text = lambda l, p: BOZUK
    try:
        for d in range(3):
            try:
                r = T.run_single_test(llm, soru); break
            except ConnectionError as e:
                if d == 2: raise
    finally:
        CI.call_llm_text = gercek
    sinif = classify_answer({**rows[qid], "set": "test_2", "cevap": r["cevap"]}, gt) if qid in rows else f"(GT={GT[qid]})"
    kayit.append({"id": qid, "sinif": sinif, "kaynaklar": r["bulunan_kaynaklar"], "cevap": r["cevap"]})
    print(f"#{qid} {sinif} | kaynak: {r['bulunan_kaynaklar'][:80]}\n   CEVAP: {r['cevap']!r}", flush=True)
(HERE / "d5_zorla_sim.jsonl").write_text("\n".join(json.dumps(k, ensure_ascii=False) for k in kayit), encoding="utf-8")
