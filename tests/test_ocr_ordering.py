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


# --- Metin katmanli iki sutun (backlog A1: #19/#20) --------------------------
# _columns_text yalniz DORT kapinin hepsi gecerse sutun boler; her kapi icin, tek
# bir seyi degistirilmis "yakin-iska" senaryosu kurulur: kapi gevsetilirse (esik
# degisikligi vb.) sonuc eski duz metinden ayrilir ve test kirilir.
from types import SimpleNamespace

import pytest
from pdfplumber.utils import cluster_objects, extract_text as duz_metin

from src.ingest import _columns_text, _find_column_split

SAYFA_GENISLIK = 720.0
BASLIK = " ".join(["baslik"] * 15)   # ~104 krk: iki sutunu da kesen tam genislikli satir


def _harfler(text, x0, top, w=6.0, size=12.0):
    out, x = [], x0
    for ch in text:
        out.append({"text": ch, "x0": x, "x1": x + w, "top": top, "bottom": top + size,
                    "doctop": top, "size": size, "upright": True})
        x += w
    return out


def _sayfa(images=()):
    return SimpleNamespace(images=list(images), width=SAYFA_GENISLIK)


def _iki_sutun(yan_yana=10, tam_genislik=1, pua=False):
    """tam_genislik baslik satiri + yan_yana satir (sol x=50, sag x=400, ayni top)."""
    chars, top = [], 0.0
    for _ in range(tam_genislik):
        chars += _harfler(BASLIK, 50, top)
        top += 20
    for i in range(yan_yana):
        sol = f"sol{i}" + ("\uf061" if pua and i == 3 else "")
        chars += _harfler(sol, 50, top) + _harfler(f"sag{i}", 400, top)
        top += 20
    return chars


def _satirlar(chars):
    return sorted(cluster_objects(chars, lambda c: c["top"], 3), key=lambda r: min(c["top"] for c in r))


def _bolme_uygulanirdi(chars):
    """Senaryonun gercekten sutun-bolme adayi oldugunu (ret sebebinin ilgili kapi oldugunu) dogrular."""
    assert _columns_text(chars, _sayfa()) != duz_metin(chars)


def test_iki_sutun_tum_kapilardan_gecer_sol_sutun_once_sag_sonra():
    chars = _iki_sutun(yan_yana=10, tam_genislik=1)   # kesen oran 1/11
    beklenen = "\n".join([BASLIK] + [f"sol{i}" for i in range(10)] + [f"sag{i}" for i in range(10)])
    assert _columns_text(chars, _sayfa()) == beklenen
    assert duz_metin(chars).splitlines()[1] == "sol0 sag0"      # eski davranis: satir satir ic ice


def test_kapi_resim_nesnesi_varsa_bolmez():
    chars = _iki_sutun()
    _bolme_uygulanirdi(chars)
    assert _columns_text(chars, _sayfa(images=[{"x0": 0}])) == duz_metin(chars)


def test_kapi_pua_karakteri_varsa_bolmez():
    temiz, pua = _iki_sutun(), _iki_sutun(pua=True)
    _bolme_uygulanirdi(temiz)
    assert _columns_text(pua, _sayfa()) == duz_metin(pua)


@pytest.mark.parametrize("yan_yana,tam_genislik", [(8, 1), (8, 2)])   # kesen oran 1/9=0.111 ve 2/10=0.20
def test_kapi_kesen_satir_orani_esigin_ustundeyse_bolmez(yan_yana, tam_genislik):
    chars = _iki_sutun(yan_yana=yan_yana, tam_genislik=tam_genislik)
    satirlar = _satirlar(chars)
    bulunan = _find_column_split(satirlar, SAYFA_GENISLIK)
    assert bulunan is not None and bulunan[1] / len(satirlar) > 0.10   # ret sebebi yalniz oran kapisi
    assert _columns_text(chars, _sayfa()) == duz_metin(chars)


def test_kapi_yetersiz_satir_bolmez():
    # (i) her sutunda yalniz 2 satir (< 3)
    az = _iki_sutun(yan_yana=2, tam_genislik=0)
    assert _find_column_split(_satirlar(az), SAYFA_GENISLIK) is None
    assert _columns_text(az, _sayfa()) == duz_metin(az)
    # (ii) 3+3 satir ama hic yan yana satir yok (sol/sag satirlari farkli top'larda, dönüşümlü)
    donusumlu = []
    for i in range(3):
        donusumlu += _harfler(f"sol{i}", 50, 40.0 * i) + _harfler(f"sag{i}", 400, 40.0 * i + 20)
    assert _find_column_split(_satirlar(donusumlu), SAYFA_GENISLIK) is None
    assert _columns_text(donusumlu, _sayfa()) == duz_metin(donusumlu)
    assert duz_metin(donusumlu).splitlines()[:2] == ["sol0", "sag0"]   # bolunseydi sol0, sol1 gelirdi
