"""
Madde 21 Adım 3 — kosu_1 ve kosu_2'yi karşılaştırır (LLM çağrısı yok).

Her soru için: benchmark sınıfı (judge CSV 'siniflandirma'), judge skorları,
"ödül" (AR>=4 ve TP>=4), iki koşu arasında cevap/bağlam aynı mı, ve cevabın
anahtar terimleri kayıtlı bağlamda geçiyor mu (kapsam.py'deki v8 kontrolünün
aynısı). v8 satırı karşılaştırma için yanına konur.

Kullanım (kökten): python experiments/madde21_judge_ret/karsilastir.py
"""
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
V8 = ROOT / "experiments/v8_bm25_stopword/results"
SET_OF = {"50": "test_2", "56": "test_2", "79": "test_3", "82": "test_3", "91": "test_4"}
# Cevabın bağlamda olup olmadığını gösteren terimler (GT referansından)
KW = {"50": ["Cumartesi"], "56": ["schemaVersion"], "79": ["dar", "geniş", "ölçekleme"],
      "82": ["konvolüsyon", "çarpım"], "91": ["Gümüş Yaprak"]}
SCORES = ("faithfulness_score", "answer_relevance_score", "task_performance_score", "alignment_score")


def read(p):
    with open(p, encoding="utf-8-sig") as f:
        return {r["id"]: r for r in csv.DictReader(f)}


def odul(j):
    try:
        return int(j["answer_relevance_score"]) >= 4 and int(j["task_performance_score"]) >= 4
    except (TypeError, ValueError):
        return False


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    k = {n: (read(HERE / f"kosu_{n}/sonuclari.csv"), read(HERE / f"kosu_{n}/sonuclari_judge.csv"))
         for n in (1, 2)}
    for i, s in SET_OF.items():
        v8s = read(V8 / f"{s}_sonuclari.csv")[i]
        v8j = read(V8 / f"{s}_sonuclari_judge.csv")[i]
        print(f"\n=== {s}#{i}: {v8s['soru'][:80]}")
        print(f"  v8      F/AR/TP/AL={[v8j[x] for x in SCORES]} | {v8s['cevap'][:90]!r}")
        for n in (1, 2):
            sr, jr = k[n][0][i], k[n][1][i]
            ctx = sr.get("context", "")
            kw = ", ".join(f"{w}={'+' if w.lower() in ctx.lower() else '-'}" for w in KW[i])
            print(f"  koşu {n}  {jr['siniflandirma']:<3} F/AR/TP/AL={[jr[x] for x in SCORES]} "
                  f"{'ÖDÜL' if jr['siniflandirma'] == 'FN' and odul(jr) else '    '} "
                  f"| bağlamda: {kw}")
            print(f"          kaynaklar: {sr['bulunan_kaynaklar'][:150]}")
            print(f"          cevap: {sr['cevap'][:160]!r}")
        a, b = k[1][0][i], k[2][0][i]
        print(f"  koşu1 vs koşu2: cevap {'AYNI' if a['cevap'] == b['cevap'] else 'FARKLI'}, "
              f"bağlam {'AYNI' if a['context'] == b['context'] else 'FARKLI'}, "
              f"kaynak listesi {'AYNI' if a['bulunan_kaynaklar'] == b['bulunan_kaynaklar'] else 'FARKLI'}")
        print(f"  v8 vs koşu1 kaynak listesi: "
              f"{'AYNI' if v8s['bulunan_kaynaklar'] == a['bulunan_kaynaklar'] else 'FARKLI'}")

    print("\n=== Özet")
    for n in (1, 2):
        j = k[n][1]
        fn = [i for i in SET_OF if j[i]["siniflandirma"] == "FN"]
        od = [i for i in fn if odul(j[i])]
        print(f"  koşu {n}: FN {len(fn)}/5 {fn} | judge ödüllendirdi {len(od)}/{len(fn)} {od}")


if __name__ == "__main__":
    main()
