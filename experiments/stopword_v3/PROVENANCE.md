# stopword_v3 — madde 19 düzeltmesi SONRASI (regresyon katman 2)

## Ölçülen kod durumu
- Taban commit `2ef9487` + commit edilmemiş `src/retrieval.py` değişikliği
  (yüzey stopword filtresi + çakışma koruması + soru ekleri stopword'e; diff:
  [../v8_bm25_stopword/src_diff.patch](../v8_bm25_stopword/src_diff.patch)).
- Bu değişiklik koşudan sonra **`392f2b3`** olarak commit edildi (diff
  `src_diff.patch` ile byte byte aynı). Ölçülen kod = `392f2b3`'teki `src/`.
- Baz çizgi: [../stopword_baseline/](../stopword_baseline/RAPOR.md), aynı DB (916 chunk).

## Koşu
- 2026-10-11, `HF_HUB_OFFLINE=1 python -u evaluation/run_stopword_set.py --out-dir experiments/stopword_v3`
- Model: qwen2.5-7b-instruct-cuda-gpu:4 (Foundry Local), embedding bge-m3. Hata 0.

## Sonuç (baz çizgi → v3)

| # | hibrit sıra | BM25 sırası | önde karıştırıcı | final5 hedef | final8 hedef | cevap recall |
|---|---|---|---|---|---|---|
| 301 | 3 → **1** | 42 → **1** | 2 → **0** | 1 → 1 | 1 → 1 | 1.0 → 1.0 |
| 302 | 3 → **1** | 53 → **1** | 2 → **0** | 1 → 1 | 1 → 1 | 1.0 → 1.0 |
| 303 | 6 → **1** | 15 → **1** | 5 → **0** | **0 → 1** | 1 → 1 | 1.0 → 1.0 |
| 304 | 7 → 7 | 13 → 13 | – | 0 → 0 | 0 → 0 | 0.0 → 0.0 |
| 306 | 1 → 1 | 14 → **2** | – | 4 → 4 | 3 → 2 | 1.0 → 1.0 |
| 307 | 1 → 1 | 5 → **2** | – | 4 → 4 | 4 → 4 | 0.667 → 0.667 |
| 308 | 1 → 1 | 2 → 3 | – | 4 → 4 | 4 → 4 | 0.0 → 0.0 |
| diğer 5 | 1 → 1 | aynı | – | 4 → 4 | 4 → 4 | aynı |

Plan §6 ölçütleri: #301–303 hibrit 1/1/1 ✅, önde karıştırıcı 0 ✅, #303 k=5
final'de ✅. #304 beklendiği gibi değişmedi (ayrı kök neden). Cevaplar anlamca
aynı (tam doğru 6/12 → 6/12); #301'de final'de artık tek "Damla Akın" var
("yalnız hedef").
