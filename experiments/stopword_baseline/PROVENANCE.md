# stopword_baseline — madde 19 düzeltmesi öncesi baz çizgi

## Ölçülen kod durumu
- **Commit:** `dffb6a5` (`feat: enhance retrieval and processing logic with OCR support and query-aware truncation`)
- Commit edilmemiş değişiklikler yalnızca ölçüm araçları ve dokümandı; pipeline
  kodu (`src/`) değişmemişti (bkz. `kod_durumu.txt`):
  `docs/backlog_retrieval.md`, `evaluation/datasets/test_stopword.csv`,
  `evaluation/ground_truth/test_stopword.json`, `evaluation/make_stopword_gt.py`,
  `evaluation/run_stopword_set.py`, `evaluation/stopword_collision.py`.
- Veritabanı: `rag.db`, 916 chunk; 8-Baglamdan_bagimsiz_dilbilgisi.pdf OCR ile
  yeniden ingest edilmiş hâli (bu set'i etkilemez, tüm sorular 728_profiles.json).

## Koşu
- 2026-10-10, `python evaluation/run_stopword_set.py --out-dir experiments/stopword_baseline`
- Model: Foundry Local varsayılanı (qwen2.5-7b-instruct-cuda-gpu:4), embedding bge-m3 (Ollama).
- 12 soru, 779 sn, hata 0.

## Dosyalar
- `sonuclar.csv` — soru başına tüm aşama sütunları ve cevap
- `log.txt` — koşu çıktısı
- `RAPOR.md` — yorum
