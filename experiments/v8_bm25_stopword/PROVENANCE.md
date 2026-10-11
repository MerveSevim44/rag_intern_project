# v8 — BM25 stopword çakışması düzeltmesi (madde 19)

## Ölçülen kod durumu
- **Taban commit:** `2ef9487` + commit edilmemiş `src/retrieval.py` değişikliği
  ([src_diff.patch](src_diff.patch); yüzey stopword filtresi, çakışma koruması,
  soru ekleri stopword listesine). Ayrıntı: `kod_durumu.txt`.
- Bu değişiklik koşudan sonra **`392f2b3`** olarak commit edildi; commit'in
  `src/` diff'i `src_diff.patch` ile byte byte aynı (doğrulandı). Ölçülen kod
  = `392f2b3`'teki `src/`.
- DB: 916 chunk, 8-Baglamdan_bagimsiz_dilbilgisi.pdf OCR ile ingest edilmiş hâli.

## UYARI: v7 → v8 farkı tek bir değişiklik DEĞİL
v7 commit `27214ff`'te koşulmuştu. Aradaki commit'ler (`2d5a42a` noktalı
tanımlayıcı, `20f4a92` TOP_K, `dffb6a5` OCR + soruya duyarlı kırpma + router)
**hiç benchmark'lanmadan** girdi. v7 → v8 farkı bunların + tokenizer + LLM
nondeterminizminin toplamıdır. Tokenizer'ın kendi etkisi aşağıda ayrıca, aynı
kod üzerinde ölçüldü (karşı-olgu).

## Koşu
- 2026-10-11, her set ayrı süreç: `python -u experiments/v8_bm25_stopword/run_set.py <set>`
  (run_tests fonksiyonları değiştirilmeden; satır satır diske yazma; negatif set
  iki segment 201–215 / 216–232). `HF_HUB_OFFLINE=1` (reranker sürüm kontrolü
  ağ hatasında beklemesin; sonucu etkilemez). k=5 (`run_single_test` varsayılanı, v7 ile aynı).
- Model qwen2.5-7b-instruct-cuda-gpu:4 (Foundry Local), embedding bge-m3 (Ollama).
- Skorlama: `benchmark_eval.evaluate_all(results_dir=results, output_dir=report)`.

## Koşu sağlığı
147 sorunun 144'ü cevaplandı. **test_2 #43, #44, #53: `service_failure`**
(Foundry `Error code: 500`, onnxruntime) — üçü de code_interpreter rotasında,
BM25 kullanmıyor; ikinci denemede de aynı (`retry_*.csv`). #43/#53 v7'de de
böyleydi; #44 v7'de cevaplanmıştı (madde 15 sınıfı). Üçü temiz setten çıkarıldı.
test_2 sürecinin sıfır olmayan çıkış kodu (`hatalar.txt`) kapanışta; 30 satırın
tamamı yazılmış, traceback yok.

## Tokenizer'ın kendi etkisi (aynı kod, yalnız tokenizer farklı)

**Katman 1** ([../bm25_tokenizer_variants/INCELEME.md](../bm25_tokenizer_variants/INCELEME.md)):
147 benchmark sorusunun **137'sinde** LLM'e giden bağlam (k=5) eski/yeni
tokenizer'da bayt bayt aynı → bu sorularda tokenizer'ın etkisi tanım gereği 0.
Beklenen kaynağı final'den kaybeden soru 0.

**Katman 1 doğrulaması:** gerçek v8 koşusunun bağlamı 121 semantic sorunun
**118'inde** katman 1'in "yeni" tahminiyle birebir aynı; 3'ünde (#36, #93, #217)
sınırdaki parça farklı (retrieval gürültü tabanı ~%2.5).

**Karşı-olgu** (`run_v0_counterfactual.py`, `results/v0_karsi_olgu.csv`):
bağlamı değişen 10 soru güncel kodda ESKİ tokenizer'la koşuldu (9/10'da bağlam
katman 1 ile aynı; #1'de 4. parça farklı — sürecin ilk çağrısı).

| | eski tokenizer | **yeni tokenizer** |
|---|---|---|
| sınıf | 7 TP, 1 FN (#92), 2 TN | **8 TP**, 0 FN, 2 TN (#92 FN → TP) |
| TP → FN | – | **0** |
| yeni FP | – | **0** (#115, #229 TN kaldı) |
| ort. F1 (10 soru) | 54.3 | **65.5** |

(#6 69→100, #7 75→100, #29 36→42, #40 15→26, #92 0→38; #47 37.5→36.7.
Tek koşu, LLM nondeterministik.)

Negatif #207, #220: k=5 bağlamı eski/yeni aynı (değişiklik yalnız k=8'deydi).

## v7 → v8 (TÜM değişiklikler birlikte — bkz. uyarı)

Temiz set: test_1..4 eksi #43, #44, #53 (97 soru).

| | v7 | v8 |
|---|---|---|
| FN | 10 | **6** |
| F1 | 39.0 | 41.2 |
| ROUGE-L | 34.4 | 36.3 |
| Semantik | 78.1 | 80.3 |
| EM / Soft | 6.2 / 12.4 | 6.2 / 14.4 |
| Negatif FP | 1/32 | **3/32** |
| test_5 FP | 2/15 | 3/15 |

Sınıf değişen 9 soru: FN→TP #25, #26, #29, #54, #92; TP→FN #50; TN→FP #103
(test_5), #222, #224. **#25, #26, #50, #54, #103, #222, #224'te bağlam eski/yeni
tokenizer'da aynı** — tokenizer'a atfedilemez.

**Yeni FP'lerin kaynağı (tokenizer DEĞİL):**
- **#103, #224:** bağlama OCR'lı alıştırma sayfaları giriyor (sayfa 22 "Chomsky
  normal biçimine (CNF) dönüştürünüz", 24, 28). Model alıştırma metninden prosedür
  uyduruyor. `dffb6a5` (OCR) kaynaklı → backlog madde 24.
- **#222:** uydurma değil; cevap yarım kalmış bir ret ("…herhangi bir bilgi
  bulunmadığından"), `check_is_not_found` tanımıyor → skorlama yapaylığı, madde 25.
