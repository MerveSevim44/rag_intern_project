# Plan: madde 20 (top_k) — benchmark `top_k=5` ≠ arayüz `TOP_K=8`

Tarih: 2026-10-18. Kapsam ölçümü: [experiments/madde20_topk_benchmark/](../experiments/madde20_topk_benchmark/).

## 1. Sorun

`src/retrieval.py`'nin `TOP_K` sabiti (hibrit aramada seçilecek aday chunk
sayısı) arayüzde (`src/app.py` slider varsayılanı) 8; ama benchmark/eval
tarafında üç yerde hâlâ eski sabit `5` hardcode edilmiş:

- `evaluation/run_tests.py::run_single_test` (`top_k=5`) — asıl benchmark koşucusu.
- `evaluation/eval_retrieval.py` (`retrieve(question, top_k=5, ...)`).
- `evaluation/llm_as_judge.py::build_context_for_question` (`top_k=5`).

Yani benchmark, kullanıcının arayüzde gördüğünden farklı (daha dar) bir aday
havuzuyla ölçüm yapıyor.

## 2. Kapsam ölçümü sonucu

`experiments/madde20_topk_benchmark/kapsam_topk.py`: tam benchmark + negatif
set (147 soru) üzerinde `retrieve(top_k=5)` ile `retrieve(top_k=8)` (reranker
ve `rerank_top_n=4` sabit) karşılaştırıldı.

- **147 sorunun 110'unda (%75)** nihai 4 chunk'lık liste birebir aynı değil.
- Ama fark **neredeyse istisnasız** 3./4. sıradaki "dolgu" chunk'ın hangi
  sayfa/profil olduğunda; 1. (ve çoğunlukla 2.) sıra her soruda birebir aynı
  kalıyor.
- **Doküman düzeyinde etki: 147/147 sorunun HİÇBİRİNDE** `beklenen_kaynak`
  (CSV ground truth) top_k=5→8 geçişiyle kaybolmuyor ya da kazanılmıyor
  (bkz. bu konuşmadaki çapraz kontrol; `kapsam_topk.jsonl` ham veri).
- **Çekince:** ground truth yalnız dosya adı düzeyinde
  (`evaluation/ground_truth/*.json`); `728_profiles.json` içindeki HANGİ
  profilin geldiği (ör. "Mert Keskin profilinde…" gibi isme özel sorular)
  otomatik doğrulanamıyor — bunu kesinleştirmek gerçek LLM+judge koşusu
  gerektirir (madde 19'un aynı çekincesi). Doküman seviyesinde ölçülebilen
  her şeyde etki sıfır olduğu için risk düşük kabul edildi.

## 3. Karar

**Üç dosyadaki `top_k=5` varsayılanı `retrieval.TOP_K`'ya bağlanır**
(hardcoded `5` yerine `TOP_K` import edilip varsayılan olarak kullanılır).
Böylece:
- Benchmark artık arayüzle aynı aday havuzuyla ölçüyor.
- `TOP_K` ileride değişirse üç dosya da otomatik senkron kalır (ayrı ayrı
  güncelleme unutulmaz).
- Deney scriptlerindeki (`experiments/madde22_ornek_cevap/simulasyon.py`,
  `experiments/madde24_ocr_alistirma/etkilenen_set.py`) hardcoded `top_k=5`
  çağrılarına DOKUNULMAZ — onlar geçmiş koşularla birebir karşılaştırılabilir
  kalması gereken donmuş ölçüm kayıtları, canlı kod değil.

## 4. Yapılacak değişiklikler

- `evaluation/run_tests.py`: `from src.retrieval import get_top_chunks, TOP_K`
  (ve local fallback'i), `run_single_test(..., top_k=TOP_K, ...)`.
- `evaluation/eval_retrieval.py`: `from src.retrieval import retrieve, TOP_K`,
  `retrieve(question, top_k=TOP_K, use_reranker=True)`.
- `evaluation/llm_as_judge.py`: `from src.retrieval import get_top_chunks, TOP_K`,
  `build_context_for_question(question, llm, top_k=TOP_K)`.

## 5. Geri dönüş

Kod değişikliği tek satırlık varsayılan parametre değişimi; `rag.db`'ye
dokunmaz, `git revert` ile risksiz geri alınabilir.
