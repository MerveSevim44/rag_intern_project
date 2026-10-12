"""
Madde 24 (D) ön verisi: semantic_rag sorularında bağlama giren adayların EN
YÜKSEK rerank skoru, eşik adaylarına göre pozitif / negatif kırılımı.
"Tüm adaylar eşiğin altındaysa bağlam boş" kuralının kaba bedel/kazanç tahmini.
Sınıf: v8 kayıtlı sınıfı (experiments/v8_bm25_stopword/report/genel_scored.csv).
Girdi: simulasyon.jsonl (retrieval, LLM yok).

Kullanım:
    python experiments/madde22_ornek_cevap/rerank_dagilimi.py > experiments/madde22_ornek_cevap/sonuc_rerank_dagilimi.txt
"""
import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
THRESHOLDS = (0.02, 0.04, 0.1, 0.2)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass
v8 = {(r["test_seti"], r["id"]): r["siniflandirma"] for r in
      csv.DictReader(open(ROOT / "experiments/v8_bm25_stopword/report/genel_scored.csv", encoding="utf-8-sig"))}
rows = [json.loads(l) for l in (HERE / "simulasyon.jsonl").read_text(encoding="utf-8").splitlines()]
for db in ("bugun", "birlesik"):
    pos, neg = [], []
    for r in rows:
        k = (r["set"], r["id"])
        if r["db"] != db or r["route"] != "semantic_rag" or not r["rerank"] or k not in v8:
            continue
        (neg if v8[k] in ("TN", "FP") else pos).append((max(r["rerank"]), k, v8[k]))
    print(f"== {db}: semantic_rag pozitif {len(pos)}, negatif {len(neg)}")
    for th in THRESHOLDS:
        lp = sorted(x for x in pos if x[0] < th)
        ln = sorted(x for x in neg if x[0] < th)
        print(f"   esik {th}: pozitif {len(lp)} (TP {sum(c == 'TP' for *_, c in lp)}) | "
              f"negatif {len(ln)} (FP {sum(c == 'FP' for *_, c in ln)})")
        for m, k, c in lp:
            print(f"      pozitif {k[0]}#{k[1]} {c} max_rerank={m:.4f}")
        for m, k, c in ln:
            if c == "FP":
                print(f"      negatif FP {k[0]}#{k[1]} max_rerank={m:.4f}")
