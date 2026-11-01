# Madde 39 — ön-ölçüm A: GPU/CPU embedding kayması nihai bağlamı ne kadar değiştiriyor?

Tam koşuya başlamadan önce (bellek baskısında Ollama'nın sessizce CPU'ya düşmesi,
bkz. madde 39 ve madde 29'un koşullu notu) sorgu embedding'inin cihazdan bağımsız
olduğunu doğrulamak için: 147 soru (test_1–5 + test_negative), LLM yok, iki ayrı
süreçte — `RAG_EMBED_NUM_GPU=99` (gpu) ve `=0` (cpu) — `retrieve()` çağrılır, nihai
bağlam karşılaştırılır (`fark.py` → `fark_gpu.jsonl`, `fark_cpu.jsonl`, `sonuc_fark.txt`).
Yerleşim sağlaması: sabit bir metnin embedding özeti mod başında ve sonunda beklenenle
eşleşiyor mu kontrol edilir (ikisinde de eşleşti). gpu kaydı madde 33 prod duman kaydıyla
147/147 birebir aynı (ek sağlama).

## Sonuç (a): fark küçük, yalnız dolgu sırasında

| | aynı | sıra farklı | küme farklı | 1. chunk farklı |
|---|---|---|---|---|
| **GENEL (147)** | **140 (%95.2)** | 0 | 7 | 1 |

7 farklılığın 6'sı yalnız bağlamın son (en düşük güvenli) chunk'ında, rerank skorları
birbirine çok yakın (fark ≤0.0015, mutlak skor ≤0.01 — "net kazanan yok" bölgesi, madde
24/34'teki gibi): test_1#11 (v8 TP), test_2#36 (TP), test_2#46 (TP), test_5#102 (TN),
test_5#107 (FP, bilinen vaka), test_negative#215 (TN). Yalnız **test_2#35**'te 1. chunk
da değişiyor (0.556 vs 0.517); bu, madde 33'ün zaten işaretlediği BM25 korpus istatistiği
kaymasına duyarlı bir soru (backlog: "#35/#46, BM25 korpus istatistiği kayması; cevaplar
aynı" — madde 33 Adım 2'de ölçülmüş, cevap değişmiyor).

**Değerlendirme:** GPU/CPU embedding farkı pratikte neredeyse etkisiz; madde 29'un
"düzeltildi" bulgusu (cosine ~0.9982, RRF skorları fark göstermedi) 147 sorunun tamamında
doğrulandı. Etkilenen 7 sorudan 6'sı düşük güven bölgesinde ve zaten bilinen/zararsız;
1'i (#35) madde 33'te ayrıca doğrulanmış, cevabı değişmeyen bir vaka.

## Sonuç (b): üretim ortamı aynı VRAM kısıtını paylaşıyor mu?

`src/app.py`: Streamlit uygulaması da `load_model()` (LLM) çağrısını `get_top_chunks()`
(retrieval/embedding) çağrısından **önce** yapıyor — benchmark'ın (`run_tests.py`)
izlediği sırayla aynı. Repoda ayrı bir dağıtım/Docker dosyası yok; README referans
donanımı "8 GB VRAM" olarak veriyor, yani tek makine varsayımı üretim için de geçerli
görünüyor. **Üretim, bu VRAM kısıtını muhtemelen paylaşıyor** — ölçülmedi (gerçek bir
Streamlit oturumunda VRAM/RAM izlenmedi), ama kod yolu ve donanım varsayımı aynı.

## Karar: C (bugünkü yolu olduğu gibi koş), B+C değil

(a)'daki fark küçük ve zaten bilinen düşük-güven bölgesinde; (b) üretim de aynı riski
taşıyor, yani CPU embedding bugünkü sistemin gerçek davranışının bir parçası. Ayrı bir
B fazı (GPU'yu garanti eden iki aşamalı koşu) üretimden farklı, yapay bir referans
üretir. Tam benchmark + negatif set, bugünkü üretim yoluyla (LLM önce yüklenir) koşulur;
her set `kosu.py`'nin `temiz` kontrolüyle (Ollama logu + nöbet özeti) işaretlenir — CPU'ya
düşerse not edilir ama koşu **durdurulmaz**, çünkü bu üretimin kendi davranışı.
