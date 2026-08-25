# Streamlit UI Grafik ve Görselleştirme Desteği (Plotly / Altair) Uygulama Planı

Bu plan, analitik sorgu sonuçlarının (örneğin sektör karşılaştırmaları, şehir yoğunlukları, dil dağılımları, profil türü oranları veya havaalanı istatistikleri) Streamlit arayüzünde otomatik olarak tespit edilip zengin tasarımlı **Plotly** ve **Altair** pasta/çubuk/halka grafiklerine ve veri tablolarına dönüştürülmesini sağlar.

---

## Kullanıcı İncelemesi Gereken Konular

> [!IMPORTANT]
> **Grafik Motoru Tercihi**: Plotly kütüphanesi hem yerel etkileşim (hover tooltip, zoom, pan, export to png) hem de koyu tema (dark mode) gradient uyumu açısından en zengin deneyimi sunmaktadır. Sistemde hem **Plotly** (varsayılan interaktif motor) hem de alternatif olarak **Altair** desteklenecek, kullanıcı arayüzünde tek tıkla Çubuk Grafik (Bar), Halka/Pasta Grafik (Donut/Pie) ve Veri Tablosu arasında geçiş yapılabilecektir.

> [!TIP]
> **Otomatik Veri Formatı Tespiti**: Kullanıcının sorduğu soru ister Kural Motoru (`rule_engine`), ister dinamik Pandas Sandbox (`code_interpreter`), ister Semantik RAG sonucundan gelsin; dönen `DataFrame`, `Series`, `dict`, `list` veya yapılandırılmış dağılım metinleri otomatik olarak algılanıp görselleştirilebilir veri formatına dönüştürülecektir.

---

## Mimarinin Görselleştirme Akışı

```
[ Analitik / Tabüler Sonuç ] (DataFrame / Series / Dict / Data Points)
                      │
                      ▼
        ┌───────────────────────────┐
        │       visualizer.py       │
        │   (extract_chart_data)    │
        └─────────────┬─────────────┘
                      │
          ┌───────────┴───────────┐
          │                       │
          ▼                       ▼
┌──────────────────┐    ┌──────────────────┐
│  Plotly Engine   │    │  Altair Engine   │
│ (Bar / Donut /   │    │ (Opsiyonel /     │
│  Horizontal Bar) │    │  Alternatif)     │
└─────────┬────────┘    └────────┬─────────┘
          │                      │
          └───────────┬──────────┘
                      ▼
        ┌───────────────────────────┐
        │  Streamlit UI Bileşeni    │
        │  - 📊 Çubuk Grafik        │
        │  - 🍩 Halka/Pasta Grafik  │
        │  - 📋 Veri Tablosu        │
        │  - 💡 KPI Özet Kartları   │
        └───────────────────────────┘
```

---

## Önerilen Değişiklikler ve Yeni Modüller

### 1. [NEW] [visualizer.py](file:///c:/Users/merve/Desktop/rag_project/visualizer.py) (Görselleştirme & Grafik Motoru)
- **`extract_chart_data(data, query="", summary="")`**:
  - `pd.DataFrame`, `pd.Series`, `dict` (anahtar -> sayısal değer), `list of dicts` ve yapısal metinleri analiz eder.
  - Veri boyutunu, kategorileri, metrik değerlerini ve birimleri (`%`, `adet`, `yıl`, `saat` vb.) belirler.
  - Kategori sayısına ve karşılaştırma tipine göre en uygun varsayılan grafik tipini (`bar`, `pie`, `donut`, `horizontal_bar`) seçer.
  - Hızlı KPI metriklerini (Toplam, En Yüksek Kategori/Değer, Kategori Sayısı, Ortalama) hesaplar.
- **`create_plotly_figure(chart_data, chart_type='bar', theme='dark')`**:
  - Uygulamanın koyu mor-gece mavisi gradient temasına (`#0f0c29`, `#302b63`, `#24243e`) uyumlu, şeffaf arkaplanlı, canlı neon renk paletli (`#8b5cf6`, `#60a5fa`, `#34d399`, `#fbbf24`, `#f472b6`, `#38bdf8`) Plotly figürleri üretir.
  - Çubuk (Bar/Horizontal Bar), Pasta/Halka (Pie/Donut), Karşılaştırma grafikleri.
  - Özel zengin hover tooltip şablonları (`%{label}: %{value}`).
- **`create_altair_chart(chart_data, chart_type='bar')`**:
  - Altair için koyu tema uyumlu alternatif grafik üreticisi.
- **`render_chart_block(chart_data, block_key)`**:
  - Streamlit içinde sekmeli (Tabs) veya Segmented Control ile kullanıcıya **📊 Çubuk Grafik**, **🍩 Pasta / Halka Grafik** ve **📋 Veri Tablosu** seçeneklerini interaktif sunar.

### 2. [MODIFY] [app.py](file:///c:/Users/merve/Desktop/rag_project/app.py) (Streamlit Arayüzü Entegrasyonu)
- **Görselleştirme Kartı & Tasarım**:
  - CSS stil dosyasına grafik kartı, KPI göstergeleri ve sekme geçişleri için modern glassmorphism stilleri ekleme.
- **Sohbet Mesajı Entegrasyonu**:
  - Asistan mesaj nesnesine (`msg["chart_data"]`, `msg["code"]`, `msg["operation"]`) alanlarının eklenmesi ve oturum geçmişinde korunması.
  - `render_assistant_message` içinde cevabın altında otomatik grafik kartı ve çalıştırılan kod expander'ı (`💻 Çalıştırılan Analiz Kodu`) gösterimi.
- **Canlı Örnek Sorgular**:
  - Görselleştirmeyi hemen tetikleyen örnek butonlar (örn: *"Sektör dağılımını göster"*, *"En çok profile sahip ilk 5 şehir hangisidir?"*, *"Hizmet modlarının (serviceModes) dağılımı nasıldır?"*).

### 3. [MODIFY] [data_engine.py](file:///c:/Users/merve/Desktop/rag_project/data_engine.py) & [code_interpreter.py](file:///c:/Users/merve/Desktop/rag_project/code_interpreter.py)
- `data_engine.py` ve `code_interpreter.py` çıktılarında `result` ve `data_points` alanlarının her zaman zengin veri (dict / series / dataframe) olarak iletilmesini garanti altına alma.
- Sektör dağılımları, şehir yoğunlukları, dil frekansları, hizmet modu oranları için yapısal `data_points` çıktısını standartlaştırma.

### 4. [MODIFY] [requirements.txt](file:///c:/Users/merve/Desktop/rag_project/requirements.txt)
- `plotly>=6.0.0` ve `altair>=5.0.0` gereksinimlerinin eklenmesi.

### 5. [NEW] [test_visualization.py](file:///c:/Users/merve/Desktop/rag_project/test_visualization.py) (Otomatik Testler)
- Sözlük, Seri, DataFrame ve karmaşık analitik çıktılardan grafik verisi çıkarma testleri.
- Plotly Bar ve Donut/Pie figür üretim doğrulama testleri.
- Sektör karşılaştırması, şehir yoğunluğu ve havaalanı dağılımı uçtan uca görselleştirme testleri.

---

## Doğrulama Planı

### Otomatik Testler
1. `test_visualization.py` çalıştırılarak görselleştirme motorunun tüm veri yapısıyla (dict, DataFrame, Series, text) hatasız çalıştığı doğrulanacak:
   ```bash
   python test_visualization.py
   ```
2. Mevcut sistem testleri (`test_sandbox_and_datasets.py`, `run_tests.py`) çalıştırılarak hiçbir regresyon oluşmadığı doğrulanacak:
   ```bash
   python test_sandbox_and_datasets.py
   ```

### Manuel UI Doğrulaması
1. `streamlit run app.py` başlatılarak aşağıdaki soru tiplerinde grafiklerin sorunsuz render edildiği doğrulanacak:
   - Sektör dağılımı: *"Veri setindeki sektör dağılımı nasıldır?"*
   - Şehir yoğunlukları: *"En çok profile sahip ilk 5 şehir hangileridir?"*
   - Hizmet modu karşılaştırması: *"serviceModes alanındaki hizmet modlarının sayısal dağılımı nedir?"*
   - Profil tipi oranları: *"profileType alanına göre individual ve business dağılımı nedir?"*
   - Tablar arası geçiş (Çubuk -> Pasta -> Tablo) ve hover etkileşimlerinin akıcılığı.
