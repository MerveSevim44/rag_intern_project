# Madde 29 — rag.db Doküman Embedding'leri Cihaz Tespiti ve Gruplama Ölçümü (2026-10-18)

Kod tabanı: `64f91a1`. Ollama 0.21.2, `bge-m3:latest`. Servis: Ollama (GPU boş, başlangıçta 83 MB VRAM).

| Dosya | Ne yapar |
|---|---|
| `cihaz_tespiti.py` | `rag.db`'deki 911 chunk'ı 3 farklı yerleşimde (`cpu`: num_gpu=0, `kismi_24`: num_gpu=24, `gpu`: num_gpu=99) yeniden embed eder; DB'deki vektörle bayt bayt ve kosinüs benzerliğiyle kıyaslar. Ayrıca gruplama (batch size 64 vs 1'erli) etkisini ölçer. |
| `cihaz_tespiti.jsonl` | 911 chunk'ın her biri için kaynak, kosinüs değerleri, maksimum mutlak fark ve bayt bayt eşleşme sınıfı. |
| `sonuc_cihaz_tespiti.txt` | Ölçüm özeti, `ollama ps` işlemci dağılımları ve kaynak bazlı eşleşme dağılımı. |
| `log_cihaz_tespiti.txt` | Çalışma anı logları ve terminal çıktısı. |
| `kod_durumu.txt` | Ölçümün yapıldığı commit hash'i (`64f91a1`). |

---

## 1. Amaç ve Hipotez

Madde 27'de (`ecc7f5a`), Ollama'nın bge-m3 modelini oturuma göre dinamik olarak CPU veya GPU'ya yüklediği ve iki yolun vektörlerinin birebir aynı olmadığı (kosinüs min ~0.9982) tespit edilmişti. Skorlayıcı tarafı `SEMANTIC_NUM_GPU=0` ile CPU'ya sabitlenmiş, ancak retrieval tarafı açık bırakılmıştı (`docs/backlog_retrieval.md` madde 29).

Retrieval sorgu embedding'ini (`src/embedder.py`) sabitlemeden önce cevaplanması gereken temel soru şuydu:
**`rag.db`'deki mevcut doküman embedding'leri hangi cihaz yerleşimiyle üretildi?**

Eğer dokümanlar CPU'da üretildiyse sorguyu CPU'ya sabitlemek; GPU'da üretildiyse sorguyu GPU'ya sabitlemek (veya DB'yi yeniden ingest etmek) gerekecektir.

---

## 2. Ölçüm Koşulları ve Yerleşimler

`ingest.py`'nin çağrısı (`BATCH_SIZE=64`, `keep_alive="5m"`) birebir taklit edilerek 10 kaynaktan gelen 911 chunk test edildi:

1. **`cpu` (`num_gpu=0`)**: Ollama `100% CPU` (1.1 GB RAM).
2. **`kismi_24` (`num_gpu=24`)**: Ollama `42%/58% CPU/GPU` (24/25 katman GPU'da, 1.2 GB).
3. **`gpu` (`num_gpu=99`)**: Ollama `100% GPU` (1.2 GB VRAM).

Her yerleşim öncesinde model `keep_alive=0` ile bellekten boşaltılarak taze parametrelerle yüklenmesi sağlandı.

---

## 3. Ölçüm Sonuçları

### 3.1. Kaynak Başına Sınıf Dağılımı (DB Vektörüyle Bayt Bayt Eşleşme)

| Kaynak | Chunk Sayısı | `kismi_24 + gpu` | `cpu` |
|---|---|---|---|
| `728_profiles.json` | 733 | **733 (%100)** | 0 |
| `airports.json` | 30 | **30 (%100)** | 0 |
| `lsarSist-H8_FourierTransform.pdf` | 14 | **14 (%100)** | 0 |
| `lsarSist-H9_ZTransform.pdf` | 19 | **19 (%100)** | 0 |
| `mock-transactions.json` | 12 | **12 (%100)** | 0 |
| `Summer School Foundry Local Plan.docx` | 8 | **8 (%100)** | 0 |
| `test1.txt` | 9 | **9 (%100)** | 0 |
| `test2.txt` | 10 | **10 (%100)** | 0 |
| `us-states-with-detail.json` | 50 | **50 (%100)** | 0 |
| `8-Baglamdan_bagimsiz_dilbilgisi.pdf` | 26 | **26 (%100)** | 0 |
| **TOPLAM** | **911** | **911 (%100)** | **0 (%0)** |

### 3.2. Kosinüs Benzerliği Dağılımı (DB ile Kıyas)

- **`cos(DB, kismi_24)`**: min = **1.000000**, medyan = **1.000000**, max = **1.000000** (911/911 bayt bayt aynı)
- **`cos(DB, gpu)`**: min = **1.000000**, medyan = **1.000000**, max = **1.000000** (911/911 bayt bayt aynı)
- **`cos(DB, cpu)`**: min = **0.997198**, medyan = **0.999916**, max = **0.999999** (0/911 bayt bayt aynı)

### 3.3. Gruplama (Batching) Etkisi

- **Örneklem**: 10 kaynaktan ilk 12'şer chunk (toplam 111 chunk).
- **Test**: CPU'da tek tek embed (`input=str`) vs 64'lük grup (`input=list[str]`).
- **Sonuç**: **111/111 bayt bayt aynı**, kosinüs min = **1.000000**.
- **Çıkarım**: Ollama bge-m3'te gruplama (batching) sayısal hiçbir sapmaya yol açmaz.

### 3.4. Bütünlük / ID Boşlukları

- Kaynak içi ID boşlukları: **Yok** (bütün kaynaklar tek seferde ardışık ID'lerle ingest edilmiş).

---

## 4. Temel Çıkarımlar

1. **`rag.db` Kesin Olarak GPU'da Üretilmiştir:**
   911 chunk'ın tamamı (%100) `num_gpu=99` ve `num_gpu=24` yerleşimleriyle bit düzeyinde (bayt bayt) özdeştir.
2. **Kısmi GPU ile Tam GPU Arasında Fark Yoktur:**
   24 katmanın GPU'da olması (`kismi_24`) ile tüm modelin GPU'da olması (`gpu`) birebir aynı floating-point çıktıları üretmektedir.
3. **Retrieval Kaymasının Kök Nedeni Doğrulandı:**
   `src/retrieval.py` -> `src/embedder.py:get_embedding(query)` çağrısı cihaza dair herhangi bir opsiyon (`num_gpu`) belirtmediği için, Ollama çalışma anındaki VRAM durumuna göre bazen CPU'yu bazen GPU'yu seçmektedir.
   - Ollama CPU seçtiğinde, `query` vektörü ile DB'deki GPU `doc` vektörleri arasında ~0.0028'e varan kosinüs kayması oluşmaktadır.
   - Sınırda (borderline) RRF skoruna sahip dokümanlarda (ör. test_2 #36, test_4 #93, negatif #217) sıralama bu kayma yüzünden değişmektedir.
   - Ollama GPU seçtiğinde ise sorgu ve doküman aynı donanım hassasiyetinde buluştuğu için sonuçlar stabil kalmaktadır.
