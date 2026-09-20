# Madde 8 — Var olmayan kolon sorulduğunda üretilen halüsinasyon

İlgili: [backlog_retrieval.md](backlog_retrieval.md) madde 8. Ölçüm çizgisi: `ce3de42`
(test_5 TN 12/15, FP 3/15). Bu doküman yalnızca durum tespiti ve plandır; kod
değişikliği içermez.

## Önce bir çerçeve düzeltmesi

Backlog'da madde 8 "kolon adı takma ad bağımlılığı (meta-boost kapısı)" diye
kayıtlı ve test_5 #107/#109'un bu kapıdan geçtiği varsayılmıştı. **Ölçüm bu
varsayımı doğrulamıyor.**

`router.route_query` üç soru için de şunu döndürüyor:

```
target=code_interpreter  reason=complexity_signal+dataset_signal
strong=['profileCode~profil', 'profileType~profil',
        'profileMedia.avatarUrl~profil', 'profileMedia.coverImageUrl~profil']
```

Eşleşmelerin tamamı gerçekten takma ad üzerinden ("profil"), yani madde 8'in
tarif ettiği kırılganlık **var**. Ama `_analyze`'daki karar şu:

```
has_dataset_signal = bool(strong_schema) or bool(matched_generic)
                     or (bool(weak_schema) and dataset_context)
```

Sorularda "728_profiles.json" ve "veri setinde" geçtiği için `matched_generic`
zaten `True`. Yani **takma ad eşleşmesini tamamen kaldırsak bile rota
değişmezdi**; soru yine `code_interpreter`'a giderdi. Takma ad kapısını
katılaştırmak bu iki FP'yi önlemez.

Dahası, rotanın kendisi yanlış değil: #108 ("cinsiyet dağılımı") aynı rotadan,
aynı takma adlarla geçiyor ve **doğru şekilde "bulunamadı" diyor** (TN). Sorun
rota seçiminde değil, **var olmayan bir kolon istendiğinde ne olduğunda.**

## Ön ölçüm — üç sorunun karşılaştırması

Veri setinde `ucret`, `fiyat`, `price`, `fee`, `satisfaction`, `memnuniyet`,
`rating`, `puan`, `gender`, `cinsiyet` içeren **hiçbir kolon yok**. Üçü de
cevaplanamaz sorular; beklenen çıktı "bulunamadı".

| # | Soru | code_interpreter davranışı | Cevap | Sınıf |
|---|---|---|---|---|
| 107 | ortalama randevu **ücreti** | 1. denemede temiz çalıştı: `df['appointmentSettings.defaultDurationMinutes'].mean()` → 45.117 | "ortalama randevu ücreti 45.12'dir" | **FP** |
| 108 | **cinsiyet** dağılımı | 1. denemede temiz çalıştı: `profileType` sayımı → Individual 599 / Business 129 | "cinsiyet dağılımı konusunda bilgi bulunamadı" | TN |
| 109 | **müşteri memnuniyet puanı** ortalaması | 3 deneme de başarısız (aşağıda) | "Müşteri memnuniyet puanı ortalaması 1.0'tır" | **FP** |

#109'un deneme zinciri:

```
Deneme 1: result = df.shape[0] / len(df)          -> 1.0, semantik doğrulama İTİRAZ ETTİ
Deneme 2: result = None                            -> ValueError (result atanmadı)
Deneme 3: result = df['customer_satisfaction_score'].mean()  -> KeyError
[CodeInterpreter] Dogrulama uyarili sonuc donduruluyor.   -> deneme 1'in 1.0'ı döndü
```

## İki ayrı kök neden

Bunlar tek bir düzeltmeyle kapanmıyor; ayrı ayrı ele alınmalı.

### Kök neden 1 — "doğrulama uyarılı" sonuç, uyarısı düşürülerek kesin sonuç gibi sunuluyor (#109)

`code_interpreter.py:600-604`: üç deneme de tutmazsa, ilk çalışan denemenin
sonucu `fallback_result` olarak dönüyor. Bu sözlükte `warning` alanı var ve
semantik doğrulayıcının itiraz metnini taşıyor. Ancak:

- Dönen sözlükte `success: True` yazıyor.
- `data_engine.py:635-660` `warning` alanını **hiç okumuyor** — `grep warning
  src/data_engine.py` sıfır sonuç veriyor.
- Dolayısıyla sonuç temiz bir başarıyla aynı yoldan gidiyor:
  `result_to_natural_language` → synthesizer'a `[KESİN HESAPLAMA SONUCU]` bloğu.
- Synthesizer prompt'u (`retrieval.COMPUTED_RESULT_INSTRUCTION`) o bloğu
  "doğruluğu garanti edilmiş NİHAİ cevap" diye tanımlıyor ve modele
  "bu bloğu görmezden gelme ve 'bulunamadı' deme" diyor.

Yani sistem kendi doğrulayıcısının itirazını üretiyor, saklıyor, sonra modele
"buna kesin olarak güven" diyor. #109'un 1.0'ı buradan geliyor.

Altyapı zaten mevcut: "0 satır eşleşti" durumu için `empty_result` →
`NO_MATCH_SUMMARY` → `EMPTY_RESULT_INSTRUCTION` zinciri var ve çalışıyor.
Eksik olan, **"uyarılı sonuç" için eşdeğer bir yol.**

### Kök neden 2 — semantik doğrulayıcı, var olan ama yanlış kolonun ikame edilmesini yakalamıyor (#107)

#107'de kod ilk denemede hatasız çalıştı, bu yüzden `_semantic_check` devreye
girdi ve **itiraz etmedi**. Model "randevu ücreti" için
`appointmentSettings.defaultDurationMinutes` (dakika cinsinden süre) kolonunu
ikame etti. Doğrulayıcı `attempt < max_retries` koşuluyla çalışıyor ve
docstring'inde belirtildiği gibi muhafazakâr: kararsızsa `None` dönüyor.

Bu durum #109'dan farklı: orada istenen kolon hiç yoktu ve kod patladı; burada
**var olan ama anlamı tamamen farklı** bir kolon kullanıldı ve kod temiz
çalıştı. Hiçbir katman "birim uyuşmazlığı" görmüyor.

Yan gözlem: `llm_client` para birimi koruması "TL"yi cevaptan sildi
(`Para birimi duzeltildi: 'TL' -> '(kaldirildi)'`). Sonuç, birimsiz bir "45.12"
oldu — halüsinasyonu engellemedi, yalnızca daha az denetlenebilir hale getirdi.
Koruma cümleyi "bu sayı neyin sayısı" sorusuna cevapsız bırakıyor.

### Neden #108 kurtuldu

#108'de de yanlış kolon ikame edildi (`profileType` → cinsiyet) ve kod temiz
çalıştı, yani #107 ile aynı desen. Fark cevapta ortaya çıkıyor: synthesizer
"bulunamadı" demeyi seçti. Bunun neden #107'de olmadığı **ölçülmedi** — olası
sebep, `Individual/Business` etiketlerinin soruyla açıkça alakasız görünmesi,
oysa çıplak bir `45.12` sayısının "ücret" gibi okunabilmesi. Bu bir hipotez;
planın 1. adımı bunu ölçecek.

## Değerlendirilen yaklaşımlar

- **A. Takma ad eşleşmesini katılaştırmak** (madde 8'in orijinal önerisi:
  tam kelime sınırı, minimum eşleşme uzunluğu). *Bu iki FP'yi çözmez* —
  yukarıda gösterildiği gibi rota `matched_generic`'ten zaten açılıyor.
  Ayrıca madde 5 planındaki risk hâlâ geçerli: katılaştırma test_2#45 gibi
  soruları kapı dışında bırakabilir. **Bu maddede ele alınmamalı**, ayrı
  kalmalı.
- **B. Uyarılı sonucu "bulunamadı" sinyaline çevirmek** (kök neden 1).
  Mevcut `empty_result` zincirinin aynısı, yeni bir bayrakla. Dar, mevcut
  desene uyuyor, tek yerde. **Tercih edilen.**
- **C. Kod üretiminden ÖNCE "sorulan büyüklük şemada var mı" kapısı.**
  Her iki kök nedeni de kapsar ama yeni ve geniş bir katman: soru → hedef
  büyüklük çıkarımı gerekiyor, bu da yeni bir LLM çağrısı (gecikme) ya da
  kırılgan bir sözlük demek. Madde 5'te reddedilen "şema-agnostik kalma"
  ilkesine de sürtünüyor. **Şimdilik hayır.**
- **D. `_semantic_check`'i birim/anlam uyuşmazlığına duyarlı hale getirmek**
  (kök neden 2). Gerekli ama B'den ayrı; doğrulayıcının prompt'una dokunmak
  ölçümü karıştırır. **Ayrı adım.**

## Önerilen sıra

Tek seferde bir değişiklik, madde 5/6'daki alışkanlığın aynısı:

1. **Ölçüm adımı (kod yok).** #107 ve #108'in synthesizer girdilerini
   (`[KESİN HESAPLAMA SONUCU]` bloğunun tam metni) yan yana dökmek ve #108'in
   neden kurtulduğunu ölçmek. Hipotez doğrulanmazsa B'nin yeterliliği
   yeniden değerlendirilir.
2. **B'yi uygula.** `fallback_result`'a `validation_warning: True` bayrağı;
   `data_engine` bunu okuyup `empty_result` ile aynı yoldan `NO_MATCH_SUMMARY`
   benzeri bir özete çevirsin. Yalnızca #109 sınıfını hedefler.
3. **Ölç:** üç katman, sırayla:
   - **test_2'nin `code_interpreter` rotasına giden 7 sorusu, soru bazında.**
     `data_engine`'in gerçekten çalıştığı yer burası ve regresyon riskini en
     çok taşıyan set bu: B fazla geniş davranırsa doğru hesaplanmış cevaplar
     "bulunamadı"ya döner. Her birinin önce/sonra cevabı tek tek
     karşılaştırılmalı, toplu yüzdeye bakmak yetmez.
   - test_5 TN/FP. Beklenti: FP 3/15 → 2/15.
   - Tam eval (test_1…test_5). Kaynak doğruluğu değişmemeli, çünkü retrieval'a
     dokunulmuyor; değişirse düzeltme sızmış demektir.
4. **D'yi ayrı madde olarak aç** (#107 sınıfı: var olan ama yanlış kolonun
   ikamesi). B ölçülmeden başlanmamalı.

## Riskler

- **B fazla geniş davranabilir.** `_semantic_check` muhafazakâr olsa da yanlış
  itiraz edebiliyor; o durumda doğru bir sonuç "bulunamadı"ya çevrilir ve TN
  artarken **doğru cevaplar kaybedilir**. test_5 yalnızca negatif sorular
  içerdiği için bu kaybı GÖREMEZ. Bu yüzden 3. adımın ilk katmanı test_2'nin
  7 `code_interpreter` sorusudur: pozitif, hesaplanmış cevap bekleyen ve
  `data_engine`'den geçen tek anlamlı küme o. Toplu başarı yüzdesi bu kaybı
  maskeleyebilir, bu yüzden soru bazında karşılaştırılmalı.
- **Ölçüm çizgisi taze değil.** test_5 TN 12/15 tek koşuluk. LLM üretimi
  deterministik değil (`temperature=0.0` ama sandbox retry zinciri değişebilir).
  B öncesi/sonrası karşılaştırma aynı oturumda yapılmalı.
- **#101 bu planın kapsamı dışında.** O bir PDF sorusu, `semantic_rag`
  rotasından geçiyor, code_interpreter'a hiç uğramıyor. Ayrı ele alınmalı.
