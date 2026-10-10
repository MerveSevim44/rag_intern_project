# Plan: "Bu bilgi dokümanlarda bulunamadı" yanlış ret düzeltmeleri

## Context

Arayüzde cevabı veritabanında (ya da veri setinde) bulunan dört soru "Bu bilgi dokümanlarda bulunamadı." döndü. İncelemede LLM'in her seferinde kendisine verilen bağlama göre doğru davrandığı görüldü. Hatalar daha önceki aşamalardaydı: ingest, retrieval, bağlam kırpma ve router. Amaç bu dört kök nedeni ayrı, küçük, ölçülebilir değişikliklerle gidermek.

## Tespit edilen sorunlar

| # | Örnek soru | Kök neden | Katman |
|---|---|---|---|
| 1 | "G4.1 dilbilgisinde VT kümesinin elemanları nelerdir?" | BM25 tokenizer "G4.1"i `g4`+`1` diye bölüyor. `g4` tüm örneklerde geçtiği için Örnek 4.1 (chunk 4115) hibritte 8. sıraya düşüyor. Arayüz slider varsayılanı `top_k=5` olduğundan reranker'a hiç ulaşmıyor. | retrieval |
| 1b | (aynı) | Slider varsayılanı (5) ≠ `TOP_K` (8). Reranker'ın kurtarabileceği adaylar baştan eleniyor. | app |
| 2 | "Örnek 8'deki G_S.4.8.1 … 2k+1 …" | PDF sayfa 22–31 (Örnek/Cevap 2, 5, 6, 7, 8) resim olarak gömülü. pdfplumber yalnızca başlığı okuyor; 10 chunk 14 karakterlik başlıktan ibaret (4134–4143). test_1 #24–#29 bu yüzden cevaplanamaz. LLM-judge bu retleri yüksek puanlayıp açığı gizliyor. | ingest |
| 3 | "searchKeywords'ün türetildiği alanlar" | `MAX_CHUNK_CHARS=1500` LLM kopyasını baştan kesiyor. 728 profilin hepsinde `searchKeywords` 1698–2250. karakterde başladığı için hiçbir soruda modele ulaşmıyor (`slug`, `about`, `status` de öyle). Ek olarak: JSON ingest KEY satırlarını embedding için bilinçli olarak 2 kez yazıyor (`ingest.py:340`). Bu tekrar LLM bütçesini de harcıyor. | bağlam kırpma |
| 4 | "Deneyim yılları histogramı" | Router iki sinyali birlikte istiyor. (a) "histogram/grafik" `COMPLEXITY_SIGNALS`'ta yok. (b) "deneyim" `EXCLUDED_GENERIC_WORDS`'te olduğu için zayıf eşleşme; arayüzde seçilen tablosal dosya router'a hiç iletilmiyor. Sonuç: `semantic_rag` → ret. | router |

## Uygulama adımları

**Kural:** Her adım ayrı commit. Adım sonunda durulur ve onay beklenir. Plan, `docs/implementation_plan_retrieval_fixes.md` olarak ilk adımın kodu ile birlikte commit edilir.

### Adım 1 — Noktalı tanımlayıcı token'ı (yapıldı, commit bekliyor)
- `src/retrieval.py` `_base_tokens`: `[^\W\d_]+\d+(?:\.\d+)+` eşleşmeleri ek token olarak eklenir (`g4.1`). Parçalar korunur. Saf ondalık sayılar kapsam dışı.
- Doğrulama yapıldı: top_k=5'te 4115 1. sırada. G4.2 ve G4.3 soruları doğru örneği getiriyor. pytest 38/39 geçiyor; tek başarısız test bilinen `test_visualization` (backlog 17).
- Yeni test: `tests/` altına `_tokenize("G4.1 …")` içinde `g4.1` olduğunu ve `"3.200"`ün bütün token üretmediğini doğrulayan birim testi.

### Adım 2 — Slider varsayılanını TOP_K'ya bağla
- `src/app.py:317` `st.slider(... value=5 ...)` yerine `value=TOP_K` (`retrieval.TOP_K` import edilir, `RERANK_TOP_N` ile aynı yerden).
- Doğrulama: uygulama açılışında slider 8 görünür. G4.1 sorusu Adım 1 olmadan da doğru parçayı getirir (reranker 0.472 ile 1. sıraya koyuyor).

### Adım 3 — Router: görsel istek kelimeleri hesaplama sinyali
- `src/router.py` `COMPLEXITY_SIGNALS`'a eklenecekler: `histogram`, `grafik`, `grafiği`/`grafigi`, `görselleştir`/`gorsellestir`, `pasta`, `çubuk`/`cubuk`. `_contains_token` normalize ettiği için aksansız biçimler kontrol edilir; gerekmiyorsa eklenmez.
- Veri seti sinyali hâlâ şart olduğu için PDF soruları (örn. "Fourier grafiği") sandbox'a kaçmaz.

### Adım 4 — Router: seçili tablosal dosya = veri seti sinyali (2a)
- `src/router.py` `_analyze` / `route_query` / `classify_query`: yeni opsiyonel parametre `selected_dataset: Optional[str] = None`. Doluysa `has_dataset_signal = True`; debug'a `"selected_dataset"` olarak yazılır.
- `src/retrieval.py` `retrieve`: `source_filter` varsa mevcut `_resolve_dataset_name(source_filter)` (retrieval.py:342) çağrılır, sonuç `classify_query(..., selected_dataset=...)`a geçirilir. PDF seçiliyse `None` döner, davranış değişmez.
- Doğrulama: 728_profiles.json filtresiyle "Deneyim yılları histogramı" → `code_interpreter`. Filtresiz ve PDF filtreli davranış önceki gibi kalır.

### Adım 5 — Soruya duyarlı + tekrarsız chunk kırpma (LLM kopyası)
- `src/llm_client.py` `truncate_chunk_text(text, max_chars, query=None)`:
  1. Metin sınırın altındaysa dokunulmaz (bugünkü davranış).
  2. Satır bazında **ardışık tekrar eden satır bloklarını tekilleştir** (ingest'in KEY×2 tekrarı yalnızca LLM kopyasından düşer; DB ve embedding etkilenmez).
  3. Hâlâ uzunsa: `query` verildiyse, sorgu token'larıyla eşleşen satırlar önce ayrılır. Eşleşme alan adı ve değer üzerinden, `retrieval._tokenize` ile aynı normalizasyonla yapılır; import döngüsü çıkarsa basit bir lower + `\w+` eşleşmesi kullanılır. Kalan bütçe orijinal sıradaki satırlarla doldurulur. Çıktıda **orijinal satır sırası korunur**, kırpıldıysa `_TRUNCATION_MARKER` eklenir.
  4. `query=None` iken bugünkü baştan kesme davranışı aynen kalır (geri uyum; eval script'leri etkilenmez).
- `src/app.py` `build_context(chunks, question)`: `truncate_chunk_text(chunk["content"], query=question)`. Evaluation tarafında aynı `build_context` muadili varsa (`evaluation/run_tests.py`) aynı parametre geçirilir, böylece benchmark arayüzle aynı bağlamı ölçer.
- `MAX_CHUNK_CHARS` / `MAX_CONTEXT_CHARS` **değişmez** (8GB VRAM sınırı).
- Doğrulama: "searchKeywords'ün türetildiği alanlar" → gönderilen kopyada `searchKeywords[*]` satırları var, uzunluk ≤1500+marker. Tam soru LLM ile tekrar sorulur. Birim testler: tekrar tekilleştirme, sorgu satırı önceliği, sıra korunması, `query=None` geri uyumu.

### Adım 6 — PDF resimli sayfalar için RapidOCR
- Bağımlılık: `rapidocr_onnxruntime` → `requirements.txt` (onnxruntime zaten kurulu).
- `src/ingest.py` `extract_chunks_from_pdf`: sayfa metni kısa (örn. <50 karakter) **ve** sayfada resim varsa (`page.images`), sayfa `page.to_image(resolution=200)` ile rasterize edilir ve RapidOCR'dan geçirilir. OCR metni başlığın altına eklenip aynı `sayfa N` chunk'ı olarak yazılır. OCR yoksa/başarısızsa uyarı loglanır, ingest durmaz (lazy import).
- PDF yeniden ingest edilir (`delete_source` + `ingest_single_file`; `invalidate_cache` zaten ingest içinde çağrılıyor).
- Doğrulama: chunk 4142/4143 karşılığı `S ==> aSaa | B`, `B ==> bbBdd | C` ve `L_S.4.8.1` içerir. OCR çıktısı 10 sayfa için elle gözden geçirilir; üst simge düzleşmesi (`b2k+1`) not edilir. test_1 #24–#29 tekrar koşulur.

### Adım 7 — Kayıt ve ölçüm
- `docs/backlog_retrieval.md`: kalan açıklar eklenir. (a) 2b (kolon parçası eşleşmesi) ileride ölçülecek. (b) LLM-judge'ın yanlış retleri "dürüst ret" diye yüksek puanlaması; ground truth'ta cevabı olan pozitif sorularda retin cezalandırılması gerektiği.
- Tam benchmark: `evaluation/run_tests.py` test_1–test_5 + **tam 32 soruluk negatif set** (llm_client.py:684'teki uyarı gereği; Adım 5 synthesizer bağlamını değiştiriyor). Sonuçlar önceki koşuyla karşılaştırılır (FN/FP).

## Kritik dosyalar
- `src/retrieval.py` — `_base_tokens`, `retrieve` (router çağrısı), `_resolve_dataset_name`
- `src/router.py` — `COMPLEXITY_SIGNALS`, `_analyze`, `classify_query`
- `src/llm_client.py` — `truncate_chunk_text`
- `src/app.py` — slider, `build_context`
- `src/ingest.py` — `extract_chunks_from_pdf`
- `evaluation/run_tests.py` — bağlam kurulumu (Adım 5'te eşitlenecek)

## Genel doğrulama
- Her adım sonrası: `python -m pytest -q tests` (beklenen tek başarısız test: `test_visualization`, backlog 17).
- Dört örnek soru, uygulama yeniden başlatılarak arayüzde tekrar sorulur.
- Adım 5 ve 6 sonrası tam benchmark + negatif set (Adım 7).

## Uygulama durumu (2026-10-10)

| Adım | Durum | Not |
|---|---|---|
| 1 | ✅ commit `2d5a42a` | |
| 2 | ✅ commit `20f4a92` | |
| 3 | ✅ | 147 benchmark sorusunda rota değişimi 0 |
| 4 | ✅ | `selected_dataset` hem `retrieval.retrieve` hem `data_engine.execute_smart_query` (router'ı ikinci kez çağırıyor) tarafından geçiriliyor. Tablosal dosyalı 30 soruda rota değişimi 0 |
| 5 | ✅ | Profil chunk'larında `searchKeywords` artık modele ulaşıyor (≤1500 karakter). Yan bulgu: backlog madde 19 ("deneyim" → `de` stopword) |
| 6 | ✅ kod / ⏳ yeniden ingest | Resimler tek tek kendi bbox'ıyla kırpılıp OCR'lanıyor (tam sayfa raster Cevap 8a satırını bozuyordu); iki sütun ayrıştırılıyor. Üst simgeler düzleşiyor (`b2k+1`); Cevap 2/6, Örnek 7 kısmen bozuk |
| 7 | ✅ backlog (madde 19–21) / ⏳ benchmark | Benchmark ve yeniden ingest Ollama + Foundry servislerini gerektiriyor |
