"""
Madde 22 Adım 2b — 147 soru, yedek DB vs yeniden ingest edilmiş rag.db (aynı süreç),
ve simülasyonun "birlesik" sonucuyla karşılaştırma (plan §4 ölçüt 1).

simulasyon.py'nin run_all'ı aynen kullanılır (retrieve top_k=5, LLM yok).

Kullanım:
    HF_HUB_OFFLINE=1 python -u experiments/madde22_ornek_cevap/adim2_retrieval.py
Çıktı: adim2_retrieval.jsonl (db: "yedek" / "yeni"), sonuc_adim2_retrieval.txt
"""
import csv
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
_spec = importlib.util.spec_from_file_location("simulasyon", HERE / "simulasyon.py")
S = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(S)

BACKUP = ROOT / "rag.db.bak_madde22_2026-10-12"
OUT = HERE / "adim2_retrieval.jsonl"


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    questions = {}
    for s in S.SETS:
        with open(ROOT / "evaluation" / "datasets" / f"{s}.csv", encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                questions[(s, r["id"])] = r["soru"]
    with open(OUT, "w", encoding="utf-8") as out:
        S.run_all(BACKUP, "yedek", questions, out)
        S.run_all(ROOT / "rag.db", "yeni", questions, out)

    cur = {(r["db"], r["set"], r["id"]): r for r in map(json.loads, OUT.read_text(encoding="utf-8").splitlines())}
    sim = {(r["db"], r["set"], r["id"]): r for r in
           map(json.loads, (HERE / "simulasyon.jsonl").read_text(encoding="utf-8").splitlines())}
    lines = []
    for label, a, b in (("yeni  vs simulasyon birlesik", "yeni", "birlesik"),
                        ("yedek vs simulasyon bugun   ", "yedek", "bugun")):
        diff = [k for k in questions if cur[(a, *k)]["kaynaklar"] != sim[(b, *k)]["kaynaklar"]]
        rdiff = [k for k in questions if cur[(a, *k)]["kaynaklar"] == sim[(b, *k)]["kaynaklar"]
                 and cur[(a, *k)]["rerank"] != sim[(b, *k)]["rerank"]]
        lines.append(f"{label}: kaynak listesi farkli {len(diff)}/{len(questions)}, "
                     f"ayni listede rerank skoru farkli {len(rdiff)}")
        for k in diff:
            lines.append(f"   {k[0]}#{k[1]}\n      simdi: {cur[(a, *k)]['kaynaklar']}\n      sim  : {sim[(b, *k)]['kaynaklar']}")
    changed = [k for k in questions if cur[("yedek", *k)]["kaynaklar"] != cur[("yeni", *k)]["kaynaklar"]]
    lines.append(f"yedek vs yeni (bu oturum): kaynak listesi degisen {len(changed)} soru")
    lines += [f"   {k[0]}#{k[1]}" for k in changed]
    text = "\n".join(lines) + "\n"
    (HERE / "sonuc_adim2_retrieval.txt").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
