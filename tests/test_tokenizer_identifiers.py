"""
BM25 tokenizer regresyon testleri — noktalı tanımlayıcılar.

"G4.1" \\w+ ile "g4" + "1" diye bölünüyordu; "g4" tüm örneklerde (G4.2, G4.3,
G4.4, G4.7) geçtiği için "G4.1 ... VT" sorusunda Örnek 4.1 chunk'ı hibrit
sıralamada 8. sıraya düşüp top_k=5'te adaylara hiç girmiyordu.
"""
from retrieval import _tokenize


def test_noktali_tanimlayici_butun_token_uretir():
    tokens = _tokenize("G4.1 dilbilgisinde VT kümesinin elemanları nelerdir?")
    assert "g4.1" in tokens


def test_parcalar_korunur():
    tokens = _tokenize("G4.1=<VN, VT, P, S>")
    assert {"g4", "1", "g4.1"} <= set(tokens)


def test_cok_seviyeli_tanimlayici():
    assert "g4.7.2" in _tokenize("Örnek G4.7.2 dilbilgisi")


def test_farkli_tanimlayicilar_ayrisir():
    assert "g4.2" not in _tokenize("G4.1 dilbilgisi")


def test_saf_ondalik_sayi_butun_token_uretmez():
    # Tablo/finans verisinin BM25 dağılımı değişmesin.
    tokens = _tokenize("Bakiye 3.200 USD")
    assert "3.200" not in tokens
    assert {"3", "200"} <= set(tokens)
