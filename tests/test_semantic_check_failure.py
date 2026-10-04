"""
Validator A asamasi regresyon testleri
(docs/implementation_plan_validator_failure.md).

Semantik dogrulayicinin LLM cagrisi patladiginda sonuc eskiden "TAMAM" ile
ayni izi birakip dogrulanmis gibi donuyordu. A asamasi davranisi DEGISTIRMEZ;
yalnizca donen sonucun dogrulama durumunu (validation_status) kaydeder ve
data_engine -> retrieval chunk'ina kadar tasir.

Servis gerekmez: kod ureten ve dogrulayan LLM, prompt'a bakan sahte bir
callable ile taklit edilir.
"""
import sys
from pathlib import Path

import pandas as pd
import pytest

_ROOT = Path(__file__).resolve().parent.parent
for _p in (str(_ROOT), str(_ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import code_interpreter                                   # noqa: E402
from code_interpreter import code_interpreter_with_retry  # noqa: E402

GOOD_CODE = "result = df['experience.years'].sum()"
BAD_CODE = "result = df['olmayan_kolon'].sum()"


@pytest.fixture
def profiles():
    return pd.DataFrame({
        "sector": ["Saglik", "Egitim", "Saglik"],
        "experience.years": [5, 9, 3],
    })


def fake_llm(codes, verdict):
    """
    codes: kod uretim cagrilarinda sirayla donecek kodlar.
    verdict: dogrulayici cevabi (str) ya da firlatilacak istisna.
    """
    codes = list(codes)

    def llm(prompt):
        if "mantik denetimi" in prompt:
            if isinstance(verdict, Exception):
                raise verdict
            return verdict
        return codes.pop(0)
    return llm


def _run(llm, df, **kw):
    return code_interpreter_with_retry("Toplam deneyim yili nedir?", df, llm,
                                       max_retries=3, verbose=False, **kw)


# ─── Durumlar ───────────────────────────────────────────────────────────────

def test_dogrulayici_coktu_failed_ve_davranis_ayni(profiles, capsys):
    crashed = _run(fake_llm([GOOD_CODE], RuntimeError("Error code: 500")), profiles)
    ok = _run(fake_llm([GOOD_CODE], "TAMAM"), profiles)

    assert crashed["validation_status"] == "failed"
    assert crashed["validation_error"].startswith("RuntimeError: Error code: 500")
    # Davranis degismedi: cokme "TAMAM" ile ayni sonucu donduruyor.
    for key in ("success", "raw_result", "code", "attempts", "empty_result"):
        assert crashed[key] == ok[key]
    assert "validation_warning" not in crashed
    # Olcum satiri verbose=False iken de basilir.
    out = capsys.readouterr().out
    assert "DOGRULAYICI CALISMADI (deneme 1/3): RuntimeError" in out


def test_dogrulayici_tamam_ok(profiles):
    res = _run(fake_llm([GOOD_CODE], "TAMAM"), profiles)
    assert res["validation_status"] == "ok"
    assert res["validation_error"] is None


def test_itiraz_ve_duzeltme_tutmadi_objection(profiles):
    # 1. ve 2. deneme calisir ama itiraz alir, 3. deneme hata verir ->
    # elde kalan, itiraz edilmis ilk sonuc (fallback) doner.
    res = _run(fake_llm([GOOD_CODE, GOOD_CODE, BAD_CODE], "SORUN: filtre eksik"), profiles)
    assert res["validation_warning"] is True
    assert res["validation_status"] == "objection"
    assert res["attempts"] == 1


def test_son_deneme_dogrulanmaz_not_run(profiles):
    res = _run(fake_llm([BAD_CODE, BAD_CODE, GOOD_CODE], "TAMAM"), profiles)
    assert res["attempts"] == 3
    assert res["validation_status"] == "not_run"


def test_self_check_kapali_not_run(profiles):
    res = _run(fake_llm([GOOD_CODE], RuntimeError("cagrilmamali")), profiles,
               self_check=False)
    assert res["validation_status"] == "not_run"


# ─── Tasima: data_engine -> retrieval ───────────────────────────────────────

def test_data_engine_ve_retrieval_durumu_tasir(monkeypatch, profiles):
    import data_engine
    import router
    import retrieval

    exec_info = {"success": True, "raw_result": 17, "code": GOOD_CODE, "attempts": 1,
                 "error": None, "empty_result": False,
                 "validation_status": "failed",
                 "validation_error": "RuntimeError: Error code: 500"}
    monkeypatch.setattr(code_interpreter, "code_interpreter_with_retry",
                        lambda *a, **k: exec_info)
    monkeypatch.setattr(code_interpreter, "result_to_natural_language",
                        lambda *a, **k: "Toplam deneyim 17 yildir.")
    monkeypatch.setattr(router, "route_query", lambda *a, **k: {
        "target": router.RouteTarget.CODE_INTERPRETER.value, "reason": "test",
        "matched_schema_columns": []})

    engine = object.__new__(data_engine.TabularDataEngine)
    selection = {"selected_dataset": "x.json", "match_score": 1, "reason": "test",
                 "ambiguous": False}
    monkeypatch.setattr(engine, "get_best_dataframe",
                        lambda **k: (profiles, "x.json", selection), raising=False)
    monkeypatch.setattr(engine, "get_schemas", lambda: {}, raising=False)

    agg = engine.execute_smart_query("Toplam deneyim yili nedir?", llm=object())
    assert agg["validation_status"] == "failed"
    assert agg["validation_error"] == "RuntimeError: Error code: 500"
    assert agg["unverified_result"] is False   # B'nin isi: unverified'a baglanmadi

    # retrieval: chunk alani tasir, etiket hala KESIN.
    monkeypatch.setattr(retrieval, "query_tabular_data", lambda *a, **k: agg)
    monkeypatch.setattr(retrieval, "classify_query", lambda *a, **k: {
        "target": router.RouteTarget.CODE_INTERPRETER.value, "reason": "test",
        "has_complexity": False, "has_dataset_signal": True,
        "matched_schema_columns": [], "strong_schema_columns": []})
    chunks = retrieval.retrieve("Toplam deneyim yili nedir?", llm=object())
    assert chunks[0]["validation_status"] == "failed"
    assert chunks[0]["validation_error"] == "RuntimeError: Error code: 500"
    assert chunks[0]["content"].startswith("[KESİN HESAPLAMA SONUCU]")


# ─── run_tests: dogrulama_durumu sutunu + run sonu ozeti ───────────────────

def _sandbox_chunk(status, error=None, label="[KESİN HESAPLAMA SONUCU]"):
    return {"source": "data/728_profiles.json", "page_info": "code_interpreter (x)",
            "content": f"{label}\nToplam 17.", "operation": "code_interpreter_sandbox",
            "validation_status": status, "validation_error": error}


def test_validation_label():
    import evaluation.run_tests as rt  # kökteki run_tests.py bir wrapper; mock gerçek modüle
    assert rt.validation_label([{"source": "a.pdf", "content": "metin"}]) == ""
    assert rt.validation_label([_sandbox_chunk("ok")]) == "ok"
    assert rt.validation_label([_sandbox_chunk("not_run")]) == "not_run"
    assert rt.validation_label([_sandbox_chunk("failed", "OpenAIAPIError: Error code: 500")]) \
        == "failed (OpenAIAPIError: Error code: 500)"


def test_main_sutun_ve_ozet(monkeypatch, tmp_path, capsys):
    import csv
    import evaluation.run_tests as rt  # kökteki run_tests.py bir wrapper; mock gerçek modüle

    chunks_by_question = {
        "s1": [_sandbox_chunk("ok")],
        "s2": [_sandbox_chunk("failed", "OpenAIAPIError: Error code: 500")],
        "s3": [_sandbox_chunk("not_run")],
        "s4": [{"source": "data/x.pdf", "page_info": "sayfa 1", "content": "pdf metni"}],
    }
    monkeypatch.setattr(rt, "load_model", lambda: object())
    monkeypatch.setattr(rt, "get_top_chunks", lambda q, **k: chunks_by_question[q])
    monkeypatch.setattr(rt, "ask", lambda *a, **k: "cevap")
    monkeypatch.setattr(rt, "free_gpu_memory", lambda: None)
    monkeypatch.setattr(rt.time, "sleep", lambda s: None)

    sorular = tmp_path / "sorular.csv"
    with open(sorular, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "soru"])
        for i, q in enumerate(chunks_by_question, 41):
            w.writerow([i, q])
    cikti = tmp_path / "sonuc.csv"
    rt.main([str(sorular), str(cikti)])

    with open(cikti, encoding="utf-8") as f:
        rows = {r["id"]: r for r in csv.DictReader(f)}
    assert rows["41"]["dogrulama_durumu"] == "ok"
    assert rows["42"]["dogrulama_durumu"] == "failed (OpenAIAPIError: Error code: 500)"
    assert rows["43"]["dogrulama_durumu"] == "not_run"
    assert rows["44"]["dogrulama_durumu"] == ""   # sandbox disi satir

    out = capsys.readouterr().out
    assert "! doğrulama: failed (OpenAIAPIError: Error code: 500) — context [1] [KESİN HESAPLAMA SONUCU]" in out
    assert "! doğrulama: ok" not in out
    assert "Semantik doğrulama (3 sandbox sorusu): ok=1 objection=0 failed=1 not_run=1" in out
    assert "  failed : #42 (OpenAIAPIError)" in out
    assert "  not_run: #43" in out
