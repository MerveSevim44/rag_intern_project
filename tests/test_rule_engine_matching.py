"""
Backlog madde 17 — kural motorunda (data_engine.execute_query) alt dize eşleşmeleri.

Sorun: tetikleyiciler normalize sorguda düz alt dize arıyordu ("iller" in q); bu
"dil**ler**"i, "profil**ler**"i, "alan" ise "k**alan**"ı yakalıyordu. Düzeltme: kelime BAŞI
sınırı (`_word_start`): Türkçe çekim ekleri sonda olduğu için "sektorlerindeki" ⊃ "sektor"
hâlâ uyar, kelime ortasındaki alt dize uymaz.

Not: kural motoru üretimde yalnız router'ın 3 sabit cümlesi için çalışır; bu testler
doğrudan `execute_query` davranışını kilitler (CI güveni, bkz. madde 17).
LLM'siz, deterministik.
"""
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
for _p in (str(_ROOT), str(_ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from data_engine import TabularDataEngine, _word_start  # noqa: E402


@pytest.fixture(scope="module")
def motor():
    return TabularDataEngine()


def _op(motor, q):
    r = motor.execute_query(q)
    return r["operation"] if r else None


# ─── _word_start ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("q, kalip, beklenen", [
    ("profillerin ortalama", "iller", False),      # kelime ortası
    ("turkce disinda diller", "iller", False),
    ("hangi illerde", "iller", True),              # çekimli kelime başı
    ("sektorlerindeki oran", "sektor", True),
    ("saglik disinda kalan profil", "alan", False),  # "kalan" ⊃ "alan" (kelime ortası)
    ("calisma alani", "alan", True),
    ("en cok sehir", "en cok", True),
    ("ben cok sehir", "en cok", False),            # "ben cok" ⊅ "en cok"
])
def test_word_start(q, kalip, beklenen):
    assert _word_start(q, kalip) is beklenen


# ─── 2H: şehir kuralı artık "iller" alt dizesine takılmaz ───────────────────

@pytest.mark.parametrize("q", [
    "publicContact alanı altında phoneVisible ve emailVisible değerleri örnek profillerde genellikle nasıl ayarlanmıştır?",
    "Bağlamdan bağımsız dilleri tanıyan yığın otomatı (pushdown automaton) nasıl tanır?",
    "Belirgin olmayan (ambiguous) dillerin uygulamada neden değeri olmadığı belirtilmiştir?",
])
def test_profiller_ve_diller_sehir_kuralini_tetiklemez(motor, q):
    assert _op(motor, q) is None


@pytest.mark.parametrize("q", [
    "Hangi illerde en çok profil var?",
    "Profiller arasında kaç farklı şehir var?",
    "Veri setinde en çok profile sahip ilk 3 şehir hangisidir?",
])
def test_gercek_sehir_sorulari_hala_eslesir(motor, q):
    assert _op(motor, q) == "nunique_city_topn"


# ─── 2G: yalın "dil"/"diller" ───────────────────────────────────────────────

@pytest.mark.parametrize("q", [
    "Türkçe dışında en sık geçen diller hangileridir?",
    "Profillerde en çok konuşulan dil hangisidir?",
])
def test_dil_sorulari_languages_kuralina_gider(motor, q):
    assert _op(motor, q) == "explode_languages"


def test_dilbilgisi_languages_kuralini_tetiklemez(motor):
    assert _op(motor, "Bağlamdan bağımsız dilbilgisi nedir?") is None


def test_cekimli_dil_bicimleri_bilerek_languages_kuralina_gitmez(motor):
    """"dillerin" / "dili" gibi çekimli biçimler bilerek hariç: kural motorunda veri-seti
    bağlamı kapısı yok ve gramer PDF'inde "dil" biçimsel dil demek (benchmark'ta 6 yanlış
    eşleşme çıkardı: test_1 #8/#11/#12/#25/#27, test_5 #102)."""
    assert _op(motor, "Belirgin olmayan (ambiguous) dillerin uygulamada neden değeri olmadığı belirtilmiştir?") != "explode_languages"
    assert _op(motor, "Bir dilin belirgin (unambiguous) olması ne anlama gelir?") != "explode_languages"


# ─── 2D: sektör kuralı ──────────────────────────────────────────────────────

def test_cekimli_sektor_hala_eslesir(motor):
    assert _op(motor, "Sağlık sektöründe kaç profil var?") == "filtered_count_sector"


def test_kalan_alan_sayilmaz(motor):
    """"kalan" ⊃ "alan" (kelime ortası): 'sektor/alan/kategori' sözcüğü yok -> 2D tetiklenmez."""
    assert _op(motor, "Sağlık dışında kalan profillerin sayısı kaçtır?") != "filtered_count_sector"
