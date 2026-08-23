# RAG Soru-Cevap

Kendi dokümanlarınız (`.txt`, `.pdf`, `.docx`, `.json`, `.jsonl`) üzerinde Türkçe soru-cevap yapan,
tamamen **yerelde** çalışan bir RAG (Retrieval-Augmented Generation) uygulaması.

Hiçbir veri dışarı çıkmaz: embedding **Ollama** ile, cevap üretimi **Foundry Local**
ile makinede yapılır; indeks tek dosyalık bir SQLite veritabanında (`rag.db`) tutulur.

## Nasıl çalışır?

```
Doküman  →  chunk'lara böl  →  embedding (bge-m3)  →  SQLite (rag.db)
                                                          │
Soru  →  embedding  →  cosine similarity (top_k)  ────────┘
                            │
                            └→ reranker (bge-reranker-v2-m3, top_n)
                                    │
                                    └→ bağlam + soru → LLM → kaynaklı cevap
```

Cosine similarity hızlı ama kaba bir ön elemedir; Cross-Encoder reranker soru ile
chunk'ı birlikte değerlendirip son sıralamayı yapar. Cevaba giren her parçanın
dosya adı ve sayfa/paragraf bilgisi korunur, böylece cevaplar kaynak gösterebilir.

## Gereksinimler

- Python 3.10+
- [Ollama](https://ollama.com) — embedding modeli için:
  ```bash
  ollama pull bge-m3
  ```
- [Foundry Local](https://learn.microsoft.com/azure/ai-foundry/foundry-local/) — cevap üreten LLM için.
  Varsayılan model `qwen2.5-7b-instruct-cuda-gpu:4` (alternatif: `Phi-4-mini-instruct-cuda-gpu:5`).
  Servis çalışır durumda olmalı; portu uygulama otomatik bulur.
- Reranker modeli (`BAAI/bge-reranker-v2-m3`) ilk çalıştırmada Hugging Face'ten indirilir.

## Kurulum

```bash
python -m venv rag_project
rag_project\Scripts\activate        # Linux/macOS: source rag_project/bin/activate
pip install -r requirements.txt
```

## Kullanım

### 1. Dokümanları indeksle

Dosyaları `data/` klasörüne koyup:

```bash
python ingest.py
```

Daha önce indekslenmiş dosyalar atlanır. Bir dosyayı güncellediyseniz `--force` ile
yeniden indeksleyin:

```bash
python ingest.py --force
python ingest.py --data_dir data --db_path rag.db --model bge-m3 --batch_size 16
```

Her dosya kendi başına commit edilir; ortada bir dosya hata verse bile öncekiler kaybolmaz.

### 2. Arayüzü başlat

```bash
streamlit run app.py
```

Kenar çubuğundan model seçip yükleyebilir, doğrudan tarayıcıdan doküman yükleyip
indeksleyebilirsiniz — `data/` klasörünü kullanmak zorunlu değil.

### 3. Sadece arama (arayüzsüz)

```bash
python retrieval.py
```

### 4. Test setini çalıştır

`test_sorulari.csv` içindeki soruları uçtan uca çalıştırır; cevap, bulunan kaynaklar
ve süreyi `test_sonuclari.csv` dosyasına yazar:

```bash
python run_tests.py
```

## Dosyalar

| Dosya | Görevi |
|---|---|
| [ingest.py](ingest.py) | Doküman okuma, chunk'lama, embedding, SQLite şeması ve migrasyonu |
| [embedder.py](embedder.py) | Ollama embedding'leri, cosine similarity, Cross-Encoder reranker |
| [retrieval.py](retrieval.py) | Soruya en alakalı chunk'ları bulma (arama + reranking) |
| [llm_client.py](llm_client.py) | Foundry Local endpoint keşfi, model yükleme, prompt ve bağlam kırpma |
| [app.py](app.py) | Streamlit arayüzü |
| [run_tests.py](run_tests.py) | Toplu test koşucusu |

## Ayarlar

Sık değiştirilen sabitler dosyaların başında duruyor:

- `retrieval.py` → `TOP_K` (aday sayısı), `RERANK_TOP_N` (nihai sonuç sayısı)
- `ingest.py` → `EMBED_MODEL`, `BATCH_SIZE`, `DB_PATH`, `DATA_DIR`
- `llm_client.py` → `DEFAULT_MODEL_ID`, `MAX_ANSWER_TOKENS`, `MAX_CHUNK_CHARS`, `MAX_CONTEXT_CHARS`

## Sorun giderme

**"Embedding oluşturulamadı"** — Ollama çalışmıyor ya da `bge-m3` yüklü değil:
`ollama list` ile kontrol edin.

**Foundry Local endpoint bulunamıyor** — servis çalışıyor olmalı. Port otomatik
bulunamazsa elle sabitleyin:

```bash
set FOUNDRY_LOCAL_ENDPOINT=http://localhost:PORT     # PowerShell: $env:FOUNDRY_LOCAL_ENDPOINT="..."
```

**GPU bellek hatası (`BFCArena ... Failed to allocate memory`, HTTP 500)** — bağlam
çok uzun. `llm_client.py` içindeki `MAX_CHUNK_CHARS` / `MAX_CONTEXT_CHARS` değerlerini
veya `TOP_K`'yı düşürün. 8 GB VRAM'de mevcut varsayılanlar çalışır durumdadır.

**`database is locked`** — ingest sürerken sorgu atılmış olabilir. Bağlantılar WAL ve
30 sn timeout ile açılıyor, genelde kendiliğinden çözülür.

**Konsolda `UnicodeEncodeError`** — Windows konsolu cp1254 kullanıyor:
`chcp 65001` ile UTF-8'e geçin.

## Lisans

MIT — bkz. [license](license).
