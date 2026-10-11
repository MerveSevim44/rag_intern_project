"""
BM25 tokenizer regresyon testleri — stem/stopword çakışması (backlog madde 19).

Stopword filtresi stem'e uygulanınca stem'i tesadüfen bir stopword stem'ine
denk gelen gerçek kelimeler siliniyordu ("deneyim" -> "de", "Damla" -> "da").
"Damla Akın" BM25'e yalnızca "ak" olarak gidiyor, aynı soyadlı 10 kişi eşit
sayılıyor ve hedef hibrit sıralamada 3.–6. sıraya düşüyordu.
"""
import pytest

from retrieval import _tokenize


@pytest.mark.parametrize("word", ["deneyim", "damla", "deniz", "iş", "ön", "data"])
def test_cakisan_icerik_kelimesi_dusmez(word):
    assert _tokenize(word), f"{word!r} BM25'ten düşmemeli"


def test_isim_sorgusu_ilk_adi_tasir():
    assert "damla" in _tokenize("Damla Akın hangi şehirde hizmet veriyor?")


@pytest.mark.parametrize("a,b", [("deniz", "deneyim"), ("damla", "data")])
def test_cakisma_korumasi_kelimeleri_ayri_tutar(a, b):
    # Yalnız yüzey filtresi olsaydı ikisi de aynı stem'e ("de" / "da") düşerdi.
    assert _tokenize(a) != _tokenize(b)


@pytest.mark.parametrize("word", ["ve", "bu", "için", "de", "da", "ne", "nedir",
                                  "nelerdir", "mıdır", "içindeki"])
def test_gercek_stopword_ve_soru_eki_duser(word):
    assert _tokenize(word) == []


def test_es_anlamli_genislemesi_hizayi_bozmaz():
    # "kbb" üç token'a genişler; sonraki kelimenin çakışma koruması yine doğru çalışmalı.
    assert _tokenize("KBB muayenesi ve deneyim")[-1] == "deneyim"


def test_noktali_tanimlayici_korunur():
    assert "g4.1" in _tokenize("G4.1 dilbilgisinde VT kümesinin elemanları nelerdir?")
