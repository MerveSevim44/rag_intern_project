"""
Backlog madde 14 — "Bulunamadı" mesajının durum ayrımı (LLM'siz, deterministik).

Kilitlenen davranışlar:
  1. Dört durumun kullanıcıya giden cümleleri (D1 yok / D2 filtre 0 / D3 doğrulanamadı /
     D4 işlenemedi) birbirinden farklı ve her biri skorlayıcı için geçerli bir ret.
  2. `llm_client.ask`, `extra_instruction` VARKEN `_trim_after_not_found`'u çağırmaz.
     Ayırt edici cümleler (D2-D4) yalnız bu erken dönüş sayesinde yaşıyor: kırpma
     çağrılsaydı üçü de düz NOT_FOUND_ANSWER'a çökerdi.
  3. retrieval, her durum için doğru etiketi ve talimatı seçer.
  4. D4 (servis çökmesi) ile D5 (kod 3 denemede çözülemedi) data_engine'de AYRI yola
     gider: D4 `service_failure` bloğu döner, D5 None döner (semantik RAG'e düşer).

Ölçüm kaydı: experiments/madde14_bulunamadi/ (olcum.py gerçek model, d5_gercek.py
gerçek D5 vakası).
"""
import re
import sys
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

_ROOT = Path(__file__).resolve().parent.parent
for _p in (str(_ROOT), str(_ROOT / "src"), str(_ROOT / "evaluation")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import llm_client                                          # noqa: E402
import retrieval                                           # noqa: E402
from llm_client import NOT_FOUND_ANSWER                    # noqa: E402
from benchmark_eval import check_is_not_found              # noqa: E402

TALIMATLAR = {
    "D2": retrieval.EMPTY_RESULT_INSTRUCTION,
    "D3": retrieval.UNVERIFIED_RESULT_INSTRUCTION,
    "D4": retrieval.SERVICE_FAILURE_INSTRUCTION,
}
SORU = "728_profiles.json veri setinde kaç profil business türündedir?"


def _cumle(talimat):
    """Talimatın modele söylettiği tırnaklı ret cümlesi."""
    m = re.search(r"'(Bu bilgi dokümanlarda bulunamadı[^']*)'", talimat)
    assert m, "talimatta ret cümlesi bulunamadı"
    return m.group(1)


def _sahte_llm(cevap):
    """`prompt | llm` zincirinde çalışan, sabit cevap dönen model."""
    return RunnableLambda(lambda _prompt: AIMessage(content=cevap))


# ─── 1. Dört durumun cümleleri ──────────────────────────────────────────────

def test_dort_durum_dort_farkli_cumle():
    cumleler = {"D1": NOT_FOUND_ANSWER, **{k: _cumle(v) for k, v in TALIMATLAR.items()}}
    assert len(set(cumleler.values())) == 4


def test_cumleler_ayni_ret_onekiyle_baslar():
    """Ortak ön ek bilinçli (skorlayıcının ret işaretleri): ayrım noktalı virgülden sonra."""
    for k, v in TALIMATLAR.items():
        c = _cumle(v)
        assert c.startswith("Bu bilgi dokümanlarda bulunamadı;"), k
    assert NOT_FOUND_ANSWER.startswith("Bu bilgi dokümanlarda bulunamadı")


@pytest.mark.parametrize("durum", ["D2", "D3", "D4"])
def test_cumle_skorlayicida_ret_sayilir(durum):
    """Ayırt edici cümleler benchmark_eval için hâlâ saf ret (FP'ye dönmemeli)."""
    assert check_is_not_found(_cumle(TALIMATLAR[durum]), SORU)


def test_service_failure_cumlesi_tekrar_denenebilir_ipucu_tasir():
    assert "tekrar denenebilir" in _cumle(retrieval.SERVICE_FAILURE_INSTRUCTION)


# ─── 2. ask(): extra_instruction varken kırpma çağrılmaz ────────────────────

@pytest.fixture
def kirpma_cagrilirsa_patla(monkeypatch):
    def _patla(_answer):
        raise AssertionError("_trim_after_not_found extra_instruction varken çağrıldı")
    monkeypatch.setattr(llm_client, "_trim_after_not_found", _patla)


@pytest.mark.parametrize("durum", ["D2", "D3", "D4"])
def test_ask_extra_instruction_varken_kirpma_cagirmaz(kirpma_cagrilirsa_patla, durum):
    cumle = _cumle(TALIMATLAR[durum])
    out = llm_client.ask(_sahte_llm(cumle), "baglam", SORU, extra_instruction=TALIMATLAR[durum])
    assert out == cumle


def test_ask_extra_instruction_yokken_kirpma_calisir(monkeypatch):
    cagrildi = []

    def _kaydet(answer):
        cagrildi.append(answer)
        return answer

    monkeypatch.setattr(llm_client, "_trim_after_not_found", _kaydet)
    llm_client.ask(_sahte_llm(NOT_FOUND_ANSWER), "baglam", SORU)
    assert cagrildi == [NOT_FOUND_ANSWER]


@pytest.mark.parametrize("durum", ["D2", "D3", "D4"])
def test_kirpma_ayirt_edici_cumleyi_cokertir(durum):
    """NEDEN erken dönüş şart: kırpma bu cümleleri düz NOT_FOUND_ANSWER'a çevirir.
    Kırpma ileride bu kuyrukları koruyacak şekilde değişirse bu test güncellenmeli ve
    ask()'taki erken dönüşün hâlâ gerekli olup olmadığı yeniden düşünülmeli."""
    assert llm_client._trim_after_not_found(_cumle(TALIMATLAR[durum])) == NOT_FOUND_ANSWER


# ─── 3. retrieval: durum -> etiket + talimat ────────────────────────────────

def _agg(**kw):
    taban = {"operation": "code_interpreter_sandbox", "summary": "ozet", "route": "code_interpreter",
             "source_file": "728_profiles.json", "result": 1, "empty_result": False,
             "unverified_result": False, "service_failure": False}
    taban.update(kw)
    return taban


@pytest.mark.parametrize("agg, etiket, talimat", [
    (_agg(service_failure=True, operation="service_failure", result=None),
     "[İŞLENEMEDİ]", retrieval.SERVICE_FAILURE_INSTRUCTION),
    (_agg(empty_result=True), "[KAYIT BULUNAMADI]", retrieval.EMPTY_RESULT_INSTRUCTION),
    (_agg(unverified_result=True), "[DOĞRULANAMAYAN SONUÇ]", retrieval.UNVERIFIED_RESULT_INSTRUCTION),
    (_agg(), "[KESİN HESAPLAMA SONUCU]", retrieval.COMPUTED_RESULT_INSTRUCTION),
])
def test_retrieve_durum_etiket_ve_talimat(monkeypatch, agg, etiket, talimat):
    monkeypatch.setattr(retrieval, "query_tabular_data", lambda *a, **k: agg)
    chunks = retrieval.retrieve(SORU)
    assert len(chunks) == 1
    assert chunks[0]["content"].startswith(etiket)
    assert chunks[0]["synthesizer_instruction"] == talimat


# ─── 4. D4 ile D5 ayrımı (data_engine) ──────────────────────────────────────

@pytest.fixture
def motor():
    from data_engine import get_data_engine
    return get_data_engine()


def test_d4_servis_cokmesi_service_failure_blogu_doner(monkeypatch, motor):
    import code_interpreter
    monkeypatch.setattr(code_interpreter, "code_interpreter_with_retry",
                        lambda *a, **k: {"success": False, "service_failure": True,
                                         "code": "", "attempts": 1, "error": "LLM servisi yanit veremedi"})
    r = motor.execute_smart_query(SORU, llm=object())
    assert r["operation"] == "service_failure" and r["service_failure"] is True
    assert r["summary"].startswith("Soru veri seti uzerinde HIC calistirilamadi")


def test_d5_kod_cozulemedi_none_doner_semantik_rag_e_duser(monkeypatch, motor):
    """D5: servis çökmedi, kod 3 denemede çözülemedi -> None (retrieve semantik aramaya düşer).
    Bu yolda kullanıcıya özel bir mesaj GİTMEZ; bkz. experiments/madde14_bulunamadi/d5_gercek.py."""
    import code_interpreter
    monkeypatch.setattr(code_interpreter, "code_interpreter_with_retry",
                        lambda *a, **k: {"success": False, "service_failure": False,
                                         "code": "x", "attempts": 3, "error": "3 denemede cozulemedi"})
    assert motor.execute_smart_query(SORU, llm=object()) is None


def test_code_interpreter_servis_cokmesi_service_failure_isaretler():
    import code_interpreter

    class _Cokuk:
        def invoke(self, _p):
            raise RuntimeError("500 BFCArena")

    import pandas as pd
    r = code_interpreter.code_interpreter_with_retry("soru", pd.DataFrame({"a": [1]}), _Cokuk(), max_retries=3)
    assert r["success"] is False and r["service_failure"] is True


def test_code_interpreter_kod_hatasi_service_failure_isaretlemez():
    import code_interpreter
    import pandas as pd

    class _Bozuk:
        def invoke(self, _p):
            return AIMessage(content="result = df['olmayan'].mean()")

    r = code_interpreter.code_interpreter_with_retry("soru", pd.DataFrame({"a": [1]}), _Bozuk(), max_retries=3)
    assert r["success"] is False and r["service_failure"] is False
    assert r["attempts"] == 3
