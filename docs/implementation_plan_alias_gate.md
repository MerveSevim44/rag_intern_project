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

### Neden #108 kurtuldu — ÖLÇÜLDÜ (adım 1)

Hipotez kısmen doğru çıktı, ama sebep tahmin edilen katmanda değil. Synthesizer'a
giden bloklar yan yana:

```
#107   raw_result = np.float64(45.11675824175824)
       [KESİN HESAPLAMA SONUCU]
       728_profiles.json veri setinde profillerin ortalama randevu ücreti 45.12'dir.

#108   raw_result = {'Individual': 599, 'Business': 129}
       [KESİN HESAPLAMA SONUCU]
       Individual profil sayısı 599'dur, Business profil sayısı 129'tür.
```

Talimat ikisinde de aynı ("doğruluğu garanti edilmiş NİHAİ cevap"). Fark
synthesizer'ın muhakemesinde değil, bir katman önce, `result_to_natural_language`
içinde oluşuyor:

- **#107'nin cümlesi sorunun kelimeleriyle kurulmuş** ("ortalama randevu
  ücreti"). Blok, soruyu birebir cevaplayan tutarlı bir iddia hâline gelmiş ve
  "garantili" damgası yemiş. Synthesizer'ın uyuşmazlığı görmesi imkânsız.
- **#108'in cümlesi verinin etiketleriyle kurulmuş** ("Individual / Business").
  Soru "cinsiyet" diyor, blok "profil tipi" diyor; synthesizer farkı görüp
  "bulunamadı" diyor.

Sebep `result_to_natural_language`'ın prompt'u: fonksiyona **soru + ham sonuç**
veriliyor, sonucun hangi kolondan geldiği ya da üretilen kod **verilmiyor**.
Sonuç kendi etiketini taşımıyorsa cümleyi kuracak tek kelime dağarcığı sorunun
kendisi oluyor:

| raw_result | Etiket taşıyor mu | Cümle kimin diliyle kurulur | Uyuşmazlık |
|---|---|---|---|
| skaler (`45.117`) | hayır | **sorunun** dili (tek seçenek) | görünmez olur |
| dict / Series | evet | **verinin** dili | görünür kalır |

Yani #108'i kurtaran şey synthesizer'ın dikkati değil, ham sonucun `dict` olup
anahtarlarını yanında getirmesiydi — yapısal bir tesadüf. Aynı soru skaler bir
sonuç üretseydi #107 gibi FP olurdu.

Bu bulgu 4. adımın yönünü değiştirdi (aşağıya bakınız).

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
- **D. `result_to_natural_language`'a kolon adını / üretilen kodu vermek**
  (kök neden 2), böylece cümle her zaman *ne hesaplandığını* anlatsın, *ne
  sorulduğunu* değil. Adım 1 ölçümünün ortaya çıkardığı yön: #107'yi #108'in
  kurtulduğu duruma çevirir ve yeni bir LLM doğrulama çağrısı gerektirmez.
  **Ayrı adım.**
- **D-eski. `_semantic_check`'i birim uyuşmazlığına duyarlı hale getirmek.**
  Adım 1'den önce planlanan yol. Terk edildi: doğrulayıcı #107'de zaten çalıştı
  ve itiraz etmedi; onu sıkılaştırmak yeni bir LLM muhakemesine bel bağlamak
  demek. D daha ucuz ve daha kesin bir yerde duruyor.

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
   ikamesi). Adım 2 ve 3 bitmeden başlanmamalı.

   **Uygulamadan önce zorunlu envanter.** D, `result_to_natural_language`'ın
   girdisini değiştiriyor ve bu fonksiyon HER `raw_result` türünden geçiyor —
   yalnızca #107'deki skaler değil. Kod şu an `DataFrame`, `Series`,
   `np.generic` ve "diğer" (dict, liste, int, str…) dallarını ayrı ayrı
   biçimlendiriyor. Değişiklikten önce her türün bugün hangi cümleye
   dönüştüğü örnekle çıkarılmalı; aksi halde skaler durumu düzeltirken
   dict/DataFrame durumu bozulabilir — ki dict durumu (#108) şu an **doğru
   çalışan** taraf, korunması gereken davranış o.

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

## Adım 4 envanteri — `raw_result` türleri (ÖLÇÜLDÜ)

Adım 4 `result_to_natural_language`'ın girdisini değiştiriyor ve o fonksiyon
HER sonuç türünden geçiyor. Değişiklikten önce her türün bugün hangi cümleye
dönüştüğü gerçek veri setiyle, gerçek fonksiyon çağrısıyla çıkarıldı.

| Tür | Dal | Kaynak | RAW | Üretilen cümle | Dağarcık |
|---|---|---|---|---|---|
| `np.float64` | `np.generic` | **#107** | `45.11675824` | "…ortalama randevu **ücreti** 45.12'dir" | SORU |
| `np.int64` | `np.generic` | türetilmiş | `728` | "Veri setinde **toplam** 728 **profil** vardır" | SORU |
| `dict` (str anahtar) | `else` | **#108 REFERANS** | `{'Individual': 599, 'Business': 129}` | "**Individual** profil sayısı 599'dur, **Business** profil sayısı 129'tür" | **VERİ** |
| `dict` (tuple anahtar) | `else` | **#35** | `{(False, False): 728}` | "**publicContact** alanındaki **phoneVisible** ve **emailVisible** değerleri False'dur" | SORU |
| `pd.Series` | `Series` | türetilmiş | `Sağlık 40, Spor… 40` | "**Sağlık** sektöründe 40 profil, **Spor ve Fitness**…" | VERİ |
| `pd.DataFrame` | `DataFrame` | türetilmiş | `İstanbul 130, İzmir 81` | "**İstanbul**'da 130 profil, **İzmir**'de 81…" | VERİ |
| `list` | `else` | türetilmiş | `['Aile Hekimliği Uzmanı', …]` | "En sık geçen 3 **meslek**: Aile Hekimliği Uzmanı…" | KARMA |
| `int` | `else` | türetilmiş | `22` | "22 **farklı sektör** vardır" | SORU |
| `float` | `else` | türetilmiş | `11.998626` | "Profillerin **ortalama deneyim yılı** 12.0" | SORU |
| `str` | `else` | türetilmiş | `'İstanbul'` | "İstanbul **en çok profile sahip şehirdir**" | SORU |
| `bool` | `else` | kenar durum | `True` | "Veri setinde hiç business profil var. **True**" | SORU |

### Çıkan kural
Belirleyici olan **tür değil, sonucun kendi etiketini taşıyıp taşımadığı**:

- **Etiket taşıyanlar** (str anahtarlı `dict`, `Series`, `DataFrame`) → cümle
  verinin diliyle kurulur → uyuşmazlık görünür kalır. 3 vaka. **Korunacak
  davranış bu**; #108 referans örnek.
- **Yalnızca değer taşıyanlar** (skaler, `int`, `float`, `str`, `bool`, çıplak
  değerli `list`, tuple anahtarlı `dict`) → cümleyi kuracak tek kelime
  dağarcığı sorunun kendisidir → uyuşmazlık kaybolur. 8 vaka. **Adım 4'ün
  hedefi bunlar.**

### Envanterin önlediği hata
"`dict` ise dokunma" gibi tür bazlı kaba bir kural yazılsaydı **#35 yanlışlıkla
güvenli sayılacaktı**: `dict` olmasına rağmen anahtarları `(False, False)`,
yani alan adı taşımıyor ve cümledeki `publicContact`/`phoneVisible`/
`emailVisible` adlarının hepsi sorudan gelmiş. Bu yüzden adım 4'ün kuralı
**tür bazlı değil davranış bazlı** olmalı: `isinstance(result, dict)` yetmez,
anahtarların gerçekten alan adı taşıyıp taşımadığına bakan bir kontrol gerekir.

### Adım 4'ün kapsamı DIŞINDA kalan iki kusur
Envanterde çıktılar, adım 4 ile aynı commit'e KARIŞTIRILMAYACAK — aksi halde
hangi düzeltmenin neyi etkilediği yine ayrılamaz:

1. **`bool` dalı zaten bozuk**: `"Veri setinde hiç business profil var. True"` —
   ham `True` cümleye sızıyor ve cümle devrik. Bağımsız kusur, ayrı madde
   olarak kaydedildi (backlog madde 12), adım 4 bittikten sonra ele alınacak.
2. **"Sayıyı asla değiştirme" kuralı `float`'ta zaten delinmiş**:
   `11.998626` → `"12.0"`. Prompt açıkça yasaklamasına rağmen model yuvarlamış.

### Adım 4'ün test aşamasına ek koşul
Sayı korunması ile alan adı kullanımı **birbirinden bağımsız iki özellik**;
biri düzelirken diğeri sessizce kötüleşebilir. Prompt'a alan adı eklemek
"sayıyı değiştirme" kuralının ağırlığını daha da azaltabilir (yukarıdaki 2.
maddeye göre kural zaten tam tutmuyor). Bu yüzden adım 4 sonrası test yalnızca
"cümle doğru alan adını mı kullanıyor" diye değil, **"sayı hâlâ olduğu gibi mi
kalıyor"** diye de bakmalı. Envanterdeki 11 vaka önce/sonra karşılaştırması
için taban oluşturur.

## Adım 4 — tasarım (onaylandı, uygulama öncesi)

### İmza
```python
def result_to_natural_language(question, result, llm, code=None, columns=None)
```
İki yeni parametre de **opsiyonel**; varsayılan `None` olduğu için mevcut çağrı
yerleri değişmeden çalışır. Tek gerçek çağrı yeri `data_engine.py` içindeki
sandbox dalı; oraya `code=exec_info.get("code")` geçilir, `columns` koddan
çıkarılır.

### Yeni yardımcı — `_carries_own_labels(result) -> bool`
Kural **tür bazlı değil davranış bazlı**; `isinstance(result, dict)` yetmez
(bkz. #35).

| Girdi | Karar | Gerekçe |
|---|---|---|
| `DataFrame` | taşıyor | kolon adları |
| `Series` | taşıyor | index etiketleri |
| `dict`, TÜM anahtarlar `str` VE en az biri alfabetik karakter içeriyor | taşıyor | `{'Individual': 599}` |
| `dict`, tuple/bool/sayı anahtarlı | **taşımıyor** | **#35 `{(False, False): 728}`** |
| `list`, elemanları `dict` ya da (etiket, değer) çifti | taşıyor | |
| `list`, çıplak değerler | taşımıyor | `['Aile Hekimliği Uzmanı', …]` |
| skaler / `int` / `float` / `str` / `bool` | taşımıyor | |

"En az bir alfabetik karakter" koşulu gerekli: `{'0': 5, '1': 3}` anahtarları
teknik olarak `str` ama alan adı değil.

### Prompt bloğu — yalnızca etiketsizlere
`_carries_own_labels(result)` False ise prompt'a sonucun hangi koddan ve hangi
alandan geldiğini bildiren bir blok eklenir ve cümlenin ALAN ADININ anlamıyla
kurulması, sorunun kelimeleriyle değil, zorunlu tutulur. True ise **hiçbir şey
eklenmez** — #108 / #35 / `Series` / `DataFrame` yolu bit düzeyinde değişmez.

### `columns` çıkarımı
Üretilen koddan `df['...']` / `df["..."]` desenleri regex ile toplanır ve
gerçek `df.columns` ile kesiştirilir. Kesişim boşsa blok EKLENMEZ — uyduracak
alan adı yoktur.

## Adım 4 — test planı

Envanterdeki 11 vaka önce/sonra, **birbirinden bağımsız iki kriterle**:

1. **Alan adı kullanımı** — cümle verinin diliyle mi kuruluyor?
2. **Sayı korunması** — ham sayının cümlede birebir geçip geçmediği
   **programatik** olarak doğrulanır (LLM yorumuna bırakılmadan). `float`
   yuvarlamasının (`11.998626` → `"12.0"`) kötüleşip kötüleşmediği dahil.
   Bu iki kriter bağımsızdır: biri düzelirken diğeri sessizce bozulabilir.

Ek olarak, uygulamaya geçmeden test planına eklenen üç nokta:

3. **Kenar durum: `code=None` ve regex kesişimi boş.** Sessiz hata değil,
   **blok eklenmeme** davranışı doğrulanmalı. Üç alt vaka ayrı ayrı denenecek:
   `code=None` geldiğinde, kod `df.shape[0]` gibi hiç kolon adı içermediğinde,
   ve koddaki kolon adı gerçek `df.columns` ile kesişmediğinde (ör. modelin
   uydurduğu `customer_satisfaction_score`). Üçünde de fonksiyon bugünkü
   davranışını aynen sürdürmeli ve istisna atmamalı.

4. **Cümlenin doğallığı.** Alan adını prompt'a sokmak, pandas/kod jargonunun
   cevaba sızmasına yol açabilir: cümlede `df[...]`, `.mean()`, alan adının
   ham hâli (`appointmentSettings.defaultDurationMinutes`) ya da kod parçası
   görünmemeli. 11 vakanın her birinde çıktı bu açıdan okunacak; ölçüt
   "kullanıcıya gösterilebilir bir Türkçe cümle mi" olacak.

5. **#107'nin başarı ölçütü NET.** Hedef "cümle daha doğru" DEĞİL. Hedef:
   **synthesizer bunu uyuşmazlık olarak görüp "bulunamadı" diyor mu.** Yani
   başarı kriteri `result_to_natural_language`'ın çıktısı değil, zincirin
   sonundaki cevap ve test_5'teki sınıfı (FP → TN). Cümle düzelip de
   synthesizer yine de sayıyı aktarıyorsa adım 4 hedefine ULAŞMAMIŞ sayılır.

Sonra sırasıyla: test_5 TN/FP (beklenti FP 2/15 → 1/15), test_2
`code_interpreter` soruları, tam eval (100/100 korunmalı).

### Kapsam dışı (kasıtlı)
`bool` bozukluğu (madde 12) ve `float` yuvarlaması düzeltilmeyecek, yalnızca
**ölçülecek**.

## Adım 4 — A BAŞARISIZ, B'ye geçildi

### A'nın sonucu (prompt'a alan adı ekleme)
Uygulandı, ölçüldü, **geri alındı**. Kolon doğru çıkarıldı ve blok doğru
eklendi, ama model talimatı yoksaydı:

```
Blok EKLENDİ, kolon = ['appointmentSettings.defaultDurationMinutes']
Cümle     : "...ortalama randevu ücreti 45.11675824175824 dir."
Synthesizer: "...ortalama randevu ücreti 45.11675824175824'dir."
```

Planın 5. test maddesindeki ölçüte göre (başarı = synthesizer'ın "bulunamadı"
demesi) **hedef tutmadı**. Ayrıca cevap kötüleşti: `45.12` → tam hassasiyet.
A'nın varsayımı — "prompt'a alan adı verirsen model onu kullanır" — yanlış
çıktı. Prompt'u sertleştirmek, adım 1'de `_semantic_check` için reddedilen
yola (yeni bir LLM muhakemesine bel bağlamak) dönmek olurdu.

A'nın yan ürünleri kayda değer:
- **`bool` dalı kapsam dışıydı ama değişti** (blok eklendiği için). Kirlenme;
  bu da B'de `bool`'un açıkça muaf tutulmasının gerekçesi.
- **Sayı biçimlendirmesi bozuldu**: `float` "12.0" → "12", `np.float64`
  tam hassasiyete kaydı. İki test kriterinin bağımsızlığı doğrulandı.
- **Regex eksiği ortaya çıktı** (aşağıda, B'nin ön koşulu).

### B — deterministik kapı

**Ölçüt, soruyu ayrıştırmaz.** "Sorunun ana ismini çıkarmak" bir LLM
sınıflandırması gerektirirdi ve B'yi A'nın kırılganlığına geri döndürürdü.
Bunun yerine soru TERSİNE çevrilir:

> Kodun GERÇEKTEN kullandığı kolon, soruda herhangi bir biçimde anılıyor mu?

Bu sorunun cevabı zaten deterministik olarak mevcut: `router.detect_schema_matches`
(kolon adları + `COLUMN_TR_ALIASES` Türkçe karşılıkları, `_contains_token` ile).
**Yeni LLM çağrısı YOK.**

```
used  = koddaki df['...'] adları  ∩  df.columns
qcols = router.detect_schema_matches(soru, df.columns)   # STRONG + WEAK
KAPI ATEŞLER  ⇔  used boş DEĞİL  ve  used ∩ qcols boş
```

Ateşlerse sonuç `result_to_natural_language`'a hiç gitmez; adım 2'de kurulan
`[DOĞRULANAMAYAN SONUÇ]` yoluna düşer (altyapı hazır, `unverified_result`).

**STRONG + WEAK olması zorunlu.** İlk dry-run yalnızca STRONG ile yapıldı ve
**3 doğru vakayı yanlışlıkla ateşledi** (`şehir`→`location.city`,
`deneyim`→`experience.years`; bunlar `EXCLUDED_GENERIC_WORDS` içinde olduğu için
WEAK sınıfına düşüyor). Bu, ölçütün alias tablosunun kapsamına ne kadar duyarlı
olduğunun ölçülmüş kanıtıdır ve tasarımın en kırılgan yeri burasıdır.

### B'nin ön koşulu — regex düzeltmesi
Mevcut çıkarım yalnızca tek köşeli `df['x']` yakalıyor; `df[['x','y']]`
kaçıyor. Bu yüzden A'nın koşusunda #35 `kolon=[]` verdi ve yanlışlıkla
"korumasız" kaldı. Kolon çıkarımı hangi tasarımda olursa olsun doğru
çalışmalı; **ayrı ve önce** ele alınacak:
`df\s*\[\s*(\[[^\]]*\]|['"][^'"]*['"])\s*\]`

### B'nin 11 envanter vakası + kenar durumlar (DRY RUN, ölçüldü)

| Vaka | Karar | Kesişim |
|---|---|---|
| **#107** (hedef) | **ATEŞLER** | `[]` — "ücret" hiçbir kolonla eşleşmiyor |
| **#108 REFERANS** | ateşlemez | `profileType` |
| **#35** | ateşlemez | `publicContact.phoneVisible/emailVisible` |
| `Series` | ateşlemez | `sector` |
| `DataFrame` | ateşlemez | `location.city` |
| `list` | ateşlemez | `occupation` |
| `int` | ateşlemez | `sector` |
| `float` | ateşlemez | `experience.years` |
| `str` | ateşlemez | `location.city` |
| `bool` | ateşlemez (ve zaten MUAF) | `profileType` |
| #109 | ateşlemez (kolonsuz) | zaten adım 2 kapsıyor |

**Yanlış karar: 0/11.** Etiket taşıyan/taşımayan ayrımı B'yi HİÇ ilgilendirmiyor
— B kolon-soru örtüşmesine bakıyor, sonucun biçimine değil. Yani adım 4'ün
(A'nın) korumaya çalıştığı `#108`/`Series`/`DataFrame` yolu B'de zaten
dokunulmadan kalıyor.

### Yanlış pozitif riski (adım 3'ün kaygısı, burada da geçerli)
test_2'nin `code_interpreter` soruları dry-run'da: **6/6 ateşlemedi.**
(#32, #35, #43, #45, #52, #60.)

Yine de risk kapanmış değil: kapı, alias tablosunun o veri seti için yeterli
olmasına bağlı. Yeni bir veri setinde kullanıcı, `COLUMN_TR_ALIASES`'ta
karşılığı olmayan bir kelimeyle doğru bir soru sorarsa kapı yanlış ateşler ve
**doğru hesaplanmış cevap "bulunamadı"ya döner.** Ölçüm planı bu yüzden
test_1…test_5'in tamamını kapsamalı, yalnızca test_5'i değil.

### Kapsam dışı — açıkça
- **`bool` (madde 12): MUAF.** Kapı ateşlense de ateşlemese de `bool` dalına
  dokunulmayacak. A'da tesadüfen değişmişti; B'de bu olmamalı.
- **Sayı biçimlendirmesi:** B'nin ateşlediği yolda hiç sayı üretilmediği için
  (çıktı `[DOĞRULANAMAYAN SONUÇ]` gövdesi) sorun OLUŞMAZ. Ama gelecekte tekrar
  bir "prompt'a blok ekle" senaryosu denenirse A'daki bozulma (12.0 → 12,
  45.12 → 45.11675824175824) yeniden karşımıza çıkar. Kayda geçiyor.

### Test planı
1. Ön koşul regex düzeltmesi: birim testi (tek/çift köşeli, `code=None`, boş).
2. 11 envanter vakası + test_2 CI soruları: kapı kararları (yukarıdaki dry-run
   canlı kodda tekrarlanmalı).
3. #107 end-to-end: **başarı ölçütü synthesizer'ın "bulunamadı" demesi**
   (FP → TN), cümlenin düzelmesi değil.
4. test_5 TN/FP — beklenti FP 2/15 → 1/15.
5. Tam eval — 100/100 korunmalı.

## B ÖLÇÜLDÜ VE BIRAKILDI — madde 8 kısmi kapanış

### B'nin ölçümü
Kapı uygulandı ve 115 sorunun tamamı `query_tabular_data(q, llm=...)` üzerinden
geçirildi. (Önemli ölçüm notu: **tam eval kapıyı test ETMİYOR** —
`eval_retrieval.py` `retrieve()`'i `llm` olmadan çağırıyor, `data_engine` ise
sandbox'a girmek için `llm is not None` arıyor. Tam eval'in 100/100'ü yalnızca
"retrieval'a sızma yok" der, davranışı doğrulamaz. Adım 2 için de aynısı
geçerliydi; o değişiklik test_2 CI soruları + test_5 ile ayrıca ölçüldüğü için
sonucu geçerli.)

Sandbox'a ulaşan 16 soru:

| Karar | Sayı | Vakalar |
|---|---|---|
| ATEŞLEDİ | 3 | #107 (doğru), **#39 (yanlış)**, **#42 (yanlış)** |
| geçti | 7 | #32, #35, #37, #51, #52, #60, #108 — hepsi doğru |
| kapı-yok | 3 | #44, #45, #109 |
| HATA (madde 11) | 3 | #43, #53, #57 |

### Neden bırakıldı
İki yanlış pozitif **alias boşluğu değil**, öngörülmemiş bir sınıf:

```
#39  "Umut Aslan profilinde services dizisindeki hizmetlerden hangileri Online..."
#42  "Emre Korkmaz ve Umut Aslan profillerinin minimumNoticeHours ve ..."
     kullanilan=['displayName']  soruda=[]
```

Soru kolonu **adıyla değil DEĞERİYLE** anıyor ("Umut Aslan" → `displayName`).
`COLUMN_TR_ALIASES`'a `displayName → isim/ad` eklemek bunu ÇÖZMEZ; soruda "isim"
kelimesi de geçmiyor.

Dahası, bu iki vakada `displayName` **filtre** olarak kullanılıyor, cevaplanan
büyüklük değil. Yani "kullanılan kolon vs. soru" çerçevesi bir kolonun iki farklı
rolünü (filtre / hesaplanan büyüklük) birbirine karıştırıyor. Ayırmak kod
yapısını ayrıştırmayı gerektirir — dördüncü bir heuristik katman.

**Üç turdur aynı desen:** A → model prompt'u yoksaydı; B v1 → alias boşluğu;
B v2 → değer farkındalığı eksik. Her tur bir öncekinin varsayımını çürüttü.
"Soru veriye nasıl referans verir" listesi açık uçlu (kolon adı, alias, değer,
kısmi değer, sayısal aralık, dolaylı referans...). Bu çözülebilir bir bug değil,
açık uçlu bir doğal dil kapsama problemi.

Değer farkındalığı denenmedi çünkü bir yanlış pozitif sınıfını yanlış negatif
sınıfıyla takas edeceği öngörüldü: `displayName` (728 tekil değer) için
`_VALUE_VOCAB_MAX_CARDINALITY = 60` sınırını kaldırmak, sık geçen bir değerin
tesadüfen soruda bulunup kolonu "anılmış" saymasına ve kapının #107'yi
kaçırmasına yol açar.

### Madde 8'in durumu — KISMİ KAPANIŞ
- **#109 çözüldü** (`3918a75`): FP → TN. Kalıcı.
- **#115 çözüldü** (yan etki, `0355b2d` sonrası ölçüldü). Kalıcı.
- **#107 AÇIK** — bilinen ve kabul edilmiş sınırlama, backlog madde 8'de
  bırakıldı.
- **#101 kapsam dışı** — `semantic_rag` rotası, sandbox'a hiç uğramıyor.

Korunan kazanımlar commit edilmiş durumda; B'nin kod değişikliği geri alındı.
Yalnızca `columns_from_code` (`40b54f3`) tutuldu — bağımsız ve doğru bir
yardımcı, şu an çağrısız.
