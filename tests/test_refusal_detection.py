"""
Gorev 2B regresyon testleri — check_is_not_found.

Ret ifadesinden sonra gelen icerik bir ACIKLAMA/GEREKCE ise cevap hala ret
sayilmali; YENI BIR IDDIA (soruda gecmeyen sayi/kod/ozel isim) iceriyorsa
halusinasyon sayilmali.

Neden: saf kelime-sayisi esigi, negatif set #231'de DURUST bir reddi
("Bulunamadi. Not: ... bulamadim.") halusinasyon olarak isaretliyordu.
"""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
for _p in (str(_ROOT), str(_ROOT / "evaluation")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# DIKKAT: kokte de bir benchmark_eval.py var ama o yalnizca bir yonlendirme
# katmani ve `import *` kullandigi icin alt cizgi ile baslayan yardimcilari
# (_new_claims gibi) disari vermiyor. Tam paket yolundan import etmek sart.
from evaluation.benchmark_eval import check_is_not_found, _new_claims  # noqa: E402


Q_AIRPORT = "airports.json veri setinin 2026 guncellemesinde eklenen havaalanlari hangileridir?"
Q_BALANCE = "mock-transactions veri setindeki ikinci hesabin (ACC-124) kapanis bakiyesi nedir?"
Q_STATE = "us-states veri setinde en son hangi tarihte eyalet siniri degisikligi kaydedilmistir?"


def test_gerekceli_durust_ret_TN_sayilir():
    """#231: model reddetti ve yalnizca gerekce verdi -> ret (TN)."""
    cevap = ("Bulunamadı. Not: Veri setinde 2026 güncellemesinde eklenen "
             "havaalanları bulamadım. Havaalanlarının listesi veri setinde mevcut değil.")
    assert check_is_not_found(cevap, Q_AIRPORT)


def test_ret_ardindan_yeni_sayi_FP_kalir():
    """Klasik tuzak: ret ifadesi var ama arkasindan uydurma bir sayi geliyor."""
    cevap = "Doğrudan bulunamadı, ancak muhtemelen ACC-124 hesabının bakiyesi 3.200 USD'dir."
    assert not check_is_not_found(cevap, Q_BALANCE)


def test_ret_ardindan_yeni_ozel_isim_FP_kalir():
    cevap = "Bu bilgi dokümanlarda bulunamadı, ancak Hawaii olabilir."
    assert not check_is_not_found(cevap, Q_STATE)
    assert "Hawaii" in _new_claims(cevap, Q_STATE)


def test_saf_ret_TN():
    assert check_is_not_found("Bu bilgi dokümanlarda bulunamadı.", Q_BALANCE)


def test_cumle_basi_buyuk_harf_ozel_isim_sayilmaz():
    cevap = "Bulunamadı. Not: Bu konuda net bir kayıt yok."
    assert check_is_not_found(cevap, Q_STATE)


def test_soru_yankisinin_iddia_sayilmamasi():
    """Sorudaki sayiyi (2026) tekrar etmek yeni iddia degildir."""
    assert _new_claims("Bulunamadı, 2026 güncellemesi yok.", Q_AIRPORT) == []


def test_soru_verilmezse_eski_davranis_korunur():
    """Geriye donuk uyumluluk: question=None -> eski uzunluk esigi."""
    cevap = ("Bulunamadı. Not: Veri setinde 2026 güncellemesinde eklenen "
             "havaalanları bulamadım. Havaalanlarının listesi veri setinde mevcut değil.")
    assert check_is_not_found(cevap) is False
