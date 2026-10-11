"""
Karşı-olgu koşusu: bağlamı tokenizer değişikliğiyle DEĞİŞEN sorular, güncel
kodda ESKİ tokenizer (v0_tokenizer) yamalıyken run_tests akışıyla (k=5).

Neden: v7 -> v8 farkı tokenizer'a ek olarak dffb6a5 değişikliklerini (OCR,
soruya duyarlı kırpma, router) ve LLM nondeterminizmini içeriyor. Katman 1,
147 sorunun 137'sinde bağlamın eski/yeni tokenizer'da bayt bayt aynı olduğunu
gösterdi; tokenizer'ın etkisi yalnız kalan 10 soruda. Bu 10 soru güncel kodda
eski tokenizer'la koşulunca "aynı kod, yalnız tokenizer farklı" karşılaştırması
elde edilir.

DİKKAT: run_tests `src.retrieval`'ı, llm_client'ın soruya duyarlı kırpması
`retrieval`'ı import ediyor — iki ayrı modül nesnesi. İkisi de yamalanır ve
bağlamın gerçekten eski tokenizer'la kurulduğu katman 1 ara kaydıyla doğrulanır.

Kullanım:
    python -u experiments/v8_bm25_stopword/run_v0_counterfactual.py
"""
import csv
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for p in (ROOT / "evaluation", ROOT / "src", ROOT, ROOT / "experiments" / "bm25_tokenizer_variants"):
    sys.path.insert(0, str(p))

import run_tests  # noqa: E402
import retrieval as R_bare  # noqa: E402
import src.retrieval as R_src  # noqa: E402
from v0_tokenizer import v0_tokenize  # noqa: E402

for mod in (R_bare, R_src):
    mod._tokenize = v0_tokenize
    mod.invalidate_cache()

CHANGED = [("test_1", "1"), ("test_1", "6"), ("test_1", "7"), ("test_1", "29"),
           ("test_2", "40"), ("test_2", "47"), ("test_2", "49"),
           ("test_4", "92"), ("test_5", "115"), ("test_negative", "229")]


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    cache = {}
    with open(ROOT / "experiments/bm25_tokenizer_variants/regresyon_cache.jsonl", encoding="utf-8") as f:
        for rec in map(json.loads, f):
            cache[rec["key"]] = rec["res"]

    llm = run_tests.load_model()
    out = HERE / "results" / "v0_karsi_olgu.csv"
    fields = ["set", "id", "soru", "cevap", "bulunan_kaynaklar", "sure_sn", "context",
              "dogrulama_durumu", "baglam_katman1_eski_ile_ayni"]
    with open(out, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for s, qid in CHANGED:
            with open(ROOT / f"evaluation/datasets/{s}.csv", encoding="utf-8-sig") as qf:
                q = next(r for r in csv.DictReader(qf) if r["id"] == qid)
            print(f"[{s} #{qid}] {q['soru']}", flush=True)
            res = run_tests.run_single_test(llm, q["soru"])
            expected = cache[f"eski|{s}|{qid}"]["5"]["baglam"]
            same = res["context"] == expected
            w.writerow(dict(set=s, id=qid, soru=q["soru"], baglam_katman1_eski_ile_ayni=same, **res))
            fh.flush()
            print(f"    -> {res['sure_sn']} sn | bağlam katman-1 eski ile aynı: {same}", flush=True)
            run_tests.free_gpu_memory()
            time.sleep(1)
    print(f"Sonuclar: {out}")


if __name__ == "__main__":
    main()
