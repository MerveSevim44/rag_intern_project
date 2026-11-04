"""
test_visualization.py — Görselleştirme ve Grafik Motoru Doğrulama Testleri

Bu test dosyası:
1. Farklı veri yapılarından (dict, Series, DataFrame, list, metin) chart_data çıkarımını test eder.
2. Plotly ve Altair grafik üretimlerinin hatasız çalıştığını ve şemaya uygun figürler ürettiğini doğrular.
3. data_engine'den gelen gerçek analitik sorgu sonuçlarının (sektör dağılımı, şehir yoğunlukları, dil istatistikleri)
   otomatik olarak görselleştirilebilir grafik modellerine dönüştüğünü test eder.
"""

import sys
from pathlib import Path

# Add src and root to sys.path for direct script runs
_root = Path(__file__).resolve().parent.parent
_src = _root / "src"
for _p in [str(_src), str(_root)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pandas as pd
import numpy as np

# Encoding ayarı
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass

try:
    from src.visualizer import (
        extract_chart_data,
        create_plotly_figure,
        create_altair_chart
    )
    from src.data_engine import TabularDataEngine
except ImportError:
    from visualizer import (
        extract_chart_data,
        create_plotly_figure,
        create_altair_chart
    )
    from data_engine import TabularDataEngine


def test_dict_extraction():
    print("\n--- Test 1: Dict Veri Çıkarımı ---")
    data = {"İstanbul": 250, "Ankara": 120, "İzmir": 95, "Bursa": 60, "Antalya": 45}
    chart_data = extract_chart_data(data, query="En çok profile sahip ilk 5 şehir hangisidir?")
    assert chart_data is not None, "Dict verisinden chart_data çıkarılamadı!"
    assert len(chart_data["df"]) == 5, f"Beklenen satır: 5, Alınan: {len(chart_data['df'])}"
    assert chart_data["kpis"]["total"] == 570
    assert chart_data["kpis"]["max_category"] == "İstanbul"
    assert chart_data["kpis"]["max_value"] == 250
    print("  [OK] Dict verisi başarıyla dönüştürüldü:", chart_data["title"])


def test_nested_dict_extraction():
    print("\n--- Test 2: İç İçe (Nested) Dict Çıkarımı ---")
    data = {
        "unique_count": 42,
        "top_cities": {"İstanbul": 180, "Ankara": 90, "İzmir": 70}
    }
    chart_data = extract_chart_data(data, query="Şehir dağılımı")
    assert chart_data is not None, "Nested dict verisinden chart_data çıkarılamadı!"
    assert len(chart_data["df"]) == 3
    assert chart_data["kpis"]["max_category"] == "İstanbul"
    print("  [OK] Nested dict (top_cities) başarıyla yakalandı:", chart_data["categories"])


def test_series_extraction():
    print("\n--- Test 3: Pandas Series Çıkarımı ---")
    s = pd.Series({"individual": 520, "business": 208}, name="profileType")
    chart_data = extract_chart_data(s, query="profileType dağılımı nedir?")
    assert chart_data is not None, "Series verisinden chart_data çıkarılamadı!"
    assert chart_data["kpis"]["total"] == 728
    assert chart_data["default_chart_type"] == "donut"
    print("  [OK] Series başarıyla donut grafik tipine dönüştü:", chart_data["kpis"])


def test_dataframe_extraction():
    print("\n--- Test 4: Pandas DataFrame Çıkarımı ---")
    df = pd.DataFrame({
        "sector": ["Sağlık", "Hukuk ve Danışmanlık", "Eğitim", "Bilişim", "Finans"],
        "count": [40, 40, 32, 32, 32]
    })
    chart_data = extract_chart_data(df, query="Sektör dağılımı ve karşılaştırması")
    assert chart_data is not None, "DataFrame verisinden chart_data çıkarılamadı!"
    assert len(chart_data["df"]) == 5
    assert chart_data["unit"] == "Profil"
    print("  [OK] DataFrame başarıyla grafik tablosuna dönüştü.")


def test_text_summary_fallback():
    print("\n--- Test 5: Metin Özetinden Regex ile Çıkarım (Fallback) ---")
    summary = "Dil dağılımı: Türkçe: 728 profil; İngilizce: 210 profil; Almanca: 45 profil; Fransızca: 18 profil."
    chart_data = extract_chart_data(None, query="Hangi diller konuşuluyor?", summary=summary)
    assert chart_data is not None, "Metin özetinden regex ile dağılım çıkarılamadı!"
    assert len(chart_data["df"]) >= 3
    assert chart_data["kpis"]["max_category"] == "Türkçe"
    print("  [OK] Metin özetinden çıkarılan kategoriler:", chart_data["categories"])


def test_plotly_figure_generation():
    print("\n--- Test 6: Plotly Figür Üretimi ---")
    data = {"Psikoloji": 54.2, "Ağız ve Diş Sağlığı": 31.8}
    chart_data = extract_chart_data(data, query="Hizmet süresi 45 dk üzeri seans yüzdeleri")
    assert chart_data is not None
    assert chart_data["unit"] == "%"

    # Bar
    fig_bar = create_plotly_figure(chart_data, chart_type="bar")
    assert fig_bar is not None
    assert len(fig_bar.data) == 1

    # Donut
    fig_donut = create_plotly_figure(chart_data, chart_type="donut")
    assert fig_donut is not None
    assert len(fig_donut.data) == 1

    # Horizontal Bar
    fig_hbar = create_plotly_figure(chart_data, chart_type="horizontal_bar")
    assert fig_hbar is not None
    assert len(fig_hbar.data) == 1

    print("  [OK] Plotly Bar, Donut ve Horizontal Bar figürleri hatasız oluşturuldu.")


def test_altair_chart_generation():
    print("\n--- Test 7: Altair Grafik Üretimi ---")
    data = {"İstanbul": 250, "Ankara": 120, "İzmir": 95}
    chart_data = extract_chart_data(data, query="Şehir yoğunlukları")
    assert chart_data is not None

    chart_bar = create_altair_chart(chart_data, chart_type="bar")
    assert chart_bar is not None

    chart_donut = create_altair_chart(chart_data, chart_type="donut")
    assert chart_donut is not None
    print("  [OK] Altair Bar ve Donut grafikleri hatasız oluşturuldu.")


def test_sector_comparison_chart_from_fixed_dict():
    """Sektör karşılaştırma sorgusunun grafiği (backlog madde 17).

    "Psikoloji ... ve Ağız ve Diş Sağlığı ... 45 dk üzeri seans oranları karşılaştırması"
    sorusunu karşılayan kural motoru kuralı (1B) 3f89ad9'da (2026-09-11) bilerek
    silindi: karmaşık/çok koşullu sorgular artık execute_query() kapsamında değil,
    code_interpreter kademesine gider. Bu yüzden grafik hattı, sandbox'ın dönebileceği
    sabit bir sonuçla test edilir (LLM'siz). Değerler data/728_profiles.json'dan
    hesaplandı: durationMinutes >= 45 olan hizmetlerin yüzdesi (Psikoloji 85/85,
    Ağız ve Diş Sağlığı 44/79).
    """
    print("\n--- Test 9: Sektör Karşılaştırma Grafiği (sabit sandbox sonucu) ---")
    q = "Psikoloji ve Danışmanlık ve Ağız ve Diş Sağlığı sektörlerindeki 45 dk üzeri seans oranları karşılaştırması"
    data = {"Psikoloji ve Danışmanlık": 100.0, "Ağız ve Diş Sağlığı": 55.7}
    chart_data = extract_chart_data(data, query=q)
    assert chart_data is not None, "Sektör karşılaştırması için chart_data üretilemedi"
    assert len(chart_data["df"]) == 2
    assert chart_data["kpis"]["max_category"] == "Psikoloji ve Danışmanlık"
    fig = create_plotly_figure(chart_data, chart_type=chart_data.get("default_chart_type", "bar"))
    assert fig is not None
    print(f"  [OK] Grafik: '{chart_data['title']}' ({len(chart_data['df'])} kategori)")


def test_data_engine_end_to_end_visualization():
    """Kural motoru (execute_query) -> görselleştirici. Kural motoru yalnız tekil/basit
    sorguları karşılar; her sorgu için BEKLENEN kuralın (operation) çalıştığı da
    doğrulanır (eskiden yalnız yazdırılıyordu, bu yüzden yanlış kural fark edilmedi).

    Dışarıda bırakılanlar:
    - "45 dk üzeri seans oranları" sorgusu: 1B kuralı silindi, bkz.
      test_sector_comparison_chart_from_fixed_dict.
    - "Türkçe dışında en sık geçen diller" sorgusu eskiden yanlış kurala (şehir) düşüyordu
      ("diller" ⊃ "iller", alt dize eşleşmesi) ama test geçiyordu; kelime-başı sınırıyla
      düzeltildi ve geri eklendi (backlog madde 17, tests/test_rule_engine_matching.py).
    """
    print("\n--- Test 8: Data Engine -> Visualizer Uçtan Uca Entegrasyon Testi ---")
    engine = TabularDataEngine()

    queries = [
        ("Veri setinde en çok profile sahip ilk 3 şehir hangisidir?", "nunique_city_topn"),
        ("profileType alanına göre kaç profil individual kaç profil business?", "value_counts_profiletype"),
        ("serviceModes alanında Yerinde hizmet, Yüz yüze ve Online modlarının sayısal karşılaştırması nedir?", "explode_servicemodes"),
        ("Veri setindeki sektör dağılımı (sectorDistribution) nasıldır?", "meta_sector_distribution"),
        ("Türkçe dışında en sık geçen diller hangileridir?", "explode_languages"),
    ]

    for q, op_expected in queries:
        res = engine.execute_query(q)
        assert res is not None, f"Query sonuç üretmedi: {q}"
        assert res.get("operation") == op_expected, (
            f"Yanlış kural: beklenen {op_expected}, çalışan {res.get('operation')} | {q}")
        data_to_plot = res.get("data_points") or res.get("result")
        chart_data = extract_chart_data(data_to_plot, query=q, summary=res.get("summary", ""), operation=res.get("operation", ""))
        assert chart_data is not None, f"Sorgu için chart_data üretilemedi: {q}"
        assert len(chart_data["df"]) >= 2, f"Grafik DataFrame'i yetersiz: {chart_data['df']}"
        fig = create_plotly_figure(chart_data, chart_type=chart_data.get("default_chart_type", "bar"))
        assert fig is not None
        print(f"  [OK] '{op_expected}' sorgusu -> Grafik: '{chart_data['title']}' ({len(chart_data['df'])} kategori, toplam={chart_data['kpis']['total']:g})")


if __name__ == "__main__":
    print("=" * 70)
    print("GÖRSELLEŞTİRME & GRAFİK MOTORU TESTLERİ")
    print("=" * 70)

    test_dict_extraction()
    test_nested_dict_extraction()
    test_series_extraction()
    test_dataframe_extraction()
    test_text_summary_fallback()
    test_plotly_figure_generation()
    test_altair_chart_generation()
    test_data_engine_end_to_end_visualization()

    print("\n" + "=" * 70)
    print("TÜM GÖRSELLEŞTİRME TESTLERİ BAŞARIYLA GEÇTİ! (8/8)")
    print("=" * 70)
