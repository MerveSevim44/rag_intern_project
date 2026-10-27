"""
Madde 21 kapsam ölçümü — judge, pozitif sorulardaki retleri ödüllendiriyor mu?

Elimizdeki her judge koşusu için: benchmark_eval'in KENDİ sınıflandırma
kuralıyla (check_is_not_found + GT negatiflik kuralı) pozitif soruda ret = FN
bulunur, judge'ın o satıra verdiği skorlar yanına konur. Yeni LLM/judge çağrısı
YOK; yalnız mevcut CSV'ler okunur.

"Ödül" tanımı (judge prompt'undaki "Doğru Ret" kuralının imzası): AR>=4 VE TP>=4.

Çapraz kontrol: v7/v8 için madde 27 sonrası yeniden skorlanmış CSV'lerdeki
'siniflandirma' sütunu ile bu script'in FN kararı karşılaştırılır.

Kullanım (kökten): python experiments/madde21_judge_ret/kapsam.py
"""
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# evaluation/ en önde: kökte de bir benchmark_eval.py (eski kopya) var.
sys.path[:0] = [str(ROOT / "evaluation"), str(ROOT / "src"), str(ROOT)]

from benchmark_eval import check_is_not_found, _is_negative_flag  # noqa: E402
from gt_utils import load_ground_truth, resolve_reference, is_run_error  # noqa: E402

SETS = ["test_1", "test_2", "test_3", "test_4", "test_5"]
RUNS = {
    # ad: (sonuç+judge dizini, yeniden skorlanmış genel CSV ya da None)
    "baz_2026-10-03": (ROOT / "evaluation/datasets", None),
    "v7": (ROOT / "experiments/v7_refusal_clarity/results",
           ROOT / "experiments/madde27_nan_embedding/yeniden_skor_v7/genel_scored.csv"),
    "v8": (ROOT / "experiments/v8_bm25_stopword/results",
           ROOT / "experiments/madde27_nan_embedding/yeniden_skor_v8/genel_scored.csv"),
}


def read(path):
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def score(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def classify(row, gt):
    """benchmark_eval.evaluate_rag_system'in TP/TN/FP/FN kuralının aynısı."""
    expected_src = (row.get("beklenen_kaynak") or "").strip()
    doc_is_negative = _is_negative_flag((row.get("dokumanda_var_mi") or "Evet").strip())
    has_reference = bool(resolve_reference(row, gt, csv_fallback=False))
    is_negative = (expected_src == "-") or (doc_is_negative and not has_reference)
    not_found = check_is_not_found(row.get("cevap", ""), row.get("soru", ""))
    if is_negative:
        return "TN" if not_found else "FP"
    return "FN" if not_found else "TP"


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    gt = load_ground_truth()
    for run, (d, scored_csv) in RUNS.items():
        scored = {}
        if scored_csv and scored_csv.exists():
            scored = {(r["test_seti"], r["id"]): r["siniflandirma"] for r in read(scored_csv)}
        n_pos = n_fn = n_reward = 0
        mismatches, rows_out = [], []
        for s in SETS:
            res, jud = d / f"{s}_sonuclari.csv", d / f"{s}_sonuclari_judge.csv"
            if not (res.exists() and jud.exists()):
                print(f"[{run}] {s}: dosya eksik, atlandı")
                continue
            judge = {r["id"]: r for r in read(jud)}
            for row in read(res):
                if is_run_error(row.get("cevap", "")):
                    continue
                st = classify(row, gt)
                key = (s, row["id"])
                if key in scored and scored[key] != st:
                    mismatches.append((key, scored[key], st))
                if st not in ("TP", "FN"):
                    continue
                n_pos += 1
                if st != "FN":
                    continue
                n_fn += 1
                j = judge.get(row["id"], {})
                if (j.get("cevap") or "") != (row.get("cevap") or ""):
                    print(f"[{run}] UYARI {s}#{row['id']}: judge cevabı sonuç cevabından farklı")
                sc = [score(j.get(k)) for k in ("faithfulness_score", "answer_relevance_score",
                                                "task_performance_score", "alignment_score")]
                reward = sc[1] is not None and sc[2] is not None and sc[1] >= 4 and sc[2] >= 4
                n_reward += reward
                rows_out.append((s, row["id"], sc, reward, row.get("cevap", "")[:70],
                                 (j.get("reasoning") or "")[:110]))
        print(f"\n=== {run}: pozitif {n_pos} | FN (pozitif soruda ret) {n_fn} | "
              f"judge ödüllendirdi (AR>=4 ve TP>=4) {n_reward}/{n_fn}")
        if scored:
            print(f"    çapraz kontrol (yeniden skorlanmış CSV): uyuşmazlık {len(mismatches)}"
                  + (f" {mismatches[:5]}" if mismatches else ""))
        for s, i, sc, rew, cev, rea in rows_out:
            print(f"  {s}#{i:<4} F/AR/TP/AL={sc} {'ÖDÜL' if rew else '    '} | {cev!r}")
            print(f"      judge: {rea!r}")


if __name__ == "__main__":
    main()
