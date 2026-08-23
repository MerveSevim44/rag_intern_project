# RAG Soru-Cevap

Kendi dokümanlarınız üzerinde Türkçe soru-cevap yapan, **tamamen yerelde** çalışan bir
RAG (Retrieval-Augmented Generation) uygulaması.

Hiçbir veri dışarı çıkmaz: embedding **Ollama** ile, cevap üretimi **Foundry Local** ile
makinenizde yapılır; indeks tek dosyalık bir SQLite veritabanında (`rag.db`) tutulur.

- **Desteklenen formatlar:** `.txt`, `.pdf`, `.docx`, `.json`, `.jsonl`
- **Kaynak gösterimi:** her cevap, dayandığı dosya ve sayfa/paragraf bilgisiyle birlikte gelir
- **Arayüz:** Streamlit; ayrıca komut satırından arama ve toplu test

---

## Hızlı başlangıç

```bash
# 1. Bağımlılıklar
python -m venv rag_project
rag_project\Scripts\activate        # Linux/macOS: source rag_project/bin/activate
pip install -r requirements.txt

# 2. Embedding modeli
ollama pull bge-m3

# 3. Dokümanları data/ klasörüne koyup indeksleyin
python ingest.py

# 4. Arayüzü açın
streamlit run app.py
```

Foundry Local servisinin çalışıyor olması gerekir (aşağıya bakın).

---

## Nasıl çalışır?

```
Doküman  →  chunk'lara böl  →  embedding (bge-m3)  →  SQLite (rag.db)
                                                          │
Soru  →  embedding  →  cosine similarity (TOP_K)  ────────┘
                            │
                            └→ reranker (bge-reranker-v2-m3, RERANK_TOP_N)
                                    │
                                    └→ bağlam + soru → LLM → kaynaklı cevap
```

Cosine similarity hızlı ama kaba bir ön elemedir; Cross-Encoder reranker soru ile chunk'ı
birlikte değerlendirip son sıralamayı yapar. Cevaba giren her parçanın dosya adı ve
sayfa/paragraf bilgisi korunur, böylece cevaplar kaynak gösterebilir.

---

## Gereksinimler

| Bileşen | Not |
|---|---|
| Python 3.10+ | — |
| [Ollama](https://ollama.com) | Embedding için. `ollama pull bge-m3` |
| [Foundry Local](https://learn.microsoft.com/azure/ai-foundry/foundry-local/) | Cevap üreten LLM. Varsayılan model `qwen2.5-7b-instruct-cuda-gpu:4` (alternatif: `Phi-4-mini-instruct-cuda-gpu:5`). Servis çalışır durumda olmalı; portu uygulama otomatik bulur. |
| `BAAI/bge-reranker-v2-m3` | Reranker; ilk çalıştırmada Hugging Face'ten otomatik iner. |

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
| `--batch_size` | `16` | Tek seferde embedding'i alınacak metin sayısı |
| `--force` | — | Zaten indekslenmiş dosyaları yeniden işle |

### Arayüzü başlat

```bash
streamlit run app.py
```

Kenar çubuğundan model seçip yükleyebilir, doğrudan tarayıcıdan doküman yükleyip
indeksleyebilirsiniz — `data/` klasörünü kullanmak zorunlu değil.

### Sadece arama (arayüzsüz)

```bash
python retrieval.py
```

### Test setini çalıştır

`test_sorulari.csv` içindeki soruları uçtan uca çalıştırır; cevabı, bulunan kaynakları ve
süreyi `test_sonuclari.csv` dosyasına yazar:

```bash
python run_tests.py
```

---

## Proje yapısı

| Dosya | Görevi |
|---|---|
| [ingest.py](ingest.py) | Doküman okuma, chunk'lama, embedding, SQLite şeması ve migrasyonu |
| [embedder.py](embedder.py) | Ollama embedding'leri, cosine similarity, Cross-Encoder reranker |
| [retrieval.py](retrieval.py) | Soruya en alakalı chunk'ları bulma (arama + reranking) |
| [llm_client.py](llm_client.py) | Foundry Local endpoint keşfi, model yükleme, prompt ve bağlam kırpma |
| [app.py](app.py) | Streamlit arayüzü |
| [run_tests.py](run_tests.py) | Toplu test koşucusu |
| [TEKNIK_RAPOR.md](TEKNIK_RAPOR.md) | Tasarım kararları ve değerlendirme sonuçları |

---

## Ayarlar

Sık değiştirilen sabitler ilgili dosyaların başında duruyor:

| Dosya | Sabit | Varsayılan |
|---|---|---|
| `retrieval.py` | `TOP_K` — cosine ile çekilen aday sayısı | `5` |
| `retrieval.py` | `RERANK_TOP_N` — reranker sonrası nihai sonuç sayısı | `3` |
| `ingest.py` | `EMBED_MODEL` / `BATCH_SIZE` | `bge-m3` / `16` |
| `ingest.py` | `DB_PATH` / `DATA_DIR` | `rag.db` / `data` |
| `llm_client.py` | `DEFAULT_MODEL_ID` | `qwen2.5-7b-instruct-cuda-gpu:4` |
| `llm_client.py` | `MAX_ANSWER_TOKENS` | `600` |
| `llm_client.py` | `MAX_CHUNK_CHARS` / `MAX_CONTEXT_CHARS` | `1500` / `6000` |

---

## Sorun giderme

**"Embedding oluşturulamadı"** — Ollama çalışmıyor ya da `bge-m3` yüklü değil;
`ollama list` ile kontrol edin.

**Foundry Local endpoint bulunamıyor** — servis çalışıyor olmalı. Port otomatik
bulunamazsa elle sabitleyin:

```bash
set FOUNDRY_LOCAL_ENDPOINT=http://localhost:PORT     # PowerShell: $env:FOUNDRY_LOCAL_ENDPOINT="..."
```

**GPU bellek hatası** (`BFCArena ... Failed to allocate memory`, HTTP 500) — bağlam çok
uzun. `llm_client.py` içindeki `MAX_CHUNK_CHARS` / `MAX_CONTEXT_CHARS` değerlerini ya da
`TOP_K`'yı düşürün. 8 GB VRAM'de mevcut varsayılanlar çalışır durumdadır.

**`database is locked`** — ingest sürerken sorgu atılmış olabilir. Bağlantılar WAL ve
30 sn timeout ile açılıyor, genelde kendiliğinden çözülür.

**Konsolda `UnicodeEncodeError`** — Windows konsolu cp1254 kullanıyor; `chcp 65001` ile
UTF-8'e geçin.

---

## Lisans

MIT — bkz. [license](license).
