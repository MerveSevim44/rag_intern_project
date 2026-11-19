# qwen3-8b-pilot (Ollama) — madde 39 kampanyasının 147 soruluk tam koşusu (2026-11-18)

Bu klasör, `docs/backlog_retrieval.md`'deki "qwen3-8b (Ollama) ile 147 soruluk TAM kampanya + kritik 20'de
ikinci koşu" deney notunun (2026-11-18) ham çıktılarıdır. Karar notu DEĞİLDİR; yalnızca ölçüm.

**İçerik:**
- `run1/` — test_1…5 + test_negative (147 soru), qwen3-8b-pilot + Ollama, tek koşu, canlı `rag.db`
  (A1 re-ingest sonrası, özet `2eb2d68359e5`). `drv.py` ile üretildi; `ham_*.csv` = ilk deneme,
  `test_*.csv` = HATA alan sorular bir kez tekrarlanmış nihai sonuç (bkz. madde 35/39 kuralı).
- `run2/` — kritik 20 sorunun (#28 #30 #41 #43 #45 #47 #61 #62 #69 #71 #73 #74 #76 #83 #84 #85 #86
  #87 #88 #231) ikinci koşusu, gürültü/tekrar denetimi için.
- `judge1/`, `judge2/` — run1/run2'nin `gpt-oss-120b` (Groq) judge sonuçları (`judge_k{1,2}_*.csv`);
  `sonuc_k{1,2}_*.csv` judge'a giren ham sonuç kopyası.
- `drv.py` — 147 soruluk kampanya sürücüsü (set başına ayrı süreç, Ollama sağlık kontrolü, HATA tekrarı).
- `judge_loop.py` — kota-dayanıklı judge yürütücü (Groq günlük TPD limitine çarpınca bekleyip devam eder;
  bu koşuda Groq API key'i iki kez değişti — 401 ve günlük kota olayları `judge1.log` / `*.loop.log`'da).
- `analiz.py` / `analiz.out` — eski kampanyayla (`../head_*`, qwen2.5-7b/Foundry) karşılaştırma: sınıf
  dağılımı, judge ortalamaları, kritik-20 gürültü analizi, A1 re-ingest / code_interpreter ayrıştırması.
- `cnt.py`, `reg.py` — yan bulguları (yeni ret kalıbı, prompt sızıntısı, regresyon örnekleri) doğrulayan
  yardımcı script'ler.

**Karşılaştırma tabanı:** `../head_test_*` (bu klasörün bir üst dizini), A1 re-ingest ÖNCESİ `rag.db`
(özet `757e97059abb`) ile koşulmuştu — bu yüzden ham "eski→yeni" farkı model/runtime değişimiyle A1
ingest düzeltmesini (zaten production'da, qwen3 ile ilgisiz) karıştırıyor. Ayrıştırma ve düzeltilmiş
sonuçlar için backlog notuna bakın.
