"""
Router regresyon testleri — görsel istek sinyali ve seçili dataset sinyali.

"Deneyim yılları histogramı" semantik RAG'e düşüp "bulunamadı" dönüyordu:
(a) "histogram/grafik" COMPLEXITY_SIGNALS'ta yoktu, (b) "deneyim" yalnızca
zayıf alias olduğu için arayüzde seçili dataset hiç sinyal sayılmıyordu.
"""
import pytest

from router import classify_query, RouteTarget
from data_engine import get_data_engine

CI = RouteTarget.CODE_INTERPRETER.value
RAG = RouteTarget.SEMANTIC_RAG.value


@pytest.fixture(scope="module")
def schemas():
    return get_data_engine().get_schemas()


@pytest.mark.parametrize("q", [
    "Profillerde deneyim yılları histogramı",
    "Profillerin sektör grafiği",
    "Profillerde şehirlere göre çubuk grafiği",
    "Veri setindeki deneyim yıllarını görselleştir",
])
def test_gorsel_istek_dataset_baglamiyla_sandboxa_gider(schemas, q):
    assert classify_query(q, df_schema=schemas)["target"] == CI


@pytest.mark.parametrize("q", [
    "Fourier dönüşümünün genlik grafiği nasıl yorumlanır?",
    "Z dönüşümünde kutup-sıfır grafiği nedir?",
])
def test_gorsel_istek_tek_basina_sandboxa_gitmez(schemas, q):
    assert classify_query(q, df_schema=schemas)["target"] == RAG


def test_secili_dataset_veri_seti_sinyalidir(schemas):
    q = "Deneyim yılları histogramı"
    assert classify_query(q, df_schema=schemas)["target"] == RAG
    r = classify_query(q, df_schema=schemas, selected_dataset="728_profiles.json")
    assert r["target"] == CI
    assert r["has_dataset_signal"]


def test_secili_dataset_tek_basina_rota_degistirmez(schemas):
    # Hesaplama sinyali yoksa seçim soruyu sandbox'a itmez.
    q = "searchKeywords’ün türetildiği alanlar"
    r = classify_query(q, df_schema=schemas, selected_dataset="728_profiles.json")
    assert r["target"] == RAG
