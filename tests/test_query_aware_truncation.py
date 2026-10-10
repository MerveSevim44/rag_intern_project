"""
LLM'e giden chunk kopyasının kırpılması — soruya duyarlı ve tekrarsız.

Baştan kesme (MAX_CHUNK_CHARS=1500), 728 profilin hepsinde 1698–2250.
karakterde başlayan searchKeywords alanını hiçbir soruda modele
ulaştırmıyordu; model de "bulunamadı" diyordu.
"""
from llm_client import truncate_chunk_text, _TRUNCATION_MARKER

FILLER = [f"weeklyAvailability[{i}].start: 09:00" for i in range(60)]
PROFILE = "\n".join(
    ["profileCode: DB-1", "sector: Sağlık"]
    + FILLER
    + ["searchKeywords[0]: Adana", "searchKeywords[1]: Sağlık", "slug: x"]
)
Q = "searchKeywords’ün türetildiği alanlar"


def test_query_none_eski_davranis():
    out = truncate_chunk_text(PROFILE, max_chars=400)
    assert out == truncate_chunk_text(PROFILE, max_chars=400, query=None)
    assert "searchKeywords" not in out


def test_sinirin_altinda_dokunulmaz():
    assert truncate_chunk_text("a: 1\na: 1", max_chars=400, query=Q) == "a: 1\na: 1"


def test_sorguyla_eslesen_satir_korunur():
    out = truncate_chunk_text(PROFILE, max_chars=400, query=Q)
    assert "searchKeywords[0]: Adana" in out
    assert "searchKeywords[1]: Sağlık" in out
    assert len(out) <= 400
    assert out.endswith(_TRUNCATION_MARKER)


def test_orijinal_satir_sirasi_korunur():
    out = truncate_chunk_text(PROFILE, max_chars=400, query=Q)
    lines = out.removesuffix(_TRUNCATION_MARKER).split("\n")
    original = PROFILE.split("\n")
    assert [original.index(line) for line in lines] == sorted(original.index(line) for line in lines)
    assert lines[0] == "profileCode: DB-1"


def test_bastaki_tekrar_blogu_atilir():
    key = ["code: ATL", "name: Atlanta", "city: Atlanta"]
    text = "\n".join(key + key + ["lat: 33.64"])
    out = truncate_chunk_text(text, max_chars=len(text) - 1, query="ATL enlemi")
    assert out == "\n".join(key + ["lat: 33.64"])


def test_eslesme_yoksa_bastan_keser():
    out = truncate_chunk_text(PROFILE, max_chars=400, query="Fourier dönüşümü")
    assert out == truncate_chunk_text(PROFILE, max_chars=400)
