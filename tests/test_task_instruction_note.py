"""
Görev/alıştırma parçası işareti (backlog madde 24).

OCR'lanan Örnek sayfaları okuyucuya görev veriyor ("…CNF'ye dönüştürünüz");
negatif sorularda model bunu "belgede anlatılan konu" gibi okuyup prosedür
uyduruyordu (#224, test_5 #103). Parçanın başına not eklenir; metin, DB ve
retrieval değişmez. Plan: docs/implementation_plan_madde24_ocr_isaret.md.

Metinler rag.db'deki gerçek OCR çıktılarıdır (aksansız olmaları OCR'dan).
"""
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT / "evaluation") not in sys.path:
    sys.path.insert(0, str(_ROOT / "evaluation"))

from llm_client import (  # noqa: E402
    task_instruction_note, task_instruction_verbs, MAX_CONTEXT_CHARS,
)
from run_tests import build_context  # noqa: E402

ORNEK = {
    22: ("4.5.2. Örnek 2\nOmek 2\nBaglamdan-bagimsiz Gs.4.2 dilbilgisi asagidaki gibi tanimlaniyor.\n"
         "Gs.4.2 = VN,VT,P, S >\nV = { S, D, E}\nVt = { a, b, c }\nP:S ==>aaSIaaD\nD==>bEbccD\n"
         "E ==> bEbI c\na) Gs.4.2 tarafindan taninan baglamdan-bagimsiz dilin (Ls.4.2) kume tanimini\n"
         "olusturunuz.\nb) Gs.42'yi Chomsky normal bicimine (CNF) donusturunuz. Donusturme\n"
         "sirasinda kullanacaginiz yeni degiskenleri A, B, C, ve X, Xz, X3, ... diye\n"
         "adlandiriniz. Olusturdugunuz CNF dilbilgisinin tanimini eksiksiz ve duzenli\n"
         "bicimde yaziniz."),
    24: ("4.5.5. Örnek 5\nOmek5\nAsagida tanimlanan baglamdan-bagimsiz dillerin her birini tureten "
         "baglamdan\nbagimsiz bir dilbilgisi tanimlayiniz.\na)L 4.5.1 = { a2k bn c2n dk1k ≥ 1 , n ≥ 1 }\n"
         "b)L 4.52 = {an+m bk cm+k d2n I n , m , k ≥ 0 }"),
    26: ("4.5.6. Örnek 6\nOmek 6\nAsagidaki baglamdan-bagimsiz her dilbilgisinin turettigi dilin kume "
         "tanimini\nveriniz.\na) Gs.4.6.1 = ≤VN,VT,P, S >\nVN = {S,A, B, C}\nVt = {a, b }\n"
         "P:S ==> aS|aA\nA==>aA|bB\nB ==>aBbC\nC ==> aC|a"),
    28: ("4.5.7. Örnek 7\nOmek7\nAsagida tanimlanan baglamdan-bagimsiz dillerin her birini tureten "
         "baglamdan\nbagimsiz bir dilbilgisi tanimlayiniz.\nm>0,k>0,n>m+k}\na) Ls.4.7.1 = { an bm ck\n"
         "b) Ls.4.7.2 = { an bm ck"),
    30: ("4.5.8. Örnek 8\nOmek8\nAsagidaki baglamdan-bagimsiz her dilbilgisinin turettigi dilin kume "
         "tanimini\nveriniz.\na) Gs.4.8.1 = <VN, Vt. P, S >\nV={S,B,C}\nV = {a, b, d }\nP:S ==>aSaaB\n"
         "B ==>bbBdd|C\nC ==> bd"),
}

CEVAP = {
    23: "4.5.2. Cevap 2\na) Ls.42 = { (aa) (cc)m b c b|  \nm20. k211\nn21,",
    25: ("4.5.5. Cevap 5\na) G 4.5.1 = < VN, VT, P, S >\nVN={S,A}\nVT = {a, b, c, d }\n"
         "P :S  aaSdIaaAd\nA=bAcc|bcc\nb) G 4.5.2 = < Vn, Vt, P, S >\nVN ={S,A,B }"),
    27: "4.5.6. Cevap 6\na) Ls.4.6.1 = { an b am b a* \nk>1}\nm>0.\nn21\nb) Ls.4.6.2 = { am+m",
    29: "4.5.7. Cevap 7\na) Gs.4.7.1 = <Vn,Vt, P S >\nVN = { S,A, B }\nVT = { a, b, c }\nP : S ==> aaAc",
    31: "4.5.8. Cevap 8\na) Ls.4.a.1 = {an b2k+1 d2k+1\na2n | n≥0,k≥0}\nb)Ls.4.8.2\nn>0,k>0}",
}

# Sayfa 2'nin başı — konu anlatımı, emir kipi yok.
ANLATIM = ("4.BAĞLAMDAN-BAĞIMSIZ DİLBİLGİSİ\n• Programlama dilleri, derleyiciler, yorumlayıcılar, "
           "sözdizim\nçözümleyiciler, aritmetik deyimler, ..vb. birçok yazılım bağlamdan bağımsız "
           "dilbilgisi ile tanımlanır.")


@pytest.mark.parametrize("sayfa", sorted(ORNEK))
def test_ornek_sayfalari_isaretlenir(sayfa):
    assert task_instruction_note(ORNEK[sayfa]) is not None


def test_sayfa_22_fiilleri_sirayla_ve_yuzey_biciminde():
    assert task_instruction_verbs(ORNEK[22]) == ["olusturunuz", "donusturunuz", "adlandiriniz", "yaziniz"]
    assert '("olusturunuz")' in task_instruction_note(ORNEK[22])


@pytest.mark.parametrize("sayfa", sorted(CEVAP))
def test_cevap_sayfalari_isaretlenmez(sayfa):
    assert task_instruction_note(CEVAP[sayfa]) is None


def test_anlatim_sayfasi_isaretlenmez():
    assert task_instruction_note(ANLATIM) is None


@pytest.mark.parametrize("metin", [
    "Dönüştürme sırasında kullanacağınız yeni değişkenleri belirtin",   # sayfa 22, cümle ortası
    "Oluşturduğunuz dilbilgisi eksiksiz olmalı.",
    "Evrakınız hazır olduğunda randevu alınabilir.",
])
def test_cumle_ortasi_iyelik_bicimi_isaretlenmez(metin):
    assert task_instruction_verbs(metin) == []


@pytest.mark.parametrize("metin,fiil", [
    ("Lütfen dilbilgisini Chomsky normal biçimine dönüştürünüz.", "dönüştürünüz"),   # aksanlı
    ("KÜME TANIMINI VERİNİZ", "VERİNİZ"),                                            # büyük harf, İ
    ("a) Ls.4.2 dilinin tanımını oluşturunuz:\nb) ...", "oluşturunuz"),
])
def test_aksanli_ve_buyuk_harfli_emir_yakalanir(metin, fiil):
    assert task_instruction_verbs(metin) == [fiil]


# --- build_context ------------------------------------------------------------

def _chunk(content, page="sayfa 2", source="data/8-Baglamdan_bagimsiz_dilbilgisi.pdf"):
    return {"source": source, "page_info": page, "content": content}


def test_isaretsiz_parcada_baglam_bayt_bayt_ayni():
    """İşaret almayan chunk'larda LLM'e giden bağlam değişiklik öncesiyle aynı."""
    chunks = [_chunk(ANLATIM), _chunk(CEVAP[25], "sayfa 25")]
    eski = "\n\n".join(f"[{i}] Kaynak: 8-Baglamdan_bagimsiz_dilbilgisi.pdf, {c['page_info']}\n{c['content']}"
                       for i, c in enumerate(chunks, 1))
    assert build_context(chunks, "soru") == eski
    assert build_context(chunks, "soru", task_notes=False) == eski


def test_not_baslik_ile_icerik_arasina_girer():
    ctx = build_context([_chunk(ORNEK[22], "sayfa 22")], "CNF adımları nelerdir?")
    header, note, first = ctx.split("\n")[:3]
    assert header == "[1] Kaynak: 8-Baglamdan_bagimsiz_dilbilgisi.pdf, sayfa 22"
    assert note == task_instruction_note(ORNEK[22])
    assert first == "4.5.2. Örnek 2"


def test_task_notes_false_kontrol_kolu_notsuz():
    ctx = build_context([_chunk(ORNEK[22], "sayfa 22")], "soru", task_notes=False)
    assert "[Not:" not in ctx


def test_not_truncate_context_sonrasi_bozulmaz():
    """Bağlam MAX_CONTEXT_CHARS'ı aşıp kesildiğinde baştaki işaretli parçanın notu tam kalır."""
    dolgu = ("profil satiri " * 120).strip()
    chunks = [_chunk(ORNEK[22], "sayfa 22")] + [_chunk(dolgu, f"sayfa {p}") for p in (2, 16, 18, 19)]
    ctx = build_context(chunks, "soru")
    assert len(ctx) <= MAX_CONTEXT_CHARS + len(" […kısaltıldı]")
    assert ctx.endswith("[…kısaltıldı]")
    assert task_instruction_note(ORNEK[22]) in ctx
