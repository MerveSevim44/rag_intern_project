# Implementation Plan — Meta-chunk Boost'unu Sorgu Sinyaline Bağlamak (Backlog Madde 5)

İlgili: [backlog_retrieval.md](backlog_retrieval.md). Baz çizgisi: `f20e3ff`.

## Sorun
`retrieval.py` içinde meta-chunk'lara (`$.fieldGuide`, `$.statistics`,
`$.safetyAndDataQuality`, `$.metadata`, `$.meta*`) sabit `+0.35` boost
uygulanıyor. Bu boost sorgu tipinden bağımsız ve normalize RRF ölçeğinin
[0..1] yaklaşık üçte biri.

## Ön ölçüm (`f20e3ff`, reranker kapalı, 115 değerlendirme sorusu + 4 manuel sorgu)
Meta-chunk 28 soruda ilk 8'e giriyor. Bu soruların tamamı `semantic_rag`
rotasına gidiyor. Router'da ayrı bir "şema sorusu" rotası yok. Meta-chunk'ların
dördü de `728_profiles.json` içinde.

| Grup | Örnekler | Boost ile sıra (boost'suz sıra) |
|---|---|---|
| Zararlı | test_1 (PDF) ×4, test_3 (PDF) ×2, test_4 (txt), "dişçi" | statistics 1 (27), safetyAndDataQuality 5 (50), statistics 8 (119) |
| Gerekli | test_2 şema soruları (weeklyAvailability, defaultDurationMinutes, profileCode…) | fieldGuide 1 (47), 3 (171), 1 (22) |
| Nötr | test_2 #31, #56 (schemaVersion) | metadata 1 (1) |

## Değerlendirilen yaklaşımlar
- **A. Yalnızca router'ın rota/sebep bilgisi** (`meta_query` / `schema_or_doc_conceptual`).
  Reddedildi: gerekli sorulardan 8'i `fallback_semantic` sebebiyle geliyor.
  Örneğin test_2#36'da fieldGuide 3. sıradan 171. sıraya düşer.
- **B. Meta-chunk'ın kendi BM25/dense skoruna orantılı boost.**
  Reddedildi: gerekli durumlarda meta-chunk'ın kendi alaka skoru zaten düşük;
  boost'a ihtiyaç duymasının sebebi bu.
- **C. Sorgu sinyaliyle kapı (seçilen).** Boost yalnızca şu durumlarda uygulanır:
  1. rota `meta_query` ise,
  2. router sebebi `schema_or_doc_conceptual` ise,
  3. sorguda veri setinin bir kolon adı geçiyorsa (`strong_schema_columns` boş değilse).

  Ölçümde gerekli şema sorularının tamamı kapıdan geçiyor. Geçmeyen #31 ve #56
  zaten boost olmadan 1. sırada. Zararlı soruların hiçbiri kapıdan geçmiyor.
  `dataset_context` bilerek kapsam dışı bırakıldı: yalnızca zaten 1. sırada
  olan iki soruyu kapsıyor, iki zararlı soruyu (test_4#98, test_5#110) içeri alıyor.

## Uygulama adımları
1. `router.classify_query` sonucuna `strong_schema_columns` alanı eklenir.
   Bu değer şu an yalnızca `debug=True` iken dönüyor. Değişiklik yalnızca
   ekleme, mevcut alanlar aynı kalıyor.
2. `retrieval.retrieve` içinde kapı hesaplanır:
   `meta_boost = 0.35 if (is_meta_chunk and meta_gate) else 0.0`.
   Boost büyüklüğü (0.35) değişmez, yalnızca kapı eklenir. Etki tek bir
   değişkenle sınırlı kalsın diye; büyüklük ayarı gerekirse ayrı bir madde olur.
3. Debug çıktısına `meta_gate=on/off (sebep)` eklenir.

## Test planı
1. Meta-chunk denetimi (28 soru + manuel sorgular): her meta-chunk'ın sırası önce/sonra.
2. Manuel sorgu tabloları: "Kocaeli çocuk dişçisi", "çocuğum için dişçi lazım",
   "dişçi arıyorum" için 3'er aday.
3. Tam değerlendirme: `evaluation/eval_retrieval.py`, tüm setler, reranker açık.
   Top-1 kaynak doğruluğu ve soru bazında top-1 `page_info` önce/sonra karşılaştırılır.
   Not: top-1 kaynak metriği, meta-chunk ile profil aynı dosyada olduğu için
   test_2 içindeki farkı göremez; bunu 1. madde kapsıyor.

## Riskler (şimdilik çözülmüyor)
- **Takma ad eşleşmeleri:** `strong_schema_columns` bazı eşleşmeleri takma ad
  üzerinden yapıyor ("profil" → `profileCode`). "profili olan diş hekimi" gibi
  sorgularda kapı açılabilir. Yalnızca ölçümde gerçek bir sorun görülürse
  raporlanacak.
- **Kaynak uyumu:** Kapı kaynağa bakmıyor. Başka bir veri seti için sorulan
  şema sorusunda 728'in meta-chunk'ları da boost alır. Gerekirse sonraki adım,
  `meta_query` için kullanılan `select_dataset` kaynak eşlemesini bu kapıya
  da eklemek.

## Sonraki madde (6) — madde 5 tamamlanınca
Türkçe stemmer. Sıra şöyle:
1. Kritik terimlerde stem çıktısını elle kontrol et (dişçi, dişçisi, hekim,
   hekimi, doktor, uzmanı, çocuk, çocuğum).
2. `TERM_SYNONYMS` içinde gereksiz kalan girdileri göster; sözlüğü onaydan
   sonra küçült.
3. Cache invalidation sonrası üç manuel sorguyu önce/sonra karşılaştır.
