"""
.txt paragraflarının MIN karakterlik chunk'lara birleştirilmesi (backlog madde 33).

test1.txt'te "Gümüş Yaprak" paragraf 1'de, "Alis" paragraf 2'de; ayrı chunk'larken
reranker ikisini eşleştiremiyordu. Eşik 500: experiments/madde33_stemmer_chunk/
sweep'i (800 ve 1200 başka cevapları sessizce bozdu).
"""
# Kokteki ingest.py bir yonlendirme katmani ve alt cizgili yardimcilari
# disari vermiyor; tam paket yolundan import etmek sart.
from src.ingest import TXT_MERGE_MIN_CHARS, _merge_txt_paragraphs, _txt_paragraphs, extract_chunks_from_txt


def _p(*lens):
    return [("x" * n, i + 1) for i, n in enumerate(lens)]


def test_paragraflar_bos_satirla_ayrilir_bos_paragraf_atlanir():
    assert _txt_paragraphs("a\n\n  \n\nb\nc\n\n") == [("a", 1), ("b\nc", 2)]


def test_min_sifir_her_paragraf_ayri():
    assert [i for _, i in _merge_txt_paragraphs(_p(10, 10), 0)] == ["paragraf 1", "paragraf 2"]


def test_esige_ulasinca_chunk_kapanir():
    out = _merge_txt_paragraphs(_p(300, 300, 600), 500)
    assert [i for _, i in out] == ["paragraf 1-2", "paragraf 3"]
    assert out[0][0] == "x" * 300 + "\n\n" + "x" * 300


def test_sondaki_kisa_artik_oncekine_eklenir():
    assert [i for _, i in _merge_txt_paragraphs(_p(600, 100), 500)] == ["paragraf 1-2"]


def test_tek_kisa_paragraf_tek_chunk():
    assert _merge_txt_paragraphs(_p(100), 500) == [("x" * 100, "paragraf 1")]


def test_varsayilan_esik_500(tmp_path):
    assert TXT_MERGE_MIN_CHARS == 500
    f = tmp_path / "a.txt"
    f.write_text("\n\n".join(["y" * 300] * 3), encoding="utf-8")
    assert [i for _, i in extract_chunks_from_txt(f)] == ["paragraf 1-3"]
    assert len(extract_chunks_from_txt(f, min_chars=0)) == 3
