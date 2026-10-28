"""
Madde 32 Adım 2 — dense güvenlik slotu (retrieval._add_dense_force).

RRF havuzu (top_k) dışında kalan dense ilk-N chunk'ları reranker havuzunun
sonuna eklenir; havuzda zaten olanlar tekrar eklenmez. Servis gerekmez.
"""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
for _p in (str(_ROOT), str(_ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import retrieval                          # noqa: E402
from retrieval import _add_dense_force    # noqa: E402


def _chunk(cid, dense_rank):
    return {"id": cid, "score_debug": {"dense_rank": dense_rank}}


# RRF sırası: 1, 2, 3, 4 ; dense sırası: 4, 3, 1, 2
CHUNKS = [_chunk(1, 3), _chunk(2, 4), _chunk(3, 2), _chunk(4, 1)]


def test_havuz_disindaki_dense_birincisi_eklenir():
    pool = CHUNKS[:2]
    assert [c["id"] for c in _add_dense_force(pool, CHUNKS, 1)] == [1, 2, 4]


def test_havuzdakiler_tekrar_eklenmez_ve_sira_dense():
    pool = CHUNKS[:2]
    assert [c["id"] for c in _add_dense_force(pool, CHUNKS, 3)] == [1, 2, 4, 3]


def test_dense_ilk_n_zaten_havuzdaysa_degisiklik_yok():
    pool = CHUNKS[2:]
    assert [c["id"] for c in _add_dense_force(pool, CHUNKS, 2)] == [3, 4]


def test_varsayilan_kapali():
    assert retrieval.DENSE_FORCE_TOP_N == 0
