# Madde 11 — Düzeltme zinciri servisi çökertiyor: durum tespiti ve seçenekler

İlgili: [backlog_retrieval.md](backlog_retrieval.md) madde 11. Bu doküman
yalnızca tespit ve seçenek değerlendirmesidir; kod değişikliği İÇERMEZ ve bir
seçenek seçilmemiştir.

## Ölçülen zincir

`call_llm_text` izlenerek, çöken ve geçen sorular yan yana koşuldu
(Foundry Local `qwen2.5-7b-instruct-cuda-gpu:4`, GPU, taze servis):

| Soru | Model yanıtları | Prompt dizisi | Sonuç |
|---|---|---|---|
| #32 | 166 / 5 / 72 krk | 9.158 → 962 → 1.105 | geçti |
| #57 | 569 / 5 / 118 krk | 9.196 → 1.484 → 1.224 | geçti |
| **#43** | 852 / **2.266** krk | 9.178 → 10.735 → **11.970** | 3. çağrıda 500 |
| **#53** | **2.322** krk | 9.351 → **12.575** | 2. çağrıda 500 |

Hata: `onnxruntime::BFCArena::AllocateRawInternal — failed to allocate
2278526976 bytes` → `openai.InternalServerError: 500`.

### Üç tespit

1. **Tetikleyici tek bir aşırı uzun yanıt, birikim değil.** #53 yalnızca BİR
   geçmiş girdisiyle, ikinci çağrıda düştü. Backlog'daki ilk "sınırsız büyüme"
   teşhisi yanlıştı ve düzeltildi.
2. **Aşırı uzun yanıtlar tavana dayanmış yanıtlardır.** ~2.3 KB,
   `MAX_ANSWER_TOKENS = 600` sınırının karşılığı (Türkçe token yoğun). Yani
   model cümlesini bitirmemiş, kesilmiş. Bu yanıt hem büyük ihtimalle bozuk
   koddur hem de bir sonraki prompt'u şişirir.
3. **Eşik ~12 KB ve tam deterministik değil.** #43 11.970'te, #53 12.575'te
   düştü. #57 bu koşuda geçti ama önceki toplu koşuda düşmüştü — GPU'da o an
   boşta olan belleğe de bağlı.

### İkinci, bağımsız kusur
`code_interpreter_with_retry` bu istisnayı yakalamıyor. `call_llm_text`'ten
fırlayan hata `query_tabular_data` → `retrieve` zincirini boydan boya geçiyor;
kullanıcı cevap yerine 500 alıyor. Bu, prompt boyutundan bağımsız bir
dayanıklılık sorunudur ve seçeneklerden hangisi seçilirse seçilsin ayrıca
karara bağlanmalı.

### `repeated` neden durdurmuyor
Tekrar tespiti var (`code_interpreter.py:548`) ama **durdurma koşulu değil,
prompt yönlendirme sinyali**: yalnızca "aynı kodu yazma" uyarısı ekliyor,
döngüde `break` eden dal yok. Üstelik tekrarlanan kod ve hatası `history`'ye
koşulsuz eklendiği için tekrarı fark etmek prompt'u KÜÇÜLTMÜYOR, büyütüyor.

## Seçenekler

### A. History pencereleme (yalnızca son N denemeyi tut)
- **Artı:** Tek satırlık değişiklik, mevcut yapıya dokunmuyor.
- **Eksi:** **Ölçüm bunun yetmediğini gösteriyor.** Geçmiş zaten `max_retries=3`
  ile sınırlı; N=1'e indirmek #43'ü ~10.7 KB'a çekerdi ama **#53'ü kurtarmazdı**
  (tek geçmiş girdisiyle 12.575'te düştü). Ayrıca model önceki hataları
  görmediği için aynı hatayı tekrarlama olasılığı artar — `build_correction_prompt`
  docstring'i tam da bu yüzden "yalnızca sonuncusu değil, tüm geçmiş" demişti.
- **Değerlendirme:** Tek başına yetersiz; ölçülen vakayı kapatmıyor.

### B. Tekrar tespitinde durmak (`repeated` → `break`)
- **Artı:** Zaten var olan sinyali kullanır, yeni kavram getirmez. #43'ün 1. ve
  2. denemeleri neredeyse aynıydı → 3. çağrıya hiç gidilmezdi.
- **Eksi:** **#53'ü kurtarmaz** — orada tekrar yok, ilk yanıt zaten devasaydı.
  Ayrıca gerçek bir düzelme şansını erkenden keser: model bazen 3. denemede
  doğruyu buluyor (#32, #57 üç çağrı kullandı, ikisi de başarılı).
- **Değerlendirme:** Kısmi; asıl tetikleyiciyi hedeflemiyor.

### C. Prompt boyutu tavanı (geçmiş girdilerini kırparak)
- **Artı:** **Ölçülen tetikleyiciyi doğrudan hedefler.** Her geçmiş girdisinin
  kodunu sabit bir sınıra (ör. 800 krk) kırpmak, 2.3 KB'lık yanıtın prompt'a
  gömülmesini engeller ve toplamı ~10 KB civarında tutar. İki çöken vakayı da
  kapsar.
- **Eksi:** Kırpılmış kod modele eksik bilgi verir; hata kodun kırpılan
  kısmındaysa düzeltme şansı düşer. Sınır değeri (800? 1200?) keyfi ve veri
  setine/modele göre değişebilir — yeni bir ayar sabiti demek. Eşiğin
  deterministik olmaması (~12 KB, GPU durumuna bağlı) güvenli sınırı seçmeyi
  zorlaştırıyor.
- **Değerlendirme:** En hedefli seçenek, ama yeni bir sihirli sayı getiriyor.

### D. İstisnayı yakalayıp `success: False` dönmek
- **Artı:** Çökmeyi kullanıcıya yansıyan 500'den, mevcut ve TEST EDİLMİŞ bir
  yola (semantik RAG fallback / "bulunamadı") çevirir. Prompt boyutuna hiç
  bakmaz, dolayısıyla eşik tahmini gerektirmez. Ölçülen her iki vakayı da
  kapsar ve gelecekteki bilinmeyen çökme sebeplerini de kapsar.
- **Eksi:** **Sebebi ortadan kaldırmaz**, yalnızca sonucunu yumuşatır. Soru
  cevapsız kalır (kullanıcı doğru cevap yerine "bulunamadı" görür). Ayrıca
  gerçek bir altyapı arızasını sessizce yutma riski var — loglanmazsa fark
  edilmez.
- **Değerlendirme:** Tek başına eksik ama **diğerlerinden bağımsız olarak her
  hâlükârda gerekli** görünüyor: hangi önlem alınırsa alınsın, LLM servisinin
  patlaması kullanıcıya 500 olarak yansımamalı.

### E. `MAX_ANSWER_TOKENS`'ı düşürmek
- **Artı:** Tetikleyiciyi kaynağında keser (tavana dayanan yanıt kısalır).
- **Eksi:** **Riskli ve kapsam dışı.** Bu sabit yalnızca kod üretiminde değil,
  kullanıcıya giden CEVAP üretiminde de kullanılıyor (`llm_client.py:26`,
  `max_tokens=MAX_ANSWER_TOKENS`). Düşürmek uzun ama meşru cevapları keser.
  Kod üretimi için ayrı bir sınır gerekirse bu ayrı bir değişikliktir.
- **Değerlendirme:** Bu maddede ele alınmamalı.

## Değerlendirme özeti

| Seçenek | #43 | #53 | Yeni sabit | Sebebi giderir |
|---|---|---|---|---|
| A. History pencereleme | kısmen | **hayır** | hayır | hayır |
| B. Tekrarda durma | evet | **hayır** | hayır | hayır |
| C. Prompt tavanı + kırpma | evet | evet | **evet** | evet |
| D. İstisnayı yakala | evet | evet | hayır | **hayır** (yumuşatır) |
| E. max_tokens düşür | evet | evet | hayır | evet, ama kapsam dışı |

Yalnızca C sebebi giderip iki vakayı da kapsıyor; yalnızca D eşik tahmini
gerektirmeden iki vakayı da kapsıyor. A ve B ölçülen vakaların yarısını
kaçırıyor.

## Karar bekleyen sorular

1. **D tek başına yeterli mi?** Çökme "bulunamadı"ya dönerse kullanıcı
   deneyimi kabul edilebilir olur mu, yoksa sorunun cevaplanması mı
   hedeflenmeli?
2. **C seçilirse sınır kaç olmalı** ve bu sayının veri seti/model değişince
   yeniden ölçülmesi gerektiği nasıl kayda geçer?
3. **C + D birlikte mi?** (C sebebi azaltır, D kalan bilinmeyenleri yakalar.)
   Bu durumda madde 8'deki disipline göre ikisi AYRI commit ve ayrı ölçüm
   olmalı, yoksa hangisinin işe yaradığı ayrılamaz.

## Ölçüm planı (seçenek belirlendikten sonra)

Madde 13'ün kuralı burada da geçerli: **tam eval bu katmanı hiç çalıştırmaz.**
Doğrulama şunlarla yapılmalı:
1. #43, #53 — çöküyor mu, hangi yola düşüyor.
2. #32, #57 — halen doğru cevap üretiyor mu (D'nin fazla geniş davranıp
   çalışan sorguları fallback'e atmaması).
3. test_2'nin `code_interpreter` soruları, soru bazında önce/sonra.
4. test_5 TN/FP — #43/#53 fallback'e düşerse negatif set etkilenebilir.
