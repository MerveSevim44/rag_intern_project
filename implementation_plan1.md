# Proje Dosyalarını Gruplama ve Modüler Dizin Yapısı Planı

Bu plan, kök dizinde biriken 35+ dosyayı işlevlerine göre mantıksal klasörlere (`src/`, `tests/`, `evaluation/`, `docs/`) ayırarak projeyi profesyonel bir Python paket mimarisine kavuşturmayı hedefler. Mevcut komutların (`streamlit run app.py`, `python ingest.py`, `python benchmark_eval.py`, testler vb.) **hiçbir şekilde bozulmadan** çalışmaya devam etmesi için kök dizinde geriye dönük uyumlu giriş noktaları (entrypoint/wrapper) korunacaktır.

---

## Hedeflenen Dizin Yapısı

```text
rag_project/
├── data/                                # Ham dokümanlar ve veri setleri (PDF, JSON, DOCX, TXT)
│   ├── 728_profiles.json
│   ├── airports.json
│   ├── ...
│
├── src/                                 # Çekirdek Kaynak Kodları (Core Engine & Logic)
│   ├── __init__.py
│   ├── app.py                           # Streamlit UI & Ana Sohbet Arayüzü
│   ├── ingest.py                        # Doküman okuma, chunk'lama ve SQLite indeksleme
│   ├── embedder.py                      # Vektör embedding motoru (bge-m3 / GPU)
│   ├── retrieval.py                     # Hibrit arama (Vektör + BM25 + RRF Reranker)
│   ├── router.py                        # Dinamik niyet sınıflandırıcı & yönlendirici
│   ├── llm_client.py                    # Foundry Local LLM istemcisi & prompt yönetimi
│   ├── data_engine.py                   # Yapılandırılmış veri motoru (JSON/Pandas analitik motoru)
│   ├── sandbox.py                       # Güvenli Python kod çalıştırma sandbox'ı (AST tabanlı)
│   ├── code_interpreter.py              # LLM kod üretici & otomatik hata düzeltme (retry)
│   └── visualizer.py                    # Plotly / Altair analitik grafik motoru
│
├── tests/                               # Birim ve Entegrasyon Testleri
│   ├── __init__.py
│   ├── test_sandbox_step1.py            # Sandbox güvenlik ve izolasyon testleri
│   ├── test_code_interpreter_step2.py   # Kod yorumlayıcı ve prompt testleri
│   ├── test_retry_mechanism.py          # Hata düzeltme & retry simülasyonu
│   ├── test_sandbox_and_datasets.py     # JSON veri setleri ve sandbox entegrasyonu
│   └── test_visualization.py            # Grafik üretimi ve Altair/Plotly testleri
│
├── evaluation/                          # Benchmark, Skorlama ve Değerlendirme Araçları
│   ├── __init__.py
│   ├── benchmark_eval.py                # Otomatik skorlama (EM, F1, Latency) & grafik üretimi
│   ├── eval_retrieval.py                # Retrieval ve router başarım testi
│   ├── run_tests.py                     # Otomatik test seti koşucusu
│   ├── ground_truth.json                # 30 soruluk standart referans cevap veri seti
│   └── datasets/                        # Test soru setleri ve çıktı CSV'leri
│       ├── test_sorulari.csv
│       ├── test_sorulari_json.csv
│       ├── test_sorulari_json_zor.csv
│       ├── test_sonuclari.csv
│       └── test_sonuclari_json_zor.csv
│
├── report/                              # Haftalık Raporlar ve Benchmark Çıktıları
│   ├── week_1_report.pdf ... week_6_report.pdf
│   ├── RAG_Kavramlari_Arastirma_Notu.pdf
│   ├── test_sonuclari_scored.csv
│   ├── benchmark_summary.json
│   └── benchmark_charts/
│       ├── benchmark_accuracy_f1.png
│       ├── benchmark_latency.png
│       └── benchmark_overall_summary.png
│
├── docs/                                # Teknik Raporlar ve Mimari Planlar
│   ├── TEKNIK_RAPOR.md                  # Kapsamlı Proje Teknik Raporu
│   ├── implementation_plan_banchmark.md # Benchmark geliştirme planı
│   ├── implementation_plan_visual.md    # Görselleştirme geliştirme planı
│   ├── walkthrough.md                   # Sandbox & Data Engine walkthrough
│   └── walkthrough_benchmark.md         # Benchmark walkthrough
│
├── app.py                               # Kök dizin Streamlit çalıştırıcı (kolay erişim)
├── ingest.py                            # Kök dizin indeksleme çalıştırıcı
├── benchmark_eval.py                    # Kök dizin benchmark çalıştırıcı
├── run_tests.py                         # Kök dizin test koşucu çalıştırıcı
├── requirements.txt                     # Python bağımlılıkları
├── README.md                            # Güncellenmiş proje dokümantasyonu
├── license                              # Lisans
├── .gitignore                           # Git ignore dosyası
└── rag.db                               # SQLite veritabanı
```

---

## Kullanıcı İncelemesine Sunulan Noktalar (User Review Required)

> [!IMPORTANT]
> **Geriye Dönük Uyumluluk (Zero Breaking Change):**
> Kök dizindeki `app.py`, `ingest.py`, `benchmark_eval.py` ve `run_tests.py` dosyaları kökte de tutulacak veya doğrudan `src/` klasörüne köprülenerek çalıştırılacaktır. Böylece daha önce kullandığınız tüm komutlar (`streamlit run app.py`, `python ingest.py`, vb.) aynen çalışmaya devam edecektir.

> [!NOTE]
> **Import & Path Yönetimi:**
> Tüm modüllerin birbirini sorunsuz bulabilmesi için `src/` klasörü Python path'ine dahil edilecek ve `ground_truth.json` / veri dosyaları için hem kök dizin hem de `evaluation/` klasörü taranacaktır.

---

## Yapılacak Değişiklikler (Proposed Changes)

### 1. Dizinlerin Oluşturulması
- [NEW] `src/`
- [NEW] `tests/`
- [NEW] `evaluation/`
- [NEW] `evaluation/datasets/`
- [NEW] `docs/`

### 2. Dosyaların İlgili Klasörlere Taşınması ve Düzenlenmesi

#### Çekirdek Modüller (`src/`)
- [MOVE] `embedder.py` → `src/embedder.py`
- [MOVE] `retrieval.py` → `src/retrieval.py`
- [MOVE] `router.py` → `src/router.py`
- [MOVE] `llm_client.py` → `src/llm_client.py`
- [MOVE] `data_engine.py` → `src/data_engine.py`
- [MOVE] `sandbox.py` → `src/sandbox.py`
- [MOVE] `code_interpreter.py` → `src/code_interpreter.py`
- [MOVE] `visualizer.py` → `src/visualizer.py`
- [MOVE] `ingest.py` → `src/ingest.py` (Kök dizinde wrapper bırakılacak)
- [NEW] `src/__init__.py`

#### Testler (`tests/`)
- [MOVE] `test_sandbox_step1.py` → `tests/test_sandbox_step1.py`
- [MOVE] `test_code_interpreter_step2.py` → `tests/test_code_interpreter_step2.py`
- [MOVE] `test_retry_mechanism.py` → `tests/test_retry_mechanism.py`
- [MOVE] `test_sandbox_and_datasets.py` → `tests/test_sandbox_and_datasets.py`
- [MOVE] `test_visualization.py` → `tests/test_visualization.py`
- [NEW] `tests/__init__.py`

#### Benchmark & Değerlendirme (`evaluation/`)
- [MOVE] `benchmark_eval.py` → `evaluation/benchmark_eval.py` (Kök dizinde wrapper bırakılacak)
- [MOVE] `eval_retrieval.py` → `evaluation/eval_retrieval.py`
- [MOVE] `ground_truth.json` → `evaluation/ground_truth.json`
- [MOVE] `test_sorulari*.csv` → `evaluation/datasets/`
- [MOVE] `test_sonuclari*.csv` → `evaluation/datasets/`
- [NEW] `evaluation/__init__.py`

#### Dokümantasyon (`docs/`)
- [MOVE] `TEKNIK_RAPOR.md` → `docs/TEKNIK_RAPOR.md`
- [MOVE] `implementation_plan_banchmark.md` → `docs/implementation_plan_banchmark.md`
- [MOVE] `implementation_plan_visual.md` → `docs/implementation_plan_visual.md`
- [MOVE] `walkthrough.md` → `docs/walkthrough.md`
- [MOVE] `walkthrough_benchmark.md` → `docs/walkthrough_benchmark.md`

#### Kök Dizin Dosyaları ve Güncellemeler
- [MODIFY] `app.py` (Import yollarını `src` ile tam uyumlu hale getirme)
- [NEW] `ingest.py` (Kök dizinden `src/ingest.py` çağıran wrapper)
- [NEW] `benchmark_eval.py` (Kök dizinden `evaluation/benchmark_eval.py` çağıran wrapper)
- [NEW] `run_tests.py` (Kök dizinden `evaluation/run_tests.py` çağıran wrapper)
- [MODIFY] `README.md` (Yeni dizin yapısı şeması ve güncellenmiş dosya yolları)

---

## Doğrulama Planı (Verification Plan)

### Otomatik Testler
1. **Sandbox Testleri:** `python tests/test_sandbox_step1.py`
2. **Görselleştirme Testleri:** `python tests/test_visualization.py`
3. **Retry Mekanizması Testleri:** `python tests/test_retry_mechanism.py`
4. **Veri Seti ve Sandbox Entegrasyonu:** `python tests/test_sandbox_and_datasets.py`
5. **Otomatik Skorlama & Benchmark:** `python benchmark_eval.py` ve `python evaluation/benchmark_eval.py`
6. **Pytest ile Toplu Test:** `python -m pytest tests`

### Manuel Doğrulama
- `streamlit run app.py` çalıştırılarak arayüzün, model seçiminin ve veri motorunun sorunsuz başlatıldığının doğrulanması.
