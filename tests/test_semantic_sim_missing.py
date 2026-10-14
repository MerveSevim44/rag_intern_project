"""
Madde 27 regresyon testleri (docs/implementation_plan_madde27_semantic_sim.md).

`compute_semantic_similarity` artik `float | None` donuyor: hesaplanamayan
skor (servis yok, istisna, sifir norm, hicbir referansin gecerli embedding'i
yok) artik 0.0 degil None. 0.0 yalniz gercek bir sonuc oldugunda kalir: bos
cevap ya da negatif kosinus. Ayrica skorlayicinin embedding cagrisi artik
`num_gpu=0` ile CPU'ya sabitleniyor (P) — bu test dosyasinda `_embed_text`
sahte bir fonksiyonla degistirildigi icin P'nin kendisi `ollama.embeddings`
cagrisini yakalayan ayri bir testte dogrulaniyor.

Servis gerekmez: `_embed_text` ve `_semantic_backend_ready` monkeypatch ile
taklit edilir.
"""
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
for _p in (str(_ROOT), str(_ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from evaluation.benchmark_eval import (  # noqa: E402
    compute_semantic_similarity, _mean_present, _round_or_none,
)
import evaluation.benchmark_eval as be  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_semantic_state(monkeypatch):
    """Her testten once/sonra modul-seviyesi cache ve hazirlik bayragini temizler."""
    monkeypatch.setattr(be, "_EMBED_CACHE", {})
    monkeypatch.setattr(be, "_SEMANTIC_AVAILABLE", True)


def _fake_embed(vectors: dict, errors: set = frozenset()):
    """
    `_embed_text`'in yerine gecen sahte fonksiyon.
    vectors: {metin: vektor} — bilinen metinler icin donecek vektor.
    errors: bu metinler icin RuntimeError firlatilir.
    """
    def fn(text):
        key = text.strip()
        if key in errors:
            raise RuntimeError(f"sahte embedding hatasi: {key}")
        return vectors[key]
    return fn


# ─── M: None donen durumlar ─────────────────────────────────────────────────

def test_servis_yok_none(monkeypatch):
    monkeypatch.setattr(be, "_semantic_backend_ready", lambda: False)
    assert compute_semantic_similarity("cevap", ["referans"]) is None


def test_cevap_embedding_istisna_none(monkeypatch, capsys):
    monkeypatch.setattr(be, "_embed_text", _fake_embed({}, errors={"cevap"}))
    assert compute_semantic_similarity("cevap", ["referans"]) is None
    assert "Semantik benzerlik hesaplanamadi (cevap embedding'i)" in capsys.readouterr().out


def test_cevap_sifir_norm_none(monkeypatch):
    monkeypatch.setattr(be, "_embed_text", _fake_embed({"cevap": [0.0, 0.0, 0.0]}))
    assert compute_semantic_similarity("cevap", ["referans"]) is None


def test_tum_referanslar_hata_none(monkeypatch, capsys):
    """Cevabin embedding'i var ama HICBIR referansinki yoksa (hepsi hata) -> None."""
    monkeypatch.setattr(be, "_embed_text", _fake_embed(
        {"cevap": [1.0, 0.0]}, errors={"ref1", "ref2"}))
    assert compute_semantic_similarity("cevap", ["ref1", "ref2"]) is None
    out = capsys.readouterr().out
    assert out.count("Referans embedding'i atlandi") == 2


# ─── M: hala 0.0 donen gercek sonuclar (None DEGIL) ────────────────────────

def test_bos_cevap_sifir_degil_none(monkeypatch):
    assert compute_semantic_similarity("", ["referans"]) == 0.0
    assert compute_semantic_similarity("   ", ["referans"]) == 0.0


def test_negatif_kosinus_sifira_kirpilir_none_degil(monkeypatch):
    # cevap ve referans tam ters yonde -> kosinus -1.0, sonuc 0.0 (None degil).
    monkeypatch.setattr(be, "_embed_text", _fake_embed({
        "cevap": [1.0, 0.0],
        "referans": [-1.0, 0.0],
    }))
    score = compute_semantic_similarity("cevap", ["referans"])
    assert score == 0.0
    assert score is not None


# ─── M: referans bazinda hata — veri kurtarma duzeltmesi ───────────────────

def test_tek_referans_hata_digeri_gecerli_skor_kurtarilir(monkeypatch, capsys):
    """
    #36 senaryosu: iki referanstan biri (ref_hatali) embedding'de istisna
    veriyor, digeri (ref_gecerli) cevaba tam ayni yonde ve gecerli.

    ESKI DAVRANIS (madde 27 oncesi, bkz. git de2694f^..de2694f ya da bu
    dosyadan ONCEKI `compute_semantic_similarity`): referanslar uzerinde tek
    bir try/except DONGUYU SARIYORDU. Herhangi bir referansin embedding'i
    istisna firlattiginda tum fonksiyon `except Exception` dalina duserdi ve
    ONCEKI iyi skor (ref_gecerli'den gelen 1.0) ATILIP 0.0 donuyordu — v7
    test_2 #36'da gorulen, iyi bir cevabin (86.7) 0.0'a dusmesiyle ayni kalip.

    YENI DAVRANIS (bu commit): try/except artik REFERANS BASINA. ref_hatali
    tek basina atlanir, ref_gecerli ile bulunan skor (1.0) kullanilir. Yani
    "ikisi de atiliyor" -> "gecerli olan kullaniliyor".
    """
    vectors = {"cevap": [1.0, 0.0], "ref_gecerli": [1.0, 0.0]}
    embed = _fake_embed(vectors, errors={"ref_hatali"})
    monkeypatch.setattr(be, "_embed_text", embed)

    yeni_skor = compute_semantic_similarity("cevap", ["ref_hatali", "ref_gecerli"])
    assert yeni_skor == pytest.approx(1.0)

    # Eski davranisin tam olarak ne dondurdugunu burada, bagimsiz ve minimal
    # bir simulasyonla gosteriyoruz: tek try/except butun referans dongusunu
    # sariyordu, bu yuzden ilk hata (ref_hatali) butun hesaplamayi 0.0'a dusurur.
    def eski_compute_semantic_similarity(prediction, ground_truths):
        import numpy as _np
        try:
            pv = _np.array(embed(prediction), dtype=_np.float32)
            pn = _np.linalg.norm(pv)
            if pn == 0:
                return 0.0
            best = 0.0
            for gt in ground_truths:
                gv = _np.array(embed(gt), dtype=_np.float32)  # ref_hatali -> raise
                gn = _np.linalg.norm(gv)
                if gn == 0:
                    continue
                best = max(best, float(_np.dot(pv, gv) / (pn * gn)))
            return max(0.0, min(1.0, best))
        except Exception:
            return 0.0

    eski_skor = eski_compute_semantic_similarity("cevap", ["ref_hatali", "ref_gecerli"])
    assert eski_skor == 0.0
    assert yeni_skor != eski_skor
    capsys.readouterr()  # uyari ciktilarini yut, baska teste sizmasin


# ─── P: embedding cagrisina num_gpu=0 geciyor mu ───────────────────────────

def test_embed_text_num_gpu_sifir_geciyor(monkeypatch):
    calls = []

    class _FakeOllama:
        @staticmethod
        def embeddings(model, prompt, keep_alive, options):
            calls.append({"model": model, "prompt": prompt,
                          "keep_alive": keep_alive, "options": options})
            return {"embedding": [1.0, 0.0, 0.0]}

    monkeypatch.setitem(sys.modules, "ollama", _FakeOllama)
    vec = be._embed_text("skorlanacak metin")

    assert vec == [1.0, 0.0, 0.0]
    assert len(calls) == 1
    assert calls[0]["options"] == {"num_gpu": be.SEMANTIC_NUM_GPU}
    assert be.SEMANTIC_NUM_GPU == 0


# ─── Ortalamalar: None'lari paydadan cikarma ───────────────────────────────

def test_mean_present_nonelari_atlar_ve_sayar():
    assert _mean_present([80.0, None, 60.0, None]) == pytest.approx(70.0)


def test_mean_present_hepsi_none_ise_none():
    assert _mean_present([None, None]) is None


def test_round_or_none():
    assert _round_or_none(None) is None
    assert _round_or_none(1.23456, nd=2) == 1.23
