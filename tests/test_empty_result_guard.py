"""
Gorev 2A regresyon testleri.

2A — Sandbox bos-sonuc korumasi: sorgu HICBIR SATIRLA eslesmediginde bunun
     "kayit bulunamadi" olarak isaretlenmesi, ama MESRU SIFIR'in (filtre satir
     buldu, deger gercekten 0) normal sonuc olarak kalmasi.

"""
import sys
from pathlib import Path

import pandas as pd
import pytest

_ROOT = Path(__file__).resolve().parent.parent
for _p in (str(_ROOT), str(_ROOT / "src"), str(_ROOT / "evaluation")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from sandbox import safe_execute                      # noqa: E402
from code_interpreter import is_no_match_result, _structurally_empty  # noqa: E402


@pytest.fixture
def transactions():
    return pd.DataFrame({
        "account_id": ["ACC-123"] * 4,
        "type": ["credit", "debit", "credit", "debit"],
        "amount": [100.0, 40.0, 60.0, 120.0],
        "currency": ["USD"] * 4,
        "date": ["2023-05-01", "2023-06-11", "2023-07-02", "2023-08-09"],
    })


@pytest.fixture
def profiles():
    return pd.DataFrame({
        "profileCode": ["P-1", "P-2"],
        "location.city": ["Ankara", "Izmir"],
        "sector": ["Saglik", "Egitim"],
        "experience.years": [5, 9],
    })


def _run(code, df):
    meta = {}
    res = safe_execute(code, df, info=meta)
    return res, is_no_match_result(res, meta.get("empty_filter", False))


# ─── 2A: (a) filtre 0 satir dondurdu -> "bulunamadi" ────────────────────────

def test_bos_filtre_ortalama_nan(profiles):
    """Olmayan sektor -> mean() NaN doner; bu 'deger sifir' degil, 'satir yok'."""
    _, empty = _run("result = df[df['sector'] == 'Havacilik']['experience.years'].mean()", profiles)
    assert empty


def test_bos_filtre_sayim_sifir(profiles):
    """#212: olmayan sehir icin shape[0] == 0. Ciplak 0, ama filtre bos."""
    res, empty = _run("result = df[(df['location.city'] == 'Erzurum')].shape[0]", profiles)
    assert res == 0 and empty


def test_bos_filtre_dict_icinde_sifir(transactions):
    """#218: olmayan hesap -> {'closing_balance': 0.0, 'currency': array([])}."""
    _, empty = _run(
        "f = df[df['account_id']=='ACC-124']\n"
        "c = f[f['type']=='credit']; d = f[f['type']=='debit']\n"
        "result = {'bakiye': c['amount'].sum()-d['amount'].sum(), 'cur': c['currency'].unique()}",
        transactions)
    assert empty


def test_bos_filtre_dict_icinde_gecerli_metinle(transactions):
    """#225: {'total': 0.0, 'currency': 'USD'} — yapisal olarak bos DEGIL,
    yalnizca maske takibi yakalayabilir."""
    _, empty = _run(
        "feb = df[df['date'].str.startswith('2024-02')]\n"
        "result = {'total': feb['amount'].sum(), 'currency': df['currency'].unique()[0]}",
        transactions)
    assert empty


def test_bos_filtre_bos_dataframe(transactions):
    """#231: dogrudan bos DataFrame."""
    _, empty = _run("result = df[df['account_id'].str.startswith('NEW_')]", transactions)
    assert empty


def test_bos_filtre_query_ile(transactions):
    """df.query() yolu da takip edilir."""
    _, empty = _run("result = df.query(\"account_id == 'ACC-999'\")['amount'].sum()", transactions)
    assert empty


# ─── 2A: (b) filtre eslesti, deger gercekten 0 -> NORMAL sonuc ──────────────

def test_mesru_sifir_bozulmaz(transactions):
    """Hesap VAR, net bakiyesi gercekten 0 -> 'bulunamadi' DEMEMELI."""
    res, empty = _run(
        "f = df[df['account_id']=='ACC-123']\n"
        "c = f[f['type']=='credit']; d = f[f['type']=='debit']\n"
        "result = c['amount'].sum()-d['amount'].sum()",
        transactions)
    assert res == 0.0 and not empty


def test_mesru_sayim_bozulmaz(profiles):
    res, empty = _run("result = df[df['location.city']=='Ankara'].shape[0]", profiles)
    assert res == 1 and not empty


def test_filtresiz_normal_sonuc(profiles):
    _, empty = _run("result = df['experience.years'].mean()", profiles)
    assert not empty


def test_yanlis_sutun_kapsam_disi(transactions):
    """#232 sinifi: filtre eslesiyor ama yanlis sutun okunuyor. Bu görevin
    kapsami DISINDA — 'bulunamadi' olarak isaretlenmemeli."""
    res, empty = _run("result = df[df['amount'].notna()]['account_id'].max()", transactions)
    assert res == "ACC-123" and not empty


def test_takip_sinifi_disari_sizmaz(transactions):
    """Sandbox'tan duz pandas nesnesi cikmali (repr prompt'a gidiyor)."""
    res, _ = _run("result = df[df['account_id']=='ACC-123']", transactions)
    assert type(res) is pd.DataFrame


def test_structurally_empty_skaler_sifiri_bos_saymaz():
    assert not _structurally_empty(0)
    assert not _structurally_empty(0.0)
    assert not _structurally_empty(False)
    assert _structurally_empty(None)
    assert _structurally_empty(float("nan"))
    assert _structurally_empty(pd.DataFrame())
    assert _structurally_empty([])
