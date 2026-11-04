"""
Madde 38 Örnek 3 triyajı — test_2 #42 ("iptal notu"): bozuk cevap ("notuwresi", "same")
normal yolda da çıkıyor mu, yoksa D5 (sandbox çözemedi -> semantik RAG) yoluna mı özgü?
Yalnız gözlem; src/ DEĞİŞMEZ.

  N   normal yol (enjeksiyonsuz), orijinal soru metni, 2 tekrar
  D5  madde 14 d5_gercek.py ile aynı enjeksiyon (kod üreten çağrı hata veren kod döndürür),
      2 tekrar. Ek olarak ask() içinde modelin HAM çıktısı (_fix_currency_hallucination
      girdisi) yakalanır: bozulma modelden mi, sonradan işlemden mi geliyor; cevap
      MAX_ANSWER_TOKENS sınırına dayandı mı (uzunluk); bağlamda bozuk sözcükler var mı.

Kullanım (kökten): python -u experiments/madde38_42_triyaj/triyaj.py
Çıktı: triyaj.jsonl, log_triyaj.txt
"""
import csv
import json
import os
import subprocess
import sys
import time
from pathlib import Path

os.environ.setdefault("RAG_EMBED_NUM_GPU", "99")
os.environ.setdefault("RAG_DENSE_FORCE_TOP_N", "0")

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT / "evaluation"), str(ROOT / "src"), str(ROOT)]

BOZUK_KOD = "result = df['olmayan_sutun'].mean()"
TEKRAR = 2
BOZUK_SOZCUKLER = ("notuwresi", "same")
OLLAMA_APP = r"C:\Users\merve\AppData\Local\Programs\Ollama\ollama app.exe"


def ollama_yeniden_baslat():
    subprocess.run(["powershell", "-NoProfile", "-Command",
                    "Get-Process ollama* -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue"],
                   timeout=30, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)
    subprocess.Popen(["powershell", "-NoProfile", "-Command", f"Start-Process '{OLLAMA_APP}'"],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(8)


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
        row = next(r for r in csv.DictReader(f) if r["id"] == "42")
    soru = row["soru"]

    llm = T.load_model()
    CI = sys.modules.get("code_interpreter") or __import__("code_interpreter")
    L = sys.modules[T.ask.__module__]
    gercek_ci = CI.call_llm_text
    gercek_fix = L._fix_currency_hallucination
    yakala = {}

    def fix_sarmal(metin, ctx):
        yakala["ham_model"] = metin
        return gercek_fix(metin, ctx)

    L._fix_currency_hallucination = fix_sarmal

    kayit = []
    for varyant in ("N", "D5"):
        for n in range(TEKRAR):
            CI.call_llm_text = (lambda l, p: BOZUK_KOD) if varyant == "D5" else gercek_ci
            yakala.clear()
            try:
                for deneme in range(3):
                    try:
                        r = T.run_single_test(llm, soru)
                        break
                    except ConnectionError as e:
                        if "Embedding" not in str(e) or deneme == 2:
                            raise
                        print(f"   ! embedding hatası, Ollama yeniden başlatılıyor ({deneme + 1}/2)", flush=True)
                        ollama_yeniden_baslat()
            finally:
                CI.call_llm_text = gercek_ci
            ham = yakala.get("ham_model")
            k = {"varyant": varyant, "tekrar": n + 1,
                 "sinif": classify_answer({**row, "set": "test_2", "cevap": r["cevap"]}, gt),
                 "kaynaklar": r["bulunan_kaynaklar"],
                 "cevap": r["cevap"], "cevap_uzunluk": len(r["cevap"]),
                 "ham_model_cikti": ham, "ham_uzunluk": len(ham) if ham else None,
                 "ham_ile_son_ayni": ham == r["cevap"] if ham else None,
                 "kelime_sayisi": len(r["cevap"].split()),
                 "bagLamda_bozuk_sozcuk": {s: (s in r["context"].lower()) for s in BOZUK_SOZCUKLER},
                 "cevapta_bozuk_sozcuk": {s: (s in r["cevap"].lower()) for s in BOZUK_SOZCUKLER},
                 "context_uzunluk": len(r["context"])}
            kayit.append(k)
            print(f"{varyant}[{n + 1}] sinif={k['sinif']} cevap_uzunluk={k['cevap_uzunluk']} kelime={k['kelime_sayisi']} "
                  f"ham==son={k['ham_ile_son_ayni']} bozuk(cevap)={k['cevapta_bozuk_sozcuk']} bozuk(bağlam)={k['bagLamda_bozuk_sozcuk']}\n"
                  f"   kaynaklar: {k['kaynaklar'][:150]}\n   CEVAP: {r['cevap']}\n", flush=True)

    with open(HERE / "triyaj.jsonl", "w", encoding="utf-8") as f:
        for k in kayit:
            f.write(json.dumps(k, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
