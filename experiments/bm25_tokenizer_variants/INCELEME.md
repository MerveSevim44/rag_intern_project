# Regresyon katman 1 — elle inceleme (2026-10-11)

Ham çıktı: [regresyon_final4.md](regresyon_final4.md), [regresyon_final4.csv](regresyon_final4.csv),
ara kayıt `regresyon_cache.jsonl`. Eski tokenizer = [v0_tokenizer.py](v0_tokenizer.py)
(git `2ef9487` ile 0 fark doğrulandı), yeni = çalışma ağacındaki `src/retrieval.py`
(diff: [../v8_bm25_stopword/src_diff.patch](../v8_bm25_stopword/src_diff.patch)).
Reranker her soruda gerçekten çalıştırıldı. 159 soru (147 benchmark + 12 test_stopword),
133 semantic_rag, 26 tablosal rota atlandı. Süre 7444 sn.

## Özet

| k | aday kümesi değişen | final kümesi değişen | bağlam değişen | beklenen kaynağı final'den kaybeden |
|---|---|---|---|---|
| 5 | 15 | 13 | 17 | **0** |
| 8 | 17 | 12 | 14 | **0** |

Bağlamı aynı kalan 116 (k=5) / 119 (k=8) soruda LLM'e giden girdi bayt bayt
aynı: bu sorularda v8 cevap farkı yalnız nondeterminizmdir.

## Değişen vakalar

**Hedeflenen (iyileşme):**
- #301 k=5/8: final'deki 3 "Akın" karıştırıcısı çıktı, yerine 2 "Damla" + 1
  alakasız profil girdi; hedef 1. sırada kaldı.
- #302, #303: karıştırıcı sayısı azaldı; **#303 k=5'te hedef 0 → 1** (ölçüt).

**Cevap sayfası korunuyor (PDF):** #1, #6, #7, #29 — cevabı taşıyan sayfa
(3 / 4 / 3 / 30) her iki tokenizer'da ve her iki k'da final'de. Yalnız alakasız
dolgu parçası değişti (ör. #1: "Cevap 5" → "Yararsız değişken", #29: Örnek 4.2 → Örnek 6).

**Profil soruları (728_profiles.json, test_2 #36, #40, #41, #47, #49, test_5 #115):**
final'deki 1–2 profil başka bir profille yer değiştirdi. Bu sorular şema/yapı
soruları; hangi örnek profilin geldiği cevabı belirlemiyor. #49 ve #304, #306 (k=5),
#312: final kümesi aynı, yalnız soruya duyarlı kırpma metni değişti (sorgu
token'ları değiştiği için satır önceliği farklı).

**İzlenecek:**
- **test_4 #92** ("Oda No: 304"): `oda` artık BM25 terimi; test1.txt'deki
  "odadaki" ile eşleşip diğer hikâyenin paragraflarını (4, 5) final'e taşıyor,
  Z-dönüşümü / dilbilgisi dolgusunu çıkarıyor. Beklenen kaynak test2.txt
  paragraf 1 her iki durumda final'de. Dolgu "alakasız"dan "yanıltıcı benzer
  hikâye"ye döndü — v8 cevabına bakılmalı (v7'de de FN).
- **test_stopword #306 k=8:** final'deki hedef profil 3 → 2 (hâlâ var; cevap doğru).
- **Negatif #207, #220, #229:** #207'de Fourier sayfası çıkıp alakasız bir profil
  girdi (wavelet sorusu için ilgili-ama-cevapsız içerik azaldı); #220, #229'da
  yalnız alakasız profiller yer değiştirdi. FP riski v8'de kontrol edilecek.
