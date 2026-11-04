"""
Madde 14 Adım 2 — GERÇEK D5 vakası: bilgi veride VAR, sandbox 3 denemede çözemiyor
(servis çökmesi DEĞİL), akış semantik RAG'e düşüyor; kullanıcıya ne gidiyor?

Düzenek (src/ DEĞİŞMEZ): kod üreten çağrı (code_interpreter.call_llm_text) hata veren
bir kod döndürecek şekilde yamalanır; geri kalan her şey gerçek: retrieve (router,
sandbox denemeleri, semantik fallback, reranker), build_context, ask, synthesizer.
Kontrol: aynı soru yamasız (gerçek sandbox cevabı).
Sorular: test_2 #32, #35, #39, #42 — madde 18'de sandbox'ın doğru cevapladığı,
bilgisi veri setinde bulunan pozitifler (TP). Negatifler (#215/#216/#226) bu soruyu
cevaplamaz; bilerek kullanılmadı.

Kullanım (kökten): python -u experiments/madde14_bulunamadi/d5_gercek.py
Çıktı: d5_gercek.jsonl, log_d5_gercek.txt
"""
import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT / "evaluation"), str(ROOT / "src"), str(ROOT)]

SORULAR = ["32", "35", "39", "42"]
# Ek (benchmark dışı) TOPLULAŞTIRMA soruları: cevap tüm 728 kaydın hesabını ister, tek
# kayıt/özet bloktan okunamaz. Gerçek değerler data/728_profiles.json'dan pandas ile
# hesaplandı (ortalama deneyim 11.9986, business 129, ort. minimumNoticeHours 9.75).
EK = {
    "A1": ("728_profiles.json veri setinde profillerin ortalama deneyim yılı (experience.years) kaçtır?", "11.9986"),
    "A2": ("728_profiles.json veri setinde kaç profil business türündedir?", "129"),
    "A3": ("728_profiles.json veri setinde profillerin ortalama minimumNoticeHours değeri kaçtır?", "9.75"),
}
BOZUK_KOD = "result = df['olmayan_sutun'].mean()"
TEKRAR = 2


def main():
    import run_tests as T
    from benchmark_eval import classify_answer
    from gt_utils import load_ground_truth

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    gt = load_ground_truth()
    with open(ROOT / "evaluation/datasets/test_2.csv", encoding="utf-8-sig") as f:
        sorular = {r["id"]: r for r in csv.DictReader(f)}

    llm = T.load_model()
    CI = sys.modules.get("code_interpreter") or __import__("code_interpreter")
    gercek = CI.call_llm_text
    cagri = {"n": 0}

    def bozuk(l, p):
        cagri["n"] += 1
        return BOZUK_KOD

    ek_mod = len(sys.argv) > 1 and sys.argv[1] == "ek"
    isler = ([(q, EK[q][0], EK[q][1]) for q in EK] if ek_mod
             else [(q, sorular[q]["soru"], None) for q in SORULAR])
    kayit = []
    for qid, soru, gt_not in isler:
        row = sorular.get(qid)
        for varyant in ("kontrol", "D5"):
            for n in range(TEKRAR):
                CI.call_llm_text = bozuk if varyant == "D5" else gercek
                cagri["n"] = 0
                try:
                    r = T.run_single_test(llm, soru)
                finally:
                    CI.call_llm_text = gercek
                sinif = (classify_answer({**row, "set": "test_2", "cevap": r["cevap"]}, gt)
                         if row else f"(GT={gt_not})")
                k = {"id": qid, "varyant": varyant, "tekrar": n + 1, "bozuk_kod_cagrisi": cagri["n"],
                     "kaynaklar": r["bulunan_kaynaklar"], "sinif": sinif, "cevap": r["cevap"],
                     "baglam_ilk_200": r["context"][:200]}
                kayit.append(k)
                print(f"#{qid} {varyant}[{n + 1}] bozuk_kod_cagrisi={cagri['n']} sinif={sinif}\n"
                      f"   kaynaklar: {r['bulunan_kaynaklar'][:160]}\n   CEVAP: {r['cevap'][:300]!r}", flush=True)

    with open(HERE / ("d5_gercek_ek.jsonl" if ek_mod else "d5_gercek.jsonl"), "w", encoding="utf-8") as f:
        for k in kayit:
            f.write(json.dumps(k, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
