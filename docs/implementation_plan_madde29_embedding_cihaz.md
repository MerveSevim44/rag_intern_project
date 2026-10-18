# Plan: madde 29 — Retrieval ve Doküman Embedding Cihazının Sabitlenmesi

Tarih: 2026-10-18. Taban: `64f91a1`. Kapsam ölçümü:
[experiments/madde29_embedding_cihaz/README.md](../experiments/madde29_embedding_cihaz/README.md).

---

## 1. Sorun ve Arka Plan (Özet)

- **Gözlem:** Madde 24 Adım 0 ve Madde 27 araştırmalarında, `src/` kod tabanı v8'den beri retrieval açısından aynı kalmasına rağmen, farklı oturumlarda 3 `semantic_rag` sorusunda (test_2 #36, test_4 #93, negatif #217) son 1–2 adayın v8'dekinden farklı sıralandığı gözlendi.
- **Kök Neden Analizi:** Farklılıkların oturum içi rastgelelik değil, Ollama'nın `bge-m3` modelini çalışma anındaki kaynaklara göre bazen **CPU**'ya bazen **GPU**'ya yüklemesinden kaynaklandığı saptandı. İki donanım yolu arasındaki sayısal hassasiyet farkı (kosinüs benzerliği ~0.9982'ye kadar iniyor), hibrit RRF sıralamasında birbirine çok yakın skorlu sınır adayların (ör. RRF 0.9307 vs 0.9303) yer değiştirmesine yol açıyordu.
- **Madde 27 Kapsamı:** Skorlayıcı tarafı (`evaluation/benchmark_eval.py`) `SEMANTIC_NUM_GPU = 0` ile CPU'ya sabitlendi ve NaN koruması eklendi (`ecc7f5a`). Ancak retrieval sorgu üretimi (`src/embedder.py:get_embedding`) bilinçli olarak açık bırakıldı; çünkü veritabanındaki (`rag.db`) 911 chunk'ın hangi cihazda üretildiği bilinmiyordu.

---

## 2. Madde 29 Ölçüm Bulguları (`experiments/madde29_embedding_cihaz/`)

`experiments/madde29_embedding_cihaz/cihaz_tespiti.py` ile veritabanındaki 911 chunk üç farklı yerleşimde (`cpu`: num_gpu=0, `kismi_24`: num_gpu=24, `gpu`: num_gpu=99) birebir taklit edilerek yeniden embed edildi ve `rag.db`'deki kayıtlı vektörlerle kıyaslandı:

1. **`rag.db` %100 GPU ile Üretilmiştir:**
   - 10 kaynaktaki **911 chunk'ın tamamı (%100)**, `kismi_24` ve `gpu` yerleşimleriyle **bayt bayt aynıdır** (`{'kismi_24+gpu': 911}`).
   - `cpu` yerleşimiyle **hiçbir chunk bayt bayt aynı çıkmamıştır** (0/911; kosinüs min: 0.997198, medyan: 0.999916, max: 0.999999).
2. **Kısmi GPU ile Tam GPU Çıktısı Bit Düzeyinde Özdeştir:**
   - Ollama'nın 24 katmanı GPU'ya alması (`kismi_24`) ile tüm katmanları GPU'ya alması (`gpu`) aynı floating-point çıktılarını vermektedir (kosinüs = 1.000000, mutlak fark = 0.0).
3. **Gruplama (Batch Size) Sayısal Sapma Yaratmaz:**
   - 111 chunk'lık örneklemde tek tek embed (`input=str`) ile 64'lü grup (`input=list[str]`) kıyaslandığında 111/111 bayt bayt aynı çıkmıştır.
4. **Veri Bütünlüğü:**
   - Kaynak içi ID boşluğu yoktur; tüm kaynaklar tek seferde ardışık ID'lerle ingest edilmiştir.

---

## 3. Mimari Karar ve Seçenekler

| Kriter | Seçenek A: Sorguyu GPU'ya Sabitlemek (`num_gpu=99`) [ÖNERİLEN] | Seçenek B: Sorgu ve DB'yi CPU'ya Sabitlemek (`num_gpu=0`) |
|---|---|---|
| **`rag.db` Durumu** | Dokunulmaz (911 chunk zaten GPU, %100 uyumlu) | Tüm DB yeniden ingest edilmek zorunda |
| **Geçmiş Benchmark Uyumu (v1–v8)** | %100 korunur (tarihsel koşular GPU DB ile yapıldı) | Sınır adaylarda milimetrik kaymalar oluşur |
| **Sorgu Gecikmesi** | Çok hızlı (~10–30 ms) | Daha yavaş (~100–300 ms) |
| **Skorlayıcı ile İlişki** | Skorlama (`SEMANTIC_NUM_GPU=0`) bağımsız toplu iş | İki taraf da CPU'da olur |
| **Uygulama Riski** | Çok düşük (yalnızca sorgu/ingest parametresi) | Orta (tüm veritabanı değişimi) |

### Karar: Seçenek A (GPU Sabitleme + Yapılandırılabilirlik)

- Retrieval sorgu embedding'i (`src/embedder.py`) varsayılan olarak GPU'ya (`EMBED_NUM_GPU = 99`) sabitlenir.
- Çevre değişkeni (`RAG_EMBED_NUM_GPU`) ile gerekirse CPU'ya veya farklı katman sayısına geçiş esnekliği sağlanır.
- `src/ingest.py` da aynı yapılandırmayı kullanarak ileride eklenecek yeni dosyaların da GPU ile uyumlu yazılmasını garanti eder.

---

## 4. Yapılacak Değişiklikler

### 4.1. `src/embedder.py`
- Sabit tanımlanır:
  ```python
  import os
  # Retrieval ve ingest embedding cihazı (backlog madde 29).
  # rag.db'deki 911 chunk'ın tamamı GPU ile üretilmiştir (experiments/madde29_embedding_cihaz/).
  # Sorgu embedding'ini GPU'ya sabitlemek oturumlar arası sayısal kaymayı önler.
  EMBED_NUM_GPU = int(os.getenv("RAG_EMBED_NUM_GPU", "99"))
  ```
- `get_embedding(text, model=EMBED_MODEL, keep_alive=OLLAMA_KEEP_ALIVE, num_gpu=EMBED_NUM_GPU)`:
  - `ollama.embed(..., options={"num_gpu": num_gpu})` eklenir.
- `get_embeddings(texts, model=EMBED_MODEL, batch_size=16, keep_alive=OLLAMA_KEEP_ALIVE, num_gpu=EMBED_NUM_GPU)`:
  - `ollama.embed(..., options={"num_gpu": num_gpu})` eklenir.

### 4.2. `src/ingest.py`
- CLI argümanı `--num_gpu` eklenir (varsayılan: `EMBED_NUM_GPU`).
- `get_embeddings` çağrısına `num_gpu` iletilir.

### 4.3. `tests/test_embedder_device.py`
- Sahte (`mock`) Ollama client ile:
  - `get_embedding("test")` çağrısının varsayılan olarak `options={"num_gpu": 99}` geçirdiği,
  - `num_gpu=0` geçildiğinde `options={"num_gpu": 0}` ilettiği,
  - `get_embeddings(["test1", "test2"])` çağrısının aynı `options`'ı taşıdığı
  birim testlerle doğrulanır.

---

## 5. Başarı Ölçütleri

1. **Birim Testler:** `tests/test_embedder_device.py` eksiksiz geçer.
2. **Argüman Doğrulaması:** `src/embedder.py` üzerinden yapılan gerçek çağrıda `ollama ps` çıktısında bge-m3'ün `100% GPU` (veya VRAM kısıtında `kismi_24`) olduğu doğrulanır.
3. **Retrieval Kararlılığı (Repeatability):** Madde 24 Adım 0'da kaydığı bilinen 3 sınır soru (test_2 #36, test_4 #93, negatif #217) bağımsız iki Python oturumunda çalıştırıldığında retrieval aday listeleri ve skorları **0 fark ile birebir aynı** çıkar.
4. **Mevcut Test Paketi:** Kırık olduğu bilinen Madde 17 haricindeki tüm testler yeşil kalır.

---

## 6. Adım Adım Uygulama Planı

- **Adım 1: Kod Değişikliği ve Birim Testler**
  - `src/embedder.py` ve `src/ingest.py`'ye `num_gpu` opsiyonu eklenir.
  - `tests/test_embedder_device.py` yazılır ve çalıştırılır.
- **Adım 2: Kayan Sorguların Doğrulanması (Retrieval Determinism Test)**
  - `experiments/madde29_embedding_cihaz/dogrulama_kayan_sorgular.py` ile #36, #93 ve #217 soruları test edilir; 2 ayrı süreçte sonuçların %100 eşleştiği teyit edilir.
- **Adım 3: Backlog Güncellemesi ve Kapanış**
  - `docs/backlog_retrieval.md` Madde 29 "Düzeltildi" olarak işaretlenir.
  - Sonuçlar ve commit özeti kullanıcıya sunulur.

---

## 7. Geri Dönüş (Rollback) Stratejisi

- `rag.db`'ye herhangi bir yazma yapılmadığı için, herhangi bir beklenmedik durumda kod değişikliği `git revert` ile risksiz şekilde geri alınabilir.
