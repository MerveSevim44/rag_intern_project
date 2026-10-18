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
| 16 | Semantik doğrulayıcının LLM çağrısı çökünce sonuç doğrulanmış gibi `[KESİN HESAPLAMA SONUCU]` olarak gidiyor | **A uygulandı ve ölçüldü** — izole koşuda `failed` 0/26; B düşük öncelik (gözlenmiş vaka yok, asıl sorun madde 18). Bkz. [implementation_plan_validator_failure.md](implementation_plan_validator_failure.md) §9 |
| 17 | `test_visualization::test_data_engine_end_to_end_visualization` kırık: rule engine karşılaştırma sorusunu tek sektör sayımına eşliyor | Açık — **bilinen kırık test**, `10f5efc` öncesinden beri; ne zaman başladığı bilinmiyor |
| 18 | Semantik doğrulayıcı gevşek: "emin değilsen TAMAM" yanlış hesapları `ok` ile geçiriyor | Açık — **4 deterministik test vakası** (#44, #51, #57, #107); madde 16'nın asıl sorunu |
| 19 | Snowball stem'i stopword'e çakışan gerçek kelimeler BM25'ten düşüyor ("deneyim" → "de", "Damla" → "da") | **Düzeltildi** — yüzey stopword filtresi + çakışma koruması; bkz. [implementation_plan_bm25_stopword.md](implementation_plan_bm25_stopword.md) §9 |
| 20 | Router kolon parçası eşleşmesi (2b, açık) ve benchmark `top_k=5` ≠ arayüz `TOP_K=8` | top_k kısmı **Düzeltildi**; 2b **Açık** |
| 21 | LLM-judge, ground truth'u olan sorulardaki retleri "dürüst ret" diye ödüllendiriyor | Açık — ölçüm körlüğü |
| 22 | OCR'lı "Cevap N" sayfaları retrieval'a gelmiyor | **Düzeltildi** — `5b494b2` (Örnek/Cevap birleştirme) + yeniden ingest; hedef 5/5 Cevap bağlamda, plan ölçütlerinin hepsi geçti. Kalan açık (OCR kalitesi) → madde 31 |
| 23 | Madde 19 korumasındaki kelimelerin çekimleri farklı token'a düşüyor ("deneyim" / "deneyimi") | Açık — bilinen sınır; bugünden kötü değil |
| 24 | OCR'lı alıştırma sayfaları negatif sorularda dolgu olarak bağlama girip uydurma ürettiriyor (test_5 #103) | Açık — **daraltıldı** (2026-10-12): yalnız #103; #224 → madde 30. Yön C (görev notu) ölçüldü ve reddedildi, kod geri alındı (`9e3a095`). D (sabit reranker eşiği) simüle edildi ve reddedildi (1 FP için 3 TP); madde 22 #103'ü çözmüyor. Açık aday: bağıl eşik (ölçülmedi) |
| 25 | Ret tespiti yarım "…bulunmadığından" cevabını tanımıyor (skorlama + üretim) | **Skorlama düzeltildi** — `f888033` (ret çerçevesi, #222 FP→TN) + `8b5d26f` (tanımlayıcı yankısı, v3 #26 TP→FN); üretim kısmı → madde 26, kalan açık → madde 28 |
| 26 | Üretim: model serbest biçimli reddi yarıda bırakıyor ("…bulunmadığından") | Açık — düşük öncelik; v8'de 1/144 (#222) |
| 27 | bge-m3 bazı metinlere NaN embedding döndürüyor; `semantic_sim` sessizce 0.0 yazıp ortalamaya katıyor | **Düzeltildi** — `ecc7f5a` (eksik değer + skorlayıcı embedding'i CPU'ya sabit) + `0d179ab` (testler); v7 #36 0.0 → 86.7, tekrar skorlamada 0 fark (`baf5cb0`). P öncesi `semantic_sim` değerleri "cihaz karışımı" (bkz. madde 27 kapanış notu) |
| 28 | Ret tespitinin ikinci aşaması içerik miktarına bakmıyor; ret kapısından geçen içerik cevapları yalnız tesadüfi "iddia"larla TP kalıyor | Açık — v3 #29 gizli FN; madde 25 Adım 3'te bilinçli bırakıldı |
| 29 | Ollama bge-m3 embedding güvenilirliği: oturumlar arası sayısal kayma sınırdaki retrieval'ı değiştiriyor | **Düzeltildi** — `EMBED_NUM_GPU=99` ile sorgu GPU'ya sabitlendi (`src/embedder.py`, `src/ingest.py`); yerel Ollama + `rag.db` ile 2 ayrı süreçte (#36, #93, #217) 0 fark doğrulanarak kapatıldı |
| 30 | Synthesizer (a) dalı ödünleşiminin sınır vakası: "Yanlış Ön Kabul" sorusu #224 bağlama göre FP/TN arasında gidip geliyor | Açık — **bug değil, bilinçli alınmış dengenin yeniden değerlendirilmesi** (FN 25→10 karşılığında kabul edilen bedel) |
| 31 | OCR'lı Cevap sayfalarının metin kalitesi: bir sayfa okunamıyor (#24), diğerlerinde üst simge / "\|" kaybı model cevabına aynen geçiyor | Açık — iki ayrı ciddiyet: okunamayan sayfa (yeniden OCR) / kısmi bozulma (son işleme) |

### Öncelik sırası (2026-10-11, güncelleme 2026-10-13)

Açık retrieval/değerlendirme maddeleri için sıra: **25 (skorlama) ✅ → 22 ✅ → 27 ✅ → 29 ✅ → 20 → 21 → 31 → 24 (bağıl eşik) → 30 → 28 → 26.**

- **25 önce:** madde 24'ün başarı ölçütü negatif set FP sayısı; skorlayıcı yarım
  retleri FP saydığı sürece (#222) bu sayı yapay olarak şişik ve 24'ün etkisi
  ölçülemez. Yalnız skorlama kısmı; üretim kısmı ayrıca değerlendirilir.
- **22, 24'ün önüne alındı (2026-10-12):** (1) Örnek/Cevap birleştirme OCR
  chunk'larının uzunluğunu ve BM25 davranışını değiştirir; #103'te dolgu olarak
  giren sayfa 24/28 doğrudan etkilenir — D şimdi ölçülse 22 sonrası yeniden
  ölçülmesi gerekirdi. (2) 22'nin hedefi somut: bilinen FN/yanlış cevaplar
  (#25, #26, #29 — Cevap sayfası gelmiyor), etki alanı 10 OCR sayfası. (3) D
  genel ve riskli bir değişiklik, tek negatif soru için; 22 sonrası #103
  kendiliğinden düzelirse gereksiz kalabilir.
- **2026-10-13 güncellemesi:** 22 kapandı. 27 öne geçti: küçük, yalnız
  skorlayıcıda, ve her benchmark'ın `semantic_sim` ortalamasını etkiliyor; 29
  ile aynı kök sorusunu paylaştığı için hemen ardından 29. **24 geriye alındı:**
  sabit eşik reddedildi, bağıl eşik ölçülmedi ve kazancı tek FP (#103) — pozitif
  soruları riske atan genel bir değişiklik için düşük getiri. **31** (OCR
  kalitesi) 5 alıştırma sorusunun cevap kalitesini etkiliyor, sınıf
  değiştirmiyor; ölçüm körlüğü maddelerinden (20, 21) sonra.
- **24 (D):** daraltılmış hâli yalnız test_5 #103 (OCR dolgu); aday çözüm
  reranker alaka eşiği, kendi riskiyle ölçülerek (bkz. madde 24 durum notu).
  Önce 22 sonrası #103'ün durumu yeniden ölçülür.
- **20, 21:** sistemin cevaplarını değiştirmiyor (benchmark ayarı / ölçüm körlüğü).
- **27:** "sessizce yanlış ortalama" ailesinden (`HATA:` satırlarının F1'i
  bozması gibi); düzeltmesi küçük ve yalnız skorlayıcıda. 24'ün ölçütü (negatif
  FP sayısı) `semantic_sim`'e dayanmadığı için 24'ün önüne alınmadı.
- **29:** 27'nin yanında — ikisi de Ollama bge-m3 embedding üretimi; aynı kökten
  geliyorsa biri araştırılırken diğeri de aydınlanır.
- **30:** gerileme değil, bilinçli bir denge; yeniden açılması tam benchmark +
  tam negatif set gerektiriyor ve FN tarafını riske atıyor. Ölçüm körlüğü
  maddelerinden (20, 21) sonra.
- **28:** bilinen etkisi tek gizli FN (v3 #29); 21 ise #24–#29'un hepsini
  görünmez kıldığı için önce 21. 24'ün ölçümünü bugün etkilemiyor (bkz. madde 24
  ölçüm notu); etkilemeye başlarsa 24'ün hemen arkasına alınır.
- **26:** ölçümü etkilemiyor (skorlama `f888033`'ten beri bu cevabı ret sayıyor).

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

### 4. Tekrar gözlemleri (2026-10-12/13)
- **OOM sonrası Foundry bozuk kaldı — 1. maddenin gerçek tekrarı.** Madde 22
  Adım 3'te (2026-10-13) negatif setin 62. işinden sonra "GPU bellek hatası" →
  ardından her istek `Model yanıt veremedi` / code_interpreter `Error code: 500`
  (#227, #228, #229). Servis kendiliğinden toparlanmadı; `foundry service stop`
  + kalan süreçleri sonlandırma + `start` ile yeni portta ayağa kalktı, kalan
  işler sorunsuz koştu. Ölçüm script'lerindeki "3 ardışık hatada dur" sınırı
  (madde 24/22 sürücüleri) bozuk servise karşı yanlış sonuç yazılmasını önledi.
- **`foundry service start` askıda kalıyor — 2. maddenin tekrarı, 3 kez:**
  2026-10-12 (madde 24 Adım 3 öncesi) ve 2026-10-13 (koşu öncesi + OOM sonrası
  yeniden başlatma). Üçünde de komut dönmedi ama servis yeni bir portta
  çalışır hâle geldi (`foundry service status` 40 sn zaman aşımıyla doğrulandı).
  `recover.sh` ile aynı desen (komuta zaman aşımı + ardından durumu ayrıca
  doğrulamak; burada PowerShell iş zaman aşımıyla uygulandı) yeterli oldu.

### Uzun vadeli çerçeve
Bu madde muhtemelen bir **process supervisor** tasarımı gerektiriyor:
- **Health check** — endpoint'in HTTP 200 dönmesi YETMEZ (yukarıdaki 1. madde);
  modelin gerçekten yanıt verdiğini sınayan bir kontrol gerekir.
- **Otomatik restart** — bozuk durum tespit edilince, kullanıcıdan bağımsız.
- **Zaman aşımı** — restart'ın kendisi de askıda kalabildiği için (2. madde).

`recover.sh`'ın 30 saniyelik tavanı bunun ilk parçası sayılabilir; üretime
taşınacaksa bu üç bileşenle birlikte tasarlanmalı.

## Madde 16 — Semantik doğrulayıcının sessiz çökmesi

`code_interpreter._semantic_check` LLM çağrısı istisna fırlatınca `None`
("itiraz yok") dönüyordu. Doğrulanmamış sonuç `[KESİN HESAPLAMA SONUCU]`
etiketiyle synthesizer'a gidiyor ve log'da "TAMAM" ile aynı izi bırakıyordu.
Ayrıca son denemenin sonucu tasarım gereği hiç doğrulanmıyor.

Faithfulness bunu yakalayamaz: yanlış sayı context'te `KESİN` olarak durduğu
için cevap onu sadakatle tekrarlar ve F=5 alır. Ground truth'a karşı doğruluk
gerekir.

**A aşaması (davranış değişmez):** dönen sonuca `validation_status`
(`ok` / `objection` / `failed` / `not_run`) eklendi ve data_engine → retrieval
chunk'ına kadar taşındı. Çökme `verbose`'dan bağımsız
`DOGRULAYICI CALISMADI` satırıyla log'a yazılıyor. **B** (`failed` →
`[DOĞRULANAMAYAN SONUÇ]` mı, tek retry mı) ölçüm sonrasında kararlaştırılacak.
Plan, ölçüm ve okuma kuralı:
[implementation_plan_validator_failure.md](implementation_plan_validator_failure.md).

## Madde 17 — Bilinen kırık test: `test_data_engine_end_to_end_visualization`

Validator A (`10f5efc`) sırasında tam test paketi koşulurken fark edildi; o
değişiklik geri alınınca da aynı şekilde kırık, yani **önceden var**. Ne zaman
kırıldığı bilinmiyor (test dosyası `22028c4`'ten beri değişmedi).

Hata:

```
AssertionError: Sorgu için chart_data üretilemedi: Psikoloji ve Danışmanlık ve
Ağız ve Diş Sağlığı sektörlerindeki 45 dk üzeri seans oranları karşılaştırması
```

Kök neden testte değil, rule engine'de: soru beklenen
`service_duration_sector_comparison` kuralı yerine `filtered_count_sector`
kuralına eşleşiyor ve yalnızca `{'sector': 'Ağız ve Diş Sağlığı', 'count': 32}`
dönüyor. Tek veri noktasıyla grafik çizilemediği için `chart_data` None.
Kullanıcı açısından bu bir **yanlış cevap**: iki sektörün 45 dk üzeri seans
oranı sorulmuş, bir sektörün toplam profil sayısı veriliyor.

Kural: tam paket koşulduğunda bu tek hata beklenen durumdur; başka bir
kırmızı test yeni bir regresyondur. Düzeltilince bu madde kapatılmalı.

## Madde 18 — Semantik doğrulayıcının gevşekliği ("emin değilsen TAMAM")

Madde 16'nın A ölçümünde ortaya çıktı
([implementation_plan_validator_failure.md](implementation_plan_validator_failure.md) §9,
veri: [experiments/validator_A/](../experiments/validator_A/PROVENANCE.md)).

Yanlış hesaplanıp `[KESİN HESAPLAMA SONUCU]` olarak giden dört cevabın dördü
de `validation_status = ok`: doğrulayıcı **çalıştı ve onayladı**. Çökme
(madde 16) değil, kabul eşiği sorunu. `_semantic_check` prompt'u bilinçli
olarak muhafazakâr: *"Somut ve kesin bir hata varsa SORUN yaz. Emin
değilsen TAMAM yaz."* Bu, doğru sonucu boşa harcamamak için seçilmişti
ama aşağıdaki türleri geçiriyor:

| # | Set | Hata türü | F1 | Judge F |
|---|---|---|---|---|
| 44 | test_2 | **Soru türü uyuşmazlığı:** kavramsal ayrım soruluyor, kod iki kolonun farkını/std'sini hesaplıyor ("-1.95 saat") | 13.3 | 5 |
| 51 | test_2 | **Eksik sonuç:** döküm (19×32 + 3×40) isteniyor, sonuç yalnızca `true` | 13.7 | 5 |
| 57 | test_2 | **Yanlış formül:** referans 91/22 ≈ 4.14; kod 33.09 / 1.50 üretiyor | 22.8 | 5 |
| 107 | test_5 | **Veride olmayan kavram:** negatif soru, kod başka bir kolondan "ortalama ücret 45.12" türetiyor (FP; madde 8'de kabul edilmiş sınırlama olarak da geçiyor) | 0 | 5 |

### Neden önemli
- **Judge bunları göremez.** Yanlış sonuç context'te `KESİN` etiketiyle
  durduğu için cevap onu sadakatle tekrarlıyor ve faithfulness 5 alıyor. Bu
  sınıf yalnızca ground truth'a karşı doğrulukla yakalanıyor.
- **Tekrar üretilebilir.** Üç koşuda (2026-10-03 ana koşu + 2026-10-05 iki
  geçiş) cevap ve context bayt bayt aynı. Dört vaka, doğrulayıcıda yapılacak
  her değişiklik için hazır regresyon seti.

### Dikkat (çözüm tasarlanırken)
- Eşiği sıkılaştırmak `objection` sayısını artırır. Düzeltme denemesi
  tutmazsa sonuç `[DOĞRULANAMAYAN SONUÇ]` olur ve kullanıcı "bulunamadı"
  görür. Doğru cevapları da reddetme riski var: 13 adaydan bu dördü ve
  context'ten sapan #37/#45 dışındaki 7'si (#32, #35, #39, #42, #52, #60,
  #108) `ok` kalmalı.
- Ölçüm: dört vaka + yedi "kalmalı" vaka birlikte koşulmalı; tam eval bu
  katmanı tek başına yeterince ölçmez (madde 13).

## Madde 19 — Snowball "deneyim" → "de" ve stopword çakışması

[implementation_plan_retrieval_fixes.md](implementation_plan_retrieval_fixes.md)
Adım 5 sırasında ortaya çıktı. Snowball Türkçe stemmer'ı `deneyim` kelimesini
`de` köküne indiriyor. `de` `_STOPWORDS` içinde olduğu için **"deneyim" BM25'ten
tamamen siliniyor**: hem sorguda hem corpus'ta (`deneyimi` → `deney`,
`deneyimimle` → `deneyim` ise kalıyor; çekime göre tutarsız).

`_STOPWORDS` stopword'lerin stem'lerinden derlendiği için başka gerçek
kelimelerle de çakışıyor: `is` (iş), `il`, `on`, `am`, `ba`, `be`, `di`, `i`, `p`.

### Etki
- "deneyim" geçen sorularda BM25 bu terimden hiç katkı almıyor (dense yine çalışıyor).
- Soruya duyarlı kırpma (`llm_client._query_aware_truncate`) `_tokenize`
  kullandığı için "deneyim" satırlarını öncelikleyemiyor; eşleşme yoksa eski
  baştan kesmeye düşüyor (gerileme değil, kazanç yok).

### Dikkat (çözüm tasarlanırken)
- Stopword filtresi stem ÖNCESİ yüzey biçimine uygulanırsa çakışma kalkar,
  ama BM25 dağılımı tüm corpus için değişir: tam benchmark + 32 soruluk
  negatif setle ölçülmeli.

### Kapsam ölçümü (2026-10-10)

Script: [evaluation/stopword_collision.py](../evaluation/stopword_collision.py).
Stemmer, `TURKISH_STOPWORDS`, `_tokenize` değişince ya da yeniden ingest
sonrası tekrar koşulur.

- **Corpus:** 39 kelime çakışıyor; 17'si işlev kelimesi (`nedir`, `nelerdir`,
  `içindeki`… — düşmeleri istenen davranış), **29'u içerik kelimesi, ~970
  geçiş**. En büyükleri: `ön` 443 (140/916 chunk), `iş`/`işi`/`işleri` ~250,
  `iç`/`içi` ~60, `birimi`/`birim` 56, `damla` 29, `deneyim` 24, `deniz` 23.
  %85'i 728_profiles.json'da (hizmet adları, sektör/meslek adları, kişi adları).
- **Mevcut test seti:** 115 pozitif sorunun yalnızca **6'sında** (#49, #60,
  #61, #76, #92, #115), 32 negatifin 1'inde (#211) içerik kelimesi düşüyor.
  Altısında da beklenen kaynak retrieval'da 1. sırada (v7): sorular teknik
  alan adlarıyla (`experience.years`, `forward`, `seed`) yazıldığı için BM25
  başka terimlerle ayakta kalıyor. **Şimdiye kadarki F1/faithfulness
  sonuçlarına etkisi pratikte yok** (en kötü 1–2 soru).
- **Asıl risk test setinin kör olduğu yerde:** alan adı içermeyen doğal
  sorularda düşen kelime çoğu zaman sorunun TEK ayırt edici terimi.
- Çekince: `retrieval_match` doküman seviyesinde; 728 profil tek kaynak
  olduğundan profil sorularında doğru *profilin* gelip gelmediğini göstermez.

### Hedefli set (taslak — `test_stopword`)

Kural: **alan adı İÇERMEYEN doğal dil soruları**; her soruda ayırt edici
terim çakışan kelimedir. 12 sorunun hepsi şu an `semantic_rag`'e gidiyor
(router doğrulandı), yani gerçekten BM25'i sınıyor.

Ground truth **mevcut 728_profiles.json'dan deterministik filtreyle**
türetilir, yeni senaryo yazılmaz:
- Yeni doküman eklemek corpus'u ve BM25 IDF'lerini değiştirir; ölçmek
  istediğimiz etkiyi kendi değişikliğimizle karıştırırız.
- Profiller yapısal; her cevap tek bir filtreyle tekrar üretilebilir
  (aşağıdaki "türetme" sütunu), elle yorum gerekmez.

| # | Soru | Düşen kelime | Ground truth | Türetme (`profiles` üzerinde) |
|---|---|---|---|---|
| 1 | Damla Akın hangi şehirde hizmet veriyor? | damla | Mersin (Mezitli) | `displayName == "Damla Akın"` → `location` |
| 2 | Deniz Akın'ın mesleği nedir? | deniz | Sağlıklı Yaşam Koçu | `displayName == "Deniz Akın"` → `occupation` |
| 3 | Deniz Çelik hangi hizmetleri sunuyor? | deniz | Birebir pilates, Başlangıç seansı, Postür değerlendirmesi | `displayName == "Deniz Çelik"` → `services[].name` |
| 4 | Ön değerlendirme hizmeti hangi meslekteki uzmanlar tarafından veriliyor? | ön | Emzirme Danışmanı, Sosyal Hizmet Danışmanı | `"Ön değerlendirme" in services[].name` → `occupation` kümesi |
| 5 | Çekim ön görüşmesi yapan uzmanlar hangi meslekten? | ön | Fotoğrafçı, Organizasyon Fotoğrafçısı | `"Çekim ön görüşmesi" in services[].name` |
| 6 | İş modeli görüşmesi sunan danışmanların mesleği nedir? | iş | Girişim Mentoru | `"İş modeli görüşmesi" in services[].name` |
| 7 | İç mimarlar hangi hizmetleri sunuyor? | iç, ön | İhtiyaç analizi, Mekân ön değerlendirmesi, Proje sunum görüşmesi | `occupation == "İç Mimar"` → `services[].name` kümesi |
| 8 | Aracın iç detay temizliğini hangi uzman yapıyor? | iç | Oto Detaylı Temizlik Uzmanı | `"İç detay temizlik" in services[].name` |
| 9 | Çevrim içi Türkçe dersi veren eğitmenlerin mesleği nedir? | içi | Yabancılara Türkçe Eğitmeni | `"çevrim içi" in headline` |
| 10 | Vatandaş danışma birimi hangi hizmetleri veriyor? | birimi, ön | Başvuru ön görüşmesi, Bilgilendirme randevusu, Evrak danışma görüşmesi | `occupation == "Vatandaş Danışma Birimi"` → `services[].name` kümesi |
| 11 | Öğrenci işleri görüşmesi hangi danışma biriminde sunuluyor? | işleri | Üniversite Öğrenci Danışma Birimi | `"Öğrenci işleri görüşmesi" in services[].name` |
| 12 | Girişimcilik ve iş geliştirme deneyimi olan uzmanlar hangi meslekte? | iş, deneyim | Girişim Mentoru | `"Girişimcilik ve iş geliştirme" in experience.credentialSummary` |

En güçlü vakalar 1–3: iki kişinin ilk adı da düşüyor ("Damla Akın" /
"Deniz Akın"), BM25'te geriye ikisinde ortak `akın` kalıyor.

Ölçüm sırası:
1. Set `evaluation/datasets/test_stopword.csv` + ground truth JSON olarak
   yazılır, türetme bir script'le (elle değil) üretilir.
2. **Düzeltmeden ÖNCE** koşulur (baz çizgi). Metrik: chunk seviyesinde
   doğru profil top-k'da mı + cevap doğruluğu. Doküman seviyesindeki
   `retrieval_match` burada yetmez (hepsi aynı kaynak).
3. Düzeltme sonrası aynı set + tam benchmark + 32 negatif.

## Madde 20 — Router: kolon parçası eşleşmesi (2b) ve benchmark top_k

1. **2b ertelendi:** "Deneyim yılları histogramı" filtresiz sorulduğunda hâlâ
   semantik RAG'e gidiyor ("deneyim" zayıf alias, bağlam kelimesi yok). Aynı
   kolonun iki parçası birlikte eşleşince (deneyim + yıl → `experience.years`)
   zayıf eşleşmeyi güçlü saymak çözer; router'ın genel davranışını değiştirdiği
   için negatif setle ayrıca ölçülmeli. (Not: madde 19 düzelmeden "deneyim"
   BM25'e de katkı vermiyor.)
2. **Benchmark `top_k=5` — düzeltildi (2026-10-18).** `evaluation/run_tests.py::run_single_test`,
   `evaluation/eval_retrieval.py` ve `evaluation/llm_as_judge.py::build_context_for_question`
   varsayılanı 5; arayüz `retrieval.TOP_K` (8) kullanıyordu. Kapsam ölçümü
   ([experiments/madde20_topk_benchmark/](../experiments/madde20_topk_benchmark/),
   plan: [implementation_plan_madde20_topk.md](implementation_plan_madde20_topk.md)):
   tam benchmark + negatif set (147 soru) üzerinde `retrieve(top_k=5)` vs
   `retrieve(top_k=8)` karşılaştırıldı — 110/147 soruda nihai 4 chunk'lık
   liste birebir aynı değil, ama fark neredeyse istisnasız 3./4. sıradaki
   dolgu chunk'ta (1. sıra her soruda aynı). **Doküman düzeyinde etki:
   147/147 sorunun hiçbirinde beklenen kaynak top_k=5→8 ile kaybolmuyor/
   kazanılmıyor** (çekince: ground truth dosya adı düzeyinde, `728_profiles.json`
   içindeki profil düzeyi otomatik doğrulanamıyor — madde 19'un aynı kısıtı).
   Üç dosyanın varsayılanı `retrieval.TOP_K`'ya bağlandı (hardcoded `5`
   kaldırıldı); donmuş deney scriptlerine (`experiments/madde22_ornek_cevap/`,
   `experiments/madde24_ocr_alistirma/`) dokunulmadı.

## Madde 21 — LLM-judge yanlış retleri "dürüst ret" diye ödüllendiriyor

test_1 #24–#29 (resimli PDF sayfaları, ground truth'ta cevabı var) "Bu bilgi
dokümanlarda bulunamadı." cevabıyla judge'dan 5/4/4/5 aldı: gerekçe "bağlamda
bilgi yok, dürüst ret". Bağlama göre doğru, ama soru açısından FN. Judge
yalnızca bağlama bakınca **ingest/retrieval kaynaklı FN'leri görünmez kılıyor**.
Pozitif (ground truth'u olan) sorularda ret, judge skorundan bağımsız olarak
ayrı bir FN sayacıyla raporlanmalı.

## Madde 22 — OCR'lı "Cevap N" sayfaları retrieval'a gelmiyor

OCR sonrası (plan Adım 6) test_1 #24–#29'da soru sayfası ("Örnek N") artık
geliyor, ama cevabın durduğu "Cevap N" sayfası gelmiyor (#29: sayfa 30 1. sırada,
sayfa 31 yok; #26: Örnek 5 var, asıl cevap olan Cevap 5 / sayfa 25 yok).
Cevap sayfası yalnızca başlık + formül taşıyor; soruda geçen "Örnek 8",
"dilbilgisi", "türettiği" kelimeleri orada yok. Sonuç: model ret yerine kendi
akıl yürütmesiyle cevap veriyor ve #29'da yanlış ("üs 4 olur…").

Çözüm adayı: ardışık "Örnek N" / "Cevap N" sayfalarını ingest'te tek chunk'ta
birleştirmek ya da cevap chunk'ına önceki sayfanın başlığını bağlam olarak
eklemek. Belgeye özel olmaması için kural "metni çok kısa OCR sayfası, önceki
sayfayla aynı bölüm numarasını taşıyor" gibi genel tanımlanmalı.

**Durum (2026-10-13) — düzeltildi.** Plan:
[implementation_plan_madde22_ornek_cevap.md](implementation_plan_madde22_ornek_cevap.md),
ölçüm: [experiments/madde22_ornek_cevap/PROVENANCE.md](../experiments/madde22_ornek_cevap/PROVENANCE.md).
- Kural: OCR'lanmış sayfa, önceki sayfayla aynı bölüm numarasını taşıyorsa onun
  chunk'ına eklenir (`ingest._merge_continuation_pages`, `5b494b2`); korpusta tam
  5 çift, page_info "sayfa N-M". Yeniden ingest: 916 → 911 chunk; yedek
  `rag.db.bak_madde22_2026-10-12` (kökte, `f61f7119a6c8`).
- Hedef 5 soru (#24, #25, #26, #28, #29): doğru Cevap sayfası 5/5 bağlamda (önce
  0/5). LLM (aynı oturum, yedek vs yeni DB): TP→FN 0, F1 3/5 arttı; içerik #25,
  #26, #28'de gerçekten düzeldi. #24 iki DB'de de yanlış (Cevap sayfası
  okunamıyor → madde 31), #29 kötüleşti (Çince sızıntısı; `llm_client`
  temizleyicisi tasarım gereği dokunmadı).
- Etki alanı 18 soru: sınıf kaybı 0; tek çapraz-doküman dolgu test_3 #87 (TP
  kaldı). Tam negatif set FP 2/32 (değişmedi), tripwire 0.

## Madde 23 — Korunan kelimelerin çekimleri farklı token'a düşüyor

Madde 19 düzeltmesinin (plan: [implementation_plan_bm25_stopword.md](implementation_plan_bm25_stopword.md),
varyant V3) bilinen sınırı. V3, stem'i bir stopword stem'ine denk gelen
kelimede stem yerine fold'lu yüzey biçimini kullanıyor; kural **yalnız o
biçime** uygulanıyor. Aynı kelimenin diğer çekimleri ya normal stem'e ya da
kendi yüzey biçimine gidiyor, yani tek bir token'da buluşmuyor:

| Yüzey | Snowball stem | V3 token |
|---|---|---|
| deneyim | `de` (stopword stem'i) | `deneyim` |
| deneyimi | `deney` | `deney` |
| deneyimle | `deney` | `deney` |
| deneyimli | `deneyimli` | `deneyimli` |
| deneyimimle / deneyimini | `deneyim` | `deneyim` |
| deniz | `de` | `deniz` |
| denizi | `de` | `denizi` |

Sonuç: "deneyim" sorgusu `deneyimimle`/`deneyimini` geçen chunk'larla
eşleşir, `deneyimi`/`deneyimle`/`deneyimli` geçenlerle eşleşmez; "deniz"
sorgusu "denizi" ile eşleşmez. Bugünkü durumdan (V0'da bu kelimeler hiç yok)
kötü değil, ama BM25 geri kazanımı kısmi.

### Çözüm adayları
- Snowball'un aşırı kısalttığı (stem ≤ 2 harf) kelimeler için en uzun ortak
  önek / sözlük tabanlı lemma. V2 ("3 harften kısa her stem → yüzey") 37
  benchmark sorusunu değiştirip ek kazanç getirmediği için genel kısa-stem
  kuralı reddedilmişti; çözüm yalnız stopword stem'ine çakışan kelime
  ailesini hedeflemeli.
- Ölçüm: `evaluation/stopword_collision.py`'ye çekim ailesi raporu
  (aynı kökten gelen yüzeylerin kaç farklı token'a dağıldığı).

## Madde 24 — OCR'lı alıştırma sayfaları negatif sette FP üretiyor

v8 koşusunda ([experiments/v8_bm25_stopword/PROVENANCE.md](../experiments/v8_bm25_stopword/PROVENANCE.md))
ortaya çıktı. `dffb6a5` ile resimli PDF sayfaları (22–31) OCR'lanınca
alıştırma metinleri corpus'a girdi; bunlar konuyu ANAN ama cevabı içermeyen
metinler. Negatif sorularda dolgu parçası olarak bağlama giriyor ve model
alıştırma metninden prosedür uyduruyor:

| # | Soru | Bağlama giren OCR sayfası | v7 → v8 |
|---|---|---|---|
| 224 | Chomsky normal formuna dönüştürme adımları | sayfa 22 ("…Chomsky normal biçimine (CNF) dönüştürünüz") | TN → FP |
| 103 (test_5) | Pompalama lemması nasıl ispatlanır | sayfa 24, 28 | TN → FP |

Tokenizer değişikliğiyle ilgisi yok: iki soruda da bağlam eski/yeni tokenizer'da
bayt bayt aynı. `dffb6a5` benchmark'lanmadan commit edildiği için ilk kez v8'de
görüldü. Madde 22 (Cevap sayfaları gelmiyor) ile aynı kökten: OCR sayfaları
"soru" metni taşıyor, "cevap" bağlamı taşımıyor.

Çözüm adayları: OCR chunk'larını `[alıştırma — çözüm içermez]` gibi bir
işaretle ingest etmek; ya da Örnek/Cevap sayfalarını birleştirip (madde 22)
soru metnini cevabıyla aynı chunk'ta tutmak. Ölçüm: negatif set tam koşu.

**Ölçüm notu (madde 28 koruması):** 24'ün FP'leri (#224, #103) sayı / özel
isim taşımayan prosedür metinleri. Düzeltme sonrası model "bilgi
bulunmamaktadır, ancak genel olarak şu adımlar…" gibi melez bir cevaba
kayarsa, ret tespitinin ikinci aşaması içerik miktarına bakmadığı için (madde
28) bu cevap TN sayılır ve FP sayısı yapay olarak iyileşmiş görünür. Bu yüzden
koşudan sonra: negatif sette `check_is_not_found` ile ret sayılan ve 120
karakterden uzun cevaplar yeniden taranır. 2026-10-11 taramasında 7 koşuda tek
eşleşme v5 #231 (dürüst ret). Yeni eşleşme çıkarsa elle incelenir; uydurma
içerik taşıyorsa madde 28 öne alınır, 24'ün sonucu 28'den sonra yeniden ölçülür.

**Durum (2026-10-12) — yön C denendi, reddedildi; madde daraltıldı.** Plan ve
ölçüm: [implementation_plan_madde24_ocr_isaret.md](implementation_plan_madde24_ocr_isaret.md) §8,
[experiments/madde24_ocr_alistirma/PROVENANCE.md](../experiments/madde24_ocr_alistirma/PROVENANCE.md).
- Görev notu (bağlamda "bu parça bir alıştırma" satırı): #224'te cevap bayt bayt
  aynı kaldı, #103 uydurmaya devam etti. Not + system prompt kuralı (izole):
  #103 TN oldu ama test_1 #24, #25, #26, #29 TP → FN. Ölçülen fayda yok, kod
  geri alındı.
- **Kök neden ayrımı:** #224'ün malzemesi sayfa 18 (yararsız değişken atma —
  gerçekten CNF'nin ön adımı, alakasız değil), tetikleyicisi sayfa 22; asıl
  belirleyen synthesizer'ın (a) dalı → **madde 30**. Bu madde artık yalnız
  **test_5 #103**: belgede olmayan konu (pompalama lemması), sayfa 24/28 BM25
  ile dolgu olarak giriyor, rerank skorlarının hepsi < 0.04.
- **Sıradaki aday D — reranker alaka eşiği** (tüm adaylar eşiğin altındaysa
  bağlam boş / ret). **Riski:** genel bir değişiklik; düşük rerank skoruyla
  doğru cevap veren pozitif soruları bozabilir. Uygulanmadan önce aynı
  titizlikle ölçülmeli: tüm benchmark sorularında rerank skor dağılımı (pozitif
  sorularda doğru chunk'ın skoru), eşik adayları için TP kaybı / TN kazancı,
  sonra tam benchmark + tam negatif set.
- Madde 22 (Örnek/Cevap birleştirme) OCR chunk'larının uzunluğunu ve BM25
  davranışını değiştireceği için #103'ün dolgu durumunu da etkileyebilir.

**D — sabit eşik reddedildi (2026-10-12).** Madde 22 kapsam ölçümünde
([experiments/madde22_ornek_cevap/README.md](../experiments/madde22_ornek_cevap/README.md),
`sonuc_rerank_dagilimi.txt`) sabit mutlak eşik simüle edildi (retrieval rerank
skorları + kayıtlı sınıflar; LLM koşusu yok): "en yüksek rerank < 0.04 ise
bağlam boş" kuralı **1 FP (#103) kazancı karşılığında 3 TP kaybettiriyor**
(test_2 #58 en yüksek 0.010, test_3 #62 0.031, test_4 #97 0.008). Kabul
edilemez oran → **reddedildi; aynı deneme (sabit mutlak eşik) tekrarlanmamalı.**
- Madde 22 sonrası da #103 çözülmüyor: birleşik DB'de dolgu sürüyor (22-23,
  28-29), tüm adaylar 0.04 altı, LLM yine FP.
- **Gerçek (yeniden ingest edilmiş) DB'de teyit (2026-10-13, madde 22 Adım 3):**
  #103 bağlamı s.16, s.2, s.28-29, s.22-23 — simülasyonla aynı; LLM cevabı yine
  uydurma (pompalama lemmasının biçimsel ifadesi model bilgisinden) → **FP**.
  Madde 24'ün kapsamı değişmedi: yalnız #103, açık aday bağıl eşik (ölçülmedi).
- **D'yi destekleyen iki bağımsız gözlem** (reranker düşük skor verdiğinde
  çoğunlukla haklı): #103 (tüm adaylar < 0.04, belgede olmayan konu) ve test_3
  #87 (Fourier sorusu; birleşik DB'de gramer PDF'inin 24-25 chunk'ı 0.001 ile
  dolgu olarak giriyor, en yüksek aday 0.487).
- İleride denenirse **soru bazlı / bağıl bir ölçüt** düşünülmeli, sabit mutlak
  eşik değil (ör. "adayın skoru, en yüksek skorun X katından azsa ele").
  Dikkat: bağıl ölçüt iki durumu ayrı ele alır. #87 tipi (bir net kazanan +
  dolgular) bağıl kesimle çözülür. #103 tipi (hiçbir aday öne çıkmıyor:
  0.036 / 0.032 / 0.011 / 0.009) bağıl kesimle **çözülmez**; o durum mutlak
  bir alt sınır ister ve tam da o sınır 3 TP'yi kaybettiriyor. Yani #103 için
  D'nin bağıl hâli de yeterli olmayabilir; ölçmeden varsayılmamalı.

## Madde 25 — Ret tespiti yarım kalmış "bulunmadığından" cevabını kaçırıyor

v8 negatif #222: cevap "Z-Dönüşümü ders notlarında 12. haftanın konu başlığına
herhangi bir bilgi bulunmadığından" (cümle yarım). Uydurma bilgi yok, anlamca
ret; `benchmark_eval.check_is_not_found` `bulunamad[ıi]` kalıbına baktığı için
`bulunmadığından` biçimini tanımıyor ve FP sayıyor. İki ayrı sorun:
1. Skorlama: ret kalıbı `bulunma(dı|dığı|dığından|mış)` çekimlerini de kapsamalı
   (negatif sette FP'yi yapay olarak artırıyor).
2. Üretim: model cümleyi yarıda bırakıyor; `NOT_FOUND_ANSWER` tek cümlesi
   yerine serbest biçimli ret üretiyor (llm_client `_trim_after_not_found`
   bu biçimi de tanımıyor).

Durum (2026-10-11): 1. kısım düzeltildi, bkz.
[experiments/madde25_ret_tespiti/README.md](../experiments/madde25_ret_tespiti/README.md).
2. kısım madde 26'ya taşındı.

## Madde 26 — Üretim: serbest biçimli ret yarıda kalıyor

Madde 25'in 2. kısmı. Model `NOT_FOUND_ANSWER` yerine kendi cümlesiyle
reddediyor ve cümleyi yarıda bırakıyor (v8 negatif #222: "…herhangi bir bilgi
bulunmadığından"). `llm_client._trim_after_not_found` yalnız sabit kalıbı
tanıdığı için bu biçimi normalize etmiyor. Kullanıcı yarım cümle görüyor ama
uydurma bilgi yok. Sıklık düşük: v8'de noktalamasız biten 9/144 cevabın
gerçekten yarım kalan tek örneği bu (diğerleri formül / kaynak atfıyla biten
meşru cevap). Skorlama artık bu cevabı ret sayıyor (`f888033`), yani ölçüm
etkilenmiyor. Düşük öncelik.

## Madde 27 — NaN embedding `semantic_sim`'i sessizce 0.0 yapıyor

Madde 25 Adım 2'deki yeniden skorlamada çıktı: v7 test_2 #36'da `semantic_sim`
86.7 → 0.0. Ollama 0.21.2 bge-m3 bu cevap metni için NaN embedding döndürüyor
(`json: unsupported value: NaN`, HTTP 500); 3/3 tekrarlanabilir.
`benchmark_eval.compute_semantic_similarity` her istisnada `0.0` döndürüyor
(`except Exception` → `return 0.0`) ve bu değer "çok kötü cevap" gibi
ortalamaya giriyor. Hesaplanamayan skor 0 değil, eksik (`None`/NaN) olarak
kaydedilmeli, ortalamadan çıkarılıp ayrıca sayılmalı.

Not: bunun v7 #36'ya özgü tek seferlik bir durum mu, yoksa bge-m3'ün belirli
uzunluktaki ya da belirli karakterler içeren başka metinlerde de tetiklediği
bilinen bir sorun mu olduğu bilinmiyor; ileride bakılacak. Embedding
güvenilirliğinin genel hâli: madde 29.

**Durum (2026-10-18) — düzeltildi.** Plan:
[implementation_plan_madde27_semantic_sim.md](implementation_plan_madde27_semantic_sim.md),
kapsam ve ölçüm: [experiments/madde27_nan_embedding/](../experiments/madde27_nan_embedding/README.md).
- **Kök neden:** Ollama bge-m3'ü oturumdan oturuma CPU'ya ya da GPU'ya yüklüyor.
  NaN yalnız GPU yolunda ve yalnız v7 test_2 #36'nın cevabında (701 metnin 1'i,
  3/3 deterministik; CPU'da 0/701). İki yolun vektörleri de farklı (cosine min
  0.9982) — `semantic_sim`'in ±0.1–0.2 gürültüsünün kaynağı.
- **Düzeltme (`ecc7f5a`):** (P) skorlayıcının embedding'i `num_gpu=0` ile CPU'da
  sabit (`SEMANTIC_NUM_GPU`); (M) hesaplanamayan skor 0.0 değil `None`, ortalamadan
  çıkar ve `semantik_hesaplanamayan_soru` olarak sayılır; tek referansın hatası
  artık tüm skoru düşürmüyor (eskiden 0.0, şimdi geçerli referansın skoru —
  `tests/test_semantic_sim_missing.py` karşılaştırmalı test). Retry ölçülüp
  reddedildi (GPU yolunda deterministik NaN).
- **Doğrulama (`baf5cb0`, `sonuc_yeniden_skor.txt`):** v7/v8 yeniden skor — #36
  86.7, hesaplanamayan 0, EM/F1/ROUGE/sınıflarda 0 fark, `semantic_sim` farkı en
  fazla 0.2 puan; ayrı süreçte ikinci skorlama birebir aynı (ikinci koşunun
  çıktı klasörleri repoda yok, sonuç raporda kayıtlı).

**P öncesi üretilmiş `semantic_sim` değerleri — "cihaz karışımı".** Aşağıdakiler
`ecc7f5a` öncesinde, Ollama'nın o oturumda seçtiği (bilinmeyen) cihazla
hesaplandı; P sonrası değerlerden ≤ ~0.2 puan farklı olabilirler, bir NaN
vakasında 0.0 olarak görünürler. Yeniden skorlanmadılar (`semantic_sim`
kararlarımızda belirleyici olmadı; F1, judge ve sınıflandırma kullanıldı):
- `experiments/{v2_baseline_trim, v3_soften_and_chunk, v5_soften_and_brevity
  (report, report_with_negative), v6_sandbox_empty_guard, v7_refusal_clarity,
  v8_bm25_stopword (report, report_karsi_olgu)}` altındaki `*_scored.csv` /
  `*_summary.json`;
- `experiments/madde25_ret_tespiti/yeniden_skor_{v7,v8}` (#36'nın 0.0'ı burada);
- bu sayıları alıntılayan dokümanlar: `experiments/{v7_refusal_clarity,
  v8_bm25_stopword, validator_A}/PROVENANCE.md`, `docs/EXPERIMENTS.md`,
  `docs/TEKNIK_RAPOR.md`, `docs/INFRASTRUCTURE_NOTES.md` ve
  `docs/implementation_plan_*.md` içindeki semantik alıntıları.
- **Etkilenmeyen:** madde 19, 22, 24 ölçümleri (`semantic_sim` kullanmadılar).
- P sonrası referans: `experiments/madde27_nan_embedding/yeniden_skor_{v7,v8}`.

## Madde 28 — Ret tespitinin ikinci aşaması içerik miktarına bakmıyor

`check_is_not_found` ret kapısından geçen cevabı yalnız "yeni iddia" (soruda
geçmeyen sayı / kod / özel isim) varsa ret saymıyor; cevabın ne kadar içerik
taşıdığına bakmıyor. İki yönlü sonuç:
- **v3 #29 gizli FN:** saf ret, ama formüldeki `bbBdd` içinde kelime ortasında
  büyük harfle başlayan `Bdd` özel isim sayılıyor → TP.
- **Tesadüfi TP'ler:** v3 #56, v7 #47, v8 #49, #59 gerçek içerik cevabı ama
  ret kapısından geçiyor ("bulunmamaktadır" vb.). Bugün yalnız kelime ortası
  taramanın ürettiği "iddialar" (`schemaVersion` → `Version`) sayesinde TP.
  Kelime sınırı düzeltmesi #29'u düzeltip bu 4'ünü FN yapıyordu
  (`experiments/madde25_ret_tespiti/sonuc_kalip_b_ilk_deneme_kelime_siniri.txt`).

İkisi birlikte çözülmeli: ret ifadesi ve gerekçesi düşüldükten sonra kalan
içerik miktarı (ya da cevabın soruya yanıt veren bir cümle taşıyıp taşımadığı)
ikinci aşamaya eklenmeden kelime ortası tarama değiştirilmemeli. Ölçüm:
`kalip_b_olcum.py` ile 845 satır, negatif sette FP→TN olmamalı.

## Madde 29 — Ollama bge-m3 embedding güvenilirliği

Madde 27 (NaN embedding) ile aynı şemsiye: Ollama 0.21.2 üzerindeki bge-m3'ün
ürettiği embedding'ler her koşulda aynı ve geçerli değil. İki gözlem:

1. **Oturumlar arası retrieval kayması** (madde 24 Adım 0,
   [experiments/madde24_ocr_alistirma/sonuc_etkilenen_set.txt](../experiments/madde24_ocr_alistirma/sonuc_etkilenen_set.txt)):
   `src/` v8'den beri retrieval açısından aynıyken 3 `semantic_rag` sorusunda
   (test_2 #36, test_4 #93, negatif #217) son 1–2 kaynak v8'dekinden farklı.
   Bugün 3/3 tekrarda kararlı, yani oturum içi gürültü değil. Fark hep hibrit
   sıralamanın neredeyse eşit skorlu sınırında (#217: 5–7. sıra RRF 0.9307 /
   0.9303 / 0.9250; v8'de sayfa 17, bugün sayfa 28 giriyor).
2. **`semantic_sim` gürültüsü** (madde 25 Adım 2): aynı cevap metinleri yeniden
   skorlandığında `semantic_sim` ±0.1–0.2 oynuyor (v7'de 12, v8'de 10 hücre).

**Doğrulanmamış hipotez:** benchmark sırasında Foundry Local modeli GPU'dayken
Ollama bge-m3'ü farklı bir cihazda / bölüşümde (CPU ya da kısmi GPU) koşuyor ve
sayısal sonuç değişiyor. Doğrulama: aynı sorgunun embedding'i Foundry yüklü ve
yüklü değilken alınıp karşılaştırılır; `ollama ps` çıktısındaki işlemci
bilgisi kaydedilir.

**Açık soru:** madde 27'deki NaN (v7 test_2 #36, 3/3 tekrarlanabilir) aynı
kökten mi geliyor? Cihaz/sayısal hassasiyet farkı NaN'ı da açıklayabilir;
ya da metne özgü ayrı bir sorundur. İkisi birlikte araştırılmalı.
Not: test_2 #36 iki yerde de geçiyor, ama farklı metinler üzerinden: madde
27'de NaN'a yol açan **cevap metninin** embedding'i, burada kayan
**sorgunun** retrieval sonucu. Bu yüzden çakışma muhtemelen tesadüf;
araştırma sırasında yine de kontrol edilmeli (ör. sorgunun embedding'inde
NaN'a yakın / aşırı değerler var mı).

**Karşı-kanıt: kayma her zaman olmuyor (2026-10-12, madde 22 Adım 2).**
- **Doküman embedding'leri kararlı:** gramer PDF'inin birleşmeyen 21 sayfası
  yeniden embed edildi; 10 Ekim'deki embedding'lerle cosine min = max =
  1.000000.
- **Sorgu tarafı da bu kez kararlı:** madde 22 simülasyonu (2026-10-12 akşamı)
  ile Adım 2 (ertesi oturum) arasında 147 sorunun kaynak listesi ve rerank
  skorları 0 farkla aynı çıktı. İki ölçümde de Foundry GPU'da yüklü DEĞİLDİ
  (yalnız retrieval koşuldu).
- Madde 24 Adım 0'daki kayma (#217, #36, #93) ise v8 koşusuna (Foundry GPU'da,
  LLM ile benchmark) göre ölçülmüştü. Bu, cihaz/bölüşüm hipotezini zayıflatmıyor,
  daraltıyor: araştırmada "Foundry yüklü vs değil" koşulu doğrudan
  karşılaştırılmalı.

**Mekanizma bulundu (2026-10-13, madde 27):** belirleyici olan "Foundry yüklü
mü" değil, **Ollama'nın bge-m3'ü o oturumda CPU'ya mı GPU'ya mı yüklediği.**
Aynı 701 metinde CPU ve GPU vektörleri farklı (cosine min 0.9982, 83 metin <
0.9999); NaN yalnız GPU yolunda. Varsayılan çağrı 2026-10-13'te VRAM boşken bile
"100% CPU" seçti. Skorlayıcı tarafı madde 27'de sabitlendi (`num_gpu=0`).
**Açık kalan: retrieval.** Sorgu embedding'i (`src/embedder.py`) hâlâ Ollama'nın
seçimine bağlı; DB'deki doküman embedding'lerinin hangi cihazda üretildiği
bilinmiyor. Sorgu tarafını sabitlemeden önce doküman embedding'lerinin cihazı
(ya da iki cihazda yeniden embed edilip karşılaştırılması) belirlenmeli.

**Ölçüme etkisi:** koşular arası karşılaştırmada sınırdaki sorular işaret ya da
kod değişikliğinden bağımsız olarak kayabilir. Bu yüzden madde 24 Adım 2 aynı
oturumda A/B koşuluyor; diğer ölçümler de aynı yaklaşımı ya da kaymanın ayrı
raporlanmasını gerektirebilir.

**Adım 1 — Cihaz Tespiti ve Kod Değişikliği (2026-10-18):**
[experiments/madde29_embedding_cihaz/](../experiments/madde29_embedding_cihaz/)
içindeki ölçüm (`cihaz_tespiti.py`), `rag.db`'deki 911 chunk'ın tamamının
(%100) `num_gpu=99`/`num_gpu=24` ile bayt bayt aynı, `num_gpu=0` (CPU) ile ise
hiçbirinin aynı çıkmadığını gösterdi (cos(DB,cpu) min 0.997198). Yani **doküman
embedding'leri GPU ile üretilmiş**; retrieval sorgu embedding'i de buna uyacak
şekilde GPU'ya sabitlendi (DB'ye dokunulmadı, re-ingest gerekmedi). Detaylı
karar ve seçenek kıyası:
[docs/implementation_plan_madde29_embedding_cihaz.md](implementation_plan_madde29_embedding_cihaz.md).
- `src/embedder.py`: `EMBED_NUM_GPU = int(os.getenv("RAG_EMBED_NUM_GPU", "99"))`
  eklendi; `get_embedding`/`get_embeddings` artık `options={"num_gpu": ...}`
  gönderiyor.
- `src/ingest.py`: `--num_gpu` CLI argümanı eklendi (varsayılan `EMBED_NUM_GPU`),
  her iki ingest yolu da bunu `get_embeddings`'e iletiyor.
- `tests/test_embedder_device.py`: sahte Ollama ile varsayılan/override
  `num_gpu` değerinin doğru iletildiği 4 birim test — geçti.

**Adım 2 — Kayan Sorguların Doğrulanması (2026-10-18, tamamlandı):**
Madde 24 Adım 0'da kaydığı bilinen 3 sınır soru (test_2 #36, test_4 #93,
negatif #217) yerel ortamda çalışan Ollama (`bge-m3:latest`) ve `rag.db` ile
[experiments/madde29_embedding_cihaz/dogrulama_kayan_sorgular.py](../experiments/madde29_embedding_cihaz/dogrulama_kayan_sorgular.py)
kullanılarak iki bağımsız Python sürecinde (`--run a` ve `--run b`) çalıştırıldı.
`--compare` çıktısı:
- `test_2#36`: AYNI (4 vs 4 aday, skorlar ve rerank skorları birebir eşit)
- `test_4#93`: AYNI (4 vs 4 aday, skorlar ve rerank skorları birebir eşit)
- `test_negative#217`: AYNI (4 vs 4 aday, skorlar ve rerank skorları birebir eşit)
- Sonuç: **0 FARK — determinist**. Kayıtlar `kayan_sorgular_sonuclari.jsonl` dosyasına yazıldı.

**Kapanış Değerlendirmesi:**
1. **DB Doküman Embedding Cihazı:** `rag.db`'deki 911 chunk'ın tamamı (%100) GPU
   (`num_gpu=99`/`num_gpu=24`) ile bayt bayt aynı, CPU (`num_gpu=0`) ile ise 0/911
   aynı çıktı (kosinüs min ~0.9972). Yani doküman embedding'leri kesin olarak GPU'da
   üretilmiştir; sorgunun GPU'ya sabitlenmesi veritabanını yeniden oluşturma ihtiyacını
   ortadan kaldırdı.
2. **Determinizm ve Kararlılık:** `--compare` doğrulaması iki bağımsız oturumda
   3 sınır sorunun tüm aday listelerinin ve skorlarının sıfır farkla aynı çıktığını
   gösterdi. Retrieval artık oturumlar ve süreçler arası tamamen determinist ve
   kararlıdır.
3. **Madde 24 Adım 0 Kaymasının Açıklanması:** Sınır sorularındaki (#217, #36, #93)
   kaymanın temel mekanizması tam olarak kanıtlandı: Ollama sorgu embedding'i için
   GPU yerine CPU seçtiğinde oluşan ~0.0028 kosinüs kayması, RRF skorları birbirine
   çok yakın olan sınır adayların (ör. #217'de 5–7. sıra RRF 0.9307 vs 0.9303;
   sayfa 17 vs sayfa 28) yer değiştirmesine neden oluyordu. Sorgu tarafının da GPU'ya
   sabitlenmesiyle hem doküman hem sorgu aynı sayısal hassasiyette buluştu ve sınır
   kayması tamamen ortadan kalktı.
- **Madde 29 "Düzeltildi" olarak kapatıldı.**

## Madde 30 — Synthesizer (a) dalı ödünleşiminin sınır vakası (#224)

**Bu bir "düzeltilmesi gereken hata" değil, "yeniden değerlendirilmesi gereken
bir denge"dir.** Acele "bug, düzelt" müdahalesi FN tarafındaki kazancı geri
alabilir.

`llm_client.ask`'taki ret kuralı bilinçli olarak iki dallı: (a) "bağlamda kısmen
ilgili bilgi varsa onu kullanarak en iyi cevabı ver", (b) "hiçbir şey yoksa tek
ret cümlesi". (a) dalı tam koşuda **FN 25 → 10** getirdi; bedeli ölçüldü ve
kabul edildi: negatif FP 7/32 → 8/32, yeni FP **#224** ("Yanlış Ön Kabul"
kategorisi; bkz. [src/llm_client.py](../src/llm_client.py) ret kuralı yorumu).

#224 o günden beri dengenin sınırında duruyor ve bağlamdaki küçük değişikliklerle
sınıf değiştiriyor: (a) dalı girişinde FP, v7'de TN (sayfa 18/2/16/19), v8'de FP
(sayfa 22 eklendi). Madde 24 ölçümleri mekanizmayı gösterdi:
- **Malzeme sayfa 18** (yararsız değişken ve kuralların atılması). Alakasız
  değil: CNF dönüşümünün gerçek ön adımı; dense 2., rerank 2. Retrieval
  sıralama hatası ya da madde 9 (RRF marj düzleşmesi) değil — sayfa 18'i
  yukarı taşıyan dense ve reranker, BM25 değil.
- **Tetikleyici sayfa 22** ("…CNF'ye dönüştürünüz"): "CNF belgede var" algısı
  verip (a) dalını devreye sokuyor.
- **Benzer vaka test_5 #101** (OCR yokken de FP; aynı CNF uydurması).
- Modeli ret vermeye iten bir prompt kuralı (madde 24 Adım 3, izole) #224'ü
  anlamca rete çevirdi ama alıştırma sorularında 4 TP'yi FN yaptı — aynı
  dengenin öbür ucu.

Yeniden değerlendirilirse: tam benchmark (FN tarafı) + tam 32 negatif + test_5
birlikte; tek soruya göre ayar yapılmamalı. Not: #224 ve #101'in Adım 3'teki
cevabı ("Ret. … belgede açıkça anlatılmamıştır.") anlamca ret ama skorlayıcı
"anlatılmamıştır"ı tanımıyor; kapı genişletmesi madde 28 ile birlikte düşünülmeli
(bkz. madde 24 planı §6).

## Madde 31 — OCR'lı Cevap sayfalarının metin kalitesi

Madde 22 Adım 3'te ortaya çıktı
([experiments/madde22_ornek_cevap/PROVENANCE.md](../experiments/madde22_ornek_cevap/PROVENANCE.md)):
birleştirmeden sonra doğru Cevap sayfası 5/5 bağlama giriyor, ama 4 soruda OCR
metninin kendisi cevabı bozuyor. **İki ayrı ciddiyet**, muhtemelen iki ayrı
çözüm:

**A — sayfa okunamıyor (ciddi; #24, Cevap 2 / s.23).** OCR çıktısı
"a) Ls.42 = { (aa) (cc)m b c b|  m20. k211 n21," — üst simgeler, koşullar ve
küme yapısı kaybolmuş; model bu sayfayı kullanamıyor ve iki DB'de de yanlış küme
veriyor. Bilgi metinde hiç yok → son işleme kurtaramaz. Çözüm adayı: o sayfa
için OCR'ı yeniden çalıştırmak (daha yüksek çözünürlük, farklı ön işleme,
görüntüyü bölme) ya da başka bir OCR motoru. Ölçüm: s.23 çıktısının referansla
(`L_S.4.2 = {(aa)^n (cc)^m b^k c b^k | n≥1, m≥0, k≥1}`) karşılaştırılması.

**B — kısmi bozulma (orta; #25, #26, #28).** İçerik okunuyor ama biçim kayıp ve
model bozuk metni aynen kopyalıyor:
- üst simgeler düz satıra iniyor: "an b am b a*" (aⁿ b aᵐ b aᵏ), "b2k+1";
- "|" kayboluyor ya da "I" oluyor: "aaSdIaaAd" (aaSd | aaAd), "A ==>aAccbBc"
  (aAcc | bBc);
- koşullar bozuluyor: "n21" (n ≥ 1 / n > 1), "m20" (m ≥ 0).
Bilgi metinde var, gösterimi bozuk → son işleme (ör. kural satırlarında
"I"/"|" düzeltmesi, bilinen kalıplarda üst simge onarımı) aday; ama kurallar
belgeye özel olmamalı ve formül olmayan metni bozmamalı. Etkisi sınırlı:
#25/#26/#28'de içerik yine de birleştirme öncesine göre düzeldi.

Kapsam: bugün yalnız gramer PDF'inin 10 OCR sayfası. Öncelik düşük–orta: 5
alıştırma sorusunun cevap kalitesini etkiliyor, sınıf (TP/FN) değiştirmiyor.
