"""
OCR kutu sıralaması — iki sütunlu slaytlarda a) ve b) şıkları karışmasın.

RapidOCR kutuları yukarıdan aşağıya sıralıyor; yan yana duran iki dilbilgisinin
kuralları satır satır iç içe geçiyordu (Örnek 8, sayfa 30).
"""
# Kokteki ingest.py bir yonlendirme katmani ve alt cizgili yardimcilari
# disari vermiyor; tam paket yolundan import etmek sart.
from src.ingest import _order_ocr_lines


def box(x0, y0, x1, text):
    return ([[x0, y0], [x1, y0], [x1, y0 + 10], [x0, y0 + 10]], text, 0.9)


def test_iki_sutun_ayrilir_tam_genislik_baslik_basta_kalir():
    result = [
        box(10, 0, 980, "Asagidaki dilbilgisinin dilini veriniz."),
        box(10, 20, 300, "a) G1"), box(600, 20, 900, "b) G2"),
        box(10, 40, 300, "S ==> aS"), box(600, 40, 900, "S ==> bS"),
        box(10, 60, 300, "B ==> b"), box(600, 60, 900, "A ==> a"),
    ]
    assert _order_ocr_lines(result, 1000) == [
        "Asagidaki dilbilgisinin dilini veriniz.",
        "a) G1", "S ==> aS", "B ==> b",
        "b) G2", "S ==> bS", "A ==> a",
    ]


def test_tek_sutunda_yukaridan_asagiya():
    result = [box(10, 40, 500, "ikinci"), box(10, 0, 500, "birinci"), box(10, 80, 500, "ucuncu")]
    assert _order_ocr_lines(result, 1000) == ["birinci", "ikinci", "ucuncu"]


def test_bos_sonuc():
    assert _order_ocr_lines([], 1000) == []
