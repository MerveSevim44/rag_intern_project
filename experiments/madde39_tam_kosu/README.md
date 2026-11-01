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

# Kapanış (2026-11-01) — tam koşu, yeni referans

C kararıyla tüm setler sıralı koşuldu (`kosu.py`). Birleşik sonuç: `tum_sonuclar.json`;
set bazlı: `{SET}/sonuclari.csv`, `ortam.json`, `hata_tekrar.csv`.

| Set | n | Sınıf | Not |
|---|---|---|---|
| test_1 | 30 | 30 TP | #2 tekrarda düzeldi |
| test_2 | 30 | 26 TP, 2 FN, 2 HATA (kalıcı) | #43/#53 bilinen kronik GPU hatası, hariç |
| test_3 | 30 | 27 TP, 3 FN | #62 tekrarda düzeldi |
| test_4 | 10 | 9 TP, 1 FN | #92/#94 tekrarda düzeldi |
| test_5 | 15 | 13 TN, 2 FP | #102/#110 tekrarda düzeldi |
| test_negative | 32 | 29 TN, 1 FN, 2 FP | — |
| **GENEL** | **145** | **92 TP, 42 TN, 7 FN, 4 FP** | 147 − 2 kronik HATA |

- **Negatif set sıfır regresyon:** FP {#224, #232} madde 33 prod kaydıyla birebir aynı.
- **v8 farkları (6 soru) hepsi açıklandı:** #91/#103 bilinen düzelmeler (madde 33/24);
  #50 içerik hâlâ yanlış ama sınıf TP (madde 21/36, yeni değil); **#48/#90 (TP→FN)
  açıklanamadı** — bağlam aynı (Ön-ölçüm A), `tekrar_kontrol.py` ile 3/3 kararlı FN
  (rastgele değil); en olası neden v8'in top_k/ingest öncesi farklı bir taban olması.
  Ayrı madde açılmadı.

## Koşu sırasında bulunan ve düzeltilen operasyonel hatalar (`kosu.py`)

1. `foundry model unload` servisin taban belleğini (~4.9 GB) bırakmıyor; yalnız
   `foundry service stop` bırakıyor. → set başına tam stop/start.
2. **`foundry service stop/start`'ı `capture_output=True` ile çağırmak Windows'ta
   süresiz kilitleniyordu** (pipe tutamacı sorunu, `subprocess.run`'ın timeout'u da
   işlemiyor) → `stdout=DEVNULL, stderr=DEVNULL` ile çağrılıyor.
3. Ollama embed isteğine hiç yanıt vermeden asılı kalabiliyor (CPU'ya düşmekten
   farklı, tam hang) → her set öncesi `curl` tabanlı sağlık kontrolü + otomatik
   yeniden başlatma (`ollama app.exe`). İlk yazılan `urllib` tabanlı kontrol de
   benzer şekilde kilitlenmişti, `curl` alt sürecine çevrildi.
4. RAM eşiği 2 → 4 GB (1 numaralı düzeltme sonrası daha fazla pay mümkün).
5. `kosu.py` yalnız `sonuclari.csv` yoksa koşuyor; test_5'te 2026-10-30'dan kalma
   eski bir dosya sessizce yeniden kullanıldı (koşulmadı) — silinip yeniden koşuldu.
