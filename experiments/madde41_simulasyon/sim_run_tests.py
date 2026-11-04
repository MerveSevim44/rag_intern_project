"""
Madde 41 ön şart ölçümü — run_tests.py'yi D5 davranış değişikliği SİMÜLE EDİLMİŞ olarak çalıştırır.
src/ ve evaluation/ DEĞİŞMEZ; yalnız bellekte monkeypatch.

Simüle edilen değişiklik: sandbox kodu 3 denemede çözemezse (servis çökmesi DEĞİL) semantik
RAG'e düşmek yerine D4-benzeri bir "hesaplanamadı" bloğu dönsün. Uygulama: code_interpreter_with_retry
sonucu `service_failure=True` ile işaretlenir (data_engine bunu zaten [İŞLENEMEDİ] bloğuna çevirir),
`operation` ise "sandbox_unsolved" yapılır ki run_tests bunu HATA'ya çevirmesin (gerçek D4 hâlâ HATA).
Cümle: mevcut SERVICE_FAILURE_INSTRUCTION ("…soru şu an işlenemedi, tekrar denenebilir.") — sınıflama
(ret mi değil mi) açısından aynı; asıl metin ayrı karar.

D5 olayları SIM_LOG (jsonl) dosyasına yazılır.
Kullanım: python sim_run_tests.py SORULAR.csv CIKTI.csv
"""
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT / "evaluation"), str(ROOT / "src"), str(ROOT)]

SIM_OZET = ("Soru veri seti uzerinde HESAPLANAMADI: uretilen kod 3 denemede cozulemedi. Bu bir 'veri yok' "
            "bildirimi DEGILDIR; sorulan bilgi veri setinde mevcut olabilir ama hesaplama yapilamadi.")


def kur():
    import code_interpreter as CI
    import importlib
    # retrieval `src.data_engine`'i kullanıyor, üst düzey `data_engine` ayrı bir modül nesnesi:
    # yama ikisinin sınıfına da uygulanır (ilk denemede yalnız üst düzeye uygulanıp etkisiz kaldı).
    DEs = [importlib.import_module(n) for n in ("data_engine", "src.data_engine")]

    log_yolu = os.environ.get("SIM_LOG")
    durum = {"d5": False}
    orijinal_ci = CI.code_interpreter_with_retry

    def ci(question, *a, **k):
        r = orijinal_ci(question, *a, **k)
        if not r.get("success") and not r.get("service_failure"):
            durum["d5"] = True
            if log_yolu:
                with open(log_yolu, "a", encoding="utf-8") as f:
                    f.write(json.dumps({"soru": question, "denemeler": r.get("attempts"),
                                        "hata": str(r.get("error"))[:200]}, ensure_ascii=False) + "\n")
            r = {**r, "service_failure": True}
        return r

    CI.code_interpreter_with_retry = ci

    for DE in DEs:
        orijinal_eq = DE.TabularDataEngine.execute_smart_query

        def eq(self, *a, _orj=orijinal_eq, **k):
            durum["d5"] = False
            res = _orj(self, *a, **k)
            if res and res.get("operation") == "service_failure" and durum["d5"]:
                res = {**res, "operation": "sandbox_unsolved", "summary": SIM_OZET}
            return res

        DE.TabularDataEngine.execute_smart_query = eq


if __name__ == "__main__":
    kur()
    import run_tests
    run_tests.main(sys.argv[1:])
