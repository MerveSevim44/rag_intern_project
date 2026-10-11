"""
Gorev 2B regresyon testleri — check_is_not_found.

Ret ifadesinden sonra gelen icerik bir ACIKLAMA/GEREKCE ise cevap hala ret
sayilmali; YENI BIR IDDIA (soruda gecmeyen sayi/kod/ozel isim) iceriyorsa
halusinasyon sayilmali.

Neden: saf kelime-sayisi esigi, negatif set #231'de DURUST bir reddi
("Bulunamadi. Not: ... bulamadim.") halusinasyon olarak isaretliyordu.
"""
import sys

import pytest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
for _p in (str(_ROOT), str(_ROOT / "evaluation")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# DIKKAT: kokte de bir benchmark_eval.py var ama o yalnizca bir yonlendirme
# katmani ve `import *` kullandigi icin alt cizgi ile baslayan yardimcilari
# (_new_claims gibi) disari vermiyor. Tam paket yolundan import etmek sart.
from evaluation.benchmark_eval import (  # noqa: E402
    check_is_not_found, _new_claims, _has_refusal_frame,
)


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


# --- Madde 25: ret cercevesi (cekimli ret bicimleri) -------------------------
# Kaynak: experiments/madde25_ret_tespiti. Metinler gercek kosu cevaplaridir.

def test_222_yarim_ret_TN_sayilir():
    """v8 negatif #222: sabit liste "bulunmadigindan"i tanimiyordu -> yapay FP."""
    soru = "Z-Dönüşümü ders notlarında 12. haftanın konu başlığı nedir?"
    cevap = "Z-Dönüşümü ders notlarında 12. haftanın konu başlığına herhangi bir bilgi bulunmadığından"
    assert check_is_not_found(cevap, soru)


@pytest.mark.parametrize("soru,cevap", [
    # v8 test_1 #12 — "yoktur" icerigin parcasi, baglam sozcugu yok
    ("Belirgin olmayan (ambiguous) dillerin uygulamada neden değeri olmadığı belirtilmiştir?",
     "Belirgin olmayan dillerin uygulamada hiçbir değeri yoktur çünkü tümceleri birden çok anlam "
     "taşıyarlarsa, bu dillerin anlamlarının belirlenmesi zorlaşır ve uygulamada kullanılması zorlaşır. "
     "Bu nedenle, kullanılan dillerin tümünün belirginlik özelliğini sağladığı varsayılacaktır."),
    # v8 test_1 #13 — "bulunmamalıdır" bir kural, ret degil
    ("Türetme ağacında bir düğümün etiketi λ ise bu düğümle ilgili hangi koşullar sağlanmalıdır?",
     "Bu düğüm bir yaprak olmalı ve bu düğümün kardeşi bulunmamalıdır. "
     "Bu durumda düğümün etiketi λ olduğu koşulu sağlar."),
    # v5 test_1 #15 — "yer almayan" tanimin parcasi
    ("Yararsız simge (useless symbol) kavramı nasıl tanımlanmıştır?",
     "Yararsız simge, bir dilbilginin uç simgelerinden biri olarak tanımlanırken, bu dilbilgisi "
     "tarafından türetilen tüm celerden hiçbirinde yer almayan simgedir. Bu, dilbilginin yapısında "
     "kullanılmayan ve herhangi bir tümcenin oluşturulmasında görünmeyen bir simge anlamına gelir."),
    # v7 test_2 #50 — "yoktur" sorunun cevabi
    ("weeklyAvailability dizisinde örnek profillerde yalnızca Pazartesi-Cuma günleri mi aktif "
     "görünmektedir, hafta sonu çalışan profil örneği var mıdır?",
     "Hayır, örnek profillerde hafta sonu çalışan profil örneği yoktur. Tüm örnek profillerde hafta "
     "sonu günde aktiflik yoktur. Cevap: Tamamıyla Pazartesi-Cuma günleri aktif görünmektedir."),
    # v8 test_4 #98 — "belirtilmediği" yorumun parcasi
    ("Anlatıcının saatin 03.13'e gelmesini fark etmesi ile önceki günlük kayıtlarında belirtilen "
     "03.14 tıkırtısı arasındaki zamansal gerilim nasıl kurgulanmıştır?",
     "Anlatıcının saatin 03.13'e gelmesini fark etmesi, 03.14'teki tıkırtının bir önceki günlük "
     "kayıtlarda belirtilmediği ve anlatıcının saatin 03.13'e geldiğinde şaşkınlık duyduğu bir durumu "
     "gösterir. Bu, 03.14 tıkırtısının bir ön sembol veya bir kod olduğunu anlatıcının aklına getirerek "
     "zamansal gerilimi artırır."),
], ids=["#12", "#13", "#15", "#50", "#98"])
def test_olumsuzluk_iceren_icerik_cevabi_ret_sayilmaz(soru, cevap):
    """Naif liste genisletme bu bes dogru cevabi FN yapiyordu."""
    assert not check_is_not_found(cevap, soru)


@pytest.mark.parametrize("cumle", [
    "Bu bilgi kaynakta bulunmaktadır.",
    "İlgili bilgi dokümanda yer almaktadır.",
    "Bu değer bağlamda belirtilmektedir.",
    "Konu metinde geçmektedir.",
])
def test_olumlu_mak_mek_bicimi_cerceveye_uymaz(cumle):
    assert not _has_refusal_frame(cumle)


def test_cerceve_bulunamadi_yakalar():
    assert _has_refusal_frame("Bu konuda dokümanda bilgi bulunamadı.")


def test_cerceve_bulunmadi_yakalar():
    assert _has_refusal_frame("Bu konuda dokümanda bilgi bulunmadı.")


def test_cerceve_baglam_sozcugu_olmadan_eslesmez():
    """Olumsuzluk yuklemi tek basina yetmez; neyin bulunmadigi soylenmeli."""
    assert not _has_refusal_frame("Bu düğümün kardeşi bulunmamalıdır.")
