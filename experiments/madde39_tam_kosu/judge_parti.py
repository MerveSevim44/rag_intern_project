"""
HEAD tam koşusunun (head_<set>/) LLM-judge değerlendirmesi, günlük Groq kotasına göre PARTİLER hâlinde,
gerçek token tüketimi ölçülerek. evaluation/ DEĞİŞMEZ: judge modeli çalışma zamanında bir callback ile
sarılır (llm_as_judge.load_judge_model), kaydedilen kullanım Groq yanıtındaki usage'tan gelir.

Girdi: head_<set>/sonuclari.csv, hata tekrarı varsa head_<set>/hata_tekrar.csv ile BİRLEŞTİRİLİR
(HATA satırı tekrarındaki cevapla değişir) ve head_<set>/birlesik.csv yazılır; judge onu okur.

Kullanım (kökten):
  python experiments/madde39_tam_kosu/judge_parti.py hazirla                  # birlesik.csv + sınıf özeti
  python experiments/madde39_tam_kosu/judge_parti.py liste                    # FN/FP kimlikleri
  python experiments/madde39_tam_kosu/judge_parti.py calistir ETIKET "test_2:43,53;test_3:79"
Çıktı: head_<set>/judge_<ETIKET>.csv ve judge_olcum.jsonl (parti başına gerçek token toplamları).
"""
import csv
import json
import os
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT / "evaluation"), str(ROOT / "src"), str(ROOT)]
csv.field_size_limit(10**9)
SETLER = ["test_1", "test_2", "test_3", "test_4", "test_5", "test_negative"]


def oku(yol):
    with open(yol, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def birlestir(s):
    d = HERE / f"head_{s}"
    satirlar = oku(d / "sonuclari.csv")
    tekrar = {r["id"]: r for r in oku(d / "hata_tekrar.csv")} if (d / "hata_tekrar.csv").exists() else {}
    cikti = [tekrar[r["id"]] if r["cevap"].startswith("HATA") and r["id"] in tekrar else r for r in satirlar]
    with open(d / "birlesik.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(satirlar[0]))
        w.writeheader()
        w.writerows(cikti)
    return cikti


def siniflar():
    from benchmark_eval import classify_answer
    from gt_utils import load_ground_truth
    gt = load_ground_truth()
    return {s: {r["id"]: ("HATA" if r["cevap"].startswith("HATA") else classify_answer({**r, "set": s}, gt))
                for r in birlestir(s)} for s in SETLER}


def calistir(etiket, spec):
    import llm_as_judge as J
    from langchain_core.callbacks import BaseCallbackHandler

    kullanim_log = HERE / f"judge_kullanim_{etiket}.jsonl"   # her çağrıda eklenir: süreç öldürülse bile ölçüm kalır

    def kaydet(**k):
        with open(kullanim_log, "a", encoding="utf-8") as f:
            f.write(json.dumps({"t": time.strftime("%H:%M:%S"), **k}, ensure_ascii=False) + "\n")

    class Kullanim(BaseCallbackHandler):
        def __init__(self):
            self.cagri = []

        def on_llm_error(self, error, **kw):
            # Groq 429 mesajları kuruluş kimliğini (org_...) içerir: repoya girmesin diye maskelenir.
            kaydet(hata=type(error).__name__, mesaj=re.sub(r"org_[A-Za-z0-9]+", "org_<maskeli>", str(error))[:500])

        def on_llm_end(self, response, **kw):
            u = (response.llm_output or {}).get("token_usage") or {}
            if not u:
                for g in response.generations:
                    for x in g:
                        m = getattr(getattr(x, "message", None), "usage_metadata", None) or {}
                        u = {"prompt_tokens": m.get("input_tokens"), "completion_tokens": m.get("output_tokens"),
                             "total_tokens": m.get("total_tokens")}
            self.cagri.append(u)
            kaydet(**{a: u.get(a) for a in ("prompt_tokens", "completion_tokens", "total_tokens")})

    k = Kullanim()

    # NOT (2026-11-10): "15 dk'dan uzun retry-after = günlük limit" sezgisi buradan KALDIRILDI.
    # evaluation/llm_as_judge.py._retry_after_seconds, Groq'un "420ms" gibi milisaniyelik
    # bekleme değerlerini "420m" (420 DAKİKA) olarak yanlış ayrıştırıyor (regex ([\d.]+)([hms])
    # "ms" sonekini "m" + artık "s" olarak eşliyor) — gerçek bir hata, evaluation/ bu ölçüm
    # turunda değişmiyor. Sezgi bu hatayla birleşip gerçek bir TPM (dakikalık) 429'u günlük
    # limit sanıp parti4b'de test_5'i 9 satır eksik bırakarak erken durdurdu. Artık yalnız
    # judge'ın kendi "per day (TPD|RPD)" metin eşleşmesine güveniliyor.
    orj = J.load_judge_model
    J.load_judge_model = lambda *a, **kw: orj(*a, **kw).with_config(callbacks=[k])
    J.REBUILD_CONTEXT = False
    hedefler = [(p.split(":")[0], [i for i in p.split(":")[1].split(",") if i]) for p in spec.split(";") if p]
    bas = time.time()
    for s, ids in hedefler:
        birlestir(s)
        J.run_judge_evaluation(sonuc_csv=str(HERE / f"head_{s}" / "birlesik.csv"),
                               output_csv=str(HERE / f"head_{s}" / f"judge_{etiket}.csv"),
                               ground_truth_path=None, judge_model=J.JUDGE_MODEL, only_ids=ids)
    toplam = lambda a: sum((c.get(a) or 0) for c in k.cagri)
    kayit = {"etiket": etiket, "spec": spec, "satir": sum(len(i) for _, i in hedefler), "groq_cagri": len(k.cagri),
             "prompt_tokens": toplam("prompt_tokens"), "completion_tokens": toplam("completion_tokens"),
             "total_tokens": toplam("total_tokens"), "sure_sn": round(time.time() - bas),
             "kullanim_olmayan_cagri": sum(1 for c in k.cagri if not c.get("total_tokens"))}
    with open(HERE / "judge_olcum.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(kayit, ensure_ascii=False) + "\n")
    print("\nTOKEN ÖLÇÜMÜ:", json.dumps(kayit, ensure_ascii=False))


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    mod = sys.argv[1]
    if mod == "hazirla":
        for s, d in siniflar().items():
            import collections
            print(s, dict(collections.Counter(d.values())))
    elif mod == "liste":
        for s, d in siniflar().items():
            print(s, "FN:", [i for i, c in d.items() if c == "FN"], "FP:", [i for i, c in d.items() if c == "FP"])
    elif mod == "calistir":
        calistir(sys.argv[2], sys.argv[3])


main()
