"""
OCR'lı devam sayfalarının birleştirilmesi (backlog madde 22).

Gramer PDF'inde "Cevap N" slaytı yalnız başlık + formül taşıyor; sorunun
kelimeleri önceki "Örnek N" slaytında. Ayrı chunk olunca Cevap sayfası bağlama
hiç gelmiyordu. Kural: OCR'lanmış sayfa, önceki sayfayla aynı bölüm
numarasını taşıyorsa ona eklenir. Plan: docs/implementation_plan_madde22_ornek_cevap.md.
"""
# Kokteki ingest.py bir yonlendirme katmani ve alt cizgili yardimcilari
# disari vermiyor; tam paket yolundan import etmek sart.
from src.ingest import _merge_continuation_pages, _section_number

# rag.db'deki gerçek OCR metinleri (kısaltılmış)
ORNEK_8 = "4.5.8. Örnek 8\nOmek8\nAsagidaki baglamdan-bagimsiz her dilbilgisinin turettigi dilin kume tanimini\nveriniz."
CEVAP_8 = "4.5.8. Cevap 8\na) Ls.4.a.1 = {an b2k+1 d2k+1\na2n | n≥0,k≥0}"
ORNEK_2 = "4.5.2. Örnek 2\nOmek 2\nBaglamdan-bagimsiz Gs.4.2 dilbilgisi asagidaki gibi tanimlaniyor."
CEVAP_2 = "4.5.2. Cevap 2\na) Ls.42 = { (aa) (cc)m b c b|"
# Sayfa 18/19: aynı bölüm numarası, ama metin katmanlı (OCR değil)
S18 = "4.3.4.1. Yararsız Değişken ve Kuralların Atılması\n• Bağlamdan-bağımsız bir dilbilgisi (G) verildiğinde"
S19 = "-4.3.4.1. Yararsız Değişken ve\nKuralların Atılması\n• İkinci adımda, algoritma 4.6 kullanılarak"


def test_bolum_numarasi():
    assert _section_number(ORNEK_8) == "4.5.8"
    assert _section_number(S19) == "4.3.4.1"          # baştaki "-" kabul
    assert _section_number("Örnek 4.7\nG4.7=<VN, VT, P, S>") is None
    assert _section_number("") is None


def test_ornek_cevap_cifti_birlesir():
    out = _merge_continuation_pages([(30, ORNEK_8, True), (31, CEVAP_8, True)])
    assert out == [(f"{ORNEK_8}\n{CEVAP_8}", "sayfa 30-31")]


def test_bes_cift_ayri_ayri_birlesir():
    pages = [(22, ORNEK_2, True), (23, CEVAP_2, True), (30, ORNEK_8, True), (31, CEVAP_8, True)]
    assert [p for _, p in _merge_continuation_pages(pages)] == ["sayfa 22-23", "sayfa 30-31"]


def test_ocr_olmayan_ayni_numarali_sayfa_birlesmez():
    out = _merge_continuation_pages([(18, S18, False), (19, S19, False)])
    assert [p for _, p in out] == ["sayfa 18", "sayfa 19"]


def test_ocr_sayfasi_onceki_metin_sayfasiyla_ayni_numaradaysa_birlesir():
    """Kural sonraki sayfanın OCR'lanmış olmasına bakar, öncekinin değil."""
    out = _merge_continuation_pages([(18, S18, False), (19, S19, True)])
    assert [p for _, p in out] == ["sayfa 18-19"]


def test_farkli_numarali_ocr_sayfasi_birlesmez():
    out = _merge_continuation_pages([(22, ORNEK_2, True), (31, CEVAP_8, True)])
    assert [p for _, p in out] == ["sayfa 22", "sayfa 31"]


def test_ardisik_olmayan_sayfa_birlesmez():
    """Aradaki sayfa boşsa (metin yok) birleştirme atlanır — zincir kopar."""
    out = _merge_continuation_pages([(30, ORNEK_8, True), (31, "", True), (32, CEVAP_8, True)])
    assert [p for _, p in out] == ["sayfa 30", "sayfa 32"]


def test_bolum_numarasi_olmayan_ocr_sayfasi_birlesmez():
    out = _merge_continuation_pages([(30, ORNEK_8, True), (31, "a) Ls = {an}", True)])
    assert [p for _, p in out] == ["sayfa 30", "sayfa 31"]


def test_uc_ardisik_sayfa_tek_chunk():
    devam = "4.5.8. Cevap 8 (devam)\nb) Ls.4.8.2"
    out = _merge_continuation_pages([(30, ORNEK_8, True), (31, CEVAP_8, True), (32, devam, True)])
    assert out == [(f"{ORNEK_8}\n{CEVAP_8}\n{devam}", "sayfa 30-32")]


def test_cok_paragrafli_onceki_sayfada_son_chunka_eklenir():
    onceki = "4.5.8. Örnek 8\nbaslik\n\nikinci paragraf"
    out = _merge_continuation_pages([(30, onceki, True), (31, CEVAP_8, True)])
    assert out == [("4.5.8. Örnek 8\nbaslik", "sayfa 30"),
                   (f"ikinci paragraf\n{CEVAP_8}", "sayfa 30-31")]


def test_birlesme_olmayan_girdide_eski_davranis():
    """Eski extract_chunks_from_pdf: sayfa "\\n\\n" ile bölünür, boşlar atlanır."""
    pages = [(1, "Baslik\n\nParagraf 1\n\n\n\nParagraf 2", False), (2, "", False),
             (3, "   ", False), (4, "Tek parca", False)]
    assert _merge_continuation_pages(pages) == [
        ("Baslik", "sayfa 1"), ("Paragraf 1", "sayfa 1"), ("Paragraf 2", "sayfa 1"),
        ("Tek parca", "sayfa 4")]
