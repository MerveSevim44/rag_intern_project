# test_stopword — baz çizgi (madde 19 düzeltmesi ÖNCESİ)

Kod: `dffb6a5` + commit edilmemiş yalnızca ölçüm dosyaları (bkz. `kod_durumu.txt`).
Set: [evaluation/datasets/test_stopword.csv](../../evaluation/datasets/test_stopword.csv),
ground truth: [test_stopword.json](../../evaluation/ground_truth/test_stopword.json),
koşu: `python evaluation/run_stopword_set.py --out-dir experiments/stopword_baseline`
(2026-10-10, 779 sn, hata 0). Ham veri: `sonuclar.csv`, log: `log.txt`.

Ölçüt chunk seviyesinde: **doğru profil** hangi aşamada kalıyor. Filtre yok
(benchmark ve arayüz varsayılanı). k=5 benchmark (`run_tests`), k=8 arayüz
(`retrieval.TOP_K`); final = reranker sonrası `RERANK_TOP_N=4`.

## Özet

| # | Düşen | Hibrit sıra (dense / BM25) | k=5 final'de hedef | k=8 final'de hedef | Cevap (k=8) |
|---|---|---|---|---|---|
| 301 Damla Akın | damla | 3 (1 / **42**) | 1 · ilk sıra | 1 · ilk sıra | ✅ |
| 302 Deniz Akın | deniz | 3 (1 / **53**) | 1 · ilk sıra | 1 · ilk sıra | ✅ |
| 303 Deniz Çelik | deniz | **6** (1 / **15**) | **0** | 1 · ilk sıra | ✅ |
| 304 Ön değerlendirme | ön | **7** (21 / 13) | **0** | **0** | ❌ yanlış meslek (Avukat) |
| 305 Çekim ön görüşmesi | ön | 1 (1 / 1) | 4 | 4 | ◐ 2 meslekten 1'i |
| 306 İş modeli görüşmesi | iş | 1 (1 / **14**) | 4 | 3 | ✅ |
| 307 İç mimar hizmetleri | iç, ön | 1 (2 / 5) | 4 | 4 | ◐ 3 hizmetten 2'si |
| 308 İç detay temizlik | iç | 1 (1 / 2) | 4 | 4 | ❌ meslek yerine işletme adları |
| 309 Çevrim içi Türkçe | içi | 1 (1 / 1) | 4 | 4 | ✅ |
| 310 Vatandaş danışma birimi | birimi, ön | 1 (2 / 1) | 4 | 4 | ✅ |
| 311 Öğrenci işleri görüşmesi | işleri | 1 (3 / 2) | 4 | 4 | ❌ birim yerine ilçe adları |
| 312 Girişimcilik deneyimi | iş, deneyim | 1 (1 / 1) | 4 | 4 | ❌ meslek yerine sektör |

- **Hedef final'de:** k=8'de 11/12, k=5'te 10/12.
- **Cevap tam doğru:** 6/12 (k=8). Ama 6 başarısızın yalnızca **1'i (#304) retrieval kaynaklı**:
  - #305 ve #307 eksik: liste sorusu, 15/8 hedef profil var ama LLM'e yalnızca 4 parça gidiyor (`RERANK_TOP_N`).
  - #308, #311 ve #312'de retrieval kusursuz (4/4 hedef): model doğru profilleri okuyup **yanlış niteliği** veriyor (meslek yerine işletme adı, ilçe ya da sektör).
- **BM25'in zayıf kaldığı yer, düşen kelimenin tek ayırt edici terim olduğu sorular:** #301–303 (kişi adı), #306 (`iş`), #304. Diğerlerinde kalan terimler (`mimar`, `detay temizlik`, `vatandas`, `ogrenci`, `girisimcilik`) BM25'i 1–5. sırada tutuyor; **dense** her vakada hedefi 1–3. sıraya koyuyor (#304 hariç).

## İsim vakaları: iki kişi de geliyor mu, biri mi kayboluyor?

**İkisi de geliyor; sorun eksik chunk değil, hibrit aşamadaki sıralama.**

| # | Hibrit 1. sıra | Hedeften önde karıştırıcı | k=5 aday / final | k=8 aday / final |
|---|---|---|---|---|
| 301 Damla Akın | karıştırıcı | 2 | ikisi de / ikisi de (hedef + 3 Akın) | ikisi de / ikisi de |
| 302 Deniz Akın | karıştırıcı | 2 | ikisi de / ikisi de (hedef + 3 Akın) | ikisi de / ikisi de |
| 303 Deniz Çelik | karıştırıcı | 5 | **hedef yok, 5 Çelik** / hedef yok, 4 Çelik | ikisi de / ikisi de (hedef + 3 Çelik) |

Mekanizma:
1. BM25 sorguyu `ak hangi sehir…` olarak görüyor: ilk ad (`damla`, `deniz`) düşmüş, soyad da `ak`'a stem'lenmiş. Aynı soyadlı 9–10 kişinin BM25 skoru eşit; uzunluk normalizasyonu hedefi 42./53. sıraya itiyor.
2. **Dense hedefi 1. sırada buluyor**, ama RRF'de BM25 karıştırıcıları öne çekiyor: hedef hibritte 3. (#301, #302) ve 6. (#303) sıraya düşüyor.
3. **Reranker, aday listesine girdiği sürece hedefi her vakada 1. sıraya koyuyor.** Model de bağlamda 3 karıştırıcı olmasına rağmen doğru kişiyi seçiyor (3/3 doğru).
4. Kayıp yalnızca **aday kesiminde** oluşuyor: #303'te hedef 6. sırada olduğu için k=5'te reranker'a hiç ulaşmıyor. Final 4 parçanın 4'ü de başka "Çelik"ler. Bu ayarda cevap yanlış kişiye dayanırdı.

**Düzeltmeden beklenen etki:** İlk adın BM25'e geri gelmesi, hedefin hibrit sırasını yükseltmeli (karıştırıcılar ilk adı taşımıyor). Reranker zaten doğru sıralıyor; kazanç, hedefin aday kesiminden **düşmemesi**. Ölçülecek şey: #301–303'te hibrit sıra (3 / 3 / 6 → 1 olmalı) ve k=5 final'de #303 hedefi (0 → 1).

## Düzeltmenin çözmeyeceği vakalar (ayrı kök nedenler)

- **#304:** Avukat profillerindeki "Hukuki **ön** görüşme" + "Dosya **değerlendirme**" sorudaki iki kelimeyi ayrı ayrı karşılıyor, dense onları öne çekiyor (hedef dense 21.). `ön` geri gelse de avukatlarda da geçiyor; asıl eksik, kelimelerin yan yana geçmesine (bigram/öbek) ağırlık verilmemesi. Kısmi iyileşme beklenebilir, garanti değil.
- **#305 / #307:** Liste sorularında tamlık `RERANK_TOP_N=4` ile sınırlı.
- **#308 / #311 / #312:** Sentez sorunu. Retrieval kusursuz, model sorulan niteliği karıştırıyor. Tek başına düzeltmenin metriğini etkilemez; ayrıca izlenmeli.

## Ölçüm notları

- Cevap skoru: ground truth anahtar kelimelerinin cevapta geçme oranı (aksan/harf duyarsız). #308'de cevap doğru profilleri adıyla sayıyor ama meslek adını vermediği için 0. Bu, sorulan niteliğe göre doğru bir 0.
- Tek koşu; LLM nondeterministik. Düzeltme sonrası karşılaştırmada retrieval sütunları (deterministik) birincil, cevap sütunu ikincil ölçüt olmalı.
