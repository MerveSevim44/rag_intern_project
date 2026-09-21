# Madde 14 — "Bulunamadı" üç farklı durumu birleştiriyor: durum tespiti

İlgili: [backlog_retrieval.md](backlog_retrieval.md) madde 14. Bu doküman
yalnızca tespit ve plandır; kod değişikliği İÇERMEZ.

## 1. Üç durum ve şu anki ayırt edilme biçimi

Sandbox yolunda üç ayrı durum **kod seviyesinde zaten ayrılmış** durumda; ayrım
synthesizer'a kadar taşınıyor ve orada **kayboluyor**.

| # | Durum | data_engine gövdesi | retrieval etiketi | Talimat | Kullanıcının gördüğü |
|---|---|---|---|---|---|
| 1 | Bilgi gerçekten yok | — | — | — | (semantik RAG'e düşer) |
| 2 | Filtre 0 satır döndürdü | `NO_MATCH_SUMMARY` | `[KAYIT BULUNAMADI]` | `EMPTY_RESULT_INSTRUCTION` | "Bu bilgi dokümanlarda bulunamadı." |
| 3a | Doğrulayıcı itiraz etti, düzeltme tutmadı | `UNVERIFIED_RESULT_SUMMARY` | `[DOĞRULANAMAYAN SONUÇ]` | `UNVERIFIED_RESULT_INSTRUCTION` | "Bu bilgi dokümanlarda bulunamadı." |
| 3b | **LLM servisi çöktü** (madde 11) | — (`success: False`) | — | — | "Bu bilgi dokümanlarda bulunamadı." |

Kod akışı:
- `data_engine.py:658-661` — üç dallı seçim (`empty_result` / `unverified` / normal).
- `retrieval.py:570-585` — etiket ve talimat aynı üç dala göre seçiliyor.
- **`EMPTY_RESULT_INSTRUCTION` ve `UNVERIFIED_RESULT_INSTRUCTION`'ın ikisi de
  modelden AYNI cümleyi istiyor:** *"Yanıtın YALNIZCA şu cümle olsun: 'Bu bilgi
  dokümanlarda bulunamadı.'"* Ayrım tam burada çöküyor.

**3b hiç ayrılmamış.** LLM çöktüğünde `code_interpreter` `success: False`
dönüyor, `data_engine` sandbox dalını atlıyor, `query_tabular_data` `None`
dönüyor ve akış semantik RAG'e düşüyor. Oradan gelen chunk soruyu
cevaplamadığı için synthesizer 1. durumun cümlesini kuruyor. Yani **teknik bir
başarısızlık, "bilgi yok" olarak raporlanıyor** ve bunu ayırt edecek hiçbir
bayrak taşınmıyor.

Ölçülen örnek (D sonrası): test_2 #43 ve #53 → "Bu bilgi dokümanlarda
bulunamadı." Oysa sorulan alanlar (`experience.credentialSummary`,
`occupation`) `728_profiles.json` içinde **mevcut**.

## 2. `check_is_not_found` — ÖLÇÜLMÜŞ sınır (kayıtlı varsayım YANLIŞTI)

Backlog madde 14'e "ret cümlesinden sonra 3+ içerik kelimesi kalırsa cevap
'iddia' sayılır" diye yazmıştım. **Ölçüm bunu çürüttü.** O kural yalnızca
LEGACY yolda geçerli.

`benchmark_eval.py:692` skorlayıcıyı şöyle çağırıyor:

```python
pred_is_not_found = check_is_not_found(prediction, question)
```

`question` verildiği için kelime sayısı dalı HİÇ çalışmıyor. Gerçek kural iki
koşullu:

1. Cevap `_REFUSAL_MARKERS`'tan en az birini içermeli:
   `bulunamadi`, `bilgi dokumanlarda`, `dokumanlarda bulunamadi`,
   `bulunmamaktadir`, `bulunmuyor`, `belirtilmemistir`, `gecmemektedir`,
   `mevcut degildir`, `yer almamaktadir`, `yer almiyor`.
2. Ret dışında kalan içerikte **yeni iddia** olmamalı — yani soruda geçmeyen
   bir sayı, alfanümerik kod veya özel isim bulunmamalı (`_new_claims`).

Kelime sayısı bir kısıt DEĞİL. Ölçüm (soru: test_2 #43):

| Aday cümle | RET? | Yeni iddia | Kalan kelime |
|---|---|---|---|
| "Bu bilgi dokümanlarda bulunamadı." | ✅ | — | 0 |
| "Bu soru şu an işlenemedi, lütfen tekrar deneyin." | ❌ | — | 7 |
| "Bu bilgi dokümanlarda bulunamadı. Sistem bu soruyu şu an işleyemedi, tekrar denenebilir." | ✅ | — | **7** |
| "Bu soruyu şu anda işleyemedim; teknik bir sorun nedeniyle hesaplama tamamlanamadı, lütfen tekrar deneyin." | ❌ | — | 12 |
| "Bu bilgi dokümanlarda bulunamadı. Belirtilen filtreye uyan kayıt yok." | ✅ | — | 4 |
| "Bulunamadı ancak muhtemelen ortalama 45.12'dir." | ❌ | `['45','12']` | 5 |

**Sonuç: gerekçeli ret MÜMKÜN.** 7 ve 4 kelimelik açıklamalar TN olarak
skorlanıyor. Başarısızlığın sebebi uzunluk değil, **ret işaretinin yokluğu**
(2. ve 4. satır) veya **yeni sayı** (son satır).

Yani madde 14'ün önündeki gerçek kısıt şu: mesajı zenginleştirebiliriz, ama
cümle bir `_REFUSAL_MARKERS` ifadesi içermeye devam etmeli ve yeni sayı/kod/
özel isim eklememeli.

## 3. Önerilen ayrım ve ön tahminler

| Durum | Önerilen cümle | Marker var mı | Yeni iddia | Tahmin |
|---|---|---|---|---|
| 1. Bilgi yok | "Bu bilgi dokümanlarda bulunamadı." (değişmez) | ✅ `bulunamadi` | yok | TN geçer |
| 2. 0 satır | "Bu bilgi dokümanlarda bulunamadı; belirtilen koşullara uyan kayıt yok." | ✅ | yok | TN geçer (ölçüldü: benzeri geçti) |
| 3a. Doğrulanamadı | "Bu bilgi dokümanlarda bulunamadı; sonuç doğrulanamadığı için aktarılmadı." | ✅ | yok | TN geçer |
| 3b. İşlenemedi | "Bu bilgi dokümanlarda bulunamadı; soru şu an işlenemedi, tekrar denenebilir." | ✅ | yok | TN geçer |

Ortak kalıp: **ret işareti başta, ayrım noktalı virgülden sonra.** Bu, hem
skorlayıcıyı korur hem kullanıcıya doğru bilgiyi verir.

**Dürüstlük notu:** 3b'nin cümlesi hâlâ "dokümanlarda bulunamadı" diyor, ki
teknik olarak yanlış. Tam dürüst bir cümle ("bu soru işlenemedi") ret işareti
taşımadığı için FP olarak skorlanır ve test_5 TN'i düşer. Yani **ölçüm tanımı,
tam dürüst mesajı engelliyor.** İki seçenek var ve karar gerekiyor:
- **(i)** Kalıbı koru (yukarıdaki tablo) — skor korunur, mesaj kısmen yanıltıcı
  kalır ama "tekrar denenebilir" ipucu eklenir.
- **(ii)** `_REFUSAL_MARKERS`'a işlenemedi/`teknik` gibi bir işaret ekle —
  mesaj tam dürüst olur, ama **skorlayıcı değişmiş olur** ve eski koşularla
  kıyas bozulur. Bu, ölçüm aracını ölçülen şeye göre değiştirmek demektir;
  madde 13'ün uyarısıyla aynı sınıfta bir risk.

### KARAR: (i) — (ii) reddedildi
**(ii) neden reddedildi (ileride sorulursa):** `_REFUSAL_MARKERS`'ı genişletmek,
ölçüm aracını ölçtüğü şeye göre değiştirmek olur. Bunun bedeli tek bir mesajla
sınırlı değil: geçmişteki TÜM karşılaştırmalar (kaynak doğruluğu 99/100 → 100/100,
test_5 TN 12/15 → 13/15, FP 3/15 → 2/15) retrospektif olarak geçersiz ya da en
azından şüpheli hale gelir, çünkü yeni skorlayıcıyla eski koşular kıyaslanamaz.
Tek bir mesajın "tam dürüstlüğü" için bu bedel ödenmez. Madde 13'ün uyardığı
risk sınıfıyla aynı: ölçüm altyapısına dokunmak, ölçülen sonuçların anlamını
sessizce değiştirir.

**(i)'nin kendi riski, kayda geçsin:** "…bulunamadı; soru şu an işlenemedi,
tekrar denenebilir" cümlesi çelişkili okunabilir — önce "yok" diyor, sonra
"işlenemedi" diyor. Bu kabul edilmiş bir ödünç: tamamen yanlış bir cümleden
(bugünkü hâl) iyidir ve kullanıcıya en azından "tekrar dene" sinyalini verir.
Madde 14'ün açılışındaki çekinceyle tutarlı: mesaj tam dürüst değil ama kabul
edilebilir bir iyileşme.

## 4. Değişecek / eklenecek sabitler

**Değişecek (mevcut):**
- `retrieval.EMPTY_RESULT_INSTRUCTION` — istenen cümle 2. durumun metnine.
- `retrieval.UNVERIFIED_RESULT_INSTRUCTION` — istenen cümle 3a'nın metnine.

**Eklenecek (yeni):**
- `retrieval.SERVICE_FAILURE_INSTRUCTION` — 3b için.
- `data_engine.SERVICE_FAILURE_SUMMARY` — 3b'nin gövdesi.

**Ayrıca gereken taşıma (3b bugün hiç taşınmıyor):**
- `code_interpreter` zaten `success: False` + `error` döndürüyor; `data_engine`
  bunu şu an **atlıyor**. `service_failure: True` gibi bir bayrağın
  `query_tabular_data`'nın dönüşüne eklenmesi ve `retrieval`'da üçüncü bir
  dala bağlanması gerekiyor — yani 3b için akış değişikliği, 1/2/3a için
  yalnızca metin değişikliği.

**Dokunulmayacak:** `COMPUTED_RESULT_INSTRUCTION` (başarılı hesaplama yolu).

## 5. Ölçüm planı

Madde 13 kuralı: tam eval bu katmanı çalıştırmaz.
1. Dört durumun her biri için tek tek: üretilen cümle + `check_is_not_found`
   sonucu (programatik, LLM yorumuna bırakmadan).
2. test_5 TN/FP — **beklenti: 13/15 ve 2/15 DEĞİŞMEMELİ.** Düşerse kalıp
   skorlayıcıdan geçmiyor demektir.
3. test_2 CI soruları — #43/#53'ün yeni mesajı, diğer 12'sinin değişmemesi.
4. #107/#109 — 3a yolunun metni değişiyor, sınıfları (FP/TN) korunmalı.
