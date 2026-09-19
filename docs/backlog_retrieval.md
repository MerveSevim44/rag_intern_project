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
