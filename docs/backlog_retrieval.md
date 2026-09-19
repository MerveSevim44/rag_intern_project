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
| 6 | Türkçe stemmer (TERM_SYNONYMS'ın yerine) | Açık — sıradaki |
| 7 | Cevap sentezinde özne karışıklığı (test_5#115) | Açık |
| 8 | Kolon adı takma ad bağımlılığı (meta-boost kapısı) | Açık |
| 9 | RRF sıra tabanlı olduğu için BM25'teki güçlü skor marjını düzleştiriyor | Açık — teorik, somut regresyon örneği bekliyor |

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
