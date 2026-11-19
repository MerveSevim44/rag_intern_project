# RAG Soru-Cevap

[![tests](https://github.com/MerveSevim44/rag_intern_project/actions/workflows/tests.yml/badge.svg)](https://github.com/MerveSevim44/rag_intern_project/actions/workflows/tests.yml)

Kendi dokümanlarınız ve veri setleriniz üzerinde Türkçe soru-cevap yapan, **tamamen yerelde**
çalışan bir RAG (Retrieval-Augmented Generation) uygulaması.

Hiçbir veri dışarı çıkmaz: embedding (`bge-m3`) ve cevap üretimi (**`qwen3-8b-pilot`**, varsayılan)
**Ollama** ile makinenizde yapılır; indeks tek dosyalık bir SQLite veritabanında (`rag.db`)
tutulur. Eski cevap-üretim yolu (**Foundry Local / qwen2.5-7b**) geri alma için kodda duruyor:
`RAG_LLM_RUNTIME=foundry` ([Ayarlar](#ayarlar) bölümüne bakın).

- **Desteklenen formatlar:** `.txt`, `.pdf`, `.docx`, `.json`, `.jsonl`
- **Hibrit arama:** BM25 (anahtar kelime) + BGE-M3 (vektör) + Cross-Encoder reranker
- **Analitik sorular:** sayma, oran, gruplama gibi sorular LLM'in ürettiği Pandas koduyla
  güvenli bir sandbox içinde **hesaplanır**, tahmin edilmez
- **Kaynak gösterimi:** her cevap, dayandığı dosya ve sayfa/paragraf bilgisiyle birlikte gelir
- **Ölçüm:** 98 soruluk doğruluk seti + 31 soruluk negatif (tuzak) seti ile otomatik skorlama

---

## Hızlı başlangıç

```bash
# 1. Bağımlılıklar
python -m venv rag_project
rag_project\Scripts\activate        # Linux/macOS: source rag_project/bin/activate
pip install -r requirements.txt

# 2. Modeller (Ollama): embedding + cevap üreten LLM
ollama pull bge-m3
ollama pull qwen3:8b
ollama create qwen3-8b-pilot -f ollama/Modelfile.qwen3-8b-pilot   # num_ctx 8192, temperature 0

# 3. Dokümanları data/ klasörüne koyup indeksleyin
python ingest.py

# 4. Arayüzü açın
streamlit run app.py
```

Ollama servisinin çalışıyor olması gerekir. Varsayılan LLM runtime'ı **Ollama / `qwen3-8b-pilot`**'tur;
elle bayrak vermeniz gerekmez. Foundry Local / qwen2.5'e dönmek için bkz. [Ayarlar](#ayarlar).

---

## Nasıl çalışır?

Her soru önce **router**'dan geçer; router sorunun tipine göre onu dört hattan birine yollar.
Amaç, matematik gerektiren bir soruyu dil modeline tahmin ettirmemek.

```
                                   ┌─ rule_engine       → sabit regex/kural motoru (anında)
                                   │
Soru → router (classify_query) ────┼─ code_interpreter  → LLM Pandas kodu → sandbox → kesin sonuç
                                   │
                                   ├─ semantic_rag      → hibrit arama → reranker → LLM
                                   │
                                   └─ meta_query        → "dokümanda olan" / "çıkarım" ayrımıyla cevap
```

Router tek bir veri setine sabitlenmiş kelime listelerine bağlı değildir; veri seti sinyali
çalışma anında gerçek kolon adlarından (`df_schema`) hesaplanır, yani yeni bir veri seti
eklendiğinde router'da değişiklik gerekmez.

Semantik hat:

```
Doküman → chunk'lara böl → embedding (bge-m3) → SQLite (rag.db)
                                                     │
Soru → BM25 + cosine similarity (TOP_K, BM25_WEIGHT) ┘
            │
            └→ reranker (bge-reranker-v2-m3, RERANK_TOP_N)
                    │
                    └→ bağlam + soru → LLM → kaynaklı cevap
```

Hibrit skor hızlı ama kaba bir ön elemedir; Cross-Encoder reranker soru ile chunk'ı birlikte
değerlendirip son sıralamayı yapar. Cevaba giren her parçanın dosya adı ve sayfa/paragraf
bilgisi korunur, böylece cevaplar kaynak gösterebilir. Chunk verileri ve BM25 indeksi ilk
sorguda cache'lenir; yeni doküman eklendiğinde cache otomatik geçersizleşir.

**Sandbox boş-sonuç koruması:** veri setinde olmayan bir varlık sorulduğunda ("ACC-124'ün
bakiyesi ne?") LLM'in kurduğu filtre hiçbir satırla eşleşmez ve üstündeki `.sum()` sessizce
`0` üretir. Sistem bu durumu sonucun *değerine* değil, *filtrenin eşleşip eşleşmediğine*
bakarak yakalar ve sonucu olgu gibi sunmak yerine "kayıt bulunamadı" der. Meşru sıfır
(hesap var, bakiyesi gerçekten 0) etkilenmez; bu ayrım
[test_empty_result_guard.py](tests/test_empty_result_guard.py) ile kilitlenmiştir.

---

## Gereksinimler

| Bileşen | Not |
|---|---|
| Python 3.10+ | — |
| [Ollama](https://ollama.com) | Embedding (`ollama pull bge-m3`) **ve varsayılan cevap üreten LLM**: `qwen3-8b-pilot` (`qwen3:8b`'den `ollama/Modelfile.qwen3-8b-pilot` ile türetilir). Thinking kodda `reasoning_effort=none` ile kapatılır. |
| [Foundry Local](https://learn.microsoft.com/azure/ai-foundry/foundry-local/) | **İsteğe bağlı, geri alma yolu** (`RAG_LLM_RUNTIME=foundry`): `qwen2.5-7b-instruct-cuda-gpu:4` (alternatif: `Phi-4-mini-instruct-cuda-gpu:5`). Yalnız bu yolu kullanacaksanız gerekir; servis çalışır durumda olmalı, portu uygulama otomatik bulur. |
| `BAAI/bge-reranker-v2-m3` | Reranker; ilk çalıştırmada Hugging Face'ten otomatik iner. |

Referans donanım: 8 GB VRAM. Varsayılan bağlam sınırları bu bütçeye göre seçilmiştir.

---

## Kullanım

### Dokümanları indeksle

Dosyaları `data/` klasörüne koyun ve:

```bash
python ingest.py
```

Daha önce indekslenmiş dosyalar atlanır; bir dosyayı güncellediyseniz `--force` kullanın.
Her dosya kendi başına commit edilir, yani ortada bir dosya hata verse bile öncekiler kaybolmaz.

```bash
python ingest.py --force
python ingest.py --data_dir data --db_path rag.db --model bge-m3 --batch_size 16
```

| Bayrak | Varsayılan | Açıklama |
|---|---|---|
| `--data_dir` | `data` | Dokümanların bulunduğu klasör |
| `--db_path` | `rag.db` | SQLite veritabanı yolu |
| `--model` | `bge-m3` | Embedding modeli |
| `--batch_size` | `64` | Tek seferde embedding'i alınacak metin sayısı |
| `--force` | — | Zaten indekslenmiş dosyaları yeniden işle |

### Arayüzü başlat

```bash
streamlit run app.py
```

Kenar çubuğundan model seçip yükleyebilir, doğrudan tarayıcıdan doküman yükleyip
indeksleyebilirsiniz — `data/` klasörünü kullanmak zorunlu değil. Analitik sorularda cevabın
yanında otomatik olarak interaktif grafik ve KPI kartları üretilir.

### Sadece arama (arayüzsüz)

```bash
python -c "from src.retrieval import retrieve; print(retrieve('Fourier dönüşümü'))"
```

---

## Değerlendirme

Ölçüm iki parçadır:

- **Doğruluk seti** — `test_1`..`test_4`, 100 soru. Her soru üç kategoriden birindedir
  (güncel tanım, 2026-11-04, madde 11 C sonrası):
  - **Temiz set (99 soru):** `test_2#53` dışındaki tüm sorular. `test_2#43` dahildir: eskiden
    kronik GPU bellek hatası verdiği için hariçti; düzeltme prompt'u tavanı (C) sonrası
    çökmüyor ve cevabı `data/728_profiles.json`'dan pandas ile doğrulandı (doğru).
  - **"Yanıt veriyor, içerik hatası bilinen" (1 soru):** `test_2#53`. Artık çökmüyor ama
    cevabındaki iki sayı yanlış (Sinem iptal 4 / gerçek 12, Umut min 6 / gerçek 4). Ne temiz
    sete ne HATA'ya sayılır; sürüm karşılaştırmalarında temiz setten ayrı tutulur. Kök neden
    kırpmadan bağımsız sentez confabülasyonu: [backlog madde 41 notu](docs/backlog_retrieval.md).
  - **HATA:** altyapı çökmesi (şu an bu sette yok; bir soru HATA verirse buraya girer).

  Not: aşağıdaki v5–v6 sonuçları ve karşılaştırmaları **eski tanımla (98 soru, #43 ve #53
  hariç)** ölçüldü ve yeniden hesaplanmadı; #43'ün sete eklenmesi o rakamları değiştirmez,
  çünkü o koşularda #43 cevap vermiyordu.
- **Negatif set** — `test_negative`, 32 tuzak soru (cevabı veri setinde olmayan sorular;
  burada doğru davranış cevap vermeyi reddetmektir). v5–v6 kıyası `#216` çıkarılarak **n=31**
  üzerinden yapılır.

`test_5` (15 soru) ikinci bir negatif settir; repoda hazırdır ve `run_all.py`'nin varsayılan
listesinde yer alır, ancak v6 koşusunda çalıştırılmamıştır — aşağıdaki rakamlara dahil değildir.

```bash
# Tam akış: retrieval + LLM cevapları + skorlama + grafikler
python evaluation/run_all.py

# Sadece retrieval/yönlendirme başarımı (LLM gerekmez, hızlı)
python evaluation/run_all.py --only-retrieval

# Cevaplar hazırsa sadece yeniden skorla
python evaluation/run_all.py --skip-llm

# Tek set
python evaluation/run_all.py --sets test_2 test_4
```

Adımları tek tek çalıştırmak isterseniz:

```bash
python run_tests.py evaluation/datasets/test_2.csv test_2_sonuclari.csv
python benchmark_eval.py test_2_sonuclari.csv --output-dir report
```

Ground truth verilmezse `evaluation/ground_truth/<set>.json` otomatik seçilir.

### Metrikler

| Metrik | Ne ölçer |
|---|---|
| **EM** | Katı tam eşleşme (uzun referanslarda pratikte çok düşük kalır) |
| **Soft EM** | Referansın kısa çekirdeği cevabın içinde geçiyor mu |
| **F1** | Token düzeyinde örtüşme — uzun cevapları cezalandırır |
| **ROUGE-L** | En uzun ortak alt dizi (LCS), EM/F1 ile aynı token uzayında |
| **Semantik** | bge-m3 embedding'leri arasında cosine benzerliği |
| **FN** | Cevap bilinmesine rağmen reddedilen soru sayısı |
| **Negatif FP** | Cevabı olmayan soruya uydurma cevap verilmesi (halüsinasyon) |

### Güncel sonuçlar (v6 — aktif)

98 soruluk doğruluk seti + 31 soruluk negatif set:

| FN | F1 | ROUGE-L | Semantik | EM | Soft | Negatif FP |
|---|---|---|---|---|---|---|
| 13 | 40.0 | 35.5 | 77.5 | 6.1 | 12.2 | **2/31** |

v6, v5'e göre doğruluk metriklerinde **birebir aynıdır** (98 cevabın 98'i karakter karakter
özdeş); tek kazanç halüsinasyonda: negatif FP 7 → 2. Deneylerin tam kaydı, hangi değişikliğin
neden alındığı/alınmadığı ve geçersiz koşular için [EXPERIMENTS.md](docs/EXPERIMENTS.md).
Her deneyin çıktıları `experiments/<sürüm>/` altında koşu kaynağıyla (`PROVENANCE.md`) saklanır.

### Birim ve entegrasyon testleri

```bash
python -m pytest tests
```

Bu komut **29 offline testi** koşar; Ollama, Foundry Local, GPU veya `torch` gerektirmez.
Canlı LLM isteyen 2 test (`test_code_interpreter`, `test_full_pipeline`) `live` marker'ıyla
varsayılan koşudan hariç tutulur — çalıştırmak için Ollama servisi ve `qwen3-8b-pilot` hazırken
(Foundry yolunu denemek için `RAG_LLM_RUNTIME=foundry` ve Foundry servisi açıkken):

```bash
python -m pytest tests -m live
```

Ayrım [pytest.ini](pytest.ini) içinde tanımlıdır. `main`'e açılan her PR'da offline set
GitHub Actions ile otomatik koşar ([.github/workflows/tests.yml](.github/workflows/tests.yml)).

---

## Proje dizin yapısı

```text
rag_project/
├── data/                                # Ham dokümanlar (PDF, JSON, DOCX, TXT)
├── src/                                 # Çekirdek motorlar
│   ├── app.py                           # Streamlit arayüzü ve ana sohbet motoru
│   ├── components.py / styles.py        # Arayüz bileşenleri ve tema
│   ├── ingest.py                        # Doküman okuma, chunk'lama ve SQLite indeksleme
│   ├── embedder.py                      # Ollama bge-m3 vektörleştirme & reranker
│   ├── retrieval.py                     # Hibrit arama (Vektör + BM25 + Cross-Encoder rerank)
│   ├── router.py                        # 4 kademeli soru yönlendirici
│   ├── llm_client.py                    # LLM istemcisi (Ollama varsayılan, Foundry Local geri alma) & prompt şablonları
│   ├── data_engine.py                   # Yapısal veri analitiği & Pandas motoru
│   ├── sandbox.py                       # Güvenli Python çalışma alanı (AST denetimi)
│   ├── code_interpreter.py              # LLM kod üretici & otomatik retry döngüsü
│   ├── visualizer.py                    # Grafik ve görselleştirme motoru (Plotly/Altair)
│   └── memory_profiler.py               # Bellek ve süre profilleme
├── tests/                               # Birim ve entegrasyon testleri
│   ├── test_sandbox_step1.py            # Sandbox güvenlik ve izolasyon testleri
│   ├── test_code_interpreter_step2.py   # Kod yorumlayıcı ve prompt testleri
│   ├── test_retry_mechanism.py          # Hata düzeltme & retry mekanizması testleri
│   ├── test_sandbox_and_datasets.py     # Veri setleri ve sandbox entegrasyonu
│   ├── test_empty_result_guard.py       # Boş filtre / meşru sıfır ayrımı
│   ├── test_refusal_detection.py        # Soru bağlamlı ret tespiti (iddia mı, gerekçe mi)
│   └── test_visualization.py            # Grafik üretimi ve Altair/Plotly testleri
├── evaluation/                          # Benchmark, skorlama ve değerlendirme
│   ├── run_all.py                       # Uçtan uca değerlendirme akışı
│   ├── run_tests.py                     # Test seti koşucusu (LLM cevaplarını üretir)
│   ├── benchmark_eval.py                # Skorlama (EM/Soft/F1/ROUGE-L/Semantik) & grafikler
│   ├── eval_retrieval.py                # Retrieval ve router başarım testi
│   ├── make_ground_truth.py             # Ground truth üretim yardımcısı
│   ├── ground_truth/                    # Set başına referans cevaplar
│   └── datasets/                        # Test soru setleri ve çıktı CSV'leri
├── experiments/                         # Sürümlenmiş deney koşuları (v2, v3, v5, v6)
├── report/                              # Haftalık raporlar ve benchmark çıktıları
├── archive/                             # Geçersiz/eski koşuların arşivi
├── docs/                                # Dokümantasyon
│   ├── TEKNIK_RAPOR.md                  # Kapsamlı teknik rapor
│   ├── EXPERIMENTS.md                   # Deney kaydı ve sonuç tablosu
│   ├── INFRASTRUCTURE_NOTES.md          # Altyapı notları ve bilinen sorunlar
│   └── walkthrough*.md                  # Adım adım anlatımlar
├── app.py / ingest.py / run_tests.py / benchmark_eval.py   # Kök dizin çalıştırıcılar
└── rag.db                               # SQLite veritabanı
```

Kök dizindeki [app.py](app.py), [ingest.py](ingest.py), [run_tests.py](run_tests.py) ve
[benchmark_eval.py](benchmark_eval.py) yalnızca ince sarmalayıcıdır; asıl kod
[src/](src/) ve [evaluation/](evaluation/) altındadır.

---

## Ayarlar

Sık değiştirilen sabitler ilgili dosyaların başında yer alır:

| Dosya | Sabit | Varsayılan |
|---|---|---|
| `src/retrieval.py` | `TOP_K` — hibrit arama ile çekilen aday sayısı | `8` |
| `src/retrieval.py` | `RERANK_TOP_N` — reranker sonrası nihai sonuç sayısı | `3` |
| `src/retrieval.py` | `BM25_WEIGHT` — hibrit skorda BM25 ağırlığı (0.0 = saf vektör) | `0.35` |
| `src/ingest.py` | `EMBED_MODEL` / `BATCH_SIZE` | `bge-m3` / `64` |
| `src/ingest.py` | `DB_PATH` / `DATA_DIR` | `rag.db` / `data` |
| `src/llm_client.py` | `DEFAULT_LLM_RUNTIME` (ortam değişkeni: `RAG_LLM_RUNTIME`) | `ollama` (`foundry` = geri alma) |
| `src/llm_client.py` | `OLLAMA_MODEL_ID` (ortam değişkeni: `RAG_OLLAMA_MODEL`) | `qwen3-8b-pilot` |
| `src/llm_client.py` | `DEFAULT_MODEL_ID` — yalnız Foundry yolunda | `qwen2.5-7b-instruct-cuda-gpu:4` |
| `src/llm_client.py` | `MAX_ANSWER_TOKENS` | `600` |
| `src/llm_client.py` | `MAX_CHUNK_CHARS` / `MAX_CONTEXT_CHARS` | `1500` / `6000` |

**Model / runtime nasıl seçilir?** Hem Streamlit (`streamlit run app.py`) hem de
`python run_tests.py` varsayılan olarak **Ollama / `qwen3-8b-pilot`** kullanır. Eski yola dönmek
(rollback) için ortam değişkeni yeterlidir, koddan bir şey silinmedi:

```bash
set RAG_LLM_RUNTIME=foundry          # PowerShell: $env:RAG_LLM_RUNTIME="foundry"
```

Geçersiz bir değer (ör. yazım hatası) sessizce varsayılana düşmez, hata verir. Arayüzdeki model
seçici etkin runtime'a göre kurulur: Ollama'da yalnız `qwen3-8b-pilot`, Foundry'de `qwen2.5-7b`
ve `phi-4-mini`.

> **Bilinen regresyon (qwen3, provizyonel migrasyon):** CFG/biçimsel-dilbilgisi sorularında
> qwen3 birbirine çok benzeyen sembolleri karıştırabiliyor (`*`↔`/`, `B`↔`b`; 147 sorudan 2'si).
> Ayrıntı ve ölçümler: [docs/backlog_retrieval.md](docs/backlog_retrieval.md), Madde 42.

`MAX_CHUNK_CHARS` / `MAX_CONTEXT_CHARS` değerlerini yükseltmeden önce
[EXPERIMENTS.md](docs/EXPERIMENTS.md) içindeki v3 deneyine bakın: bağlam ~8700 karaktere
çıktığında 8 GB VRAM'de Foundry Local çöküyor ve ölçülen kazanç marjinaldi.

---

## Sorun giderme

**"Embedding oluşturulamadı"** — Ollama çalışmıyor ya da `bge-m3` yüklü değil;
`ollama list` ile kontrol edin.

**"Ollama servisi ... yanıt vermiyor" / "Ollama'da 'qwen3-8b-pilot' modeli yok"** — Ollama
çalışmıyor ya da model oluşturulmamış: `ollama create qwen3-8b-pilot -f
ollama/Modelfile.qwen3-8b-pilot` (önce `ollama pull qwen3:8b`).

**Foundry Local endpoint bulunamıyor** — yalnız `RAG_LLM_RUNTIME=foundry` ile ilgili; servis
çalışıyor olmalı. Port otomatik bulunamazsa elle sabitleyin:

```bash
set FOUNDRY_LOCAL_ENDPOINT=http://localhost:PORT     # PowerShell: $env:FOUNDRY_LOCAL_ENDPOINT="..."
```

**GPU bellek hatası** (`BFCArena ... Failed to allocate memory`, HTTP 500) — bağlam çok
uzun. `llm_client.py` içindeki `MAX_CHUNK_CHARS` / `MAX_CONTEXT_CHARS` değerlerini ya da
`TOP_K`'yı düşürün. 8 GB VRAM'de mevcut varsayılanlar çalışır durumdadır.

**Benchmark sırasında "Connection error"** — LLM servisi (Ollama; Foundry yolunda Foundry Local)
koşu ortasında çökmüş olabilir.
Bu satırlar skorlamayı bozar (hata satırları ret sayılmazsa metrikler yapay olarak iyi
görünür); koşuyu geçersiz sayıp tekrarlayın — örnek olarak v4 deneyi bu yüzden iptal edildi.

**`database is locked`** — ingest sürerken sorgu atılmış olabilir. Bağlantılar WAL ve
30 sn timeout ile açılıyor, genelde kendiliğinden çözülür.

**Konsolda `UnicodeEncodeError`** — Windows konsolu cp1254 kullanıyor; `chcp 65001` ile
UTF-8'e geçin.

---

## Lisans

MIT — bkz. [license](license).
