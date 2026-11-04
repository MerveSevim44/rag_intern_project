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
| 11 | Aşırı uzun model yanıtı prompt'u ~12 KB'a taşıyor → Foundry GPU OOM | **C kapandı** (`245a78c`: prompt tavanı 10.500, #43/#53 çökmüyor); D (`90a08e9`) 1. katmanı kapsıyor; toparlanma UYGULANMADI → madde 15 |
| 12 | `result_to_natural_language` `bool` sonuçta devrik cümle üretiyor ve ham `True` sızdırıyor | Açık — madde 8 adım 4'ten SONRA |
| 13 | **Ölçüm altyapısı körlüğü**: tam eval `data_engine`/`code_interpreter` davranışını HİÇ çalıştırmıyor | **Yapısal sınırlama** — her `data_engine` değişikliğinde hatırlanmalı; kapatılacak bir bug değil |
| 14 | "Bulunamadı" mesajı iki farklı durumu birleştiriyor: *bilgi yok* ile *şu an işlenemedi* | Açık — **kullanıcı güvenini etkileyen netlik sorunu**, düşük öncelikli değil |
| 15 | Servis süreç yönetimi: OOM sonrası Foundry bozuk kalıyor, toparlanma askıda kalabiliyor | Açık — **işletimsel dayanıklılık**, madde 11'den ayrı problem sınıfı; kapı deneyi 2026-11-04 (§5): servis kendiliğinden kapanmış bulundu, kalıcı bozulma yeniden üretilemedi |
| 16 | Semantik doğrulayıcının LLM çağrısı çökünce sonuç doğrulanmış gibi `[KESİN HESAPLAMA SONUCU]` olarak gidiyor | **A uygulandı ve ölçüldü** — izole koşuda `failed` 0/26; B düşük öncelik (gözlenmiş vaka yok, asıl sorun madde 18). Bkz. [implementation_plan_validator_failure.md](implementation_plan_validator_failure.md) §9 |
| 17 | `test_visualization::test_data_engine_end_to_end_visualization` kırık: rule engine karşılaştırma sorusunu tek sektör sayımına eşliyor | Açık — **bilinen kırık test**, `10f5efc` öncesinden beri; ne zaman başladığı bilinmiyor |
| 18 | Semantik doğrulayıcı gevşek: "emin değilsen TAMAM" yanlış hesapları `ok` ile geçiriyor | Açık — **4 deterministik test vakası** (#44, #51, #57, #107); madde 16'nın asıl sorunu |
| 19 | Snowball stem'i stopword'e çakışan gerçek kelimeler BM25'ten düşüyor ("deneyim" → "de", "Damla" → "da") | **Düzeltildi** — yüzey stopword filtresi + çakışma koruması; bkz. [implementation_plan_bm25_stopword.md](implementation_plan_bm25_stopword.md) §9 |
| 20 | Router kolon parçası eşleşmesi (2b, açık) ve benchmark `top_k=5` ≠ arayüz `TOP_K=8` | top_k kısmı **Düzeltildi**; 2b **Açık** |
| 21 | LLM-judge, ground truth'u olan sorulardaki retleri "dürüst ret" diye ödüllendiriyor | Açık — ölçüm körlüğü |
| 22 | OCR'lı "Cevap N" sayfaları retrieval'a gelmiyor | **Düzeltildi** — `5b494b2` (Örnek/Cevap birleştirme) + yeniden ingest; hedef 5/5 Cevap bağlamda, plan ölçütlerinin hepsi geçti. Kalan açık (OCR kalitesi) → madde 31 |
| 23 | Madde 19 korumasındaki kelimelerin çekimleri farklı token'a düşüyor ("deneyim" / "deneyimi") | Açık — bilinen sınır; bugünden kötü değil |
| 24 | OCR'lı alıştırma sayfaları negatif sorularda dolgu olarak bağlama girip uydurma ürettiriyor (test_5 #103) | **Beklemede (2026-10-30)** — #103 FP bugünkü sistemde tekrar etmiyor, bağıl eşik adayı not edildi, aktif müdahale yok, yeni FP görülürse yeniden açılır |
| 25 | Ret tespiti yarım "…bulunmadığından" cevabını tanımıyor (skorlama + üretim) | **Skorlama düzeltildi** — `f888033` (ret çerçevesi, #222 FP→TN) + `8b5d26f` (tanımlayıcı yankısı, v3 #26 TP→FN); üretim kısmı → madde 26, kalan açık → madde 28 |
| 26 | Üretim: model serbest biçimli reddi yarıda bırakıyor ("…bulunmadığından") | Açık — düşük öncelik; v8'de 1/144 (#222) |
| 27 | bge-m3 bazı metinlere NaN embedding döndürüyor; `semantic_sim` sessizce 0.0 yazıp ortalamaya katıyor | **Düzeltildi** — `ecc7f5a` (eksik değer + skorlayıcı embedding'i CPU'ya sabit) + `0d179ab` (testler); v7 #36 0.0 → 86.7, tekrar skorlamada 0 fark (`baf5cb0`). P öncesi `semantic_sim` değerleri "cihaz karışımı" (bkz. madde 27 kapanış notu) |
| 28 | Ret tespitinin ikinci aşaması içerik miktarına bakmıyor; ret kapısından geçen içerik cevapları yalnız tesadüfi "iddia"larla TP kalıyor | Açık — v3 #29 gizli FN; madde 25 Adım 3'te bilinçli bırakıldı |
| 29 | Ollama bge-m3 embedding güvenilirliği: oturumlar arası sayısal kayma sınırdaki retrieval'ı değiştiriyor | **Düzeltildi** — `EMBED_NUM_GPU=99` ile sorgu GPU'ya sabitlendi (`src/embedder.py`, `src/ingest.py`); yerel Ollama + `rag.db` ile 2 ayrı süreçte (#36, #93, #217) 0 fark doğrulanarak kapatıldı **Koşullu (2026-10-30):** LLM yüklüyken boş VRAM < 457 MiB ise Ollama `num_gpu=99`'a rağmen sessizce CPU'ya düşüyor (0/25), bkz. madde 39 |
| 30 | Synthesizer (a) dalı ödünleşiminin sınır vakası: "Yanlış Ön Kabul" sorusu #224 bağlama göre FP/TN arasında gidip geliyor | **Beklemede — madde 39'a bağlı**; bug değil, bilinçli denge. Tam koşu bitince gerçek FN/FP sayılarıyla değerlendirilecek; #224 ve #101'in durumu o koşudan doğrulanacak |
| 31 | OCR'lı Cevap sayfalarının metin kalitesi: bir sayfa okunamıyor (#24), diğerlerinde üst simge / "\|" kaybı model cevabına aynen geçiyor | Açık — iki ayrı ciddiyet: okunamayan sayfa (yeniden OCR) / kısmi bozulma (son işleme) |
| 32 | RRF birleştirmesi BM25=0 olan en iyi dense chunk'ını havuzdan atıyor (test_3 #79/#82) | **Kapandı (mekanizma)** — `8d3f33d` dense güvenlik slotu, N=1'de #79 FN→TP; **bayrak KAPALI, açma kararı ayrı ve AÇIK** (bkz. madde 32 kapanış notu) |
| 33 | Stemmer tutarsızlığı + iki chunk'a bölünmüş cevap (test_4 #91) | **Kısmen kapandı** — `.txt` birleştirme MIN=500 üretimde (`ba46059`, 2026-10-29; DB `757e97059abb`; #91 düzeldi, madde 39'da TP; duman testi geçti). **Açık:** stemmer tutarsızlığı (kapsamı ölçülmedi, #91'e katkısı 0; ayrı satırı yok, madde 23'te izleniyor); birleştirme politikası yalnız 2 kısa `.txt` üzerinde, tek koşu/tek değerlendiriciyle ölçüldü; **açık üretim riski:** `rag.db` git'te izlenmiyor (aşağıdaki not) |
| 34 | Cevap chunk'ı bağlamda 1. sırada, model yine reddediyor (test_3 #82) | **Kapandı (2026-10-29)** — neden dil/sembol değil, konu dışı "türetme" chunk'ı (4333); desen #56'da da doğrulandı ama kapsam dar (net getiri ≤1 soru, kısmen doğru, yalnız dense bayrağı açıkken). Müdahale yapılmadı; bağıl eşik bulgusu → madde 24 |
| 35 | `run_tests.py` kapanışta aralıklı 0xC0000005 ile çıkıyor | Açık — **düşük öncelik**; sonuçlar tam yazılıyor, iş-around `uretim.py`'de (`b469350`) |
| 36 | `classify_answer` TP'si doğruluk değil: TP'lerin %32'si yanlış cevap | **Karar verildi** — ret tespiti güvenilir (FN/TN 0 çelişki); bağlam değişen ölçümlerde sınıfın yanında ayrı doğruluk kontrolü kural (b), raporlarda TP yerine "cevap verdi" (a), `classify_answer` koduna dokunulmaz (c) |
| 37 | Yorum isteyen soruda ret kırılgan: bağlam bileşimine monoton olmayan şekilde bağlı (test_4 #100) | Açık — şüphe: yorum sınırı / subjektif soru; madde 34'ten ayrıldı, mekanizma ölçülmedi |
| 38 | Ret kalksa da içerik hatalı: sınıf TP ama GT karşılanmıyor — içerik doğruluğu ret/kabul ayrımından ayrı bir sorun (test_2 #56, test_3 #82) | Açık — genel başlık; madde 34'ten ayrıldı, madde 36 ailesi (TP ≠ doğru). Örnekler: #56 genel geçer cevap, #82 yanlış formül |
| 39 | Güncel sistemle tam benchmark + negatif set koşusu yok; kapsam kontrolleri eski/karma kayıtlara dayanıyor | Açık — **aktif hedef**; test_5 ölçüldü (11.6 dk), tam koşu tahmini ~1.5–2 saat, parçalı koşu planı bekliyor. Son tam pozitif koşu v8 |
| 40 | Üretim (Streamlit app.py) aynı VRAM açlığı riskini taşıyor; gerçek oturumda doğrulanmadı | Açık — düşük öncelik, doğrulanmamış; madde 39'dan ayrıldı |

**Uyarı (madde 36):** bağlam değişen ölçümlerde TP = doğru cevap DEĞİLDİR;
`classify_answer` yalnız ret / cevap ayrımı yapar, doğruluk ayrıca kontrol edilir.

**GT değişikliği (2026-10-28, `747fb8a`):** test_negative #214 negatiften pozitife
alındı (`airports.json`'da IST/TR var). Negatif set **32 → 31** soru. Bu tarihten
önce kaydedilmiş negatif set rakamları (`x/32`, baz ve v2–v8 TN/FP) **eski
etikete dayanır**. Yeni etiketle yeniden sınıflandırıldığında geçmiş 6 koşunun
(v2, v3, v5, v6, v7, v8) hepsinde #214 ret cevabı **TN→FN** oluyor: TN −1,
payda 31, pozitif FN +1; FP sayıları değişmez. Test_1–5 üzerinden hesaplanan
FN sayıları (ör. madde 21: baz 10 / v7 13 / v8 6) etkilenmez. Eski ve yeni
rakamları doğrudan karşılaştırmadan önce bu farkı düşün.

### Öncelik sırası (2026-10-11, güncelleme 2026-10-13)

Açık retrieval/değerlendirme maddeleri için sıra: **25 (skorlama) ✅ → 22 ✅ → 27 ✅ → 29 ✅ → 20 (top_k ✅, 2b açık) → 21 (raporlama ✅; 4 FN açık) → 32 (mekanizma ✅; bayrak kararı açık) → 36 (karar ✅: doğruluk kontrolü kural) → 33 ✅ → 34 ✅ → 24 (beklemede) → 39 ✅ (tam koşu + yeni referans) → 40 (düşük öncelik) → 30 (güncel taban hazır, karar açık) → 28 → 26 → 31 → 35 (en alt).**

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

### AÇIK ÜRETİM RİSKİ — eşzamanlı oturumlarda toparlanma (2026-11-04)
Madde 11'in toparlanma tasarımı (kademe 2: Foundry'de modeli HTTP ile
unload/load etmek) **başka bir oturumun uçuştaki LLM çağrısını öldürebilir**:
model servis genelinde tek bir örnek, yeniden yükleme sırasında tüm çağrılar
düşer. Tasarım **tek kullanıcı / düşük eşzamanlılık** varsayımıyla yapıldı
(ağır işlemler zaten ardışık; Foundry + Ollama + reranker 8 GB VRAM'i tek iş
yüküyle dolduruyor, bkz. madde 39/40). Kaç eşzamanlı oturumun "olağan"
sayıldığı ÖLÇÜLMEDİ; varsayım: tipik 1, en çok birkaç, çoğu zaman aynı anda
LLM çağıran tek oturum. Azaltıcılar tasarımda: tek uçuşlu kilit (aynı anda tek
toparlanma), devre kesici (60 sn'de en fazla 1, art arda 3 başarısızlıkta
bırak). **Ortadan kaldırmıyorlar** — kilit toparlanmaları serileştirir ama
kurban oturumun çağrısını kurtarmaz. Çok kullanıcılı üretime geçilirse bu risk
yeniden değerlendirilmeli (ör. toparlanmayı yalnız hiçbir çağrı uçuşta değilken
yapmak ya da servisi oturum başına ayırmak).

### Kapanış (2026-11-04) — C uygulandı ve ölçüldü; toparlanma UYGULANMADI (madde 15'e devredildi)
- **C kapandı** (`245a78c`): düzeltme prompt'u 10.500 krk ile sınırlı, geçmiş bütçeli kırpılıyor.
  Ölçüm: #53 eskiden 9.351 → 12.575 krk'ta 500 verip servisi bozuyordu (doğrulandı); artık
  9.351 → 10.500 → 10.500 ile çökmüyor ve yanıt veriyor (3/3 tekrar aynı). #43 de çökmüyor
  (2/2), cevabı pandas ile doğrulandı. Tam paket 203 geçti. Kalan iki test (`test_code_interpreter`,
  `test_full_pipeline`) canlı servis ister ve değişiklikten önce de kalıyordu.
- **Gerçek C etkisi yalnız #43 ve #53 üzerinden raporlanır.** test_5 #102/#110'un HATA'dan
  düzelmesi C'ye YAZILMAZ (ikisi `call_llm_text` çağırmıyor).
- **#53'ün yanıtı yanlış sayı içeriyor** (Sinem iptal 4 / gerçek 12, Umut min 6 / gerçek 4); bu
  C'den bağımsız sentez confabülasyonu: madde 41'in sonundaki nota bakınız. README'de #53 ayrı
  kategoride tutulur.
- **Toparlanma uygulanmadı.** Kapı deneyi kademe 2'nin bozuk servisi düzelttiğini kanıtlamadı
  (bozulma kalıcı olarak yeniden üretilemedi); ayrıntı ve açık sorular
  [madde 15 §5](#5-madde-11-toparlanma-kapı-deneyi-2026-11-04--toparlanma-uygulanmadı)'te.
  Aşağıdaki "eşzamanlı oturum riski" bu yüzden şu an teoriktir: toparlanma kodu yok. Toparlanma
  ileride yazılırsa yeniden değerlendirilmelidir.
- Katmanlar: **1. katman** (sorunun cevabı kayboluyor) D ile (`90a08e9`); **önleme** C ile;
  **2. katman** (servis sonraki istekler için bozuluyor) → madde 15, açık.

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
  **Uyarı (2026-11-04, madde 18):** bu seçenek "kolay yedek" değil. Madde 18'in
  ölçümünde aynı 7B model, kendi gerekçesinde sorunu yazıp yine TAMAM dedi
  (#44, #42, #52, #60), gerekçe-önce biçim 3 hedef vakanın en fazla 2'sini
  yakaladı ve yanlış itiraz üretti (VE 1/7, VNE 4/7); #51'i gerekçeyle bile
  göremedi. Ayrı bir LLM katmanına geçmek büyük olasılıkla aynı kapasite
  duvarına çarpar; beklenti düşük tutulmalı, denenirse farklı/daha büyük bir
  model ya da yapılandırılmış çıktı sözleşmesi gibi somut bir değişkenle.

Heuristik yarışına devam edilmemesinin gerekçesi: her katman kendi test yükünü,
kendi kenar durumlarını ve kendi bakım borcunu getiriyor; çözülen tek vakanın
(#107) değeri bu maliyeti karşılamıyor.

### Ek (2026-11-04): #232 aynı desen; kapsam sonucu
Madde 18 Adım 3 (`experiments/madde18_dogrulayici/adim3_kapsam.py`, LLM'siz,
madde 30 tam koşusunun logları): sandbox'tan sonuç dönen 14 soruda (147'den;
11 TP, 2 FP, 1 TN) "soru bir kavramdan bahsediyor, kod+sonuçta yok" deseni
**3 soruda, üçü de negatif**: **#107** (FP; "ücret" → `defaultDurationMinutes`),
**#232** (FP, test_negative; "en son hangi tarihte sınır değişikliği" → kod
`founded` ile eyalet adı (Hawaii) döndürüyor, tarih/değişiklik yok;
doğrulayıcı `ok`), **#108** (TN; başka katman "bilgi bulunamadı" diyor).
Benchmark'taki 4 FP'nin 2'si (#107, #232) bu desen; diğer ikisi madde 30.
**#232 de aynı kök nedenle kabul edilmiş sınırlamaya eklendi.** 11 pozitif
sorunun hiçbirinde gerçek eksik kavram yok.

Deterministik kapı yine açılmadı: sorular Türkçe, kolonlar İngilizce
(doğru #32'de bile "meslek"/"sektör" kodda geçmiyor), yani düz sözcük
eşleştirmesi #107'yi #32'den ayıramaz; alias tabanlı kapı ise bu maddenin 2.
denemesi olarak zaten çürüdü ve #39/#42'de (gerçekten `ok` kalması gereken
vakalar, madde 18) filtre/hesaplanan sütun ayrımında kırılırdı.

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

*[Güncel değil — bu paragraf ayrımın kodda uygulanmasından önce yazıldı; aşağıdaki
"Durum (2026-11-04)" bölümüne bakın.]* Çözüm şimdi tasarlanmadı. Ele alınırken dikkat: `EMPTY_RESULT_INSTRUCTION`
bilinçli olarak ÇIPLAK ret istiyor, çünkü `benchmark_eval`'in
`check_is_not_found` kontrolü ret cümlesinden sonra 3+ içerik kelimesi kalırsa
cevabı ret DEĞİL "iddia" sayıyor (bkz. `retrieval.py` içindeki açıklama ve
negatif set #231). Mesajı zenginleştiren her çözüm bu ölçüm tanımıyla
çakışabilir — yani düzeltme, ölçüm tarafını da beraberinde düşünmeyi
gerektiriyor.

### Durum (2026-11-04) — ayrım kodda zaten uygulanmış; D5 açık
Ölçüm ve testler: [experiments/madde14_bulunamadi/](../experiments/madde14_bulunamadi/),
[tests/test_refusal_messages.py](../tests/test_refusal_messages.py).

**Referans düzeltmesi.** "Madde 11'in D ölçümü" diye anılan
[implementation_plan_retry_oom.md](implementation_plan_retry_oom.md) **madde 11'in**
planıdır; "D" onun D seçeneğidir (LLM istisnasını yakala, `success: False` dön). Dosya
D'yi ve ölçüm planını tanımlar, D sonrası bir ölçüm sonucu içermez; madde 14 o
seçeneğin sonucundan doğdu.

**Ayrım zaten koddadır.** `data_engine.py` + `retrieval.py` dört durumu ayrı etiket,
özet ve synthesizer talimatıyla taşır; `run_tests.py` servis çökmesini `HATA`'ya çevirir
(test_2 #43/#53'ün kronik HATA'sı bu yolun çalıştığının işaretidir, skorlanmaz).

| Durum | Etiket | Kullanıcıya giden cümle |
|---|---|---|
| D1 veri gerçekten yok | — (semantik RAG) | "Bu bilgi dokümanlarda bulunamadı." |
| D2 filtre 0 satır | `[KAYIT BULUNAMADI]` | "…bulunamadı; belirtilen koşullara uyan kayıt yok." |
| D3 doğrulanamadı | `[DOĞRULANAMAYAN SONUÇ]` | "…bulunamadı; sonuç doğrulanamadığı için aktarılmadı." |
| D4 servis çöktü | `[İŞLENEMEDİ]` | "…bulunamadı; soru şu an işlenemedi, tekrar denenebilir." |
| **D5** kod 3 denemede çözülemedi (servis sağlam) | yok → semantik RAG'e düşer | semantik RAG ne üretirse (aşağıya bakın) |

**Ölçüm sınırı (açıkça):** D2–D4 cümleleri `olcum.py` ile, retrieval'ın ürettiği bloğun
biçimi **elle kurularak** gerçek modele sorularak ölçüldü — gerçek bir çökme, boş filtre
ya da doğrulayıcı itirazı üretilmedi. Tek soru (#43), 2 tekrar (aynı). Betiğin ilk
sürümünde "ham/kırpma" sütunu hatalıydı (kırpma bu yolda hiç çağrılmıyor); düzeltilip
yeniden koşuldu.

**Kırılgan nokta kilitlendi.** `llm_client.ask`, `extra_instruction` varken
`_trim_after_not_found`'u çağırmaz; çağırsaydı D2–D4 cümlelerinin üçü de düz
`NOT_FOUND_ANSWER`'a çökerdi (fonksiyonda doğrudan ölçüldü). Ayrım yalnız bu erken
dönüş sayesinde yaşıyor. `tests/test_refusal_messages.py` (21 test) dört cümleyi,
skorlayıcıdaki ret geçerliliğini, bu davranışı, retrieval etiket/talimat eşlemesini ve
D4/D5'in data_engine'de ayrı yola gidişini kilitler; erken dönüşü bozmak testleri düşürür
(mutasyonla doğrulandı).

**D5 — gerçek vaka (`d5_gercek.py`).** Sandbox'ın kod üreten çağrısı hata veren kod
döndürecek şekilde yamalandı (3 deneme `KeyError`, servis sağlam); geri kalan her şey
gerçek (router, semantik fallback, reranker, synthesizer). Bilgisi veride bulunan sorular:
- **Tek kayıttan/özet bloktan cevaplananlar (benchmark #32, #35, #39, #42): 4/4
  semantik fallback doğru cevabı buldu** (TP; #42'nin cevabında bozuk sözcükler var:
  "iptal notuwresi same" — ilk kayıttaki "yarıda kesik" ifadesi YANLIŞTI, betiğin 300
  karakterlik yazdırma sınırından kaynaklanıyordu; bkz. madde 38 Örnek 3).
- **Tüm 728 kaydın hesabını isteyen toplulaştırma soruları (benchmark dışı, gerçek
  değer pandas'tan): 0/3 doğru cevap.** A1 ortalama deneyim (gerçek 11.9986): uydurma
  hesap ("19+13+12=44 … 44/364"). A2 business profil sayısı (gerçek 129): "Bu bilgi
  dokümanlarda bulunamadı." — bilgi VAR, kullanıcıya "yok" deniyor, tekrar ipucu yok.
  A3 ortalama minimumNoticeHours (gerçek 9.75): "24", güvenle yanlış.

**D5 kararı: ayrı bir mesaj tek başına yetersiz; davranış değişikliği
madde 41'e
devredildi, burada UYGULANMADI.** Gerekçe: D5'te gözlenen zarar çoğunlukla ret değil
**yanlış sayı** (2/3) — yeni bir cümle yalnız A2'yi (1/3) düzeltirdi; asıl mekanizma
mesaj değil, sandbox başarısız olunca toplulaştırma sorusunun semantik RAG'e düşmesi.
Ayrıntı, çözüm adayı ve blokaj şartları madde 41'de. Bu işin mesaj/durum ayrımıyla
(madde 14'ün konusu) farklı bir risk sınıfı olduğu orada yazılı.

**#42'nin bozuk cevabı** (D5 yolunda "iptal notuwresi same") madde 38'e Örnek 3 diye
kaydedildi; triyajı orada.

**Madde 14 kapanışı (tamamlandı DEĞİL):** ayrım kodda zaten var + D5 gözlemi yapıldı +
davranış değişikliği yeni açılan madde 41'e devredildi. Mesaj metinlerinde ve ayrımda bu
turda hiçbir değişiklik yapılmadı; testler (`tests/test_refusal_messages.py`) mevcut
davranışı kilitler.

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

### 5. Madde 11 toparlanma kapı deneyi (2026-11-04) — toparlanma UYGULANMADI
Madde 11'in C kısmı (`245a78c`) uygulandıktan sonra "toparlanma" (sağlık kontrolü + modeli
HTTP ile unload/load, "kademe 2") tasarlandı ve uygulanmadan önce bir kapı deneyiyle sınandı
([experiments/madde11_toparlanma/](../experiments/madde11_toparlanma/)). **Sonuç: kademe 2'nin
bozuk servisi düzelttiği kanıtlanamadı; bu yüzden uygulanmadı, iş bu maddede açık duruyor.**

- **Servis kesintiden sonra kendiliğinden kapanmış bulundu.** Bir oturum kesintisinin ardından
  `foundry service status` "not running" döndü (başlatan biz değildik). Üretimde bunu tespit
  eden ya da yeniden başlatan **hiçbir şey yok**: `src/` içinde `foundry service start/stop`,
  sağlık kontrolü ya da restart yok; `llm_client._endpoint_cache` bir kez yazılır ve servis
  ölse/port değişse bile hiç temizlenmez; `app.py` modeli bir kez yükleyip `session_state`'te tutar.
- **Kalıcı bozulma koşula bağlı ve güvenilir biçimde yeniden üretilemedi.** Yukarıdaki §4 ve bu
  sabahki gözlem (uzun süredir açık serviste #53'ün OOM'undan sonra #43'ün 9 KB'lık ilk çağrısı
  `Exception during initialization` verdi) kalıcı bozulmanın GERÇEK olduğunu gösteriyor. Ama
  bugün: taze başlatılmış serviste tek OOM kalıcı bozulma bırakmadı; ~30 dk açık bir örnekte
  ~29 normal istek + 4 OOM denemesi (12.600 / 15.000 krk, GPU 7.9/8.2 GB dolu, boş RAM 0.7-1.5 GB)
  yalnız **1 geçici** başarısızlık üretti (9 KB prob OOM'dan 5 sn sonra 500), ~1,5 dk içinde,
  müdahale olmadan kendiliğinden düzeldi. **Süre/durum birikimiyle ilişkili olabilir,
  kanıtlanmadı**: saatler süren bir örnek simüle edilemedi (denenen birikim yalnız istek sayısı,
  OOM sayısı ve bellek baskısı). Eşik de duruma göre kayıyor (12.575 krk bir serviste çöktü, taze
  bir örnekte geçti).
- **Kademe 2'nin etkisi ölçülemedi.** Mekanik güvenli: `unload_model` anında döner, `load_model`
  6,5-24 sn sürdü, askıda kalma olmadı. Ama deneydeki "DÜZELDİ: true" **boş bir doğrulama**:
  geçici bozulma kademe 2 çalıştığında zaten kendiliğinden geçmişti (`tier2_basta` probu
  müdahalesiz 200). Bozuk bir servisi onardığı gösterilmedi. (Kademe 3, `service stop/start`,
  denenmedi: yukarıdaki §4'te 3 kez askıda kaldığı kayıtlı.)
- **Bırakılan açık sorular:** sağlık kontrolünün probu ne boyutta olmalı (kısa prob mu, ~9 KB mı —
  bozuk durumda hangisinin başarısız olduğu ölçülemedi); kalıcı bozulmanın yeniden üretilebileceği
  bir koşul (uzun süre açık örnek).

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

**Servis ölürse boşluğu (madde 11 turunda tespit edildi, 2026-11-04) — B'ye bağlı,
BU TURDA DOKUNULMADI.** `_semantic_check` sırasında LLM servisi ölürse
`info["error"]` dolar, `validation_status="failed"` olur, ama sonuç yine de
`success=True` ile ve doğrulanmış gibi döner (`code_interpreter.py`, B'nin
konusu olan aynı dal). Madde 11'in toparlanma kancası bu çağrı noktasına
eklense bile **dönüş değeri bilinçli olarak değişmez** (A aşamasının "davranış
değişmez" kararı korunur); kanca yalnız servisi onarmayı dener. Sonuç: servis
doğrulayıcıdan sonra ölürse sıradaki çağrılar (`result_to_natural_language`,
`ask`) başarısız olabilir ya da `failed` bir sonuç temiz görünmeye devam eder.
`failed` → `[DOĞRULANAMAYAN SONUÇ]` / `service_failure`'a çevirme kararı B'nin
(yukarıdaki plan) kapsamında verilecek. Not: yalnızca bu yol için gözlenmiş
vaka yok (izole koşuda `failed` 0/26).

## Madde 17 — Bilinen kırık test: `test_data_engine_end_to_end_visualization`

Validator A (`10f5efc`) sırasında tam test paketi koşulurken fark edildi; o
değişiklik geri alınınca da aynı şekilde kırık, yani **önceden var**.

Hata:

```
AssertionError: Sorgu için chart_data üretilemedi: Psikoloji ve Danışmanlık ve
Ağız ve Diş Sağlığı sektörlerindeki 45 dk üzeri seans oranları karşılaştırması
```

### Teşhis (2026-11-04) — ilk kaydın bazı iddiaları düzeltildi
- **Ne zaman kırıldı:** `3f89ad9` (2026-09-11, "refactor: optimize dataset loading…").
  Sorgunun karşılandığı kural (1B "hizmet süresi ve sektör karşılaştırması") 1A, 1C, 1D ile
  birlikte **bilerek silindi**: karmaşık/çok koşullu sorgular artık `execute_query()`
  kapsamında değil, `code_interpreter` kademesine gider (`data_engine.py` belge notu).
  Test (`e75654c`) o kural varken yazılmıştı ve güncellenmedi.
- **Kök neden iki katmanlı:** (1) **eskimiş test** — silinen kuralı bekliyor; ayrıca beklenen
  `operation` adı hiçbir yerde assert edilmiyordu, yalnız yazdırılıyordu (6 sorgudan ikisinde
  adlar eskimişti, biri — "Türkçe dışında en sık geçen diller" — yanlış kurala, şehir kuralına,
  düşüp yine de "geçiyordu"); (2) **aşırı geniş alt dize eşleşmesi** — soru, kural 2D'ye
  (`filtered_count_sector`) düşüyor: `"sektor" in q_norm` ("sektörlerindeki" de uyar), sonra
  sektör adlarından sorguda geçen İLKİNİ sayıyor; iki sektörün, eşiğin, "oran/karşılaştırma"nın
  varlığı denetlenmiyor → `{'sector': 'Ağız ve Diş Sağlığı', 'count': 32}`, tek veri noktası,
  `chart_data` None. Aynı sınıf: 2H'deki `"iller" in q_norm` "dil**ler**"i ve "profil**ler**"i
  yakalıyor (147 sorunun 17'sinde alt dize eşleşir, kelime sınırıyla 0).
- **Düzeltilen iddia:** ilk kayıt bunu "kullanıcı açısından **yanlış cevap**" diye yazmıştı.
  **Üretimde ulaşılamıyor:** `execute_smart_query` kural motorunu yalnızca rota `rule_engine`
  ise çalıştırır; router bu rotayı yalnızca **3 sabit, çapalı cümleye** verir
  (`SIMPLE_RULE_PATTERNS`: toplam profil sayısı, kaç farklı sektör, kaç farklı meslek). 147
  benchmark sorusunun hiçbiri `rule_engine` rotasına gitmiyor (121 semantic_rag, 26
  code_interpreter); bu sorunun rotası `code_interpreter`. `execute_query`'yi doğrudan çağırınca
  27 soruya anlamsız bir kural uyar, ama bu yol yalnız testte ve `__main__` demosunda var.
  Etki: CI güveni ve kodun gelecekteki kullanımı, kullanıcı cevabı değil.

### Durum
1. **Test düzeltildi (A):** sektör karşılaştırma sorgusu rule-engine testinden çıktı; grafik hattı
   sabit sandbox sonucuyla ayrıca test ediliyor (`test_sector_comparison_chart_from_fixed_dict`);
   `operation` adları güncellendi ve **assert ediliyor**. "Diller" sorgusu bilerek testten
   çıkarıldı (yanlış kuralla geçiyordu), 2. adımda geri eklenecek.
2. **Alt dize eşleşmeleri (C + 2G) düzeltildi:** `data_engine._word_start` (kelime BAŞI sınırı;
   Türkçe ekler sonda olduğundan "sektorlerindeki" ⊃ "sektor" hâlâ uyar, "diller" ⊅ "iller",
   "kalan" ⊅ "alan"). 2A, 2D, 2G, 2H ve metadata fallback tetikleyicilerine uygulandı;
   `tests/test_rule_engine_matching.py` (20 test) kilitler, eski kodda 5 davranış testi düşer.
   Ölçüm (173 sorgu, önce/sonra): benchmark'ta kural sonucu döndüren soru **27 → 18**,
   `nunique_city_topn` **16 → 3** (kalan 3: #55 gerçekten şehir sorusu, #92/#114 hikâye
   sorularındaki "şehir", kural motorunda veri-seti kapısı olmadığı için; kapsam dışı).
   Demo (`__main__`) sorgularının hiçbiri değişmedi.
   - **2G bilerek dar:** yalnız yalın "dil"/"diller". Çekim ekleriyle genişletince ("dilin",
     "dili", "dillerin") gramer PDF'indeki biçimsel-dil sorularında 6 yanlış `explode_languages`
     çıktı (test_1 #8/#11/#12/#25/#27, test_5 #102); benchmark'ta dil-alanı sorusu yok, yani hepsi
     yanlıştı. Çekimli biçimler ancak veri-seti bağlamı kapısıyla birlikte düşünülebilir.
   - **Açığa çıkan yan etki (kapsam dışı, üretimde ulaşılamıyor):** yanlış şehir kuralı artık
     engellemediği için test_5 #107/#109 ve test_negative #216 ("randevu ücreti / memnuniyet /
     kredi puanı … kaç") `_query_from_metadata_only`'nin `meta_profile_count` koluna düşüyor
     (`"profil"` + `"kac"` koşulu fazla gevşek); test_2 #58 `nunique_occupation`'a düşüyor. Önceki
     sonuç (şehir sayısı) da yanlıştı; yani "farklı yanlış", yeni bir gerileme değil. Düzeltme
     ayrı bir karar.
3. **2D koruması (B) uygulandı.** Önce #52'nin 2D'ye bağımlı olmadığı doğrulandı: rotası
   `code_interpreter`, `execute_smart_query` içinde `execute_query` 0 kez çağrılıyor (router'ın
   3 sabit cümlesinde 1 kez, kontrol), iki benchmark koşusunda da cevabı sandbox'tan
   (`[KESİN HESAPLAMA SONUCU]`, doğrulama `ok`); `filtered_count_sector` adına başka kullanıcı yok.
   B'nin düzelttiği iki hata:
   - **Eşik/oran dışlama:** 2D, iki sektör adı ve "45 dk üzeri seans oranları karşılaştırması"
     içeren soruda yalnız ilk sektörün sayısını döndürüyordu (bu maddenin kırık testi).
     Artık yalnız tam bir sektör adı kaldıysa ve soruda oran/yüzde/karşılaştır/fark/daha/üzeri/üstü/
     altında/dakika/ortalama ya da "N dk" yoksa eşleşir.
   - **İç içe geçen ad hatası (önceden vardı):** "Sağlık", "Beslenme ve Sağlıklı Yaşam"
     içinde kelime başında geçtiği için "Beslenme ve Sağlıklı Yaşam sektöründe kaç profil var?"
     **Sağlık'ın sayısını (40)** döndürüyordu (doğrusu 32). Başka bir sektör adının içinde kalan
     eşleşme artık elenir; ikisi ayrı ayrı geçerse (iki sektör) eşleşmez.
   Ölçüm (173 sorgu, önce/sonra): yalnız test_2 #52 (`filtered_count_sector` →
   `meta_sector_distribution_filter`) ve T4 değişti; benchmark'ta 2D hit'i 1 → 0; `__main__` demo
   sorguları değişmedi. `tests/test_rule_engine_matching.py` 31 test; eski kodla 10'u düşer.
   **Bilinen sınırlama (uygulanıyor, ama eksiksiz değil):** oran/eşik/karşılaştırma sözcük
   listesi (`_SEKTOR_KARMASIK_KALIPLARI`) **sezgiseldir ve kapsayıcı değildir**; listede olmayan
   bir eşik ifadesi ("… en az 60 dakikalık …" gibi listedeki köklerle yakalanmayan bir kurgu)
   2D'den tek sektörlü bir soruda yine sessizce bir sayım döndürebilir. Kural üretimde
   ulaşılamadığı için etki CI güveni/gelecekteki kullanımla sınırlı.
4. **Ertelendi (D):** "ölü kuralları buda / `execute_query`'yi router desenlerine bağla"
   seçeneği ertelendi, öncelik verilmedi. Gerekçe: üretimde yalnız 3 cümle rule_engine'e
   gidiyor, 2A–2H'nin çoğu fiilen ölü; ama router desenleri genişlerse yeniden canlanırlar —
   ayrı, daha büyük bir karar.
5. **Ertelendi (çekimli dil biçimleri):** "dilin / dili / dillerin" biçimleri veri-seti bağlamı
   kapısı olmadan 2G'ye eklenemez — kapısız genişletme 6 yanlış pozitif üretiyor (test_1
   #8/#11/#12/#25/#27, test_5 #102), bu yüzden ertelendi, öncelik verilmedi.
6. **Ertelendi (metadata fallback koşulları):** `_query_from_metadata_only`'nin gevşek koşulları
   (`"profil"` + `"kac"`, occupation kolu) şimdi test_5 #107/#109, test_negative #216 ve test_2
   #58'de farklı yanlış eşleşmelere yol açıyor (gerileme değil, önceki sonuç da yanlıştı);
   üretimde ulaşılamıyor, düzeltme ayrı karara bırakıldı, öncelik verilmedi.

### Kapanış (2026-11-04) — madde KAPALI
Planlanan dört adım tamamlandı:
- **A** (`c135935`): eskimiş test düzeltildi; `operation` adları assert ediliyor, sektör
  karşılaştırma grafiği sabit dict ile ayrı test ediliyor.
- **C + 2G** (`caf6aca`): kural motorundaki alt dize eşleşmeleri kelime başına çevrildi
  (`_word_start`); yalın "dil/diller" `explode_languages`'a gidiyor. Benchmark'ta kural sonucu
  döndüren soru 27 → 18, yanlış şehir eşleşmesi 16 → 3.
- **B** (bu commit): 2D kuralı iç içe geçen sektör adını eler ("Beslenme ve Sağlıklı Yaşam" artık
  Sağlık'ın sayısını döndürmez) ve oran/eşik/karşılaştırma sözcüğü varsa eşleşmez.
- **D** ertelendi (aşağıda).

Sonuç: tam paket yeşil (196 test), kırık test kalmadı. Kök neden (eskimiş test + aşırı geniş
alt dize eşleşmeleri) giderildi; kural motoru üretimde yalnız router'ın 3 sabit cümlesi için
çalıştığından kullanıcı cevabı hiç etkilenmemişti, kazanç CI güveni ve kodun gelecekteki
kullanımı.

**Bilerek ertelenen / bilinen sınırlamalar** (hiçbiri bu maddenin kapsamında çözülmedi):
- **Çekimli dil biçimleri** (dilin, dili, dillerin): veri-seti bağlamı kapısı olmadan
  eklenemez (kapısız genişletme 6 yanlış pozitif üretiyor); öncelik verilmedi.
- **Metadata fallback gevşekliği** (`"profil"` + `"kac"`, occupation kolu): test_5 #107/#109,
  test_negative #216, test_2 #58'de farklı yanlış eşleşmelere yol açıyor (gerileme değil);
  öncelik verilmedi.
- **Sözcük listesi eksiksiz değil:** 2D'nin oran/eşik/karşılaştırma listesi sezgisel;
  listede olmayan bir eşik ifadesi kaçabilir.
- **D** (ölü kuralları buda / `execute_query`'yi router desenlerine bağla): ertelendi,
  öncelik verilmedi.
- Kural motorunda hâlâ veri-seti bağlamı kapısı yok (#92/#114 hikâye sorularındaki "şehir"
  sözcüğü şehir kuralına uyuyor); üretimde ulaşılamıyor.

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
  #108) `ok` kalmalı. **[Düzeltme 2026-11-04: bu 7'nin ikisi yanlış etiketli.
  #108 negatif soru (veride cinsiyet sütunu yok), baseline'da zaten TN —
  doğrulayıcı itiraz etse doğru olur, "kalmalı" değil. #52'nin kodunda gerçek
  hata var ("Diğer Sektörlerden Fazla Sayı": 0 anlamsız, değişken iki kez
  ezilmiş) — itiraz savunulabilir, "kalmalı" değil. #60 doğrulayıcıya hiç
  gitmiyor (3. denemede çözülüyor). Gerçek "kalmalı" kümesi: #32, #35, #39,
  #42 (4 vaka). Madde 18 Adım 2'ye bakın.]**
- Ölçüm: dört vaka + yedi "kalmalı" vaka birlikte koşulmalı; tam eval bu
  katmanı tek başına yeterince ölçmez (madde 13).

### Teşhis (2026-11-04) — aday çözüm değil
[experiments/madde18_dogrulayici/](../experiments/madde18_dogrulayici/): doğrulayıcının
HAM yanıtı 4 vakada yakalandı (V0 bugünkü prompt, VN "Emin değilsen TAMAM"
cümlesi çıkarılmış, VE/VNE gerekçe-önce tanı varyantları; tekrarlar birebir
aynı, tek model, n=4). **Dört vaka aynı kök nedenden gelmiyor:**
- **Yanıt biçimi (#44, #107, kısmen #57).** Tek kelimelik TAMAM/SORUN formatı
  modelin kendi doğru tespitini engelliyor; gerekçe yazdırınca üçünde de
  uyuşmazlığı görüyor (#44 süre/fark ≠ kavramsal soru, #107 süre ≠ ücret).
  #57'de itiraz yanlış nedenle ("grafik yok"); asıl hata olan formülü hiç
  adlandırmıyor.
- **Model kapasitesi (#51).** Gerekçe yazarken bile görmüyor (uydurma kontrol
  listesi). **Beklenti notu: gerekçe-önce biçim "3/4 vakayı çözer, #51
  kalır"; #51 bu müdahalenin başarısızlığı sayılmaz, kapsam dışıdır.** #51 için
  ayrı yol (LLM yargısı yerine deterministik kontrol ya da kabul edilmiş
  sınırlama) gerekirse ayrıca konuşulur.
- "Emin değilsen TAMAM" cümlesi tek başına suçlu değil (VN: 12/12 TAMAM);
  yalnız gerekçe-önce biçimde etkili (#44: VE TAMAM, VNE SORUN).
- Çözülmeden bırakılan: `_semantic_check` "SORUN ile başlıyorsa" ayrıştırması
  gerekçe-önce yanıtla uyumsuz, #107'de çift hüküm (SORUN sonra TAMAM) var.
  Yön seçilirse serbest metinden "son satırı oku" yerine modele net sözleşme
  (ör. son satır tam olarak `VERDICT: TAMAM|SORUN`) verilmeli; bu, 7 "kalmalı"
  vakada yanlış pozitif maliyeti ölçüldükten SONRA tasarlanacak.

### Adım 2 (2026-11-04) — gerekçe-önce biçimin bedeli: net zararlı; madde kapatıldı
`experiments/madde18_dogrulayici/adim2_kalmali.py`: 7 "kalmalı" vakada V0 / VE /
VNE (gerçek `_semantic_check` prompt'u, tek model, tanı amaçlı ayrıştırma:
yanıttaki SON hüküm).
- **Yanlış itiraz:** VE 1/7 (#35), VNE 4/7 (#35, #42, #52, #108; #60 çift
  hüküm). Kazanç: ikisi de 3 vakanın en fazla 2'si, hiçbiri 3/3 değil ve #57
  yanlış nedenle (grafik yok; formül hiç adlandırılmıyor). Doğru nedenle
  yakalanan tek vaka: VE'de #107, VNE'de #44.
- **Gerekçe ile hüküm tutarsız:** #44, #42, #52, #60'ta (VE) model sorunu yazıp
  yine TAMAM diyor; biçim güvenilir sinyal vermiyor.
- **"Grafik yok" itirazı ayırt edici değil:** #57, #42, #60'ta aynı gerekçe;
  sorular "grafikle göster" diyor, doğrulayıcının gördüğü kod grafik üretmiyor.
- **Referans setindeki etiket hataları** (ayrı commit'te düzeltildi): #108 negatif
  soru ve baseline'da TN (itirazı içerik olarak doğru); #52'nin kodunda gözlenen
  gerçek hata var. Bunlar "kalmalı" değil. #60 production'da doğrulayıcıya hiç
  gitmiyor (3. denemede çözülüyor; `attempt < max_retries`).

**Karar: reasoning-first benimsenmiyor; madde 18 kabul edilmiş sınırlama olarak
kapatıldı.** İki mekanizma var (biçim: #44/#107/#57, kapasite: #51) ve bu
yaklaşım ikisini de çözmüyor. **#44, #51, #57 için şu an geçerli bir müdahale
yok** — araştırma burada durduruldu. #107 (kavram veride yok: "ücret" sorulmuş,
kod süre ortalamasını alıyor) farklı, dar bir desen; kapsamı ayrıca ölçülüyor
(LLM'siz kapsam kontrolü), tek soru çıkarsa o da kabul edilmiş sınırlama
listesine eklenecek.

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
  negatif setle ölçülmeli (#214 düzeltmesinden sonra 31).

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

   **Doğrulama (2026-10-27) — hâlâ AÇIK.** "Mekanizma zaten var" çıkarımı
   ölçümle çürüdü. `selected_dataset` sinyali ve `tests/test_router_signals.py`
   bu notla AYNI commit'te (`dffb6a5`) eklendi; not, o mekanizmanın
   kapsamadığı durumu ("filtresiz" = arayüzde dataset seçili değil) tarif
   ediyor. Test bunu kilitliyor: `test_secili_dataset_veri_seti_sinyalidir`
   seçimsiz soruda `RAG` bekliyor. Ölçüm
   ([experiments/madde20_router_2b/](../experiments/madde20_router_2b/)):
   orijinal soru + 7 varyant (ortalama, "kaç kişi", "en fazla", görselleştir…)
   **seçimsiz 8/8 `semantic_rag`** (`fallback_semantic`, güçlü kolon eşleşmesi
   yok), 728_profiles seçiliyken 8/8 `code_interpreter`. Arayüzün varsayılanı
   `source_filter=None` olduğundan kullanıcının ilk karşılaştığı durum tam da
   çözülmemiş olan. "Profillerde …" varyantı da `experience.years` sayesinde
   değil, "profil" kelimesi sayesinde doğru gidiyor. Çözüm adayı (yukarıdaki
   iki parça eşleşmesi) ve negatif setle ölçülmesi gerekliliği geçerli.
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

**Durum (2026-10-27) — raporlama düzeltildi; kör nokta artık görünür.** Plan:
[implementation_plan_madde21_judge_ret.md](implementation_plan_madde21_judge_ret.md),
ölçüm: [experiments/madde21_judge_ret/](../experiments/madde21_judge_ret/).
- **Kapsam:** #24–#29 örneği güncelliğini yitirmiş (v8'de altısı TP). Üç
  judge koşusunda (baz/v7/v8) yapısal olarak ödüllendirilen 4 soru:
  test_2 #56, test_3 #79, #82, test_4 #91. Judge bağlamda cevap varsa reti
  cezalandırıyor (v8 #100); kör nokta tam olarak chunk düzeyinde retrieval
  kaçırması.
- **Düzeltme (`c587b2c`):** TP/TN/FP/FN kuralı `benchmark_eval.classify_answer`
  yardımcısına çıkarıldı (döngü de onu kullanıyor); judge CSV'si
  `siniflandirma` sütunu taşıyor, özet "Pozitif soruda ret (FN): N — judge'ın
  ödüllendirdiği: M [id]" satırı ve "FN hariç" ortalama sütunu basıyor. Judge
  prompt'u değişmedi. Eşdeğerlik: baz/v7/v8 eski vs yeni kodla skorlandı,
  20 scored CSV + 3 genel özet birebir aynı; judge sınıfı vs benchmark satır
  düzeyinde 0 uyuşmazlık.
- **Güncel sistemde yeniden koşu (2 koşu, madde 19/20/22/29 sonrası):**
  #56, #79, #82, #91 **hâlâ FN ve hâlâ ödüllendiriliyor** (5/4/4/5). İki
  koşu cevap, bağlam ve kaynak listesi düzeyinde birebir aynı. Not: üretici
  ve judge `temperature=0`, yani 2. koşu örnekleme varyansı değil,
  tekrarlanabilirlik gösteriyor. Cevap, kayıtlı bağlamda yok (#79
  "dar/geniş/ölçekleme", #82 "konvolüsyon/çarpım", #91 "Gümüş Yaprak");
  top_k 5→8 bu sorularda yalnız dolgu chunk'ı değiştirdi.
  **Güncellendi (2026-11-04): #91 artık FN değil.** Bu tespit (2026-10-27) madde 33'ün
  düzeltmesinden ÖNCE, eski DB'yle (911 chunk) yapıldı; `.txt` birleştirmesi 2026-10-29'da
  üretime alındı (`ba46059`, DB `757e97059abb`) ve madde 39 tam koşusunda (6/6 set bu DB'yle)
  #91 TP ("Gümüş Yaprak"). #56, #79, #82 için bu tespit değişmedi (üretimdeki DB ile yeniden
  ölçülmedi). Madde 33'ten önceki judge çıktıları (baz/v7/v8, bu yeniden koşu) güncel DB ile
  karşılaştırılamaz: bağlamı değişen 13 soru farklı.
- **Açık kalan (ayrı iş):** bu 4 FN'nin kendisi, yani chunk düzeyinde
  retrieval kaçırması. Madde 21 yalnız görünmezliği çözdü.

**Yan bulgular (kapsam dışı):**
- **test_2 #50 — judge yanlış cevabı ödüllendiriyor, sınıf ifadeye bağlı:**
  v8'de "…profil örneği bulunmamaktadır." → skorlayıcı FN saydı; güncel
  koşularda aynı içerik "…örneği yoktur." → TP. Cevap iki hâlde de yanlış
  (GT: 248 profil Cumartesi açık), judge 5/5/5/5 veriyor çünkü bağlamda
  yalnız 4 profil var. İki ayrı sorun: (1) ret tespiti içerik cevabını
  ifadeye göre ret sayabiliyor (madde 28 ailesi); (2) judge kısmi bağlama
  sadık ama yanlış cevabı ödüllendiriyor (madde 21'in kardeş kör noktası).
- **FN kırılımı yanlış atfediyor:** `retrieval_match` dosya adı düzeyinde;
  #79/#82/#91'de doğru dosya geldi ama doğru chunk gelmedi, `benchmark_eval`
  bunları "doğru kaynak geldi ama cevap yok" (üretim sorunu) sayıyor.

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
  kaldı). Tam negatif set FP 2/32 (değişmedi; #214 düzeltmesinden önceki
  negatif set, bkz. üstteki GT değişikliği notu), tripwire 0.

## Madde 23 — Korunan kelimelerin çekimleri farklı token'a düşüyor

**Çapraz referans (2026-11-04):** [madde 33](#madde-33--stemmer-tutarsızlığı--iki-chunka-bölünmüş-cevap-test_4-91)'ün
stemmer yarısı (`kütüphane`/`kütüphanenin`/`kütüphanesi` farklı token'a düşüyor) bu maddeyle aynı
aileden; madde 33'ün özet tablosunda ayrı satırı yok, burada izlenir. Madde 33 Adım 1'de bu
tutarsızlığın #91'e katkısı 0 ölçüldü; kapsamı (kaç soruda BM25'i sıfırlıyor) iki maddede de
ölçülmedi.

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

**Not (2026-10-29) — bağıl eşik iki maddeyi birlikte ilgilendiren aday (madde 34 girdisi).**
Hedef değişmedi: madde 24 = test_5 #103 FP. Madde 34
([experiments/madde34_ingilizce_ret/](../experiments/madde34_ingilizce_ret/README.md))
aynı aracın ters yöndeki kullanımını buldu: pozitif soruda düşük rerank'lı konu
dışı chunk haksız **ret (FN)** üretiyor (#82, #56).
- **Ortak aday:** bağıl rerank eşiği ("adayın skoru en yüksek skorun X katından
  azsa ele"). Ölçülürse tek deneyde, çift ölçütle: negatifte FP azalıyor mu,
  pozitifte TP→FN var mı, ve içerik doğru mu (madde 36/38).
- **Test vakaları:** #82 (bağıl eşik 0.25 ile ret kalkıyor, içerik kısmen —
  formül hatası; madde 34 Adım 3), #56 (konu dışı profiller ≈0.001 oranında;
  ret kalkınca cevap yanlış, madde 38), #87 (gramer dolgusu 0.001, en yüksek
  0.487; yukarıdaki "bir net kazanan + dolgular" tipi).
- **Düşük beklenti uyarısı:** #103 ve #82'nin ikisi de "net kazanan yok"
  tipinde (#103: 0.036 / 0.032 / …; #82: en yüksek 0.015, zararlı ve zararsız
  chunk'lar 0.0031–0.0032'de iç içe). Yukarıdaki uyarıya göre bağıl kesim bu
  tipi çözmez; bağıl eşiğin madde 24'ün asıl hedefini çözme olasılığı düşük.

**Durum (2026-10-30) — beklemeye alındı.** #103 FP bugünkü sistemde tekrar etmiyor,
bağıl eşik adayı not edildi, aktif müdahale yok, yeni FP görülürse yeniden açılır.
Ön-test ([experiments/madde24_bagil_esik/](../experiments/madde24_bagil_esik/README.md)):
V0 ve üst sınır (yalnız en yüksek chunk) 2/2 **TN**; bağlam s.16, s.2, s.18, s.24-25
(skorlar 0.036 / 0.032 / 0.013 / 0.012). Kesin neden bilinmiyor. Yukarıdaki notta
#103'ün aktif hedef gibi anlatılması ve eski skorları bu tarihten önceki duruma aittir.

## Madde 40 — Üretim aynı VRAM açlığı riskini taşıyor, doğrulanmadı

Madde 39 Adım A'da bulundu: `src/app.py`, `load_model()` (LLM) çağrısını
`get_top_chunks()` (retrieval/embedding) çağrısından önce yapıyor — `run_tests.py`
benchmark'ıyla aynı sıra. Repoda ayrı bir dağıtım/Docker dosyası yok; README referans
donanımı "8 GB VRAM". Yani gerçek bir Streamlit oturumunda da, LLM yüklüyken boş VRAM
Ollama'nın istediği 457 MiB'ın altına düşerse, sorgu embedding'i sessizce CPU'ya kayabilir.

**Ölçülmedi:** gerçek bir Streamlit oturumunda VRAM/RAM izlenmedi; bu bir çıkarım, teyit
değil. Madde 39 Adım A'nın ölçtüğü fark küçük (%95.2 aynı bağlam) olduğu için pratik
etkisi de muhtemelen küçük, ama ayrı bir ciddiyet taşıyor: üretim kullanıcısını etkiler,
oysa madde 39 bir ölçüm/değerlendirme altyapısı sorunuydu. Doğrulama madde 39 kapandıktan
sonra, ayrı bir zamanda ele alınabilir.

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

**Durum güncellemesi (2026-10-30) — sabitleme koşullu.** LLM yüklüyken boş VRAM < 457 MiB
ise (Ollama'nın GPU için istediği en az; ölçülen boş 62–318 MiB) Ollama `num_gpu=99`'a
rağmen modeli tamamen CPU'ya yüklüyor (`offloaded 0/25`), hata vermeden; vektör değişiyor
(`d16e…` → `5b82…`). Loglarda 2026-10-27'de de 8 adet 0/25 var (düzeltmeden sonra); hangi
koşulara ait olduğu eşleştirilmedi. Ayrıntı: madde 39.

## Madde 30 — Synthesizer (a) dalı ödünleşiminin sınır vakası (#224)

**Bu bir "düzeltilmesi gereken hata" değil, "yeniden değerlendirilmesi gereken
bir denge"dir.** Acele "bug, düzelt" müdahalesi FN tarafındaki kazancı geri
alabilir.

`llm_client.ask`'taki ret kuralı bilinçli olarak iki dallı: (a) "bağlamda kısmen
ilgili bilgi varsa onu kullanarak en iyi cevabı ver", (b) "hiçbir şey yoksa tek
ret cümlesi". (a) dalı tam koşuda **FN 25 → 10** getirdi; bedeli ölçüldü ve
kabul edildi: negatif FP 7/32 → 8/32 (#214 düzeltmesinden önceki negatif set),
yeni FP **#224** ("Yanlış Ön Kabul"
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

**Güncel taban (2026-11-01, madde 39 tam koşusundan) — önceki paragrafın istediği
üçü de artık taze veriden:** #224 **hâlâ FP** (test_negative, fresh koşu — madde
33'ün duman kaydına değil, bugünkü koşuya dayanıyor; ikisi de aynı: regresyon yok).
#101 **hâlâ FP** (test_5, fresh koşu). FN tarafı (test_1–5, kronik HATA hariç 145
soru): **6 FN** (test_2: 2, test_3: 3, test_4: 1) — tarihsel "baz 10 / v7 13 / v8 6"
karşılaştırmasındaki v8 sayısıyla aynı düzeyde, kötüleşme yok. **Karar hâlâ
verilmedi** — bu yalnız bölümün istediği taze tam ölçüm; (a)/(b) dalı ayarı
tartışmaya açılırsa bu sayılar taban olarak kullanılabilir.

**(a2) denemesi — negatif sonuç (2026-11-02).** Madde 24 Adım 3'teki izole
denemenin (bkz. yukarı) markörden bağımsız genelleştirilmiş hali
[src/llm_client.py](../src/llm_client.py)'a eklendi: bağlamdaki bir parça
yalnızca okuyucuya bir görev/alıştırma tanımlıyorsa ve konuyu açıkça anlatan
başka bir parça yoksa, bu görev tanımının (a) dalını tetiklememesi istendi.
Tüm setler taze tabanla (6c60f60) birebir aynı kapsamda yeniden koşuldu
(`experiments/madde30_sikilastirma/`, commit `5764296`).

Sonuç: **genel sayılar birebir aynı** (92 TP, 42 TN, 7 FN, 4 FP) — kazanç da
kayıp da yok. **#224 ve #101 hâlâ FP**, cevapları öncekiyle aynı mantıkla
üretiliyor (CNF dönüştürme adımlarını sayıyor). Neden: (a2)'nin koşulu
("o işlemi AÇIKÇA ANLATAN başka bir parça yoksa") bu vakada sağlanmıyor —
bağlamda CNF'ye yakın, gerçek bir açıklayıcı sayfa VAR (sayfa 18, "yararsız
değişken/kural atma" adımı; bu paragrafın üstünde zaten teşhis edilen
mekanizma). Yani sorun bir görev-tanımı cümlesini kanıt sayma değil,
**alakalı ama yanlış bir açıklama sayfasının CNF sorusuna yanlış eşlenmesi**;
(a2) bu mekanizmayı hedeflemiyordu, o yüzden hiç tetiklenmedi.

İki soruda sınıf değişti ama her ikisi de (a2) ile ilgisiz: test_2#50 TP→FN
(içerik aynı, cevaba eklenen bir kuyruk cümle ret kapısını tetiklemiş
olabilir), test_3#90 FN→TP (bu soru madde 39'un kendi notunda zaten
"açıklanamayan" bir nondeterminizm/bağlam kayması şüphesi olarak
işaretliydi; bu koşuda test_2/test_3 Ollama'nın CPU'ya düştüğü sete denk
geldi — madde 29'un embedding kayması olası açıklama).

(a2) no-op olduğu için [src/llm_client.py](../src/llm_client.py)'dan geri
alındı.

**Adım 2 — X/XR izolasyonu (2026-11-02): "tek kötü chunk" teorisi çürüdü.**
Madde 34 disipliniyle (`experiments/madde30_sikilastirma/adim2_izolasyon.py`
+ ad-hoc `sayfa 22-23` varyantı): #224 ve #101 için V0 (bugünkü bağlam, FP),
X (sayfa 18 chunk'ı — 4344 — çıkarılmış), XR (yerine konuyla ilgisiz bir
Fourier chunk'ı konmuş) ve ayrıca sayfa 22-23 chunk'ı (4348, bir CNF
alıştırmasının SORU+ÇÖZÜMÜ — "Örnek 2"/"Cevap 2") için de X2/XR2.
**Her varyant (6+4=10 koşu, hepsi 2/2 tekrar birebir aynı) hâlâ FP.** Tek
bir chunk'ı çıkarmak (18 ya da 22-23, ayrı ayrı) sonucu değiştirmiyor —
geri kalan chunk'lar (16/17/19/22-23 ya da 16/17/18/19, hepsi aynı
dilbilgisinin yalınlaştırma/CNF algoritmalarına ait sayfalar) tek başına
yetiyor. **Taban oranı kontrolü de aynı yöne işaret ediyor:** sayfa 18
chunk'ını taşıyan 13 sorudan 10'u (test_1, VN/VT/yararsız-öğe soruları) TP,
1'i (test_5#103, pompalama lemması) TN — yalnız SORU "CNF'ye dönüştürme
adımları" olduğunda (#101, #224) FP çıkıyor. Yani **sayfa 18 (ya da 22-23)
tek başına bir "kötü chunk" değil**; FP'yi üreten şey bu belgenin CNF'ye
komşu birkaç algoritma sayfasının (16/17/18/19/22-23) BİRLİKTE, soru tam
olarak "genel CNF dönüştürme adımları" olduğunda modele "yeterince ilgili
görünen" bir malzeme havuzu sunması — herhangi bir alt kümesi yetiyor.
Retrieval tarafında tek-chunk filtresi (madde 24/32 tarzı) bu nedenle işe
yaramaz; müdahale (varsa) ya tüm bu sayfa kümesini birlikte hedeflemeli ya
da üretim tarafında (ör. "adımları say" türü sorularda genel algoritma
adı/numarası yoksa ret) olmalı — bu hâlâ denenmedi, sayılarla ölçülmedi.

Ham çıktı: `experiments/madde30_sikilastirma/adim2_izolasyon.jsonl`,
`sonuc_adim2_izolasyon.txt`, `sonuc_adim2b_sayfa2223.txt`. Tek soruya göre
değil, tam 32 negatif + FN tarafı birlikte ölçülmeli (bu bölümün yukarıdaki
uyarısı hâlâ geçerli) — herhangi bir müdahale denenirse.

**Durum (2026-11-04): ödünleşim yeniden değerlendirildi, iki müdahale/hipotez
denendi (ikisi de no-op/çürütüldü), kabul edilmiş sınırlama olarak kapatıldı.**
#224 ve #101 FP olarak kalıyor; taban 92 TP / 42 TN / 7 FN / 4 FP (madde 39).

**İzleme notu — "adım sayma + komşu sayfa havuzu" deseni.** "…adımları
nelerdir / hangi adımlardan oluşur" tipi sorularda, belgede genel adım listesi
açıkça yazılı değilken ama komşu algoritma sayfaları (burada 16-19 ve 22-23)
birlikte bağlama girdiğinde model bu sayfalardan bir adım listesi kuruyor ve
FP üretiyor; tek bir chunk'ı çıkarmak etkisiz. Yeni bir FP bu desene uyuyorsa
(adım/aşama sorusu + aynı konuya ait çok sayıda komşu sayfa) madde 30'un aynı
ailesi sayılmalı, yeniden soruşturulmamalı. Müdahale denenmek istenirse yön:
tüm sayfa kümesini birlikte hedefleyen retrieval kuralı ya da üretimde "genel
algoritma adı/numarası yoksa ret" — ikisi de denenmedi.

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

## Madde 32 — RRF birleştirmesi BM25=0 olan en iyi dense chunk'ını havuzdan atıyor

İki pozitif soru güncel sistemde FN (madde 21 yeniden koşusu, 2 koşu,
[experiments/madde21_judge_ret/](../experiments/madde21_judge_ret/)): beklenen
DOSYA 1. sırada geliyor ama cevabı taşıyan CHUNK gelmiyor; model bağlama göre
doğru reddediyor, judge 5/4/4/5 veriyor.

| Soru | Cevap chunk'ı |
|---|---|
| test_3 #79 (bant genişliği ters orantı) | 4183, Fourier sayfa 10 "Ölçekleme (Scaling)" |
| test_3 #82 (zamanda çarpım ↔ frekansta konvolüsyon) | 4185, Fourier sayfa 12 "Sinuzoidal Genlik Modülasyonu" |

**Adım 1 sonucu (2026-10-27) — ölçüm:**
[experiments/madde32_chunk_kacirma/](../experiments/madde32_chunk_kacirma/README.md)
(`8329a85`). Madde 20 yalnız reranker SONRASI nihai 4 chunk'ı karşılaştırmıştı;
katman katman ölçüm:
- Cevap chunk'ı **dense'te 1/911** ve havuza girseydi **reranker'da da 1.**
  sırada olacaktı (#79: 0.658, havuzun en iyisi 0.015).
- Ama **BM25=0** (Türkçe soru, İngilizce slayt gövdesi; ortak token yok) olduğu
  için RRF'ten BM25 katkısı almıyor (`bm25_contrib`), normalize skoru en fazla
  0.5. İki listede orta sıradaki chunk'lar onu geçiyor (#79'da dense'te 348.
  bir profil havuza giriyor). Hibrit sırası 12 ve 17, TOP_K=8 havuzuna
  giremiyor. **Kayıp RRF birleştirmesinde; sorun ne dense'te ne reranker'da.**
- **Kapsam:** dense #1 chunk BM25=0 yüzünden havuz dışında kalan pozitif soru
  yalnız #79 ve #82 (87 semantic_rag sorusu). GT terimi ölçütü 14 soru
  işaretledi ama 11'i v8'de TP. Fourier PDF'inde GT terimleri Türkçe, metin
  İngilizce ve semboller bozuk; ölçüt bu dosyada güvenilir değil.

**Adım 2 sonucu (2026-10-28) — dense güvenlik slotu:** dense ilk-N chunk'ı
hibrit/RRF sırasından bağımsız olarak reranker havuzuna eklenir;
`RAG_DENSE_FORCE_TOP_N` bayrağı, varsayılan kapalı (0).
[experiments/madde32_adim2_dense_force_include/](../experiments/madde32_adim2_dense_force_include/README.md).
- Bayrak kapalıyken nihai bağlam madde 20 kaydıyla 147/147 aynı.
- **#79: FN → TP** (N=1, 3, 5). **#82: FN kalıyor.** Cevap chunk'ı artık
  bağlamda 1. sırada ama model reddediyor (İngilizce, sembolleri bozuk slayt
  metni). Retrieval kısmı çözüldü, kalan üretim tarafı.
- Pozitif setlerde **sınıfta** yan etki yok: TP→FN 0 (bağlamı değişen soru
  N=1: 5, N=5: 29). **Düzeltme (madde 36):** doğrulukta N=1'de değişim yok,
  ama N=3'te #87, N=5'te #30 ve #87 sınıf aynı kalırken kısmen doğrudan
  yanlışa döndü (6 iyileşmenin yanında). N=1 önerisi etkilenmiyor.
- Negatif sette yeni FP: N=1 #214, N=3 +#222, N=5 +#226.
  - #214 **GT etiketi yanlış**: `airports.json`'da IST/TR var; "IST" cevabı doğru.
  - #222 gürültü: ilgisiz profil chunk'ı giriyor, iki cevap da yarım cümle.
  - #226 **gerçek FP**: veri 2024, soru 2023; model yılı yakalamadan cevaplıyor.
- Öneri: N=1. Varsayılanı açmak ayrı karar.

**Açık:** #82 üretim tarafı → madde 34; #214 GT düzeltmesi (ayrı commit).

**Kapanış (2026-10-29) — mekanizma kapandı, bayrak kararı AÇIK.**
- **Kapanan:** mekanizma doğrulandı ve düzeltme yolu ölçüldü. RRF birleştirmesi
  BM25=0 olan en iyi dense chunk'ını havuz dışına itiyordu (Adım 1);
  `RAG_DENSE_FORCE_TOP_N=1` bunu düzeltiyor: #79 FN→TP, #82'nin chunk'ı
  bağlamda 1. sırada, pozitiflerde TP→FN 0 (Adım 2, `8c1b1da`). #214'teki FP
  bir GT etiketi hatasıydı, düzeltildi (`747fb8a`). Testler geçiyor
  (`tests/test_dense_force.py`; tam paket 136 geçti, 1 bilinen kırık, madde 17).
- **Kapanmayan — bayrak varsayılanı:** `DENSE_FORCE_TOP_N` **bilinçli olarak 0
  (kapalı)**. "Madde 32 kapandı" bayrağın açılmaya hazır olduğu anlamına
  **gelmez**. Açmak ayrı bir karar ve henüz verilmedi; açmadan önce:
  - N=1'in negatif setteki etkisi yeni GT ile (31 soru) yeniden doğrulanmalı.
    #222 gürültüsü N=3'te çıktı, N=1'de yok; #226'daki gerçek FP yalnız N=5'te.
  - Gerçek etki tek bir soruda (#79) ölçüldü; #82 madde 34 çözülmeden kazanç
    getirmiyor.
  - Etkinleştirme commit'i bu notu ve yeni ölçümü referans göstermeli.
- **Ayrılan:** #82 generation → madde 34; #91 → madde 33; `run_tests.py`
  kapanış çökmesi → madde 35.

**Kapsam dışı:**
- **test_4 #91 → madde 33** (farklı mekanizma; Adım 1'de birlikte ölçüldü).
- **test_2 #56:** cevap çıkarım gerektiriyor ("schemaVersion 1.1'den ne
  çıkarılabilir"); ilgili chunk (`$.metadata`) bağlamda VAR, model yine
  reddediyor. Retrieval değil üretim/çıkarım sorunu.

## Madde 33 — Stemmer tutarsızlığı + iki chunk'a bölünmüş cevap (test_4 #91)

"Alis'in çalıştığı kütüphanenin adı nedir?" güncel sistemde FN (madde 21
yeniden koşusu). OCR'sız, tek dosyalı basit bir olgu sorusu. Madde 32 Adım 1'de
ölçüldü ([experiments/madde32_chunk_kacirma/](../experiments/madde32_chunk_kacirma/README.md)):
cevap chunk'ı (4227, test1.txt paragraf 1: "… devasa bir kütüphane
yükselirdi: Gümüş Yaprak.") dense 12/911, BM25=0, hibrit 34. → havuz dışında.
Madde 32'nin RRF mekanizmasından farklı; iki ayrı alt neden:

1. **Stemmer tutarsızlığı:** aynı kelimenin çekimleri farklı token'a düşüyor:
   "kütüphane"→`kutupha`, "kütüphanenin"/"kütüphanede"→`kutuphane`,
   "kütüphanesi"→`kutuphanes`. Soru ile chunk aynı kelimeyi taşıdığı halde BM25
   eşleşmiyor (madde 6 Sorun B — stemmer'ın kendi sınırlılığı, kabul edilmişti;
   madde 23 ile aynı aile). Kapsamı ölçülmedi: kaç soruda bu kelime çiftleri
   BM25'i sıfırlıyor?
2. **Cevap iki chunk'a bölünmüş:** paragraf 1'de kütüphanenin adı var ama
   "Alis" yok; "Alis, bu kütüphanede çalışan …" paragraf 2'de (4228, hibritte
   1.). Soru iki paragrafı birleştirmeyi gerektiriyor (eşgönderim). Paragraf 1
   havuza girse bile reranker 5. sıraya koyuyor (0.0034; 4. eşik 0.0037).
   Yalnız (1)'i düzeltmek yetmeyebilir.

Madde 32 Adım 2'nin dense slotu bunu çözmez (dense sırası 12).

**Adım 1 sonucu (2026-10-29) — iki neden ayrı ayrı:**
[experiments/madde33_stemmer_chunk/](../experiments/madde33_stemmer_chunk/README.md).
Oracle varyantlar `src/`/DB değişmeden süreç içinde: S (yalnız `kütüphane` ailesi
tek stem'e), M (paragraf 1+2 tek chunk, embedding ingest yolundan), SM; ayrıca
üretim tavanı G (paragraf 1 ayrı chunk olarak bağlama zorla konur).
- **Yalnız stemmer (S): kazanç 0.** BM25 0→10.6, hibrit 34→7, havuza giriyor;
  ama reranker 5. sıraya koyuyor (0.0034, eşik 0.0037), çünkü paragraf 1'de
  "Alis" yok. Nihai bağlam ve cevap V0 ile aynı (FN).
- **Yalnız birleştirme (M): tam kazanç.** Birleşik chunk BM25 1., dense 2.,
  rerank 0.98 / 1.; cevap "Gümüş Yaprak" (2/2 tekrar).
- **İkisi birlikte (SM):** M ile aynı. Stemmer'ın #91'e katkısı yok.
- **Tavan (G), iki ayrı chunk bağlamda:** sıraya bağlı. Paragraf 1 2. sıradaysa
  kısmen doğru ("Unutulmuş Parşömen'in Gümüş Yaprak kütüphanesi"), 4.
  sıradaysa yanlış (başlığı ad sanıyor). `classify_answer` ikisini de TP sayıyor;
  ret/ret-değil ayrımı doğruluğu ölçmüyor.
- **Belirleyici neden bölünmüş cevap.** Stemmer tutarsızlığı gerçek ama #91'i
  tek başına değiştirmiyor; ayrı bir madde olarak kapsamı ölçülmeli.
- **Ölçülmedi:** genel politikaların (tüm .txt'de komşu paragraf birleştirme,
  genel stemmer düzeltmesi) tam benchmark + negatif setteki yan etkisi.
  Müdahale seçildikten sonra madde 32 Adım 2 disipliniyle ölçülecek.
  **Güncellendi (2026-11-04): birleştirme yarısı ölçüldü** (Adım 2: 147 soru × 4 MIN +
  negatif setler + üretim duman testi, aşağıda), **stemmer yarısı hâlâ ölçülmedi ve yapılmadı.**

**Adım 2 (2026-10-29) — genel birleştirme politikası:**
`.txt` paragrafları, birikmiş metin en az MIN karakter olana kadar komşularıyla
birleştirilir (sondaki artık öncekine eklenir); `.txt` yeniden ingest'i süreç
içinde simüle edilir (`politika.py`; embedding ingest yolundan, `src/`/DB
değişmez). Sweep: MIN = 500 / 800 / 1200 (≈ 2 / 3 / tüm paragraflar; test1.txt
9 → 3 / 2 / 1 chunk). Yalnız `.txt` etkilenir (19 chunk; pdf/docx/json'ın
chunker'ı ayrı).
- **Duman testi** (`sonuc_duman_adim2.txt`): #91'de üç MIN'de de "Gümüş
  Yaprak" + "Alis" aynı chunk'ta ve nihai bağlamda 1. sırada; MIN=0 bugünkü
  bağlamla aynı.
- **Ölçüm** (`havuz2.py` Faz A: 147 soru × 4 MIN, nihai bağlam; `uretim2.py`
  Faz B: bağlamı değişen sorularda üretim) madde 36 kuralıyla: sınıf geçişinin
  yanında bağlamı değişen her sorunun doğruluğu. MIN seçimi "#91 düzeldi mi"
  ile değil, "başka soru sessizce bozuldu mu" ile birlikte yapılacak.
- **Sonuç** ([README](../experiments/madde33_stemmer_chunk/README.md),
  `dogruluk_adim2.txt`): MIN=0 == madde 32 n0 (147/147). Bağlamı değişen soru
  500: 13, 800/1200: 15 (+2 dolaylı: test_2 #35/#46, BM25 korpus istatistiği
  kayması; cevaplar aynı). Negatif setlerde 3/3 ret korundu.
  - **500:** #91 ret→doğru, #98 K→D; doğrulukta bozulan **0**.
  - **800:** #91, #97, #100 iyileşiyor ama #96 sınıf aynı kalırken D→K
    (test2.txt'ten tarih karışması) — sessiz bozulma.
  - **1200:** #91 düzelmiyor; #95/#96 cevap verdi→ret, #97 K→Y ve #94 D→K
    sınıf aynı. Eleniyor.
  - **Öneri: MIN=500** (en küçük ayak izi, sessiz bozulma yok). Sınır: tek
    koşu, tek değerlendirici, 2 kısa `.txt`. Uygulama (ingest'te birleştirme +
    `.txt` yeniden ingest) ayrı onay bekliyor.
    **Güncellendi (2026-11-04): `ba46059` bunu geçersiz kılıyor** — uygulama aynı gün
    (2026-10-29) yapıldı; aşağıdaki "Durum — production'a alındı" bloğuna bakınız. (Onayın
    kaydı bu dosyada yok; commit'in varlığı onay verildiğini ima eder.)

**Durum (2026-10-29) — production'a alındı (MIN=500).**
- Kod: `ingest.extract_chunks_from_txt` → `_merge_txt_paragraphs`,
  `TXT_MERGE_MIN_CHARS = 500` (`tests/test_txt_paragraph_merge.py`); çıktı
  deneydeki `politika.birlestir` ile iki dosyada birebir aynı.
- Yeniden ingest yalnız `test1.txt` / `test2.txt` (`ingest_single_file`):
  9+10 → 3+3 chunk, DB 911 → 898 (`757e97059abb`). Yedek
  `rag.db.bak_madde33_2026-10-29` (kökte, `fc73a4780bca`, alındığı commit
  `8559799`); bir süre saklanacak.
- Duman testi (`duman_prod.py` → `sonuc_duman_prod_retrieval.txt`,
  `sonuc_duman_prod.txt`): nihai bağlam 147/147 beklenenle aynı (değişen 13/13 =
  Faz A MIN=500, değişmemesi gereken 134/134 = madde 32 n0); Faz B'nin 13
  sorusunda cevap metni 13/13 birebir aynı (doğruluk etiketleri geçerli); tam
  negatif set aynı oturumda yedek vs yeni DB: 32/32 cevap aynı, FP 2/32 → 2/32
  (#224, #232), yeni FP yok.

**Açık kalan (2026-11-04 güncellemesi):** (1) stemmer tutarsızlığı — ayrı bir tablo satırı yok,
aynı aile olduğu için [madde 23](#madde-23--korunan-kelimelerin-çekimleri-farklı-tokena-düşüyor)
üzerinden izlenir (`kütüphane`→`kutupha`, `kütüphanenin`→`kutuphane`, `kütüphanesi`→`kutuphanes`;
#91'e katkısı 0 ölçüldü, kapsamı ölçülmedi). (2) Birleştirme politikasının MIN=500 seçimi yalnız
2 kısa `.txt`, tek koşu, tek değerlendirici üzerinden; yeni `.txt` eklenirse kodda otomatik
uygulanır ama o dosyalarda ölçülmedi.

### AÇIK ÜRETİM RİSKİ — `rag.db` git'te izlenmiyor, üretim durumu yerel dosyada (2026-11-04)
Madde 33'ün üretim durumu **kodda DEĞİL, yerel `rag.db` dosyasında** taşınıyor: `.txt`
birleştirmesi ingest sırasında uygulanıyor (`src/ingest.py`), sonucu ise veritabanında duruyor.
`rag.db*` `.gitignore`'da ve git'te izlenmiyor (`git ls-files rag.db*` boş). Güncel DB: 898 chunk
(`.txt` için 6), özet `757e97059abb`.
- **Sessiz geri dönüş riski:** eski bir yedekten geri dönülürse (`rag.db.bak` 916 chunk,
  `rag.db.bak_madde22_2026-10-12` 916, `rag.db.bak_madde33_2026-10-29` 911 — üçünde de `.txt`
  için 19 chunk) madde 33 düzeltmesi **hiçbir uyarı olmadan** geri alınır: #91 ve bağlamı
  değişen diğer 12 soru eski davranışa döner. Uygulama çalışmaya devam eder, hata vermez.
- **Yakalayan mekanizma yok:** `src/` ve `app.py` içinde DB özeti/şema sürümü doğrulaması yok
  (`src/` ve `app.py`'de `sha256`/`hashlib`/`DB_OZET` arandı, bulunamadı). Tek koruma `experiments/
  madde39_tam_kosu/kosu.py`'deki `DB_OZET` denetimi ve o yalnız **benchmark** koşusunu korur;
  üretim uygulamasını korumaz.
- Ölçülmedi: üretimde `rag.db`'nin kaç kez, hangi koşullarda değiştiği/geri alındığı.
- Çözüm adayları (UYGULANMADI, öncelik verilmedi): başlangıçta DB özetini veya bir şema/sürüm
  damgasını doğrulamak; DB'yi ingest'ten yeniden üretilebilir kılan bir betik ve beklenen
  chunk sayısı denetimi.

## Madde 34 — Cevap chunk'ı bağlamda 1. sırada, model yine reddediyor (test_3 #82)

"Zamanda çarpımın frekansta konvolüsyona karşılık geldiği özellik hangi
türetme ile gösterilmiştir?" — madde 32 Adım 2'de retrieval kısmı çözüldü:
dense güvenlik slotu (N=1/3/5) cevap chunk'ını (4185, Fourier sayfa 12
"Sinuzoidal Genlik Modülasyonu") nihai bağlamın **1. sırasına** getiriyor.
Model üç N'de de "Bu bilgi dokümanlarda bulunamadı." diyor
([experiments/madde32_adim2_dense_force_include/](../experiments/madde32_adim2_dense_force_include/README.md)).
**Retrieval tarafı çözüldü (bayrak açıkken; varsayılan hâlâ kapalı), generation tarafı açık.**

Bağlamdaki chunk: başlık Türkçe, gövde İngilizce ("Multiplication in the time
domain is convolution in the frequency domain"), formüller PDF çıkarımında
bozuk (δ, ω, ∫ kaybolmuş; satırlar parçalı). Soru Türkçe ve "hangi türetme"
diye soruyor; cevap (cos ile çarpım → δ ile konvolüsyon, kaydırma özelliği)
bozuk formül satırlarında.

Ölçülmemiş adaylar (karar yok):
- Dil/terim eşlemesi: model "çarpım"/"konvolüsyon"u İngilizce gövdeyle
  eşleştiremiyor mu?
- Bozuk formül metni: madde 31 (OCR/formül temizliği) ile aynı aile mi?
- Ret eşiği: prompt "kısmi kanıtla cevapla" yerine tam eşleşme mi bekliyor?
  (#56 da bağlamda chunk varken ret — aynı mekanizma olabilir.)

Önce: aynı bağlamla prompt varyantları / chunk metni elle temizlenmiş hâli
üretime verilip hangi değişikliğin reti kaldırdığı ölçülmeli.

**Madde 31 B ile karşılaştırma (2026-10-29):** aynı mekanizma değil. 31 B'de
OCR'lı sayfanın içeriği okunuyor, yalnız gösterim bozuk ve model bozuk metni
aynen **kopyalıyor** (sınıf değişmiyor). #82'de ise OCR'sız PDF metin katmanında
semboller kaybolmuş ve gövde İngilizce; model **reddediyor** (FN). Ortak payda
yalnız "bozuk formül metni" ailesi. Bu yüzden 34 ayrı madde kalıyor; bozuk sembol
payı ölçülürse 31 B'nin son işleme adayları (sembol onarımı) burada da denenebilir.

**Adım 1 sonucu (2026-10-29) — neden dil/sembol değil, dikkat dağıtıcı chunk:**
[experiments/madde34_ingilizce_ret/](../experiments/madde34_ingilizce_ret/README.md).
- **Kapsam (LLM'siz):** "bozuk semboller" Symbol fontunun PUA kod noktaları
  (U+F0xx), mekanik eşlenebiliyor. EN gövde + PUA deseni Fourier/Z PDF'lerinin
  geneli (Fourier 8/14, Z 8/19 chunk); test_3'te 1. sırası EN olan 20 sorunun
  18'i v8'de TP. Aynı chunk'ı (4185) taşıyan #83/#84/#89 bugün TP. Desen
  tek başına ret açıklamıyor.
- **İzole varyantlar** (yalnız 4185 metni; 2 tekrar, birebir aynı): yalnız
  sembol (A1 mekanik, A2 elle), yalnız Türkçe (B), ikisi (C, tavan), mekanik
  eşleme tüm bağlama (A1T) → **hepsi FN**.
- **Reti kaldıran:** bağlamın 3. chunk'ı 4333'ün (dilbilgisi PDF'i "4.2
  Türetme Ağacı"; sorudaki "türetme" ile sözcük eşleşmesi, konu dışı)
  çıkarılması → TP. Kontrol X3R: yerine başka bir konu dışı dilbilgisi
  chunk'ı konunca da TP; etki chunk sayısından değil, o chunk'tan. Doğruluk
  iki hâlde de kısmen (madde 36).
- **Ölçülmedi:** mekanizmanın kapsamı (sorudaki terimle eşleşen, başka alandan
  chunk bağlamda + ret; #56 adayı) ve müdahale (kaynak/alan tutarlılığı,
  rerank eşiği — madde 24 ile ilişkili, ya da prompt talimatı). Karar yok.

**Adım 2 sonucu (2026-10-29) — genelleme:** aynı klasör, README "Adım 2".
- **Tarama (LLM'siz):** FN evreni (v8 ∪ madde 32 n0 ∪ madde 33 prod) 6 soru.
  Aday: #56 (aynı JSON içinde konu dışı profiller), #100 (test1.txt chunk'ları);
  #50/#79/#91 aday değil. Taban oranı: v8 TP'lerinin 16/91'inde de aday chunk
  var — ölçüt tek başına ret öngörmüyor.
- **X/XR:** **#56 doğrulandı** (X TP, XR TP; cevap yine de yanlış, madde 36).
  **#100 kırılgan:** 4355 tek başına geçiyor ama ikisi birlikte çıkarılınca
  yine ret; doğrulanmış sayılmadı.
- **Doğrulanan 2 soru (#82, #56):** zararlı chunk'lar cevap chunk'ına göre düşük
  rerank'lı (bağıl 0.22 ve ≈0.001), ama yerine gelen zararsızlar daha düşük;
  mutlak eşik ayırmıyor. Sıradaki: (a) bağıl rerank eşiği (madde 24) +
  regresyon ölçümü. Karar yok.

**Adım 3 (2026-10-29) — (a) bağıl eşik ön-testi, sweep yapılmadı:**
`on_test.py` → `sonuc_on_test.txt`. #82 N=1 bağlamında rerank / ilk oranı: 4187
0.297, 4333 0.216, 4184 0.206 → 4333'ü eleyen her eşik 4184'ü de eler. Eşik 0.25
ile bağlam [4185, 4187]: sınıf TP (2/2), içerik **kısmen** (türetme adı doğru,
eklenen formül yanlış: `F(ω+ω0) * F(ω−ω0)`). Kapı "doğru geliyorsa sweep" idi.

**Kapanış (2026-10-29) — desen belirlendi, kapsamı dar, müdahale yapılmadı.**
- **Belirlenen:** #82'deki ret İngilizce gövde / PUA sembolden değil (A1/A2/B/C
  hepsi FN), bağlamdaki konu dışı, sorudaki terimle eşleşen bir chunk'tan
  (4333 "Türetme Ağacı"; X3/X3R ile izole). #56'da da doğrulandı (aynı JSON
  içinde konu dışı profiller).
- **Neden müdahale yok:** net getiri tavanı tek soru (#82) ve o da kısmen doğru;
  #82'nin cevap chunk'ı yalnız `RAG_DENSE_FORCE_TOP_N=1` açıkken bağlamda
  (varsayılan kapalı, madde 32). #56'da ret kalkınca cevap yanlış (madde 38),
  kazanç sayılmaz. Taban oranı: v8 TP'lerinin 16/91'inde de benzer aday chunk
  var, ölçüt tek başına ret öngörmüyor — genel bir eleme kuralı yan etki riski
  taşıyor.
- **Ayrılan:** #100 → madde 37 (yorum sınırı, kırılgan ret); #56 içerik →
  madde 38; bağıl rerank eşiği bulgusu (zararlı chunk'lar cevap chunk'ına göre
  0.22 / ≈0.001 oranında, ama zararsız yedekler daha düşük → mutlak eşik
  ayırmaz) → madde 24. PUA→Symbol eşlemesi (`varyant.pua_esle`) ret çözmüyor
  ama gösterim temizliği olarak madde 31 B ailesinde değerlendirilebilir.
- **Yeniden açma koşulu:** dense bayrağı açılırsa veya madde 24'ün bağıl eşiği
  tam benchmark'ta ölçülürse #82 / #56 bu nota göre yeniden kontrol edilir.

## Madde 35 — `run_tests.py` kapanışta aralıklı 0xC0000005 ile çıkıyor

Madde 32 Adım 2'de görüldü: N=0 koşusunda `evaluation/run_tests.py` 44 sorunun
hepsini `sonuclari.csv`'ye yazdıktan, özet satırlarını bastıktan **sonra**
`3221225477` (0xC0000005, access violation) çıkış koduyla döndü. Aynı gün N=1,
N=3 ve N=5 koşuları (aynı script, aynı makine) 0 ile çıktı: **4 koşuda 1**.
Sonuç dosyası tam ve doğruydu; veri kaybı yok.

Kök neden bilinmiyor, araştırılmadı. Aday (doğrulanmamış): kapanışta native
kütüphane temizliği (torch/CUDA, reranker, matplotlib; log'da "Starting a
Matplotlib GUI outside of the main thread" uyarısı vardı).

İş-around: `experiments/madde32_adim2_dense_force_include/uretim.py` başarıyı
çıkış koduna göre değil, yazılan satır sayısına göre doğruluyor (`b469350`).
Çıkış koduna bakan başka bir otomasyon (CI, zincirlenmiş koşu) bu çökmeyle
tamamlanmış koşuyu hata sayar.

**Öncelik: düşük.** Tekrarlanırsa ya da çıkış koduna bakan bir otomasyon
eklenirse ele alınır.

## Madde 36 — `classify_answer`'ın TP'si doğruluk değil

Madde 33 Adım 1'de görüldü: #91 G4 cevabı ("Unutulmuş Parşömen …") yanlış ama
`classify_answer` TP diyor. Fonksiyon tasarım gereği yalnız **ret mi, cevap mı**
ayrımı yapıyor (`check_is_not_found` + GT polaritesi). Ama madde 32/33
raporlarında "TP→TP, yan etki yok" ifadesi kalite iddiası gibi okunuyor.

**Ölçüm (2026-10-29):** [experiments/madde36_classify_dogruluk/](../experiments/madde36_classify_dogruluk/README.md).
Madde 32 Adım 2 + madde 33 Adım 1 cevapları: 73 tekil çift, 45 soru. Doğruluk
elle değerlendirildi (soru + GT referansı; tek değerlendirici, ikinci göz yok).
Bu cevapların çoğu daha önce elle incelenmemişti; yalnız sınıfı değişenlere
bakılmıştı.
- **Ret tespiti güvenilir:** FN 5/5 ve TN 17/17 gerçek ret; FP 4'ün 3'ü gerçek
  uydurma, 1'i #222 yarım cümle (bilinen, madde 25/26).
- **TP'lerin %32'si yanlış:** 47 TP → doğru 16, kısmen 16, **yanlış 15**.
- **Madde 32 Adım 2'ye etkisi:** N=1'de TP→TP kalanlarda doğruluk değişimi 0;
  **N=1 önerisi geçerli**. N=3'te #87 K→Y; N=5'te #30 ve #87 K→Y (6 iyileşme
  yanında). "Pozitiflerde yan etki yok" ifadesi N=3/5 için yalnız sınıfta doğru.

**Ciddiyet: ciddi (yorumlama açısından).** Fonksiyonun kendisi bozuk değil; ret
dedektörü olarak doğru çalışıyor. Sorun, bağlam değişikliği ölçümlerinde tek
kalite sinyali olarak kullanılması. **Düzeltme planı ayrı onay bekliyor.**
Adaylar (karar aşağıda):
- (a) Raporlarda TP'yi "cevap verdi" diye adlandırmak, doğruluk iddiasını ayrı
  bir sinyale bağlamak.
- (b) Bağlamı değişen sorularda doğruluk kontrolü: GT `anahtar_kelimeler`
  eşleşmesi ya da judge'ın correctness skoru, sınıf geçişinin yanında.
- (c) `classify_answer`'a dokunmamak: geçmiş koşularla karşılaştırılabilirlik
  ve madde 21 / 25 ölçümleri ona bağlı.

**Geçici kural (plan onaylanana kadar):** bağlam değiştiren her ölçümde
(madde 33 Adım 2 dahil), sınıfı değişmeyen ama bağlamı değişen sorular da
doğruluk açısından elle (ya da GT anahtar kelimesiyle) kontrol edilir.

**Karar (2026-10-29) — (b) + (a), (c) sonucu:**
- **(b) ana çözüm, kural oldu:** bağlamı değiştiren her ölçümde (retrieval,
  chunking, prompt), bağlamı değişen soruların hepsinde sınıf geçişinin
  YANINDA ayrı bir doğruluk kontrolü yapılır: GT `anahtar_kelimeler`
  eşleşmesi ya da judge correctness skoru, gerekirse elle. Yukarıdaki geçici
  kural bununla kalıcı oldu. "Yan etki yok" yalnız sınıf VE doğruluk birlikte
  değişmediyse yazılır.
- **(a) adlandırma:** raporlarda pozitif sorudaki TP "**cevap verdi**", FN
  "**ret**" diye yazılır; "TP" kısaltması doğruluk çağrıştırdığı yerde
  kullanılmaz. `classify_answer`'ın çıktı değerleri (TP/TN/FP/FN) aynı kalır.
- **(c) `classify_answer`'ın koduna dokunulmaz.** İç mantığını doğruluk ölçecek
  biçimde değiştirmek geçmiş tüm ölçümlerin (madde 21, 25, 32, v2–v8)
  karşılaştırılabilirliğini bozar; seçenek olarak düşünülmüyor.
- Geçmiş kapanmış maddelerin toplu yeniden denetimi yapılmaz (orantısız).
  Yalnız etkilendiği kesin iddialar düzeltilir: madde 32 Adım 2'nin N=3/5 "yan
  etki yok" notu düzeltildi.

## Madde 37 — Yorum isteyen soruda ret kırılgan (test_4 #100)

"Günlükteki koparılmış yirmi sayfa ile arka kapaktaki kroki/koordinat arasındaki
anlatısal boşluk, okuyucuda nasıl bir belirsizlik ve merak etkisi yaratacak şekilde
kurgulanmıştır?" — madde 34 Adım 2'de dikkat dağıtıcı adayı olarak test edildi
([experiments/madde34_ingilizce_ret/](../experiments/madde34_ingilizce_ret/README.md),
`sonuc_dogrulama.txt`). Cevap chunk'ı (4358, test2.txt paragraf 5-10) N=0 bağlamında
1. sırada (rerank 0.563); model reddediyor.
- 4355 (test1.txt) çıkarılınca ya da yerine başka chunk konunca TP; 4353 çıkarılınca
  FN; **ikisi birlikte çıkarılınca (bağlamda yalnız test2.txt) yine FN.**
- Ret, konu dışı chunk'ın varlığıyla monoton değil → madde 34'ün "dikkat dağıtıcı"
  deseni olarak doğrulanmadı.
- **Şüphe (ölçülmedi):** soru yorum/çıkarım istiyor ("nasıl bir etki yaratacak
  şekilde kurgulanmıştır"); model bağlamda doğrudan ifade aramakta ve sınırda
  kalıyor. Aday kontroller: aynı bağlamla soru yeniden ifade edildiğinde, prompt'un
  çıkarım talimatıyla.
- TP cevaplar kısmen doğru (X[4355]'te test1.txt'ten karışma var).

## Madde 38 — Ret kalksa da içerik hatalı (genel başlık; test_2 #56, test_3 #82)

**Desen:** bir müdahale reti kaldırıyor (sınıf FN → TP), ama gelen cevap GT'yi
karşılamıyor. **İçerik doğruluğu, ret/kabul ayrımından ayrı bir sorun**;
`classify_answer` bu cevapları TP sayıyor (madde 36). Reti kaldıran bir müdahale bu
yüzden tek başına "kazanç" sayılmamalı, içerik ayrıca kontrol edilmeli.

**Örnek 1 — test_2 #56** ("schemaVersion 1.1 olarak belirtilmiş olması … ne tür bir
çıkarım yapılmasına imkan tanır?"): madde 34 Adım 2'de dikkat dağıtıcı deseni
**doğrulandı** (konu dışı profiller çıkarılınca ya da başka profillerle
değiştirilince ret kalkıyor). Ama gelen cevap **yanlış**: genel geçer ("daha yeni
özellikler eklenmesi … hangi alanlarda değişiklik yapılacağı belirtilmemiş"); GT somut
alanlar istiyor (yeni sektör/meslek, `publicContact`, hafta sonu kuralları, yeni
`profileType`).
- Ölçülmedi: GT'deki alanlar `$.metadata` chunk'ında var mı (yoksa GT bağlamdan
  fazlasını mı bekliyor), yoksa model çıkarımı mı yapamıyor.

**Örnek 2 — test_3 #82** (madde 34 Adım 3, `sonuc_on_test.txt`): bağıl rerank eşiği
0.25 ile bağlam [4185, 4187]; ret kalkıyor, türetmenin adı doğru ("Sinüzoidal Genlik
Modülasyonu"), ama eklenen **formül yanlış**: `Y(ω) = F(ω+ω0) * F(ω−ω0)`; doğrusu
`Y(ω) = ½F(ω+ω0) + ½F(ω−ω0)` (GT: `(1/2π) F(ω) ∗ (πδ(ω+ω0) + πδ(ω−ω0))`). Cevap
chunk'ındaki formül satırları PUA sembolleri ve parçalı düzen yüzünden bozuk (madde
34 Adım 1); hatanın bundan mı geldiği ölçülmedi (A1/A2 varyantları retti, içeriği
test edilmedi).

**Örnek 3 — test_2 #42, yalnız D5 yolunda** (madde 14 Durum; `d5_gercek.py`; triyaj
2026-11-04: [experiments/madde38_42_triyaj/](../experiments/madde38_42_triyaj/)).
Sandbox'ın kod üretimi bozulup (servis sağlam) akış semantik RAG'e düşünce cevap sınıfta TP
ama metinde uydurma/yabancı sözcükler var: "…her iki profesyonelin de iptal **notuwresi
same** (24 saat) … Minimum **Notuwresi**: 6 saat / İptal **Notuwresi**: 24 saat". Sayılar
sandbox kontrolüyle (6/4/24/24) tutarlı.
- **Düzeltme:** ilk kayıttaki "yarıda kesik" ifadesi **yanlıştı**; kesiklik betiğimin 300
  karakterlik yazdırma sınırının eseriydi. Cevap 709 karakter, tam bir cümleyle bitiyor.
- **Normal yolda çıkmıyor:** enjeksiyonsuz (sandbox çözüyor) 2/2 temiz, madde 39 ve madde 30 tam
  koşularındaki kayıtlarla aynı; cevapta "notuwresi/same" yok (yalnız küçük biçimbilim
  kaymaları: "uyarı saatları / saatlarına").
- **D5 yolunda tekrar üretiliyor:** 4/4 (iki ayrı koşu × 2 tekrar), bayt bayt aynı. D5 enjeksiyonu
  yalnız TETİKLEYİCİ; semantik fallback yolu gerçek ve sandbox çözemediğinde üretimde de
  kullanılır. Yani "yalnız stres koşulunun yan etkisi" denemez ama yol nadir (benchmark'ta
  pozitif D5 yok).
- **Bozulma modelin kendi çıktısında:** ham model çıktısı (712 karakter) bozuk sözcükleri zaten
  içeriyor; son işleme yalnız boşluk/satır sonu düzenliyor. Token tavanına (`MAX_ANSWER_TOKENS`
  = 600) dayanma yok (~100 kelime, doğal bitiş), yabancı-yazı temizliği tetiklenmedi, bağlamda
  bu sözcükler **yok** (bağlam İngilizce alan adlı ham profil JSON'ları: `minimumNoticeHours`
  vb.). Yani retrieval bloğu ve token sınırı suçlu değil; 7B modelin İngilizce alan adlarını
  Türkçeleştirirken uydurduğu sözcükler.

**Kapanış (2026-11-04): #42 / Örnek 3 kendi başına, doğru kök nedenle kapatıldı.** Kök neden
kesiklik değil: 7B sentezleyici, ham İngilizce alan adlı JSON bağlamından Türkçe üretirken
sözcük uyduruyor (confabülasyon). Normal yolda görülmüyor; D5 fallback'inde 4/4 tekrar
üretiliyor. Bu, **madde 41'den ayrı bir hata sınıfı** (madde 41 sayısal toplulaştırma
hatası; burada sayılar doğru, bozuk olan metin sentezi) ve ona bağlanmadı.
- **Ertelendi (sentezleyici confabülasyonu):** Sentezleyici, ham İngilizce alan adlı JSON
  bağlamından Türkçe üretirken kelime uydurabilir (confabülasyon). Normal semantik RAG yolunda
  da (D5 dışında) olup olmadığı ölçülmedi. Öncelik verilmedi, ayrı değerlendirilecek.

**Ölçülmedi:** desenin kapsamı (reti kaldıran diğer müdahalelerde içerik ne kadar
sık hatalı) ve ortak neden (bağlam eksikliği / bozuk metin / model çıkarımı).

## Madde 39 — Güncel sistemle tam benchmark + negatif set koşusu yok

**Boşluk:** retrieval ve DB, son tam koşudan sonra değişti, ama tam pozitif + negatif
set hepsinden sonra yeniden koşulmadı. Madde 34 Adım 2 ve madde 24 ön-testi aynı
sınıra takıldı: FN evreni ve taban oranı eski/karma kayıtlardan çıkarıldı; #103'ün
FP'sinin artık tekrar etmediği ancak tek soru koşulunca görüldü.
- **Son tam pozitif koşu:** v8 (tüm setlerin kayıtlı son tam skoru). Sonraki pozitif
  koşular kısmi: madde 21 (5 soru), madde 22 Adım 3 (etki alanı), madde 32 Adım 2 (44),
  madde 33 (bağlamı değişenler). "Güncel sistemde" diye anılan madde 21 koşusu tam
  değildir.
- **Son tam negatif koşu:** madde 33 duman testi (`test_negative`, FP 2/32: #224,
  #232); `test_5` o koşuda yalnız kısmi.
- **v8'den sonraki değişiklikler:** madde 20 (`top_k`), 22 ve 33 (yeniden ingest),
  29 (embedding cihazı). Madde 32'nin bayrağı varsayılan kapalı; açılırsa ayrıca
  sayılır.

**Yapılacak (aktif hedef):** güncel sistemle test_1–5 + `test_negative` tam koşu,
madde 36 kuralıyla, sonuçlar yeni referans olarak kaydedilir. Bu koşu olmadan yapılan
kapsam kontrolü ve taban oranı, kayıtların hangi sisteme ait olduğunu belirtmelidir.

**Süre ölçümü (2026-10-30, [experiments/madde39_tam_kosu/test_5/](../experiments/madde39_tam_kosu/test_5/)):**
test_5 15 soru 693 sn (11.6 dk, soru başına ~46 sn). 147 soruya oran ~1.9 saat; v8'in
set süreleri (toplam ~1 saat) bugünkü hızla (~1.4 kat) ~1.5 saat veriyor. **#102 HATA**
(Ollama embedding runner çöktü; v8'de TN), yeniden koşulmalı; bu set henüz tam değil.
- **#101 hâlâ FP** (v8 ile aynı; CNF dönüşümü uyduruyor), #103'ün aksine düzelmemiş.
  #103 TN (ön-testle tutarlı), #107 FP (v8 ile aynı). Kesin hüküm tam koşudan.

**Bulgu (2026-10-30, pilotla düzeltildi) — CPU'ya düşme VRAM kaynaklı.**
- **VRAM (baskın):** LLM yüklüyken boş VRAM 62–318 MiB, Ollama'nın istediği en az 457 MiB;
  bu yüzden model 0/25 ile CPU'da. Pilot `pilot_a/` (başta 7.1 GB boş RAM, koşu boyunca
  2.4–3.8 GB boş) ve `pilot_a_1/` (6.07 GB): ikisinde de 10/10 soru CPU'da, HATA yok,
  `temiz: false`. İki CPU koşusu kendi içinde tutarlı (10/10 kaynak ve cevap aynı).
- **RAM (ayrı sınır):** ilk `test_negative` denemesi (`test_negative_ilk_deneme/`, geçersiz)
  boş RAM ~750 MB iken yükleme hatasıyla durdu.
- **Düzeltme:** önceki not ("kayma RAM baskısına bağlı, RAM yetince LLM'den bağımsız aynı")
  yanlış ya da eksikti. `kayma.py`'de LLM yüklüyken 25/25 ve bayt aynı çıkmıştı (o an VRAM
  7543/8188 MiB dolu); bugünkü koşularla farkı açıklanamadı. Ayrıca `kosu.py`'nin 7.5 GB RAM
  eşiği (tahmin) bu sorunu önlemiyor. `temiz` kontrolü doğru çalışıyor.
- **test_5 ölçümü doğrulanamıyor** (Ollama logu yok); #101/#103/#107 kesin değil.

**Ön-ölçüm A sonucu (2026-11-01) — fark küçük, C kararı verildi.**
[experiments/madde39_tam_kosu/](../experiments/madde39_tam_kosu/README.md): LLM yok,
147 soru iki süreçte (`RAG_EMBED_NUM_GPU=99` / `=0`) `retrieve()` ile karşılaştırıldı.
- **%95.2 (140/147) nihai bağlam birebir aynı.** 7 farklılığın 6'sı yalnız en düşük
  güvenli (son) chunk'ta, rerank skorları ≤0.01 farkla ("net kazanan yok" bölgesi);
  biri bilinen vaka (test_5#107, FP). Yalnız **test_2#35**'te 1. chunk da değişiyor —
  madde 33'ün işaretlediği BM25 korpus kaymasına duyarlı, zaten cevabı değişmeyen bir
  soru. Madde 29'un "düzeltildi" bulgusu 147 sorunun tamamında doğrulandı.
- **Karar: C** (bugünkü üretim yolu, LLM önce yüklenir; `kosu.py`'nin `temiz` kontrolü
  CPU'ya düşmeyi işaretler ama koşuyu **durdurmaz**). B (GPU'yu zorlayan iki aşamalı
  koşu) gereksiz: fark küçük ve üretim de aynı riski taşıyıyor (madde 40), yapay bir
  GPU-referans üretimden farklı bir sistem ölçerdi.

**Kapanış (2026-11-01) — tam koşu tamamlandı, yeni referans kaydedildi.**
Tüm setler (test_1–5 + test_negative, 147 soru) C kararıyla, sıralı, `kosu.py` ile
koşuldu. Ham sonuçlar ve ortam kanıtı: `experiments/madde39_tam_kosu/{SET}/`
(`sonuclari.csv`, `ortam.json`, `hata_tekrar.csv`); birleşik sınıflandırma
`tum_sonuclar.json`.

| Set | n | Sınıf | Not |
|---|---|---|---|
| test_1 | 30 | 30 TP | #2 ilk denemede HATA, tekrarda düzeldi |
| test_2 | 30 | 26 TP, 2 FN, **2 HATA (kalıcı)** | #43/#53 bilinen kronik GPU hatası (EXPERIMENTS.md), tekrar da düzeltmedi — **98 soruluk temiz set kuralıyla hariç** |
| test_3 | 30 | 27 TP, 3 FN | #62 ilk denemede HATA, tekrarda düzeldi |
| test_4 | 10 | 9 TP, 1 FN | #92/#94 ilk denemede HATA, tekrarda düzeldi |
| test_5 | 15 | 13 TN, 2 FP | #102/#110 ilk denemede HATA, tekrarda düzeldi |
| test_negative | 32 | 29 TN, 1 FN, 2 FP | — |
| **GENEL** | **145** (147 − 2 kronik HATA) | **92 TP, 42 TN, 7 FN, 4 FP** | |

- **Negatif set: sıfır regresyon.** FP = {#224, #232} — madde 33 prod duman kaydıyla
  (son tam negatif koşu) **birebir aynı** (32/32 cevap karşılaştırıldı, 0 fark). #214
  FN, bilinen GT düzeltmesi (pozitife alındı).
- **v8 (son tam pozitif koşu) ile farklar — 6 soru, hepsi açıklandı:**
  - #91 (FN→TP): madde 33'ün prod düzeltmesi (`.txt` birleştirme) — beklenen.
  - #103 (FP→TN): madde 24'ün bugün bulduğu düzelme — beklenen, ikinci kez doğrulandı.
  - #50 (FN→TP, sınıf): içerik hâlâ **yanlış** (GT: 248 profil Cumartesi açık; cevap
    "hafta sonu çalışan yok" diyor) — madde 21/36'nın bilinen "ifadeye bağlı sınıf"
    sorunu, yeni değil; TP ≠ doğru.
  - **#48, #90 (TP→FN) — açıklanamadı, ama gerçek ve kararlı.** Ön-ölçüm A ikisinde de
    bağlamı **değiştirmiyor** (test_3'te 0 fark, #48 test_2'nin 3 farklılığında yok).
    `tekrar_kontrol.py`: aynı bağlamla 3 tekrar, ikisi de **3/3 FN** — rastgele değil.
    v8 bu karşılaştırma için zaten güvenilir bir taban değil (bu maddenin kendi
    uyarısı: madde 20 top_k, 22/33 yeniden ingest v8'den SONRA); en olası açıklama
    v8'in bağlamının bugünkünden farklı olması (ör. top_k düzeltmesi öncesi). Kök
    neden araştırılmadı — ayrı bir madde açılmadı, bu nottan takip edilebilir.
- **`temiz: false` beklendiği gibi hemen her sette** (CPU'ya düşme, madde 29/40); hiçbir
  CPU etkisi Ön-ölçüm A'nın öngördüğü küçük/zararsız kümenin dışına çıkmadı.

**Operasyonel bulgular (kosu.py'ye işlendi, retrieval/eval koduna dokunulmadı):**
1. `foundry model unload` servisin taban belleğini (~4.9 GB) bırakmıyor; yalnız
   `foundry service stop` bırakıyor (boş RAM ~2 GB → ~7.9 GB). `kosu.py` artık set
   başına tam `stop` + gerekirse `start` yapıyor.
2. **`foundry service stop/start`'ı `capture_output=True` ile çağırmak Windows'ta
   süresiz kilitleniyor** (muhtemelen arka planda kalan bir ajan stdout/stderr
   tutamacını miras alıp pipe'ı açık tutuyor) — `subprocess.run`'ın kendi `timeout`
   parametresi bile işlemiyor; iki kez ~7 dk "takılı" göründü. Düzeltme: bu iki komut
   `stdout=DEVNULL, stderr=DEVNULL` ile (pipe yok) çağrılıyor.
3. Ollama embed isteğine **hiç yanıt vermeden** asılı kalabiliyor (CPU'ya düşmekten
   farklı, daha ciddi — tam hang); `ollama app.exe` ile yeniden başlatmak düzeltiyor.
   `kosu.py` artık her set öncesi `curl` tabanlı bir sağlık kontrolü yapıyor, gerekirse
   otomatik yeniden başlatıyor (ilk denemede `urllib` ile yazılan sağlık kontrolü de
   benzer şekilde timeout'a uymadan kilitlendi — `curl` alt sürecine çevrildi).
4. RAM eşiği 2 GB → 4 GB (1 numaralı düzeltme sonrası `service stop` daha fazla RAM
   geri verdiği için daha güvenli bir pay mümkün).
5. `kosu.py` yalnız `sonuclari.csv` yoksa koşuyor; test_5 klasöründe 2026-10-30'dan
   kalma eski bir sonuç dosyası vardı, ilk "tam koşu" denemesi bunu sessizce
   yeniden kullandı (koşmadı). Silinip yeniden koşuldu; script bu konuda
   uyarmıyor — ileride aynı tuzağa düşülmemeli.

**Kapanış kararı:** madde 39 kapandı. Yeni referans yukarıdaki tablo; #48/#90'ın
açıklanamayan kısmı ayrı bir maddeye çıkarılmadı (küçük, v8-karşılaştırma zaten
güvenilmez taban uyarısı altında), gerekirse ileride buradan takip edilir.

## Madde 41 — Toplulaştırma sorularında sandbox+fallback güvenilmezliği — sessizce yanlış sayı
Madde 14 Durum bölümünün D5 gözleminden doğdu
([experiments/madde14_bulunamadi/](../experiments/madde14_bulunamadi/), `d5_gercek.py`,
`d5_gercek_ek.jsonl`). **Önceliklendirme kullanıcıya bırakıldı; "düşük öncelikli"
etiketi bilerek konmadı.**

**Neden ayrı bir risk sınıfı.** Madde 14 mesaj netliğiyle ilgilidir (kullanıcı yanlış
cümle okur). Burada kullanıcı **hiç uyarı almadan, güvenle yanlış bir sayı** okuyor:
D4/D3/D2'deki gibi ret cümlesi yok, `[KESİN HESAPLAMA SONUCU]` da yok — semantik
fallback sıradan bir cevap gibi sunuyor. Judge ve `classify_answer` bu sınıfı
yakalamaz (madde 13, madde 36).

**Düzenek.** Sandbox'ın kod üreten çağrısı hata veren kod döndürecek şekilde yamalandı
(3 deneme `KeyError: 'olmayan_sutun'`, servis sağlam, `service_failure` False); router,
semantik fallback, reranker ve synthesizer gerçek. Soru tüm 728 kaydın hesabını ister
(tek kayıt/özet bloktan okunamaz). Kontrol: aynı soru yamasız (sandbox doğru cevaplar).
Gerçek değerler `data/728_profiles.json`'dan pandas ile hesaplandı. Her biri 2 tekrar,
tekrarlar aynı.

| Soru | Gerçek değer | Yamasız (sandbox) | D5 (fallback) |
|---|---|---|---|
| Ortalama deneyim yılı (`experience.years`) | **11.9986** | 11.9986 | uydurma hesap: "…toplam deneyim yıl sayısı 19 + 13 + 12 = 44'tür … 44/364…" |
| Kaç profil `business` türünde? | **129** | 129 | "Bu bilgi dokümanlarda bulunamadı." (bilgi VAR; tekrar ipucu da yok) |
| Ortalama `minimumNoticeHours` | **9.75** | 9.75 | **"24"** (güvenle yanlış) |

Karşıt gözlem (adil olmak için): tek kayıt/özet bloktan cevaplanabilen benchmark
sorularında (#32, #35, #39, #42) fallback doğru cevabı buldu (4/4 TP). Zarar
**toplulaştırma** sorularında; fallback hesap yapamayan bir yöntemle birkaç kayıttan
"hesaplıyor".

**Mekanizma (gözlenen, tam ölçülmedi).** `code_interpreter_with_retry` 3 denemede
çözemeyince `success: False` döner; `data_engine` yalnız `service_failure` için özel
blok üretir, aksi halde `None` → `retrieve` semantik aramaya düşer
(`tests/test_refusal_messages.py::test_d5_kod_cozulemedi_none_doner_semantik_rag_e_duser`).
Bu yolda hiçbir etiket/talimat yok.

**Çözüm adayı (UYGULANMADI).** Toplulaştırma sorusunda sandbox çözemezse semantik
fallback yerine D4 benzeri "hesaplanamadı" döndürmek (davranış değişikliği; mesaj
değil). Açık alt sorular: "toplulaştırma sorusu"nu neyin tanıdığı (router sinyali mi,
sandbox rotasında olmak mı), yeni mesajın ret skorlayıcısıyla uyumu (madde 14 yorumları).

**Blokaj şartları — bunlar sağlanmadan uygulanmaz.**
1. Tam negatif set (32) + test_2 ölçümü. Özellikle negatif sette kodu çözemeyip semantik
   fallback ile **doğru TN** olan #215, #216, #226'yı bozma riski: bu üç soru D5 yolunu
   zaten kullanıyor (madde 18 Adım 3 / madde 14 Durum).
2. Pozitif sette sandbox'ı zor/belirsiz soru nedeniyle 3 denemede çözemeyen ve fallback
   ile doğru cevaplanan vaka olup olmadığı. 147 soruluk benchmark'ta pozitif D5 yok
   (madde 30 tam koşusu), yani bu risk ölçüm tarafında görünmez (madde 13).
3. Tek soruya göre ayar yapılmaz (madde 30 disiplini).

**Sınırlar.** Hata enjeksiyonu sentetik; gerçek D5 hataları (modelin kodu 3 kez
bozması) belirsiz/zor sorulara kayıyor olabilir. Toplulaştırma sorusu 3 adet ve
benchmark dışı (GT pandas'tan). Doğal sıklık bilinmiyor.


### Kapanış (2026-11-04) — önerilen davranış değişikliği araştırıldı ve ölçüldü; net kazanç vermediği için UYGULANMADI
**Bu madde "çözüldü" değildir.** Sorun (toplulaştırma sorusunda sandbox çözemeyince semantik
fallback'in sessizce yanlış sayı üretebilmesi) olduğu gibi duruyor; yalnız önerilen çözüm
(fallback yerine D4 benzeri "hesaplanamadı") ölçülüp reddedildi. Bu, madde 17'deki ölü kodun
aksine **canlı üretim yolu**; bu yüzden "net kazanç yoksa uygulama" eşiği daha sıkı uygulandı.

Ölçüm: `experiments/madde41_simulasyon/` — davranış bellekte monkeypatch ile simüle edildi
(`sim_run_tests.py`, src/ değişmedi), gerçek hat `test_negative` (32) ve `test_2` (30) üzerinde tam
koşturuldu; madde 39 taban ve madde 30 koşusuyla karşılaştırıldı (`karsilastir.py`,
`sonuc_karsilastir.txt`); zorla D5 vakaları `d5_zorla_sim.py` ile (`sonuc_vagg.txt`: V_agg kelime
ipucu hesabı). (İlk deneme sarmalayıcı yalnız üst düzey `data_engine` modülünü yamaladığı için
geçersizdi — `retrieval` `src.data_engine`'i kullanıyor; düzeltilip baştan koşuldu.)

Uygulanmama gerekçeleri:
- **Sıfır net sınıflandırma etkisi.** test_negative 29 TN / 1 FN / 2 FP → aynı; test_2 26 TP / 2 FN /
  2 HATA → aynı. test_2'de hiç D5 olayı yok; doğal D5 yalnız 3 negatifte (#215, #216, #226) ve üçü
  TN → TN. Kazanç yalnız zorla/enjekte edilmiş vakalarda görünüyor.
- **Doğal negatiflerde yanıltıcı mesaj.** Üç soru da veride gerçekten olmayan bilgiyi soruyor
  (`KeyError: 'population'`, `'creditScore'`, boş filtre); düz "…bulunamadı." yerine "…soru şu an
  işlenemedi, **tekrar denenebilir**" kullanıcıya yeniden denemenin işe yarayacağını söylüyor —
  yanlış. Skorlayıcı farkı görmez, kullanıcı görür.
- **Zorlanmış D5'te 4 doğru cevap kaybı.** #32, #35, #39, #42 bugün fallback'le doğru cevaplanıyor
  (TP) → ret (FN). Kazanç: A1 uydurma hesap ve A3 "24" (gerçek 9.75) önlenir, A2 "bulunamadı"
  (gerçek 129) "tekrar denenebilir"e döner: **4 doğru cevap kaybına karşı 2 yanlış sayı önleme +
  1 kısmi iyileşme**, net pozitif değil.
- **V_agg (kelime ipucu) yetmiyor.** "ortalama/toplam/kaç/sayısı/en yüksek/oran…" ipucu #35/#39/#42'yi
  korur ama #32'yi ("toplam kaç profil") yine kaybeder ve üç doğal negatifin üçünde de tetiklenir;
  üstelik sezgisel ve kapsayıcı değil.
- **Güvenilir hata-tipi ayırıcısı yok.** "Sütun yok (`KeyError`) = veri yok" fikri 3 örnekte tutarsız:
  #215 `KeyError`, #216 son hata `ValueError` (`result` atanmadı; ilk denemelerde `KeyError`),
  #226 `IndexError`.

Sınırlar: zorla D5 sentetik ve 7 soru; doğal D5 yalnız 3 negatif; D5 dışı sorularda koşular arası
metin farkı var (negatifte 29'un 26'sı, test_2'de 30'un 16'sı birebir aynı), sınıf sayıları sabit.
Madde açık kalır (sessizce yanlış sayı riski duruyor); yeni bir çözüm adayı çıkarsa aynı eşikle
ölçülmeli.

- **Ertelendi (nötr ret cümlesi):** D5 bloğunda "tekrar denenebilir" ifadesini kaldırıp nötr bir
  cümle (ne yeniden deneme vaadi ne kesin yokluk iddiası) kullanma fikri ölçülmedi, gelecekte ayrıca
  değerlendirilebilir, öncelik verilmedi.


### Not (2026-11-04): normal yolda iki adımlı confabülasyon zinciri — `result_to_natural_language` → `ask()` (test_2 #53)
Madde 11 C ölçümü sırasında bulundu; **madde 38'in confabülasyon bulgusuyla ve bu maddenin
"benchmark'ta TP görünüp gerçekte yanlış sayı" riskiyle aynı sınıf**, ama farklı yol: burada
sandbox **doğru** hesaplıyor (D5/fallback değil). **Öncelik verilmedi, izleniyor.**

**Örnek (test_2 #53, sandbox çıktısı gerçek veriyle birebir doğru):**

| Kişi | min saat (gerçek) | iptal saati (gerçek) | Son cevap |
|---|---|---|---|
| Sinem Arslan | 12 | **12** | min 12 ✅, iptal **4** ❌ |
| Umut Aslan | **4** | 24 | min **6** ❌, iptal 24 ✅ |
| Emre Korkmaz | 6 | 24 | 6 ✅ / 24 ✅ |

**Zincir (bağlam ve ara çıktılar kaydedilerek ölçüldü):**
1. `result_to_natural_language` doğru dict'i alıyor ve onu bulanık bir cümleye indiriyor:
   *"Emre Korkmaz ve Umut Aslan'ın iptal bildirme saatleri 24 saat, minimum uyarı saatleri ise
   Emre Korkmaz 6 saat, Sinem Arslan ve Umut Aslan 12-4 saat arasındadır."*
2. `ask()` bağlamında yalnızca bu cümle var (394 krk, ham sayı yok). Bulanıklıktan **spesifik ama
   yanlış** sayılar üretiyor (Sinem iptal=4, Umut min=6).

**Düzeltme prompt'u kırpmasından (madde 11 C) bağımsız — kanıtlandı.** Kod üretimi tamamen
atlanıp doğru sandbox çıktısı doğrudan verildiğinde (`stub` varyantı, C devre dışı, 2 koşu) birebir
aynı yanlış cevap çıkıyor; C'li koşu da (tavan 10.500) aynı. Kırpılan düzeltme prompt'u yalnız
kod+hata geçmişi taşır, kişi değerleri taşımaz, dolayısıyla değerleri karıştıramaz. Tavan 11.500
koşusu farklı bir kod/çıktı ürettiği için (n=1) bu soruyu ayırmakta kullanılmadı.

**Benchmark etkisi:** `classify_answer` bu cevabı TP sayıyor (madde 36), judge de yakalamaz
(madde 13). README'de bu soru **"yanıt veriyor, içerik hatası bilinen"** üçüncü kategorisine
konuldu (temiz sete eklenmedi, HATA da sayılmadı).

**Çözüm adayı (UYGULANMADI, öncelik yok):** sentezleyiciye sandbox'ın ham sonucunu da vermek ya da
`result_to_natural_language` çıktısında girdideki sayıların korunduğunu denetlemek. Ölçülmedi.
Ölçüm betikleri `experiments/` altına taşınmadı (scratchpad'de kaldı).
