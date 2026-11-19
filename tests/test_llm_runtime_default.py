"""
LLM runtime varsayılanı (2026-11-19 provizyonel migrasyon) regresyon testleri.

Varsayılan runtime artık Ollama / qwen3-8b-pilot; Foundry/qwen2.5 yolu koddan
silinmedi, yalnız `RAG_LLM_RUNTIME=foundry` ile erişilen geri alma yolu.

Servis gerekmez: `_load_ollama_model` ve `_load_foundry_model` sahte
fonksiyonlarla değiştirilir, yalnız hangisinin çağrıldığı doğrulanır.
"""
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
for _p in (str(_ROOT), str(_ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import llm_client  # noqa: E402


@pytest.fixture
def sahte_yukleyiciler(monkeypatch):
    cagrilar = []
    monkeypatch.setattr(
        llm_client, "_load_ollama_model", lambda alias=None: cagrilar.append(("ollama", alias)) or "OLLAMA_LLM"
    )
    monkeypatch.setattr(
        llm_client,
        "_load_foundry_model",
        lambda alias=llm_client.DEFAULT_MODEL_ID, unload_previous=True: cagrilar.append(("foundry", alias))
        or "FOUNDRY_LLM",
    )
    return cagrilar


def test_varsayilan_runtime_ollama(monkeypatch):
    monkeypatch.delenv(llm_client.LLM_RUNTIME_ENV_VAR, raising=False)
    assert llm_client.DEFAULT_LLM_RUNTIME == "ollama"
    assert llm_client.get_llm_runtime() == "ollama"


def test_bos_deger_varsayilana_duser(monkeypatch):
    # Windows'ta `set RAG_LLM_RUNTIME=` degiskeni bos birakir; hata degil varsayilan olmali.
    monkeypatch.setenv(llm_client.LLM_RUNTIME_ENV_VAR, "  ")
    assert llm_client.get_llm_runtime() == "ollama"


def test_load_model_varsayilan_ollama_yolunu_kullanir(monkeypatch, sahte_yukleyiciler):
    monkeypatch.delenv(llm_client.LLM_RUNTIME_ENV_VAR, raising=False)
    assert llm_client.load_model() == "OLLAMA_LLM"
    assert sahte_yukleyiciler == [("ollama", llm_client.DEFAULT_MODEL_ID)]


def test_foundry_geri_alma_yolu_hala_erisilebilir(monkeypatch, sahte_yukleyiciler):
    monkeypatch.setenv(llm_client.LLM_RUNTIME_ENV_VAR, "foundry")
    assert llm_client.get_llm_runtime() == "foundry"
    assert llm_client.load_model() == "FOUNDRY_LLM"
    assert [c[0] for c in sahte_yukleyiciler] == ["foundry"]


def test_buyuk_kucuk_harf_ve_bosluk_duyarsiz(monkeypatch, sahte_yukleyiciler):
    monkeypatch.setenv(llm_client.LLM_RUNTIME_ENV_VAR, " Foundry ")
    assert llm_client.load_model() == "FOUNDRY_LLM"
    monkeypatch.setenv(llm_client.LLM_RUNTIME_ENV_VAR, "OLLAMA")
    assert llm_client.load_model() == "OLLAMA_LLM"


def test_gecersiz_deger_sessizce_varsayilana_dusmez(monkeypatch, sahte_yukleyiciler):
    # "ollma" gibi bir yazim hatasi yanlis modelle olcum/cevap uretmesin.
    monkeypatch.setenv(llm_client.LLM_RUNTIME_ENV_VAR, "ollma")
    with pytest.raises(ValueError, match="geçersiz"):
        llm_client.get_llm_runtime()
    with pytest.raises(ValueError, match="geçersiz"):
        llm_client.load_model()
    assert sahte_yukleyiciler == []
