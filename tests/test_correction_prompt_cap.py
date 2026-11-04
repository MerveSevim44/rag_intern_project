"""
Madde 11, secenek C: duzeltme promptu boyut tavani ve gecmis kirpma.

Olculen vaka: #53'te tek bir 2.322 krk'lik yanit duzeltme promptunu 9.351 ->
12.575 krk'a cikardi ve servis cokti. Tavan (MAX_CORRECTION_PROMPT_CHARS) gecmisi
kirpar; hata metni onceliklidir.
"""
import sys
from pathlib import Path

import pandas as pd
import pytest

_root = Path(__file__).resolve().parent.parent
for _p in (str(_root / "src"), str(_root)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    import src.code_interpreter as CI
except ImportError:
    import code_interpreter as CI

DF = pd.DataFrame({"a": [1, 2]})


def _fixed():
    """Gecmissiz promptun boyutu (temel + talimat)."""
    return len(CI.build_correction_prompt("q", DF, []))


def _with_room(monkeypatch, room):
    monkeypatch.setattr(CI, "MAX_CORRECTION_PROMPT_CHARS", _fixed() + room)


def test_butce_yeterliyse_eski_bicimle_birebir_ayni(monkeypatch):
    history = [("x = 1", "KeyError: a"), ("y = 2", "NameError: b")]
    out = CI.build_correction_prompt("q", DF, history)
    eski_blok = "\n".join(
        f"--- Deneme {i} ---\nKod:\n{c}\nHATA: {e}\n" for i, (c, e) in enumerate(history, 1)
    )
    assert eski_blok in out
    assert "kirpildi" not in out


@pytest.mark.parametrize("room", [300, 800, 2000])
def test_tavan_asilmaz_asiri_uzun_yanit(monkeypatch, room):
    """#53 benzeri: tek bir 2.3 KB'lik kod + uzun hata."""
    _with_room(monkeypatch, room)
    out = CI.build_correction_prompt("q", DF, [("c" * 2322, "ValueError: " + "e" * 700)])
    assert len(out) <= CI.MAX_CORRECTION_PROMPT_CHARS
    assert "ValueError" in out  # hata metni onceliklidir


def test_en_eski_girdi_once_duser(monkeypatch):
    _with_room(monkeypatch, 700)
    history = [("eski_kod" * 100, "EskiHata"), ("yeni_kod" * 100, "YeniHata")]
    out = CI.build_correction_prompt("q", DF, history)
    assert len(out) <= CI.MAX_CORRECTION_PROMPT_CHARS
    assert "YeniHata" in out and "EskiHata" not in out
    assert "kirpildi" in out


def test_kirpilan_kodun_basi_korunur(monkeypatch):
    _with_room(monkeypatch, 600)
    kod = "BASLANGIC" + "z" * 3000
    out = CI.build_correction_prompt("q", DF, [(kod, "Hata")])
    assert "BASLANGIC" in out and "...[kirpildi]" in out
    assert len(out) <= CI.MAX_CORRECTION_PROMPT_CHARS


def test_cok_uzun_hata_siniri(monkeypatch):
    out = CI.build_correction_prompt("q", DF, [("x", "E" * 5000)])
    assert "E" * (CI.MAX_HISTORY_ERROR_CHARS + 1) not in out


def test_kod_sigmazsa_yalniz_hata_kalir(monkeypatch):
    _with_room(monkeypatch, 150)
    out = CI.build_correction_prompt("q", DF, [("k" * 3000, "KeyError: sutun")])
    assert "KeyError: sutun" in out
    assert "kkkkk" not in out
    assert len(out) <= CI.MAX_CORRECTION_PROMPT_CHARS


def test_tavan_temel_prompttan_kucukse_cokmez(monkeypatch):
    monkeypatch.setattr(CI, "MAX_CORRECTION_PROMPT_CHARS", 10)
    out = CI.build_correction_prompt("q", DF, [("x", "Hata")])
    assert out.endswith("Kod:")
