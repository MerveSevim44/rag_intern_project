# Plan: madde 27 — `semantic_sim`: eksik değer (M) + embedding cihazını sabitleme (P)

Tarih: 2026-10-13. Taban: `de2694f`. Kapsam ölçümü:
[experiments/madde27_nan_embedding/README.md](../experiments/madde27_nan_embedding/README.md).

## 1. Sorun (özet)

- `benchmark_eval.compute_semantic_similarity` beş durumda 0.0 döndürüyor ve bu
  değer ortalamaya gerçek skor gibi giriyor. Durumlar şunlar: boş girdi,
  servis yok, sıfır norm, herhangi bir istisna, negatif kosinüs.
  - İstisna durumunda referanslardan **biri** hata verse bile diğer
    referanslarla bulunmuş skor da atılıyor.
- **Gözlenen vaka:** v7 test_2 #36. Madde 25'teki yeniden skorlamada 86.7
  0.0'a düştü.
- **Kök neden ölçüldü:** Ollama bge-m3'ü bazı oturumlarda CPU'da, bazılarında
  GPU'da çalıştırıyor.
  - NaN yalnızca GPU yolunda ve yalnızca bu metinde oluşuyor. 701 metnin 1'i,
    3/3 deterministik. CPU yolunda 0/701.
  - CPU ve GPU vektörleri birbirinden farklı. Kosinüs en düşük 0.9982; 83
    metinde 0.9999'un altında. Madde 25'te görülen `semantic_sim` ±0.1–0.2
    gürültüsünün kaynağı bu.

## 2. Değişiklik (yalnız `evaluation/benchmark_eval.py`)

**P: skorlayıcının embedding'i CPU'ya sabitlenir.**
- `_embed_text` içindeki `ollama.embeddings(...)` çağrısına
  `options={"num_gpu": SEMANTIC_NUM_GPU}` eklenir. Sabit
  `SEMANTIC_NUM_GPU = 0`, `SEMANTIC_KEEP_ALIVE`'ın yanında tanımlanır ve
  gerekçesi yorumla yazılır.
- **Kapsam dışı:** retrieval'ın sorgu embedding'i (`src/embedder.py`) ve
  ingest. DB'deki doküman embedding'lerinin hangi cihazda üretildiği bilinmeden
  sorgu tarafı sabitlenemez; bu madde 29'un işi.
- **Bilinen yan etki:** Aynı Ollama sunucusunda retrieval (varsayılan seçenek)
  ile skorlama (`num_gpu=0`) iç içe koşarsa model farklı seçenekle yeniden
  yüklenir. Skorlama toplu ve ayrı bir iş olduğu için pratikte bir kez yüklenir.

**M: hesaplanamayan skor eksik değer olur.**
- `compute_semantic_similarity` artık `float | None` döndürür.
- **None döndüğü durumlar:** servis yok, istisna, cevabın normu sıfır, ya da
  hiçbir referansın geçerli embedding'i yok.
- **Geçerli skor sayılmaya devam edenler:** Negatif kosinüs 0.0 olarak kalır;
  bu bir hata değil, gerçek bir "alakasız" sonucu. Boş cevap da 0.0 kalır;
  cevap gerçekten boş, bu da gerçek bir sonuç.
- **Referans bazında hata:** Bir referansın embedding'i hata verirse yalnızca o
  referans atlanır. Diğer referanslardan skor bulunursa o skor kullanılır;
  hiçbiri yoksa None döner.
- **Kayıt:** Satırın `semantic_sim` alanına `None` yazılır. Scored CSV'de bu
  boş hücre olarak görünür.
- **Ortalamalar:** Dört yerde hesaplanıyor. Hepsinde None'lar paydadan
  çıkarılır:
  1. kategori `sem_sum / acc_cnt` (yaklaşık satır 851 / 914),
  2. `overall_semantic` (yaklaşık 895),
  3. `_summary_from_records` kategori ortalaması (yaklaşık 1251),
  4. `_summary_from_records` genel ortalaması (yaklaşık 1272).
  Her özete yeni bir alan eklenir: `semantik_hesaplanamayan_soru` (sayı). Hepsi
  None ise ortalama da None olur.
- **Negatif sorular:** Bu sorularda `semantic_score = em_score` (ikili)
  davranışı değişmez.
- **Uyarı:** Konsoldaki uyarı korunur ve hatanın türünü yazar (`NaN 500`,
  bağlantı vb.).

## 3. Başarı ölçütleri

1. **Birim testler** (`tests/test_semantic_sim_missing.py`). `_embed_text`
   sahte bir fonksiyonla değiştirilir, gerçek servis kullanılmaz. Senaryolar:
   - İstisna → None.
   - Tek referans hata, diğeri geçerli → geçerli skor.
   - Bütün referanslar hata → None.
   - Negatif kosinüs → 0.0, None değil.
   - Boş cevap → 0.0.
   - Ortalama None'ları atlar ve sayar.
   - Hepsi None → ortalama None.
   - `_embed_text` çağrısına `num_gpu=0` geçiyor mu? Çağrı argümanları
     yakalanarak kontrol edilir.
2. **Yeniden skorlama (v7 ve v8, servis gerekir, LLM gerekmez):**
   `evaluate_all(results_dir=experiments/<v>/results,
   output_dir=experiments/madde27_nan_embedding/yeniden_skor_<v>)`. Madde 25
   Adım 2 ile aynı yöntem. Beklenenler:
   - v7 test_2 #36'nın `semantic_sim`'i hesaplanıyor ve ~86.7 civarında. 0.0
     değil, None da değil.
   - `semantik_hesaplanamayan_soru` 0.
   - Diğer satırlarda `semantic_sim` farkı küçük, beklenen ≤ ~0.2 puan.
     Dağılım raporlanır. 1 puandan büyük bir fark çıkarsa elle incelenir.
   - **Diğer bütün metrikler ve sınıflar bayt bayt aynı:** EM, soft-EM, F1,
     precision, recall, ROUGE-L, retrieval, TP/TN/FP/FN.
3. **Tekrarlanabilirlik:** Aynı yeniden skorlama ikinci kez, ayrı bir süreçte
   koşulur. `semantic_sim` değerleri birinci koşuyla birebir aynı çıkmalı. Bu,
   P'nin gürültüyü kapattığının doğrudan kanıtı.
4. **Tam test seti:** Mevcut testler ve yeni testler geçer; tek beklenen kırık
   madde 17.

## 4. P öncesi üretilmiş `semantic_sim` değerleri ("cihaz karışımı" kaydı)

Aşağıdakilerin `semantic_sim` / "semantik benzerlik" değerleri P öncesinde
üretildi. Ollama bge-m3'ü o oturumda hangi cihaza yüklediyse onunla
hesaplandılar; cihaz bilinmiyor. Bu yüzden P sonrası değerlerle ≤ ~0.2 puan
fark edebilirler. #36 gibi bir NaN vakası varsa bu fark 0'a düşüş olarak
görünür.

Hepsi yeniden skorlanmayacak, çünkü `semantic_sim` kararlarımızda belirleyici
olmadı. Kararlar F1, judge ve sınıflandırma üzerinden verildi. Bunlar yalnızca
"P öncesi" olarak işaretlenir:
- **Koşu raporları:** `experiments/{v2_baseline_trim, v3_soften_and_chunk,
  v5_soften_and_brevity (report, report_with_negative), v6_sandbox_empty_guard,
  v7_refusal_clarity, v8_bm25_stopword (report, report_karsi_olgu)}` altındaki
  `*_scored.csv` ve `*_summary.json` dosyaları.
- **Madde 25 yeniden skorlaması:**
  `experiments/madde25_ret_tespiti/yeniden_skor_{v7,v8}`. #36'nın 0.0'ı burada.
- **Bu sayıları alıntılayan dokümanlar:**
  - `experiments/v7_refusal_clarity/PROVENANCE.md`,
  - `experiments/v8_bm25_stopword/PROVENANCE.md` (v7 → v8 tablosundaki
    "Semantik 78.1 / 80.3"),
  - `experiments/validator_A/PROVENANCE.md`,
  - `docs/EXPERIMENTS.md`, `docs/TEKNIK_RAPOR.md`, `docs/INFRASTRUCTURE_NOTES.md`,
  - `docs/implementation_plan_*.md` içindeki semantik alıntıları.
- **Etkilenmeyenler:** Madde 19, 22 ve 24 ölçümleri. Bunlar `semantic_sim`
  kullanmadı; F1 ve sınıflar `compute_token_f1` / `check_is_not_found` ile
  yeniden hesaplandı.

**Kayıt yeri:**
- Bu liste backlog'da madde 27'nin kapanış notuna taşınır.
- `docs/EXPERIMENTS.md`'nin başına tek satırlık bir uyarı eklenir:
  "`semantic_sim` değerleri `<P commit>` öncesi cihaz karışımıyla üretildi;
  bkz. backlog madde 27".
- PROVENANCE dosyalarına dokunulmaz, çünkü tarihsel kayıtlar.

## 5. Adımlar (her biri ayrı commit, adım sonunda durulur)

**Adım 1: M + P kodu ve birim testler.** Plan dosyası bu adımla commit edilir.

**Adım 2: v7/v8 yeniden skorlama ve tekrarlanabilirlik.**
- Ölçüt 2 ve 3 uygulanır.
- Sonuçlar `experiments/madde27_nan_embedding/yeniden_skor_*` altına,
  `semantic_sim` fark dağılımı `sonuc_yeniden_skor.txt` dosyasına yazılır.

**Adım 3: kayıt.**
- Backlog madde 27 kapatılır ve §4'teki liste oraya taşınır.
- `docs/EXPERIMENTS.md`'ye uyarı satırı eklenir.
- Madde 29'a not düşülür: mekanizma bulundu, retrieval tarafı açık.

**Geri dönüş:** Adım 2'de bir ölçüt kalırsa Adım 1 commit'i `git revert` ile
geri alınır. DB ya da veri değişmediği için başka bir adım gerekmez.

## 6. Kapsam dışı

- **Retrieval sorgu embedding'inin cihazı:** madde 29.
- **Negatif soruların `semantic_sim`'i:** İkili 0/100 değerlerle genel ortalamaya
  karışıyor. Bu bir ölçüm tasarımı sorusu, ayrı ele alınır.
- **Geçmiş raporların toplu yeniden skorlanması:** §4 gereği yalnızca v7 ve v8.

## 7. Kritik dosyalar

- `evaluation/benchmark_eval.py`: `_embed_text`, `compute_semantic_similarity`
  ve dört ortalama noktası.
- `tests/test_semantic_sim_missing.py`: yeni.
- `experiments/madde27_nan_embedding/`: Adım 2 çıktıları.
