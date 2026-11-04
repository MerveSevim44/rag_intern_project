"""
Madde 14 Adım 1 — "Bulunamadı" mesajının hangi durumlarda aynı cümleye düştüğü
(ÖLÇÜM; src/ değişmez).

Dört durumun synthesizer'a giden bloğu retrieval.py'nin ürettiğiyle BİREBİR kurulur
(etiket + data_engine özeti + synthesizer_instruction), run_tests.build_context ve
llm_client.ask ile gerçek modele sorulur. Ham model çıktısı ve son (kırpma sonrası)
çıktı yan yana kaydedilir: `_trim_after_not_found` ham cümleyi değiştiriyor mu?

  D1 yok      : semantik RAG, bağlamda cevap yok -> base prompt (ask, extra_instruction=None)
  D2 filtre 0 : [KAYIT BULUNAMADI] + EMPTY_RESULT_INSTRUCTION
  D3 doğrulanamadı: [DOĞRULANAMAYAN SONUÇ] + UNVERIFIED_RESULT_INSTRUCTION
  D4 işlenemedi: [İŞLENEMEDİ] + SERVICE_FAILURE_INSTRUCTION
Soru: test_2 #43 (gerçek service_failure vakası). Her durum 2 tekrar.

Kullanım (kökten): python -u experiments/madde14_bulunamadi/olcum.py
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT / "evaluation"), str(ROOT / "src"), str(ROOT)]

SORU = ("experience.credentialSummary alanı occupation türüne göre nasıl değişmektedir; "
        "Aile Hekimliği Uzmanı ile Yetenek Yönetimi Uzmanı örnekleri üzerinden karşılaştırın.")
TEKRAR = 2


def main():
    import run_tests as T
    import llm_client as L
    import retrieval as R
    from data_engine import NO_MATCH_SUMMARY, UNVERIFIED_RESULT_SUMMARY, SERVICE_FAILURE_SUMMARY

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

    def sandbox_chunk(etiket, ozet):
        return {"id": 0, "source": "data/728_profiles.json",
                "page_info": "code_interpreter (code_interpreter_sandbox)",
                "content": f"{etiket}\n{ozet}"}

    # D1: gerçek semantik arama; bağlamda alakasız bir Fourier chunk'ı
    alakasiz = [dict(c) for c in R.retrieve("Fourier dönüşümünün temel özellikleri nelerdir")][:2]

    durumlar = [
        ("D1 yok (semantik RAG, alakasız bağlam)", alakasiz, None),
        ("D2 filtre 0 satır", [sandbox_chunk("[KAYIT BULUNAMADI]", NO_MATCH_SUMMARY)], R.EMPTY_RESULT_INSTRUCTION),
        ("D3 doğrulanamadı", [sandbox_chunk("[DOĞRULANAMAYAN SONUÇ]", UNVERIFIED_RESULT_SUMMARY)], R.UNVERIFIED_RESULT_INSTRUCTION),
        ("D4 işlenemedi (service_failure)", [sandbox_chunk("[İŞLENEMEDİ]", SERVICE_FAILURE_SUMMARY)], R.SERVICE_FAILURE_INSTRUCTION),
    ]

    L = sys.modules[T.ask.__module__]  # run_tests'in kullandığı modül nesnesi (src.llm_client / llm_client ayrı olabilir)
    llm = T.load_model()
    ham = {}
    gercek_trim = L._trim_after_not_found

    def kaydeden(a):
        ham["son"] = a
        return gercek_trim(a)

    L._trim_after_not_found = kaydeden

    kayit = []
    for ad, chunks, talimat in durumlar:
        ctx = T.build_context(chunks, SORU)
        for n in range(TEKRAR):
            ham.clear()
            son = T.ask(llm, ctx, SORU, extra_instruction=talimat)
            # extra_instruction varken ask() _trim_after_not_found'u HİÇ çağırmaz
            # (llm_client.ask sonu): ham boş kalır -> kırpma bu yolda devre dışı.
            k = {"durum": ad, "tekrar": n + 1, "kirpma_cagrildi": "son" in ham,
                 "kirpma_girdisi": ham.get("son"), "son_cikti": son,
                 "kirpma_degistirdi": ("son" in ham) and ham["son"] != son}
            kayit.append(k)
            print(f"{ad} [{n + 1}] kırpma çağrıldı: {k['kirpma_cagrildi']} | girdi: {k['kirpma_girdisi']!r}\n"
                  f"   KULLANICIYA GİDEN: {son!r}", flush=True)

    (HERE / "olcum.jsonl").write_text("\n".join(json.dumps(k, ensure_ascii=False) for k in kayit), encoding="utf-8")
    sonlar = {}
    for k in kayit:
        sonlar.setdefault(k["son_cikti"], set()).add(k["durum"].split()[0])
    print("\nKULLANICIYA GİDEN FARKLI SON CÜMLELER:")
    for s, d in sonlar.items():
        print(f"  {sorted(d)} -> {s!r}")


if __name__ == "__main__":
    main()
