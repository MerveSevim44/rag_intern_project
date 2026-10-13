# Madde 27 — NaN embedding → sessiz `semantic_sim` 0.0: kapsam ölçümü (2026-10-13)

Kod `754ed43`. Ollama 0.21.2, bge-m3. Servis: Ollama (+ bir taramada Foundry).

| Dosya | Ne yapar |
|---|---|
| `nan_tarama.py` → `tarama_foundry_yok.jsonl` | Kayıtlı koşulların 701 benzersiz cevap + referans metni, varsayılan çağrı (`benchmark_eval._embed_text` ile aynı) |
| `foundry_yuklu_tarama.py` → `tarama_foundry_yuklu.jsonl` | Aynı tarama, qwen2.5 Foundry'de GPU'da yüklüyken |
| `gpu_cpu_karsilastirma.py` → `gpu_cpu.jsonl`, `sonuc_gpu_cpu.txt` | Aynı 701 metin, bge-m3 CPU'ya (`num_gpu=0`) ve GPU'ya (`num_gpu=99`) zorlanarak |

## 1. Skorlayıcıdaki 0.0 yolları (`benchmark_eval.compute_semantic_similarity`)

Beş yol 0.0 döndürüyor ve 0.0 ortalamaya gerçek skor gibi giriyor (`accuracy_pool`):
1. cevap ya da referans listesi boş, 2. embedding servisi yok
(`_semantic_backend_ready`; tüm koşu için), 3. vektör normu 0,
4. **herhangi bir istisna** (`except Exception` → 0.0), 5. negatif kosinüs → 0'a kırpılır.

(4)'ün ek bir etkisi: referanslardan **birinin** embedding'i hata verse bile
diğer referanslarla bulunmuş iyi skor da atılıyor — NaN cevaptan da referanstan da
gelebilir.

## 2. Kayıtlı koşulardaki görülme

9 skor dosyası, ~800 pozitif satır: `semantic_sim` = 0.0 olan **tek satır**
v7 test_2 #36 — yalnız madde 25 yeniden skorunda (2026-10-11); v7'nin özgün
raporunda aynı satır 86.7.

## 3. Bugün tekrar üretilebiliyor mu — ve NEREDE

| Koşul | bge-m3 işlemcisi (`ollama ps`) | NaN / hata (701 metin) |
|---|---|---|
| Varsayılan çağrı | **100% CPU** | 0 |
| Varsayılan çağrı, Foundry qwen GPU'da yüklü | 100% CPU | 0 |
| `num_gpu=0` (CPU zorla) | 100% CPU | 0 |
| `num_gpu=99` (GPU zorla) | **100% GPU** | **1 — tam olarak v7 test_2 #36'nın cevabı**, 3/3 deterministik (`json: unsupported value: NaN`, 500) |

- **NaN GPU yoluna özgü ve metne özgü:** 701 metnin yalnız biri, yalnız GPU'da.
  #36'nın referansları iki yolda da temiz (madde 25'teki "cevap metni" atfı doğru).
- **Ollama işlemciyi kendi seçiyor:** bugün varsayılan çağrı, VRAM'in 1.7/8 GB'ı
  doluyken bile CPU'ya yüklüyor; 11 Ekim'de (NaN alındığında) GPU'ya yüklemiş
  olmalı. Foundry'nin GPU'da olması bugün seçimi değiştirmedi.

## 4. Madde 29 ile bağlantı: iki yolun vektörleri aynı değil

`cosine(CPU vektörü, GPU vektörü)`, 700 metin: min **0.998212**, medyan 0.999989,
max 1.000000; **83 metin < 0.9999**, 3 metin < 0.999. Yani:
- `semantic_sim`'in madde 25'te gördüğümüz ±0.1–0.2 gürültüsü ve
- madde 29'un oturumlar arası retrieval kayması (sınırda eşit skorlu adaylar)

için somut bir mekanizma: **Ollama'nın o oturumda bge-m3'ü CPU'ya mı GPU'ya mı
yüklediği.** "Foundry yüklü vs değil" değil, Ollama'nın cihaz seçimi.
(Retrieval tarafının doğrulaması madde 29'un işi; burada yalnız embedding
düzeyinde ölçüldü.)

## 5. Çözüm seçenekleri (ölçümle değerlendirildi)

| Seçenek | Değerlendirme |
|---|---|
| **R — aynı çağrıyı yeniden dene** | **Reddedildi:** GPU yolunda 3/3 deterministik NaN; retry aynı sonucu verir. |
| **F — hata olursa CPU'ya düşüp yeniden dene** | NaN'ı kurtarır (CPU 0/701), ama tek bir skoru başka cihazdan üretir: koşu içinde iki cihaz karışır ve cihaz bağımlılığı gizlenir. Tek başına önerilmez. |
| **M — hesaplanamayan skor eksik değer (None)** | Backlog'daki yön. Her başarısızlık türünü (servis, NaN, boş vektör) kapsar; ortalamadan çıkarılır ve sayısı raporlanır. Küçük, savunma amaçlı. |
| **P — skorlayıcının embedding'ini tek cihaza sabitle (`num_gpu=0`)** | Kök nedene yönelik: bugünkü taramada NaN 0/701, ve skorlama oturumdan oturuma aynı cihazda (±0.1–0.2 gürültünün kaynağını kapatır). Bedel: tüm `semantic_sim` değerleri bir kez ≤ ~0.2 puan oynar (eski raporlarla birebir karşılaştırma için yeniden skor gerekir). CPU hızı yeterli (701 metin 2.7 dk). |

Öneri: **M + P birlikte** — P NaN'ı ve gürültüyü kaynağında kaldırır, M ise
geriye kalan her hata türünde 0.0 yerine "eksik" yazar.
