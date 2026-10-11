# BM25 stopword çakışması — hibrit sıralama düzeltmesi (madde 19)

İlgili: [backlog_retrieval.md](backlog_retrieval.md) madde 19, baz çizgi
[experiments/stopword_baseline/RAPOR.md](../experiments/stopword_baseline/RAPOR.md)
(commit `2ef9487`). Bu doküman plandır; uygulama her adımda ayrı onayla yapılır.

## 1. Sorun

Baz çizgide isim vakalarında (#301–303) iki kişi de geliyor, ama hedef
hibrit sıralamada 3., 3. ve 6. sıraya düşüyor. #303'te top_k=5'te hiç
reranker'a ulaşmıyor. Dense hedefi her üç vakada 1. sırada buluyor;
sıralamayı BM25 bozuyor.

## 2. Hibrit skor nasıl birleştiriliyor — sorun ağırlık mı, normalizasyon mu?

[retrieval.py, ADIM 6b](../src/retrieval.py) **Reciprocal Rank Fusion** kullanıyor:

```
rrf = 1/(60 + dense_sıra) + [bm25 > 0 ise] 1/(60 + bm25_sıra)
rrf = rrf / (2/60)          # [0..1] ölçeği; sorgudan bağımsız sabit bölen
```

- **Ağırlık:** Dense ve BM25 eşit (her biri `1/(60+sıra)`).
- **Normalizasyon:** RRF yalnızca **sırayı** kullanıyor, ham skoru değil. BM25'in
  [0..∞] ile dense'in [0.4..0.8] arasındaki ölçek farkı füzyona girmiyor; biri
  diğerini ölçek yüzünden ezemez. Bölen sabit, sorguya göre değişmiyor.
- Ölçeğe duyarlı tek bileşen `keyword_boost`: `0.08 × bm25_norm × key_coverage`
  (bm25_norm sorgu içi max'a bölünüyor). Üst sınırı 0.08, RRF tavanı 1.0;
  bu vakalarda belirleyici değil.

**Sonuç: sorun ne ağırlık ne normalizasyon, BM25'in girdisi.** Tokenizer
ayırt edici terimi siliyor (`Damla Akın` → `['ak']`); BM25 aynı soyadlı 10
kişiyi eşit sayıyor, uzunluk normalizasyonu hedefi 42.'ye itiyor. RRF bu
yanlış sıralamayı doğru biçimde birleştiriyor. Kanıt (bölüm 4): RRF'ye hiç
dokunmadan yalnız tokenizer düzeltilince üç vaka da 1. sıraya çıkıyor.

**Reddedilen alternatif — BM25 ağırlığını düşürmek:** Bu üç vakayı da
iyileştirirdi, ama (a) kök nedeni bırakır, (b) BM25'in doğru çalıştığı
sorularda (ör. #310 dense 2 / BM25 1, #305, #309) katkısını her soruda
köreltir. Ölçülmedi; kök neden düzeltmesi aynı kazancı daha dar bir
değişiklikle verdiği için gerek görülmedi.

## 3. Kapsam: 5 soruya özel mi, genel mi?

**Genel, ama yalnız çakışan kelimelere dokunan bir tokenizer değişikliği.**
Soruya ya da kelime listesine özel kod yok; kural, hangi kelimelerin
etkileneceğini kendisi belirliyor.

Seçilen varyant **V3**, iki kuraldan oluşuyor:

1. **Stopword filtresi stem ÖNCESİ yüzey biçimine uygulanır.** Gerçek
   stopword'ler (`ve`, `bu`, `için`, `de`…) aynen düşer; stem'i tesadüfen
   stopword'e denk gelen gerçek kelime (`deneyim`, `damla`) artık düşmez.
2. **Stem'i bir stopword stem'ine denk gelen kelimede stem yerine fold'lu
   yüzey biçimi kullanılır.** Aksi hâlde düşmeyen kelimeler bu sefer
   birbirleriyle çakışıyor: V1'de `deniz` ve `deneyim` ikisi de `de`,
   `damla` ve `data` ikisi de `da` oluyordu.

| Girdi | V0 (mevcut) | V1 (yalnız kural 1) | **V3** |
|---|---|---|---|
| Deniz Akın | `ak` | `de ak` | `deniz ak` |
| deneyim yılları | `yil` | `de yil` | `deneyim yil` |
| Damla | — | `da` | `damla` |
| seed data | `seedi` | `seedi da` | `seedi data` |
| ve bu için de | — | — | — |

Bilinen sınır: kural 2 yalnız çakışan biçime uygulanıyor. `deneyim` yüzey
biçiminde kalırken `deneyimi` hâlâ `deney`'e stem'leniyor; çekimler arasında
eşleşme kopabilir. Bu bugünkü durumdan kötü değil (bugün `deneyim` hiç
yok); kapsam dışı bırakılıyor ve backlog **madde 23** olarak izleniyor.

Değişecek yer: `src/retrieval.py::_tokenize`. Corpus token'ları cache
yüklenirken `_tokenize` ile üretildiği için **yeniden ingest gerekmez**.
`_key_field_tokens` (keyword_boost) de `_tokenize` kullandığı için tutarlı kalır.

## 4. Ön ölçüm (bu plan için, reranker yok, deterministik)

Script: geçici deney (`tokenizer_variants.py`); varyantlar bellek içinde yamalandı,
`src/` değişmedi. Uygulama adımında `experiments/bm25_tokenizer_variants/`
altına kanıt olarak alınacak.

**test_stopword — hedefin hibrit sırası (BM25 sırası), önündeki karıştırıcı:**

| # | V0 | V1 | V3 |
|---|---|---|---|
| 301 Damla Akın | 3 (42), 2 önde | 1 (1), 0 | **1 (1), 0** |
| 302 Deniz Akın | 3 (53), 2 önde | 1 (1), 0 | **1 (1), 0** |
| 303 Deniz Çelik | 6 (15), 5 önde | 1 (2), 0 | **1 (1), 0** |
| 304 Ön değerlendirme | 7 (13) | 7 (13) | 7 (13) |
| 306 İş modeli | 1 (14) | 1 (2) | 1 (2) |
| diğer 7 soru | 1 | 1 | 1 |

#304 beklendiği gibi değişmiyor: `ön` geri geliyor ama avukatların "Hukuki
**ön** görüşme" hizmetinde de geçiyor (baz çizgi raporu).

**Benchmark (147 soru; 121'i semantic_rag, kalan 26'sı code_interpreter, BM25 kullanmıyor):**

| | V1 | V3 |
|---|---|---|
| top-8 aday kümesi değişen | 14 | 14 |
| top-5 aday kümesi değişen | 10 | 12 |
| beklenen kaynağın ilk sırası kötüleşen | 0 | **0** |
| top-5'ten beklenen kaynağı kaybeden | 0 | **0** |

(V2 — kural 2 yerine "3 harften kısa her stem" — 37 soruyu değiştirdi, ek
kazanç yok; reddedildi.)

V3'te aday kümesi değişen 14 soru: test_1 #11, test_2 #34, #36, #41, #47,
#49, #50, test_3 #66, #87, test_4 #92, #95, negatif #207, #220, #229.

## 5. Diğer 107 soru nasıl korunacak — regression check

Ön ölçüm doküman seviyesinde ve reranker'sız; garanti için yetmez. Üç katman:

1. **Deterministik retrieval karşılaştırması (birincil):** 147 sorunun hepsi
   için reranker DAHİL final 4 parça, V0 ve V3'te (k=5 ve k=8). Final
   kümesi aynı kalan soruda LLM'e giden bağlam bayt bayt aynıdır. O
   sorularda cevap farkı yalnız nondeterminizmdir, regresyon olamaz.
   Kümesi değişen her soru chunk seviyesinde elle incelenir: yeni giren
   parça soruyla ilgili mi, çıkan parça cevabı taşıyor muydu?
2. **test_stopword yeniden koşusu:** `run_stopword_set.py --out-dir
   experiments/stopword_v3`, baz çizgiyle sütun sütun karşılaştırma.
3. **Tam benchmark + 32 negatif (v8):** v7 ile karşılaştırma. Ama sinyal yalnız
   1. katmanda final kümesi değişen sorulardan okunur; değişmeyenler
   nondeterminizm gürültüsünün ölçüsü olarak kullanılır. Negatif setteki üç
   değişen soru (#207, #220, #229) FP riski açısından ayrıca bakılır
   (llm_client.py'deki uyarı: bağlamı değiştiren her değişiklik tam negatif
   setle doğrulanmalı).

Tam v7'yi tekrar koşmak gerekli mi? **Evet, ama karar aracı olarak değil, kayıt
olarak.** Sıralamanın bozulmadığını 1. katman deterministik olarak gösterir;
v8, PROVENANCE düzeni ve negatif set FP kontrolü için koşulur.

## 6. Başarı ölçütü

Zorunlu:
- [ ] #301, #302, #303 hibrit sıra **3 / 3 / 6 → 1 / 1 / 1**, önünde karıştırıcı **0**.
- [ ] **top_k=5**'te #303 hedefi final 4 parçada (baz çizgide 0).
- [ ] 147 soruda beklenen kaynak final 4'ten **hiçbir soruda düşmez** (k=5 ve k=8).
- [ ] Final kümesi değişen her soru incelenmiş ve gerekçesi kayıtlı.
- [ ] Negatif sette FP artışı yok (v7: test_negative özeti).
- [ ] Mevcut testler + yeni tokenizer testleri geçiyor (tek beklenen kırmızı: madde 17).

Beklenmeyen / ölçüt değil:
- #304 değişmez (ayrı kök neden). #305/#307 (RERANK_TOP_N) ve #308/#311/#312
  (sentez) bu değişiklikten etkilenmez.
- Cevap doğruluğu ikincil ölçüt (tek koşu, nondeterministik).

## 7. Testler

`tests/test_tokenizer_identifiers.py`'ye (ya da yeni `test_tokenizer_stopwords.py`):
- `deneyim`, `damla`, `deniz`, `iş`, `ön` artık token üretir.
- `deniz` ≠ `deneyim`, `damla` ≠ `data` (çakışma koruması).
- `ve`, `bu`, `için`, `de`, `nedir` hâlâ düşer.
- `g4.1` tanımlayıcı token'ı korunur (önceki düzeltme).

`evaluation/stopword_collision.py` bugün çakışmayı `_stem` + `_STOPWORDS`
üzerinden hesaplıyor; düzeltmeden sonra da aynı listeyi basar. Ölçümü
`_tokenize` çıktısı üzerinden yapacak şekilde güncellenir: "kelime gerçek
stopword değil ama `_tokenize` onu siliyor ya da başka bir kelimeyle aynı
token'a indiriyor". Beklenen düzeltme sonrası değer: 0.

## 8. Commit sırası (her biri ayrı onayla)

1. `evaluation/stopword_collision.py` + backlog madde 19 eki (şu an açıkta duranlar).
2. Bu plan + `experiments/bm25_tokenizer_variants/` (ön ölçüm kanıtı).
3. `fix(retrieval)`: `_tokenize` V3 + testler + `stopword_collision.py` güncellemesi.
4. `chore(eval)`: regression katman 1 + `experiments/stopword_v3/` + v8 benchmark ve PROVENANCE.

## 9. Sonuç (2026-10-11)

Uygulama V3'ten iki noktada sapmalı (ikisi de regresyon katmanlarıyla ölçüldü):
(a) çakışma koruması `_apply_synonyms` içinde token başına (deney sürümü eş
anlamlı genişlemesinde hizasız kalıyordu); (b) soru ekleri/edat çekimleri
(`nedir`, `nelerdir`, `içindeki`…) `TURKISH_STOPWORDS`'e eklendi — eskiden stem
çakışmasıyla tesadüfen düşüyorlardı, yüzey filtresinde açıkça listelenmeleri gerekti.

| Ölçüt (§6) | Sonuç |
|---|---|
| #301/#302/#303 hibrit sıra 3/3/6 → 1/1/1, önde karıştırıcı 0 | ✅ ([stopword_v3](../experiments/stopword_v3/PROVENANCE.md)) |
| top_k=5'te #303 hedef final'de | ✅ 0 → 1 |
| 147 soruda beklenen kaynak final'den düşmez (k=5, k=8) | ✅ 0 kayıp ([INCELEME](../experiments/bm25_tokenizer_variants/INCELEME.md)) |
| Final kümesi değişen her soru incelenmiş | ✅ INCELEME.md |
| Negatif sette tokenizer kaynaklı FP artışı yok | ✅ bağlamı değişen negatif sorular (#229, #115) TN kaldı; karşı-olguda yeni FP 0 |
| Testler | ✅ 6 yeni tokenizer testi + mevcutlar |

Tokenizer'ın kendi etkisi (karşı-olgu, aynı kod): bağlamı değişen 10 soruda
TP→FN 0, yeni FP 0, #92 FN→TP, ort. F1 54.3 → 65.5. Ayrıntı:
[v8 PROVENANCE](../experiments/v8_bm25_stopword/PROVENANCE.md).

v8'de görülen negatif FP artışı (1 → 3/32) tokenizer'dan DEĞİL: #224/#103
OCR'lı alıştırma sayfalarından (`dffb6a5`, madde 24), #222 skorlama yapaylığı
(madde 25).
