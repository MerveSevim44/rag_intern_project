# Retrieval Regresyon Backlog'u

Bağlam: `2ccc796` (RRF + alan karakterizasyonu) sonrası "Kocaeli çocuk dişçisi"
sorgusunda doğru profil (3440, Gizem Arslan / Çocuk Diş Hekimi / Kocaeli)
yanlış adayların gerisine düştü. Maddeler ayrı ayrı, onayla ve ayrı commit /
PR olarak ele alınır.

| # | Madde | Durum |
|---|-------|-------|
| 1 | Aday bazında skor dökümü (`retrieve(debug=True)`) | Tamam — `2ab03c7` |
| 2 | BM25 Türkçe normalizasyon + eş anlamlı sözlük + stopword | Tamam — `7fb3b8c`, TODO `fc6828e` |
| 3 | Keyword hit boost formülü (`+0.08/(1+dense)`) düşük dense'e daha büyük boost veriyor; BM25 alaka gücüyle doğru orantılı olmalı | Tamam — `f20e3ff`: `0.08 × bm25_norm × key_coverage` |
| 4 | Linear combination vs RRF kıyası | Tamam — RRF'de kalındı. Regresyonu bozuk BM25 + RRF birleşimi üretti; düzeltilmiş BM25 ile ikisi de 3440'ı 1. sıraya koyuyor. Linear'ın daha geniş farkı madde 5'teki meta-boost kaynaklı (linear ölçekte `$.statistics` 2. sıraya giriyor). |
| 5 | `$.statistics` / meta-chunk boost'u | Tamam — `eec3c9c`: boost yalnızca meta_query / şema sorusu / kolon adı geçen sorgularda |
| 6 | Türkçe stemmer (TERM_SYNONYMS'ın yerine) | Tamam — `ed5aeb8` + `0355b2d`. Sözlüğün YERİNİ almadı, yanında duruyor (bkz. Sorun B) |
| 7 | Cevap sentezinde özne karışıklığı (test_5#115) | Kapandı — #115 artık TN (ölçüm `0355b2d`). Kasıtlı bir düzeltme yapılmadı |
| 8 | Var olmayan/yanlış kolon sorulduğunda halüsinasyon | **Kısmi kapandı** — #109 ve #115 çözüldü; #107 kabul edilmiş sınırlama olarak açık |
| 9 | RRF sıra tabanlı olduğu için BM25'teki güçlü skor marjını düzleştiriyor | Açık — teorik, somut regresyon örneği bekliyor |
| 10 | Para birimi koruması birimi siliyor ama sayıyı bırakıyor; halüsinasyonu engellemeden denetlenebilirliği azaltıyor | Açık — düşük öncelik |
| 11 | Aşırı uzun model yanıtı prompt'u ~12 KB'a taşıyor → Foundry GPU OOM | **Kısmen ele alındı** — D (`90a08e9`) 1. katmanı kapsıyor; C açık seçenek |
| 12 | `result_to_natural_language` `bool` sonuçta devrik cümle üretiyor ve ham `True` sızdırıyor | Açık — madde 8 adım 4'ten SONRA |
| 13 | **Ölçüm altyapısı körlüğü**: tam eval `data_engine`/`code_interpreter` davranışını HİÇ çalıştırmıyor | **Yapısal sınırlama** — her `data_engine` değişikliğinde hatırlanmalı; kapatılacak bir bug değil |
| 14 | "Bulunamadı" mesajı iki farklı durumu birleştiriyor: *bilgi yok* ile *şu an işlenemedi* | Açık — **kullanıcı güvenini etkileyen netlik sorunu**, düşük öncelikli değil |
| 15 | Servis süreç yönetimi: OOM sonrası Foundry bozuk kalıyor, toparlanma askıda kalabiliyor | Açık — **işletimsel dayanıklılık**, madde 11'den ayrı problem sınıfı |

## Madde 5 — Meta-chunk boost'u
Sabit `+0.35` meta-chunk boost'u sorgu tipine bakmaksızın uygulanıyor ve RRF
ölçeğini domine ediyor (normalize RRF [0..1] aralığının ~⅓'ü). Örnek: "dişçi
arıyorum" sorgusunda `$.statistics` chunk'ı BM25=0 ve dense sırası 41 iken bile
1. sıradaydı. Sorgu rotası (query routing) farkındalığı olan, koşullu bir
boost'a çevrilmeli. Madde 4 ile aynı PR'da ele alınmayacak.

Sonuç (`eec3c9c`, baz çizgisi `f20e3ff`): kaynak doğruluğu 99/100 → 99/100
(top-1 değişen soru 0). Alakasız meta-chunk'ın ilk 8'e girdiği 14 sorgunun
hepsinde çıktı. Kapının açık kaldığı 26 sorguda sıralama değişmedi. test_5
TN 10/15 → 9/15 (#115). Bu bilinçli bir trade-off, bkz. madde 7.

Gözlem (madde 3 sonrası): Profillerin keyword boost tavanı yükseldiği için
meta-chunk'ın görünürlüğü bazı sorgularda azaldı ("dişçi arıyorum"da
`$.statistics` 2. sıradan 5. sıraya indi). Ama sabit +0.35 boost hâlâ
duruyor ve farklı bir sorguda yine öne çıkabilir. Sorun çözülmedi, yalnızca
gizlendi. Bu yüzden madde 5'in önceliği düşürülmemeli.

## Madde 7 — Cevap sentezinde özne karışıklığı (test_5#115)
Soru: "Oda No: 304 hikâyesinde anlatıcının mesleği nedir?" (negatif; doğru
cevap "bulunamadı"). Madde 5'ten sonra bağlamda alakasız 728 `$.statistics`
yerine Summer School b5 geliyor ve model test2.txt p1'deki **ev sahibinin**
mesleğini ("antikacı bir amca") anlatıcınınki gibi aktarıyor. Sonuç
deterministik: iki modda 3/3. Önceki TN, alakasız bir chunk'ın tesadüfi
etkisiydi. Bu retrieval'dan bağımsız bir sentez/prompt sorunu.

Planlanacak: synthesizer prompt'u, bağlamdaki bilgiyi sorunun öznesine göre
ayırt etmeli (ör. "yalnızca doğrudan sorunun öznesine ait bilgiyi kullan;
bağlamda başka bir kişiye ait bilgi varsa onu özneye atfetme, 'bulunamadı'
de"). Önce prompt'un nerede kurulduğu (`llm_client.ask`) ve test_5 +
test_4 üzerindeki etkisi ölçülerek plan yazılacak.

## Madde 8 — Kolon adı takma ad bağımlılığı
Madde 5 planındaki risk gerçekleşti. `code_interpreter`'dan semantik aramaya
düşen 16 sorunun kapıdan geçenlerinin çoğu, yalnızca takma ad eşleşmesiyle
geçiyor ("profil" → `profileCode`/`profileType`). Kapının açık kaldığı 26
sorgudan 7'si yalnızca takma ada dayanıyor (test_5 #108/#109/#111 dahil).
Eşleşme katılaştırılırsa (tam kelime sınırı, minimum eşleşme uzunluğu vb.)
bu sorgular kapı dışında kalabilir. Örneğin test_2#45'te fieldGuide
boost'suz 11. sıraya düşer ve top-1 dilbilgisi PDF'ine kayar. Katılaştırma
gerekip gerekmediği, madde 5'in denetim scripti (meta-chunk sıraları, boost'lu
ve boost'suz) önce/sonra çalıştırılarak ölçülmeli.

## Gözlem — Keyword boost tavanı (madde 3)
Boost tavanı yükseldi: eski formülde pratikte ~0.05'ti
(`0.08/(1+dense)`, dense ≈ 0.6), yenisinde KEY alanında tam eşleşme ve en
güçlü BM25 skoru için 0.08. Üç test sorgusunda sorun çıkmadı. Ancak ileride
BM25'i fazla domine eden bir chunk türü çıkarsa (ör. KEY alanları çok kısa
ama sorguyla alakasız bir kayıt), bu tavan yeniden gözden geçirilmeli.
Şimdilik aksiyon gerekmiyor.

## Not — KEY alan tekrarı (ilk listedeki alan tekrarı testi)
DB'deki 733 profil chunk'ının hiçbirinde KEY tekrarı yok: tekrarlı hâl
`MAX_RECORD_CHARS=3000` sınırını aştığı için hepsi tekrarsız sürüme düştü.
Dense skorlarındaki değişim yalnızca yeniden sıralama + narrative kırpmadan
geliyor.

## Madde 9 — RRF'nin BM25 skor marjını düzleştirmesi
"kocaeli çocuk dişçisi" sorgusunun teşhisi sırasında çıktı. Bu sorguda **sonuç
doğru**: veri setinde Kocaeli'de tek bir çocuk diş hekimi var (`$.profiles[60]`,
DB-QMY5ZS3R / Gizem Arslan) ve sistem onu 1. sıraya koyuyor. 2. ve 3. sıradaki
adayların Antalya (`$.profiles[61]`) ve Eskişehir (`$.profiles[59]`) olması bir
sıralama hatası değil: `RERANK_TOP_N = 3` kalan iki slotu mesleği tutan ama
şehri tutmayan adaylarla doldurmak zorunda, çünkü ikinci bir doğru aday yok.
Bu maddenin konusu o sıralama değil, altındaki mekanizma.

Sorun: `kocaeli` yüksek-IDF bir terim ve BM25 bunu net ayırıyor —
21.18 (Kocaeli) vs 17.38 (sıradaki, Eskişehir), yani ~%22 marj. RRF yalnızca
*sırayı* kullandığı için bu marj tamamen atılıyor: `RRF_K = 60` ile 1. sıra ile
3. sıra arasındaki katkı farkı `1/61` vs `1/63`, yaklaşık **%3**. Şehir
sinyalinin ayırt ediciliği burada düzleşiyor. Bu sorguda sonucu değiştirmedi
çünkü dense taraf da aynı yönde oy verdi; ama dense yanlış şehirdeki bir profili
öne koysaydı, BM25'in 21 vs 17'lik marjı onu geri çekmeye yetmezdi.
`KEYWORD_BOOST_MAX = 0.08` de bu farkı telafi edecek büyüklükte değil.

Durum: **teorik kırılganlık.** Bugüne kadar hiçbir test setinde (test_2 /
test_4 / test_5, 100 soruluk kaynak doğruluğu koşusu) somut bir regresyon
üretmedi. Öncelik, dense'in yanlış şehri öne çıkardığı **gerçek bir sorgu
örneği** bulunursa yükseltilir; bulunana kadar madde 6/7/8'in gerisinde.

Neden şimdi yapılmıyor: madde 6 (stemmer) hâlâ ölçüm aşamasında (3 manuel
sorgu + tam eval + test_5 bekleniyor). RRF'nin kendisini aynı anda değiştirmek,
hangi değişikliğin hangi etkiyi yarattığını ayırt edilemez hale getirir.

Çözüm yönü henüz **net değil** ve ayrı bir tasarım tartışması gerektiriyor.
"Skor marjına duyarlı bir bileşen" eklemek, RRF'nin tercih edilme gerekçesiyle
(ölçek bağımsızlığı — bkz. `retrieval.py` ADIM 6 yorumu ve madde 4) doğrudan
çelişiyor: dense [0.6–0.8] ile BM25 [0–∞] farklı ölçekte ve RRF tam da bu yüzden
seçilmişti. Marjı geri getiren her çözüm, madde 4'te reddedilen linear
combination'a bir adım geri dönüştür. Olası yönler (hiçbiri değerlendirilmedi):
RRF'ye normalize BM25'ten küçük bir katkı eklemek, `RRF_K`'yı düşürmek (üst
sıraları keskinleştirir ama tüm sorguları etkiler), ya da yüksek-IDF KEY
eşleşmelerini `keyword_boost` üzerinden ayrıca ödüllendirmek. Aceleye
getirilmeden, kendi planıyla ele alınmalı.

## Not — Kaynak kartlarındaki skor gösterimi (`a197843`)
Aynı teşhiste çıkan ayrı ve düşük riskli bir UI bug'ı: kart sırasını reranker
belirlerken kartın üzerinde rerank *öncesi* hibrit skor basılıyordu, bu yüzden
ekranda [2] 0.9629 ile [3] 1.0247 gibi sıralamayla çelişen sayılar görünüyordu.
Retrieval mantığına dokunmadan düzeltildi. Madde 9 ile ilgisi yok; teşhis
sırasında yan ürün olarak bulundu.

## Madde 6 — Türkçe stemmer
Snowball Türkçe stemmer'ı `ed5aeb8` ile eklendi (`snowballstemmer`, bağımlılık
`0355b2d`'de requirements'a yazıldı — o commit'e kadar temiz kurulumda uygulama
açılmıyordu). Planın adımları `implementation_plan_meta_boost.md` sonundaki
"Sonraki madde (6)" listesinde.

### Sorun A — boru hattı kendi belgelediği sırayı uygulamıyordu (düzeltildi)
`_base_tokens` ve `_tokenize` docstring'leri aksanların stem için korunduğunu,
katlamanın stem'den SONRA geldiğini söylüyordu ("v3 — stem_before_fold"). Ama
`_tokenize` adım 1'de `_base_tokens_folded` çağırıyordu: fold önce, stem sonra.
Snowball Türkçe stemmer'ı ünlü uyumuna dayandığı için aksansız ASCII girdide
ekleri çözemiyor:

| kelime | fold→stem (hatalı) | stem→fold (doğru) |
|---|---|---|
| çocuğum | `cocugu` | `cocuk` |
| çocuğa | `cocugu` | `cocuk` |
| uzmanı | `uzmani` | `uzma` |

Ölçülen etki, manuel sorgu "çocuğum için dişçi lazım": `cocugu` token'ı
corpus'taki `cocuk` ile eşleşmediği için "çocuğum" BM25'e **sıfır** katkı
veriyordu — sorgunun BM25 skoru 12.39, yani "dişçi arıyorum" ile birebir aynı.
Düzeltmeden sonra 17.32; terim gerçekten ayırt edici hale geldi. Diğer iki
manuel sorgu ("Kocaeli çocuk dişçisi", "dişçi arıyorum") çekim eki taşımadığı
için değişmedi. Düzeltme: `0355b2d`.

### Sorun B — stemmer'ın kendi sınırlılığı (çözülmüyor, kabul edildi)
Sıradan bağımsız, Snowball'ın kendi davranışı:

- `hekim` → `hek` ama `hekimler` → `hekim`: aynı kökte birleşmiyor. Corpus
  "Çocuk Diş Hekimi" → `hek` üretirken "diş hekimleri" diye arayan sorgu
  `hekim` üretir ve eşleşmez.
- `uzman` → `uzma`, `uzmanlar` → `uzman`, `uzmanlık` → `uzmanlik`: dört biçim
  üç ayrı kök.
- `kocaeli'nde` → `['kocael', 'nde']`: kesme işaretinden artık token.
- `dişi` → `dis`: "diş" ile çakışıyor (aşırı stem).

**Sonuç: stemmer `TERM_SYNONYMS`'ın yerini ALMIYOR, yanında tamamlayıcı olarak
duruyor.** Planın 2. adımı (sözlüğü küçültme) İPTAL. `dişçi → diş hekimi` gibi
kurallar hâlâ sözlükten geliyor; stemmer tek başına bunu üretmiyor. Bu, maddenin
başındaki "stemmer sözlüğü küçültecek" varsayımının yanlış çıktığının kaydıdır.
Düzeltmeye çalışıp yeni bir karmaşaya girmek yerine olduğu gibi kabul edildi.

### Ölçüm sonuçları (`0355b2d`)
Ortam: Ollama `bge-m3` (embedding) + BGE-reranker-v2-m3, Foundry Local
`qwen2.5-7b-instruct-cuda-gpu:4` (GPU/CUDA).

Retrieval kaynak doğruluğu — `evaluation/eval_retrieval.py --all`, reranker açık:

| Set | Soru | Skorlanabilir | Doğru | Başarı | Ort. ms |
|---|---|---|---|---|---|
| test_1 | 30 | 30 | 30 | %100 | 13530 |
| test_2 | 30 | 30 | 30 | %100 | 16635 |
| test_3 | 30 | 30 | 30 | %100 | 9788 |
| test_4 | 10 | 10 | 10 | %100 | 8633 |
| test_5 | 15 | 0 | — | — | 15036 |
| **GENEL** | **115** | **100** | **100** | **%100** | 13134 |

Zorluk bazında 22/22 Kolay, 58/58 Orta, 20/20 Zor. Rota: SEMANTIC_RAG 105
(%91.3), CODE_INTERPRETER 10 (%8.7).

test_5 (negatif set, halüsinasyon matrisi) — `run_all.py --sets test_5`:

| Metrik | Madde 5 sonrası (`eec3c9c`) | Şimdi (`0355b2d`) |
|---|---|---|
| TN (negatif test başarısı) | 9/15 | **12/15 (%80)** |
| FP (halüsinasyon) | 6/15 | **3/15 (%20)** |
| FN | — | 0/15 |

Kalan 3 FP: **#101** (Chomsky normal formu — PDF'te olmayan algoritma adımlarını
üretti), **#107** (ortalama randevu ücreti 45.12 — veri setinde böyle bir alan
yok), **#109** (müşteri memnuniyet puanı 1.0 — code_interpreter
`customer_satisfaction_score` için KeyError aldıktan sonra "doğrulama uyarılı
sonuç" olarak `df.shape[0]/len(df)` = 1.0 döndürdü). #107 ve #109 madde 8'in
(takma ad bağımlılığı / var olmayan kolon) kapsamına giriyor, retrieval
sıralaması değil.

### Atıf uyarısı
Baz çizgi 99/100 ve TN 9/15, `eec3c9c`'de ölçülmüştü. Aradan `ed5aeb8`
(stemmer'ın ve hibrit retrieval modülünün eklenmesi) geçti. Dolayısıyla
99→100 ve 9/15→12/15 farkları **`ed5aeb8` + `0355b2d` toplamının** sonucudur;
yalnızca Sorun A düzeltmesine yazılamaz. Ayrıştırmak için `0355b2d~1`'de bir
baz koşu daha gerekir; yapılmadı. Ayrıca `report/*.csv` git'te izlenmediği ve
eski koşunun çıktısı üzerine yazıldığı için 99/100'deki başarısız sorunun
kimliği tespit edilemedi.

### Madde 7 hakkında
test_5 #115 ("Oda No: 304 hikâyesinde anlatıcının mesleği nedir?") bu koşuda
**TN** çıktı, yani model doğru şekilde "bulunamadı" dedi. Madde 7 için planlanan
synthesizer prompt değişikliği YAPILMADI; sorun retrieval tarafındaki
değişikliklerin yan etkisiyle kapandı. Tek koşuluk bir gözlem olduğu için
kırılgan olabilir — madde 5'teki TN'in de "alakasız bir chunk'ın tesadüfi
etkisi" olduğu hatırlanmalı. Yeniden görülürse madde 7 açılır.

## Not — Birim testler (`0355b2d`)
pytest 9.1.1 ile `tests/` altında 31 test: 28 geçti, 3 başarısız. Üçü de
tokenizasyon değişikliğinden bağımsız:
- `test_code_interpreter_step2.py::test_code_interpreter` ve
  `test_sandbox_and_datasets.py::test_full_pipeline` — `@pytest.mark.live`,
  Foundry Local kapalıyken `RuntimeError`.
- `test_visualization.py::test_data_engine_end_to_end_visualization` — önceden
  var olan hata; `0355b2d~1`'deki retrieval.py ile de birebir aynı şekilde
  başarısız oluyor. "45 dk üzeri seans oranları" sorgusunda `data_engine` sonuç
  üretiyor ama `extract_chart_data` `None` dönüyor. Retrieval'dan bağımsız,
  `data_engine` → `visualizer` yolunda. Backlog'a alınmadı.

pytest requirements.txt'ye eklenmedi (dev bağımlılığı, repoda
`requirements-dev.txt` yok).

## Madde 10 — Para birimi koruması denetlenebilirliği azaltıyor
Madde 8'in teşhisi sırasında yan ürün olarak çıktı (bkz.
[implementation_plan_alias_gate.md](implementation_plan_alias_gate.md)).

test_5 #107: "728_profiles.json veri setinde profillerin ortalama randevu
ücreti kaç TL'dir?" Sandbox, ücret kolonu olmadığı için
`appointmentSettings.defaultDurationMinutes` (dakika) ortalamasını aldı: 45.117.
Model cevabı "…ortalama randevu ücreti 45.12 TL'dir" diye kurdu.
`llm_client._fix_currency_hallucination` devreye girdi ve "TL"yi sildi
(`Para birimi duzeltildi: 'TL' -> '(kaldirildi)'`, iki kez). Nihai cevap:

> "728_profiles.json veri setinde profillerin ortalama randevu ücreti 45.12'dir."

Koruma uydurma para birimini kaldırmayı başardı, ama **halüsinasyonu
engellemedi**: cevap hâlâ var olmayan bir ücreti bildiriyor. Dahası, birimi
silmek sayıyı bağlamsız bıraktı — "45.12 TL" okuyan biri en azından neyin
iddia edildiğini görüp itiraz edebilirdi; çıplak "45.12" hangi büyüklüğün
söylendiğini gizliyor. Yani koruma, yanlış cevabı **daha az denetlenebilir**
hale getirdi.

Bu, "halüsinasyonu engelleme çabasının denetlenebilirliği azaltması"na dair
genel bir örnek; korumayı kaldırmak da çözüm değil (uydurma para birimi gerçek
bir sorundu, bkz. `COMPUTED_RESULT_INSTRUCTION` içindeki "Para birimi uydurma"
kuralı). Olası yönler (hiçbiri değerlendirilmedi): birimi silmek yerine cevabı
tamamen reddetmek, ya da birimi sayının çıktığı kolon adıyla değiştirmek
("ortalama randevu süresi 45.12 dakika").

Düşük öncelik: #107'nin asıl sorunu birim uyuşmazlığı (madde 8 planındaki
4. adım). Bu madde o çözülünce zaten büyük ölçüde konusuz kalabilir —
ama kararı o zaman verilmeli, şimdi kapatılmamalı.

### Ek kanıt — adım 4 envanterinden (tekil kaza değil, düzenli davranış)
Madde 8'in `raw_result` envanteri koşulurken (bkz.
[implementation_plan_alias_gate.md](implementation_plan_alias_gate.md)) para
birimi koruması **11 vakanın 3'ünde** tetiklendi: `np.float64` (#107),
`pd.Series` ve saf `float`. Üçü de sayısal sonuç.

Yani model, hesaplama sonucunda hiçbir para birimi geçmemesine ve prompt'ta
açık bir "PARA BİRİMİ KURALI" yasağı bulunmasına rağmen sayısal sonuçlara
kendiliğinden "TL" ekliyor; koruma da düzenli olarak devreye girip siliyor.
İlk kayıtta bu #107'ye özgü bir gözlem gibi duruyordu; envanter bunun
sistematik olduğunu gösteriyor.

Önceliğin yükseltilip yükseltilmeyeceği madde 8 bitince değerlendirilecek.

## Madde 11 — Düzeltme zinciri prompt'u şişirip servisi çökertiyor
Madde 8'in adım 3 regresyon koşusu sırasında ortaya çıktı, ama **madde 8 ile
aynı hata sınıfı değil.** Buraya o yüzden ayrı yazılıyor.

### Kök neden — DÜZELTİLDİ (ilk kayıt yanlıştı)
**İlk kayıt "history sınırsız büyüyor, prompt katlanarak şişiyor" diyordu.
Ölçüm bunu çürüttü ve buraya doğrusu yazıldı.**

Geçmiş sınırsız DEĞİL: `max_retries=3` onu üç girdiyle sınırlıyor. Sentetik
ölçümde büyüme yalnızca %26 (9.093 → 11.454 karakter) — tek başına 2.27 GB'lık
bir tahsis talebini açıklamıyor.

Gerçek zincir, `call_llm_text` çağrılarının izlenmesiyle ölçüldü:

| Soru | Yanıt boyutları | Prompt dizisi | Sonuç |
|---|---|---|---|
| #32 | 166 / 5 / 72 krk | 9.158 → 962 → 1.105 | ✅ geçti |
| #57 | 569 / 5 / 118 krk | 9.196 → 1.484 → 1.224 | ✅ geçti |
| **#43** | 852 / **2.266** krk | 9.178 → 10.735 → **11.970** | ❌ 3. çağrıda 500 |
| **#53** | **2.322** krk | 9.351 → **12.575** | ❌ 2. çağrıda 500 |

Belirleyici olan **tek bir aşırı uzun model yanıtı**, biriken turlar değil.
~2.3 KB'lık yanıtlar `MAX_ANSWER_TOKENS = 600` tavanına dayanmış (Türkçe
token yoğun), yani model kendini kesene kadar yazmış. O yanıt `history`'ye
aynen gömülünce bir sonraki düzeltme prompt'u ~12 KB'ı aşıyor ve ONNX runtime
2.27 GB'lık bir tahsis isteyip başarısız oluyor.

Eşik ~12 KB civarında: #53 ikinci çağrıda 12.575 ile, #43 üçüncü çağrıda
11.970 ile düştü. #57 bu koşuda geçti ama daha önceki toplu koşuda düşmüştü —
yani eşiğe yakın sorularda sonuç GPU'da o an boşta olan belleğe de bağlı,
tam deterministik değil.

Not: #32 ve #57'nin 2. ve 3. çağrılarının küçük olması (≈1 KB) yanıltmasın —
onlar düzeltme prompt'u değil, `_semantic_check` / `result_to_natural_language`
çağrıları.

Gözlemlenen koşu (test_2 #43, `experience.credentialSummary` / `occupation`
karşılaştırması):

```
Deneme 1: uzun kod, tanımsız percent_change  -> ValueError
Deneme 2: NEREDEYSE AYNI kod                 -> aynı ValueError
Deneme 3: prompt iki uzun kod bloğu + iki hata taşıyor
          -> openai.InternalServerError: 500
             onnxruntime::BFCArena::AllocateRawInternal
             Failed to allocate memory for requested buffer of size 2278526976
```

### Gözlemlenen etki
`code_interpreter_with_retry` bu istisnayı **yakalamıyor**. `call_llm_text`
içinden fırlayan hata `query_tabular_data` → `retrieve` zincirini boydan boya
geçiyor ve çağrı tamamen patlıyor. Uygulamada kullanıcıya cevap değil, 500
hatası yansır.

### `repeated` bayrağı neden durdurmuyor — ölçülen cevap
Tekrar tespiti zaten var (`code_interpreter.py:548`: `repeated = norm in
seen_codes`), ama **durdurma koşulu değil, prompt yönlendirme sinyali.**
Yaptığı tek şey `build_correction_prompt`'a bir uyarı metni eklemek
("Ayni kodu tekrar yazmak YASAK, farkli bir yaklasim sec", satır 392-397).
Döngüde `repeated` True olduğunda `break`/erken dönüş yapan hiçbir dal yok;
akış bir sonraki denemeye devam ediyor.

Yani tasarım niyeti "tekrarı **tespit edip bir sonraki denemeyi iyileştirmek**",
"tekrarı görünce **durmak**" değil. Ters etkisi de var: tekrar tespit edildiğinde
prompt KÜÇÜLMÜYOR, tam tersine büyüyor — tekrarlanan kod ve hatası `history`'ye
koşulsuz ekleniyor (satır 559) ve üstüne bir de uyarı metni biniyor. Yani
tekrarı fark etmek, OOM'a giden yolu hızlandırıyor.

Bu bir gözlemdir, çözüm önerisi değil; maddeyi ele alan kişi bu soruyu baştan
araştırmasın diye kaydedildi.

### Etki alanı ÖLÇÜLDÜ — sanılandan geniş (D ölçümü sırasında)
Madde 11'in etkisi tek bir sorunun cevabını kaybetmekle sınırlı değil. Üç
katman ölçüldü:

1. **Sorunun kendi cevabı kayboluyor** (bilinen).
2. **Servis sonraki istekler için bozuluyor.** test_2'nin 14 CI sorusu sırayla
   koşulduğunda #43'ün OOM'undan SONRAKİ 9 sorunun hepsi
   `RuntimeError: Model yanıt veremedi` verdi. Foundry'nin yönetim servisi
   HTTP 200 dönmeye devam ediyordu (yani "ayakta" görünüyordu) ama model
   yanıt vermiyordu ve süreç RAM'i 4 GB'a şişmişti. Yani **bir ağır soru,
   kullanıcının o oturumdaki sonraki TÜM sorularını bozuyor.** Daha önce
   "#45 toplu koşuda düştü, izole koşuda geçti" gözlemi de bununla açıklanıyor.
3. **Toparlanma mekanizmasının kendisi güvenilir değil.** `foundry service
   stop/start` çevrimi bu oturumda **3 kez bağımsız olarak askıda kaldı** ve
   çağıran süreci kilitledi; D'nin ölçümünü tamamlamak için her seferinde
   **manuel müdahale** (askıdaki süreçleri sonlandırma) gerekti.

### Seçenek C'nin yeniden konumlandırılması (D ölçümünden sonra)
C (prompt boyutu tavanı + geçmiş girdilerini kırpma) ilk değerlendirmede
"düşük öncelikli" bırakılmıştı; gerekçe "yalnızca iki sorunun cevaplanmasını
sağlar, karşılığında keyfi bir sabit getirir" idi. **Etki alanı ölçüldükten
sonra bu gerekçe eksik kalıyor:** C, OOM'un OLUŞMA olasılığını azalttığı için
yalnızca 1. katmanı değil, 2. katmanı da (servisin bozulması) hedefliyor —
OOM olmazsa servis de bozulmaz.

C ile "toparlanamayan servisi zorla yeniden başlatma" **birbirinin yerine
geçmez, tamamlayıcıdır**:
- **C = önleyici** — OOM'un oluşma olasılığını azaltır.
- **Zorla yeniden başlatma = tepkisel** — OOM oluştuktan sonra sistemin kendini
  toparlamasını sağlar (bkz. madde 15).

Etiket: **"düşük öncelikli" DEĞİL, "acil" de DEĞİL.** Madde 11'in bir sonraki
turunda C ile yalnızca-toparlanma-güçlendirme kıyası yeniden yapılmalı, çünkü
C'nin faydası ilk düşünülenden geniş. Keyfi sabit sorunu ve eşiğin
deterministik olmaması itirazları hâlâ geçerli.

### Sonuç: çözümün kapsamı genişliyor
Üretimde bu manuel müdahale mümkün olmayabilir. Servis kendi kendine
toparlanamıyorsa, madde 11'in çözümü yalnızca **"çökmeyi yakala"** olamaz;
**"toparlanamayan servisi de tespit et ve zorla yeniden başlat"** kısmını da
içermelidir. Bu, D'nin (istisna yakalama) kapsamının ötesinde ve ayrı bir
tasarım kararı gerektiriyor.

### D'nin SINIRI — açıkça
D (`call_llm_text` istisnasını yakalayıp `success: False` dönmek) çökmenin
kullanıcıya 500 olarak yansımasını engelliyor, **ama servisin bozulmasını
engellemiyor.** D uygulandıktan sonra bile #43'ten sonraki sorular bozuk
servise çarpıyor. "D madde 11'i çözdü" diye okunmamalı; D yalnızca 1. katmanı
kapsıyor.

### Öncelik notu
Bu madde diğerleriyle **aynı ölçekte sıralanmamalı.** Madde 8 "yanlış ama
kendinden emin cevap" sınıfı; bu madde "sistemin tamamen çökmesi" sınıfı.
Kullanıcı deneyimi açısından çökme daha kötü bir sonuç olabilir: halüsinasyon
en azından bir cevap veriyor ve denetlenebiliyor, çökme hiç cevap vermiyor.
Bu yüzden "düşük öncelik" diye işaretlenmedi — sıraya sokulmadan, ayrıca
değerlendirilmesi gereken bir madde olarak duruyor.

Şimdi çözülmüyor: madde 8'in adım 3'ü (regresyon koşusu + test_5 + tam eval)
tamamlanmadan ne bu maddeye ne de madde 8'in adım 4'üne geçilmiyor.

## Madde 12 — `bool` sonuçta devrik cümle ve ham değer sızması
Madde 8'in adım 4 envanterinde çıktı (bkz.
[implementation_plan_alias_gate.md](implementation_plan_alias_gate.md)).

`result_to_natural_language`'a `bool` bir sonuç geldiğinde üretilen cümle hem
devrik hem de ham değeri sızdırıyor:

```
SORU  : Veri setinde hiç business profil var mı?
RAW   : True
CUMLE : "Veri setinde hiç business profil var. True"
```

Beklenen: "Veri setinde business profil vardır." Şu anki çıktıda hem "hiç …
var" yapısı bozuk (olumsuzluk beklerken olumlu bitiyor) hem de cümlenin sonuna
`True` iliştirilmiş.

`bool`, `formatted_result` için ayrı bir dal DEĞİL — `else` dalına düşüyor ve
prompt'a çıplak `True` olarak giriyor. Model bunu bir değer olarak aktarmaya
çalışıyor.

**Adım 4 ile aynı commit'te düzeltilmeyecek.** Adım 4 aynı fonksiyonun
girdisini değiştiriyor ve bu dala da dokunacak; iki düzeltme karışırsa hangisinin
neyi etkilediği ayrılamaz. Adım 4 tamamlanıp ölçüldükten sonra ele alınacak.

Kapsam notu: envanterde yalnızca tek bir `bool` vakası denendi. Ele alınırken
önce `False` durumu ve "var mı / yok mu" kalıplarının başka biçimleri de
örneklenmeli; tek örnekten genelleme yapılmamalı.

## Madde 8 — kısmi kapanış ve #107'nin kabul edilmiş sınırlama olarak bırakılması
Tam kayıt: [implementation_plan_alias_gate.md](implementation_plan_alias_gate.md).

Çözülenler (commit edilmiş, kalıcı):
- **#109** (`3918a75`) — doğrulama uyarılı sandbox sonucu artık kesin cevap gibi
  sunulmuyor. FP → TN.
- **#115** — madde 7'nin konusuydu, retrieval değişikliklerinin yan etkisiyle
  düzeldi.

Açık bırakılan: **#107** ("ortalama randevu ücreti kaç TL" sorusuna
`appointmentSettings.defaultDurationMinutes` ortalamasının aktarılması).

### Neden kapatılmadı — kök neden
Sorunun veriye referans verme biçimleri **açık uçlu**: kolon adı, Türkçe takma
ad, kolonun bir değeri ("Umut Aslan" → `displayName`), kısmi değer, sayısal
aralık ifadesi ("30 dakikadan az"), dolaylı referans ("bu kişinin randevu
ayarları")... Pattern-matching tabanlı bir kapı bunu tam kapatamıyor.

Üç deneme yapıldı, üçü de bir sonraki turda çürüdü:
1. Prompt'a alan adı verme → model talimatı yoksaydı.
2. Kolon-soru örtüşme kapısı (alias tabanlı) → alias boşlukları.
3. Değer farkındalığı → bir yanlış pozitif sınıfını yanlış negatif sınıfıyla
   takas edeceği öngörüldüğü için denenmedi.

Üçüncü turda ayrıca şu ortaya çıktı: kapı, bir kolonun **filtre** rolüyle
**hesaplanan büyüklük** rolünü ayırt edemiyor (#39/#42'de `displayName` filtre).
Ayırmak kod yapısını ayrıştırmayı gerektirir.

### Kalıcı çözüm muhtemelen deterministik değil
İki seçenek var ve ikisi de şimdi seçilmedi:
- **Kabul edilebilir kalıntı risk olarak bırakmak** (şu anki karar).
- İleride **ayrı bir LLM tabanlı doğrulama katmanı** değerlendirmek — kendi
  maliyeti (ek çağrı, gecikme) ve güvenilirlik ödünleşimiyle. Madde 8 boyunca
  LLM muhakemesine bel bağlamaktan kaçınıldı çünkü `_semantic_check` #107'de
  zaten çalışıp itiraz etmemişti; ayrı bir katman bu deneyimi hesaba katmalı.

Heuristik yarışına devam edilmemesinin gerekçesi: her katman kendi test yükünü,
kendi kenar durumlarını ve kendi bakım borcunu getiriyor; çözülen tek vakanın
(#107) değeri bu maliyeti karşılamıyor.

## Madde 13 — Tam eval'in yeşil olması `data_engine` için kanıt DEĞİLDİR
Bu bir bug kaydı değil, **ölçüm altyapımızdaki yapısal bir körlüğün** kaydıdır.
Kapatılmayacak; her `data_engine` / `code_interpreter` değişikliğinde
hatırlanacak.

### Tespit
`evaluation/eval_retrieval.py:106` retrieval'ı şöyle çağırıyor:

```python
retrieved_chunks = retrieve(question, top_k=5, use_reranker=True)   # llm YOK
```

`src/data_engine.py:658` ise sandbox'a girmek için şunu arıyor:

```python
if llm is not None:
```

Yani tam eval koşusunda **`code_interpreter` hiç çalışmaz**, sandbox'a hiç
girilmez, `data_engine`'in hesaplama yolu hiç yürütülmez. CI rotasına atanan
sorular sessizce semantik RAG'e düşer.

Ölçülmüş kanıt: madde 8'in B varyantı için konan kapı, tam eval log'unda
**sıfır** karar üretti (`grep -c kolon_kapisi` → 0), oysa aynı sorular
`query_tabular_data(q, llm=...)` ile koşulduğunda 16 karar üretti.

### Neden tehlikeli
Tam eval'in "100/100" çıktısı doğrudur ama YALNIZCA şunu söyler:
**retrieval sıralamasına sızma olmadı.** `data_engine` veya `code_interpreter`
davranışı hakkında hiçbir şey söylemez. Bu ayrım yapılmazsa biri "tam eval
geçti, commit edilebilir" diye yanlış güvenebilir — bu oturumda adım 2 ve adım 4
için tam olarak bu risk doğdu ve son anda fark edildi.

### Kural
`data_engine` / `code_interpreter` / sandbox davranışını değiştiren HER
değişiklik şu iki ölçümle ayrıca doğrulanmalı; tam eval bunların yerini
TUTMAZ:

1. **test_2'nin `code_interpreter` rotasına giden soruları**, soru bazında
   önce/sonra (pozitif, hesaplanmış cevap bekleyen tek anlamlı küme).
2. **test_5** TN/FP (negatif set, halüsinasyon matrisi) —
   `run_all.py --sets test_5` LLM cevaplarını gerçekten üretir.

Tam eval yine koşulmalı, ama yorumu "retrieval'a sızma yok" ile sınırlı
kalmalı.

### Neden "düzeltilmiyor"
`eval_retrieval.py`'a llm bağlamak, retrieval değerlendirmesinin süresini ve
determinizmini bozar (her CI sorusu için sandbox + düzeltme döngüsü; bkz.
madde 11'in OOM'u). Ayrı ölçüm zaten mevcut ve yeterli; eksik olan, tam eval'in
neyi kapsamadığının YAZILI olmasıydı. Bu madde o boşluğu kapatır.

## Madde 14 — "Bulunamadı" mesajı iki farklı durumu birleştiriyor
Madde 11'in D ölçümünde ortaya çıktı (bkz.
[implementation_plan_retry_oom.md](implementation_plan_retry_oom.md)).

D uygulandıktan sonra test_2 #43 ve #53 artık kullanıcıya 500 vermiyor; sandbox
çöküşü yakalanıyor, akış semantik RAG'e düşüyor ve synthesizer doğru şekilde
şunu diyor:

> "Bu bilgi dokümanlarda bulunamadı."

Kullanıcı deneyimi ham bir 500'e göre çok daha iyi ve mesaj sistemin başka
yerlerde de kullandığı tutarlı ret cümlesi. **Ama cümle teknik olarak yanlış.**

Bilgi dokümanlarda VAR (`experience.credentialSummary`, `occupation` —
#43'ün sorduğu alanların ikisi de `728_profiles.json` içinde). Bulunamayan
şey bilgi değil; sistem hesaplayamadı. Aynı cümle şu anda üç farklı durumu
birden anlatıyor:

1. Sorulan bilgi veri setinde gerçekten yok (test_5 negatif seti — doğru kullanım).
2. Filtre 0 satır döndürdü (`NO_MATCH_SUMMARY` yolu).
3. **Sistem teknik bir sebeple işleyemedi** (madde 11 çökmesi — yanlış kullanım).

### Neden düşük öncelikli değil
Kullanıcı "veri yok" anladığı için **soruyu bir daha sormaz**. Oysa 3. durumda
tekrar denese çalışabilir: madde 11'in eşiği deterministik değil (#57 bir
koşuda düştü, diğerinde geçti — GPU'da o an boşta olan belleğe bağlı). Yani
sistem, geri kazanılabilir bir başarısızlığı kalıcı bir yokluk gibi sunuyor.
Bu bir kullanıcı güveni / netlik sorunu.

### Kayda geçen ifade
"Bulunamadı" ile "şu an işlenemedi" arasındaki ayrımın kullanıcıya doğru
yansıtılması gerekiyor; bu iki farklı durumu aynı cümlede birleştirmek
yanıltıcıdır.

Çözüm şimdi tasarlanmadı. Ele alınırken dikkat: `EMPTY_RESULT_INSTRUCTION`
bilinçli olarak ÇIPLAK ret istiyor, çünkü `benchmark_eval`'in
`check_is_not_found` kontrolü ret cümlesinden sonra 3+ içerik kelimesi kalırsa
cevabı ret DEĞİL "iddia" sayıyor (bkz. `retrieval.py` içindeki açıklama ve
negatif set #231). Mesajı zenginleştiren her çözüm bu ölçüm tanımıyla
çakışabilir — yani düzeltme, ölçüm tarafını da beraberinde düşünmeyi
gerektiriyor.

## Madde 15 — Servis süreç yönetimi ve toparlanma güvenilirliği
Madde 11'den **ayrı bir problem sınıfı.** Madde 11 prompt mühendisliği /
kaynak yönetimi ("prompt neden ~12 KB'ı aşıyor"); bu madde işletimsel
dayanıklılık ("servis çöktükten sonra ne oluyor"). Tek maddede tutulursa
"madde 11 çözüldü" denip toparlanma sorununun unutulması riski var.

### 1. OOM sonrası Foundry bozuk kalıyor
test_2'nin 14 CI sorusu sırayla koşulduğunda, #43'ün OOM'undan SONRAKİ 9
sorunun hepsi `RuntimeError: Model yanıt veremedi` verdi. Kritik ayrıntı:
**yönetim servisi HTTP 200 dönmeye devam ediyordu**, yani dışarıdan "ayakta"
görünüyordu; ama model yanıt vermiyordu ve süreç RAM'i 4 GB'a şişmişti.
Basit bir health check (endpoint cevap veriyor mu) bu durumu YAKALAMAZ.

Aynı gözlem daha önce "#45 toplu koşuda düştü, izole koşuda geçti" olarak
karşımıza çıkmış ama yanlış yorumlanmıştı ("GPU belleği birikiyor").

### 2. Toparlanma mekanizmasının kendisi askıda kalabiliyor
`foundry service stop/start` çevrimi bu oturumda **3 kez bağımsız olarak**
askıda kaldı ve çağıran süreci kilitledi (bir kez 30 dakika). Her seferinde
manuel müdahale (askıdaki `powershell.exe` süreçlerini sonlandırma) gerekti.

**Çözüm bulundu ve çalıştı — sıfırdan başlanmasın:**
`recover.sh` (ölçüm için yazıldı, repo'da değil):
- `timeout 30` ile stop/start çevrimine sert tavan,
- ardından son 2 dakikada başlamış askıda `foundry`/`powershell` süreçlerini
  zorla temizleme,
- ardından 15 saniye boyunca servisin GERÇEKTEN cevap verdiğini doğrulama
  (yeni portu `foundry service status` çıktısından okuyarak).

Bu koruma ile 4. bir manuel müdahale gerekmedi.

### 3. Ollama da düştü — TEK GÖZLEM, doğrulama bekliyor
Bir koşuda `Embedding olusturulamadi: llama runner process has terminated`
alındı (test_2 #53), hemen #52'nin OOM'undan sonra. **Tekrarlanmadı**: aynı
soru temiz servisle koşulduğunda normal çalıştı.

Bu, kararsızlığın Foundry'ye özgü olmayıp genel bir kaynak baskısı olabileceğini
düşündürüyor, **ama tek örnekten bu iddia kurulamaz.** İkinci bir gözlem
görülürse buraya eklenmeli; görülmezse bu satır tekil bir olay olarak kalmalı.

### Uzun vadeli çerçeve
Bu madde muhtemelen bir **process supervisor** tasarımı gerektiriyor:
- **Health check** — endpoint'in HTTP 200 dönmesi YETMEZ (yukarıdaki 1. madde);
  modelin gerçekten yanıt verdiğini sınayan bir kontrol gerekir.
- **Otomatik restart** — bozuk durum tespit edilince, kullanıcıdan bağımsız.
- **Zaman aşımı** — restart'ın kendisi de askıda kalabildiği için (2. madde).

`recover.sh`'ın 30 saniyelik tavanı bunun ilk parçası sayılabilir; üretime
taşınacaksa bu üç bileşenle birlikte tasarlanmalı.
