# Plan: madde 22 — OCR'lı Örnek/Cevap sayfalarını tek chunk'ta birleştirmek

Tarih: 2026-10-12. Taban: `fbe73e1`. Kapsam ölçümü:
[experiments/madde22_ornek_cevap/README.md](../experiments/madde22_ornek_cevap/README.md).

## 1. Sorun (özet)

Gramer PDF'inin sayfa 22–31'i resim; `dffb6a5` ile OCR'lanıyor ve her sayfa ayrı
chunk. "Örnek N" sayfası soruyu, hemen ardındaki "Cevap N" sayfası cevabı
taşıyor. Ama Cevap sayfası yalnız başlık ve formülden ibaret. Sorudaki
kelimeler ("Örnek 8", "dilbilgisi", "türettiği") orada geçmiyor ve sayfa
bağlama gelmiyor. Hedef 5 sorunun hiçbirinde doğru Cevap sayfası bağlamda
değil:

| Soru | Cevap sayfası | Bugün |
|---|---|---|
| test_1 #24 | s.23 | hibrit sırada 40'tan sonra (OCR bozuk) |
| test_1 #25 | s.27 | 10. |
| test_1 #26 | s.25 | 12.; yerine yanlış Cevap (s.27) giriyor |
| test_1 #28 | s.29 | 7.; yerine yanlış Cevap (s.27) giriyor |
| test_1 #29 | s.31 | **2.** ama reranker eliyor |

Simülasyonda birleştirmeyle hedef 5 sorunun 5'inde doğru Cevap bağlama giriyor.

## 2. Değişiklik

**Yer: `src/ingest.py::extract_chunks_from_pdf`** (yalnız ingest; retrieval,
prompt, skorlayıcı değişmez).

**Kural R (belgeye özel değil):** bir sayfa iki koşulu birden sağlıyorsa önceki
sayfanın son chunk'ına eklenir:
1. Sayfa bu ingest'te OCR'lanmış olmalı (metin katmanı < `OCR_MAX_TEXT_CHARS`,
   sayfada resim var, OCR metin üretmiş).
2. Sayfanın ilk satırındaki bölüm numarası önceki sayfanınkiyle aynı olmalı.
   Numara regex'i: `^\s*-?(\d+(?:\.\d+)+)\.?\s`, örneğin `4.5.2.`.

- **Birleşik chunk'ın biçimi:** Metin "önceki\nOCR sayfası" olur. `page_info`
  `"sayfa N-M"` olur; aynı numarayla ardışık birden çok sayfa gelirse
  `"sayfa N-K"`.
- **Bugünkü korpusta etkisi:** Kural tam 5 çifti birleştirir: 22+23, 24+25,
  26+27, 28+29, 30+31.
  - Gramer PDF'indeki 18 ve 19. sayfalar aynı numaralı (4.3.4.1) ama OCR
    sayfası değil, bu yüzden birleşmez.
  - Fourier ve Z PDF'lerinde OCR sayfası yok.
- **Kod yapısı:** Birleştirme saf bir fonksiyona taşınır:
  `_merge_continuation_pages(pages: list[tuple[int, str, bool]]) -> list[tuple[str, str]]`.
  Girdi `(sayfa no, sayfa metni, OCR'landı mı)` listesi, çıktı bugünkü
  `(chunk_text, page_info)` listesi.
  - Bugünkü paragraf bölme (`"\n\n"`) aynen bu fonksiyonda kalır.
  - `extract_chunks_from_pdf` önce sayfaları toplar, sonra bu fonksiyonu
    çağırır.
  - Fonksiyon PDF ve OCR gerektirmeden test edilebilir.
- **`page_info` biçiminin tüketicileri:** "sayfa 22-23" biçimi kontrol edildi.
  - `components.py` kaynak kartında metni olduğu gibi gösteriyor.
  - `benchmark_eval.parse_sources` parantez içini atıyor.
  - Sayfa numarasını sayı olarak çözen bir yer yok.
  - Tek istisna geçmiş ölçüm script'i
    `experiments/madde24_ocr_alistirma/kapsam.py`: `\(sayfa (\d+)\)` regex'i
    birleşik sayfayı tanımaz. Script'in kendisi değişmez, README'sine not
    düşülür.
- **Chunk id'leri:** Yeniden ingest bu PDF'in chunk id'lerini değiştirir
  (`DELETE` + `INSERT`). id'ye dayanan bir tüketici yok; ölçümler `page_info`
  üzerinden yapılıyor.

## 3. DB yedeği ve geri dönüş

- **Yedek:**
  - Yeniden ingest'ten hemen önce repo kökündeki `rag.db`,
    `rag.db.bak_madde22_2026-10-12` olarak aynı dizine kopyalanır.
  - Mevcut `rag.db.bak` (26 Ağustos) dosyasına dokunulmaz.
  - `.gitignore`'daki `rag.db.bak` satırı `rag.db.bak*` olur ki yedek repoya
    girmesin.
  - Yedeğin doğruluğu iki değerle kontrol edilir: chunk sayısı 916 ve
    `(id, source, content, page_info)` sha1 parmak izi `f61f7119a6c8`
    (bugünkü DB).
- **Geri dönüş** (yeniden ingest başarısızsa ya da Adım 3'te ölçüt kalırsa):
  1. Uygulama ve koşan süreçler durdurulur.
  2. `rag.db.bak_madde22_2026-10-12` dosyası `rag.db` üzerine kopyalanır.
  3. Chunk sayısı 916'ya ve parmak izi `f61f7119a6c8`'e döndü mü doğrulanır.
  4. Adım 1 commit'i `git revert` ile geri alınır.

  Retrieval önbelleği süreç içinde tutulduğu için yeni süreçte DB'den yeniden
  yüklenir.

## 4. Başarı ölçütleri ve regresyon kontrolü

Üretim deterministik (madde 24 Adım 2: kol içinde 3/3 aynı cevap) → **tek
tekrar**. Karşılaştırma **aynı oturumda yedek DB ile yeni DB** arasında
yapılır (madde 29 kayması karışmasın). LLM çağrısı `db_path` sabitlenmiş
`get_top_chunks` ile (`experiments/madde22_ornek_cevap/llm_103.py` yöntemi).

**Başarı (hepsi gerekli):**
1. **Retrieval:**
   - Hedef 5 sorunun 5'inde doğru Cevap sayfası bağlamda olmalı.
   - Yeni DB'nin retrieval'ı simülasyonun "birleşik" sonucuyla aynı olmalı:
     147 sorunun kaynak listesi karşılaştırılır. Fark çıkarsa raporlanır.
     Fark iki yerden gelebilir: yeniden OCR'ın metni değişmesi ya da embedding.
2. **Hedef 5 soru (LLM):**
   - Hiçbiri TP → FN olmamalı.
   - F1 (v8 referanslarına karşı) en az 3/5'te artmalı.
   - 5 cevap elle gözden geçirilir: doğru küme/kural mı? F1 tek başına yetmez.
   - OCR bozukluğu yüzünden yanlış kalan cevaplar ayrıca not edilir. Örnek:
     s.23 üst simgeleri düz okuyor ("Ls.42 = { (aa) (cc)m b c b|").
3. **Etki alanının regresyonu:** Kaynak listesi değişen 18 sorunun tamamı
   test edilir.
   - Pozitiflerde TP → FN olmamalı.
   - Negatiflerde TN → FP olmamalı. #217 ve #102 TN kalmalı.
   - Bilinen FP'ler kapsam dışı: #103 (madde 24), #224 (madde 30), #101.
     Bunlar yalnızca raporlanır.
4. **Yeni dolgu riskleri:**
   - Her soruda, beklenen kaynağı başka bir doküman olduğu hâlde bağlamına
     birleşik bir chunk ("sayfa N-M") giren durumlar listelenir. Simülasyonda
     bunun bir örneği var: test_3 #87 (Fourier sorusu; 24-25 chunk'ı rerank
     0.001 ile giriyor).
   - #87 TP kalmalı ve cevabı gramer içeriğine atıf yapmamalı.
   - Listede #87 dışında yeni bir dolgu çıkarsa elle incelenir.
5. **Tam negatif set** (32) yeni DB'de bir kez koşulur:
   - FP artmamalı. Taban: bugünkü skorlayıcıyla 2/32 (#224, #232).
   - Tripwire (`uzun_ret_tripwire.py`) 0 eşleşme vermeli.

Prompt değişmediği için tam benchmark gerekmiyor. Gerekçe: bağlamı değişen
sorular retrieval'dan deterministik olarak biliniyor (18 soru). Adım 2'deki
147 soruluk retrieval karşılaştırması bu kümeyi gerçek DB üzerinde yeniden
doğrular. Kümenin dışına çıkan soru olursa o sorular da LLM ölçümüne eklenir.

## 5. Adımlar (her biri ayrı commit, adım sonunda durulur)

**Adım 1 — kod + birim testler (yeniden ingest yok).**
- `_merge_continuation_pages` fonksiyonu ve `extract_chunks_from_pdf`'in buna
  geçmesi.
- `tests/test_pdf_page_merge.py`:
  - Örnek+Cevap çifti birleşir, `page_info` "sayfa 22-23" olur.
  - OCR'lanmamış ama aynı numaralı sayfa (18/19 deseni) birleşmez.
  - Farklı numaralı OCR sayfası birleşmez.
  - Üç ardışık sayfa "sayfa N-K" olur.
  - Çok paragraflı önceki sayfada son chunk'a eklenir.
  - Bölüm numarası olmayan sayfa birleşmez.
  - Birleştirmenin olmadığı girdide çıktı bugünküyle aynıdır (geri uyum).
- Tam test seti: 98 + yeni testler geçmeli; tek bilinen kırık madde 17.

Plan dosyası bu adımla commit edilir.

**Adım 2 — yedek + yeniden ingest + retrieval doğrulaması** (Ollama + reranker;
LLM yok).
1. §3'teki yedek alınır ve doğrulanır. `.gitignore` güncellenir.
2. `delete_source("data/8-Baglamdan_bagimsiz_dilbilgisi.pdf")` ve ardından
   `ingest_single_file(...)` çağrılır. OCR yeniden koşar.
3. Yeni DB doğrulanır:
   - 911 chunk olmalı.
   - Birleşik 5 chunk'ın metni, yedekteki Örnek ve Cevap metinlerinin
     birleşimiyle karşılaştırılır. Bu, yeniden OCR'ın deterministik olup
     olmadığını gösterir; fark varsa diff raporlanır.
   - Diğer 906 chunk'ın içeriği değişmemiş olmalı. Gramer PDF'inin
     birleşmeyen 21 sayfası da yeniden ingest edildiği için metin
     karşılaştırması yapılır.
4. 147 soru yedek ve yeni DB üzerinde aynı oturumda koşulur. Sonuç
   simülasyonla karşılaştırılır (§4 ölçüt 1).
5. Sonuçlar `experiments/madde22_ornek_cevap/` altında `adim2_*` dosyalarına
   yazılır. DB'ler commit edilmez.

**Adım 3 — LLM ölçümü** (Foundry):
- Etki alanı (18 soru + Adım 2'de çıkabilecek ekler) iki DB'de, aynı oturumda,
  tek tekrar.
- Ardından tam negatif set yeni DB'de.
- §4 ölçütleri raporlanır ve PROVENANCE.md yazılır.
- Ölçüt kalırsa §3'teki geri dönüş uygulanır.

**Adım 4 — backlog:**
- Madde 22 kapatılır ya da kalan açık (örneğin OCR kalitesi) yeni maddeye
  taşınır.
- Madde 24'e #103'ün yeni DB'deki durumu yazılır.

## 6. Kapsam dışı

- **#103 (madde 24):** Birleştirmeyle çözülmüyor (simülasyon + LLM).
- **#224 (madde 30), #101:** Synthesizer dengesinden kaynaklanıyor, bu işin
  konusu değil.
- **Cevap sayfalarının OCR kalitesi** (üst simge kaybı): Birleştirmeden
  bağımsız. Adım 3 bunun cevaba etkisini gösterirse ayrı backlog maddesi
  açılır.
- **Sayfa 18/19 gibi OCR'sız aynı numaralı sayfalar:** Kural bilerek
  dışarıda bırakıyor. Genişletmek tüm PDF'lerin chunk yapısını değiştirir;
  ayrı karar.

## 7. Kritik dosyalar

- `src/ingest.py`: `extract_chunks_from_pdf`, yeni `_merge_continuation_pages`.
- `tests/test_pdf_page_merge.py`: yeni.
- `.gitignore`: `rag.db.bak*`.
- `experiments/madde22_ornek_cevap/`: Adım 2–3 script'leri ve sonuçları.
