# Deney Kaydi

Bu dosya, RAG hattinda yapilan olculmus deneyleri ve her birinin hangi klasore
karsilik geldigini kaydeder. Amac: bir kosunun hangi kod durumuna ait oldugunu
klasor adindan tahmin etmek zorunda kalmamak.

## Ozet

Tum rakamlar **98 soruluk temiz set** uzerinden (kronik GPU bellek hatasi veren
`test_2#43` ve `test_2#53` her deneyden cikarildi — bkz. "Bilinen sorunlar").
Negatif set FP'si her zaman **tam 32 soruluk** kosudan gelir.

| Deney | FN | F1 | ROUGE-L | Semantik | EM | Soft | Negatif FP | Durum |
|---|---|---|---|---|---|---|---|---|
| v2 — baseline + trim duzeltmesi | 23 | 39.6 | **36.6** | 73.9 | 6.1 | 9.2 | 7/32 | superseded |
| v3 — yumusatma + kirpma | **10** | 32.1 | 27.9 | 75.6 | 3.1 | 12.2 | 8/32 | ❌ alinmadi |
| **v5 — yumusatma + kisalik** | 13 | **40.0** | 35.5 | **77.5** | 6.1 | **12.2** | **7/32** | ✅ **aktif** |
| v4 — basarisiz kosu | — | — | — | — | — | — | — | ⚠️ gecersiz |

---

## v2 — Baseline + Trim Duzeltmesi
- **Commit:** `e5287b5`
- **Klasor:** `experiments/v2_baseline_trim/`
- **Degisiklik:** Trim mantigi formul + ret kuyrugu profilini artik kirpmiyor;
  yabanci alfabe (dil sizintisi) icin deterministik son kontrol katmani.
- **Sonuc (98 soru):** FN 23, F1 39.6, ROUGE-L 36.6, Semantik 73.9, EM 6.1,
  Soft 9.2, Negatif FP 7/32
- **Not:** FN orani %25 ile yuksekti; sonraki deneylerin cikis noktasi bu oldu.
  Negatif set kosusu birebir eslesmiyor — bkz. `v2_baseline_trim/PROVENANCE.md`.
- **Durum:** Superseded (v5 tarafindan)

## v3 — Yumusatma + Kirpma Denemesi
- **Commit:** commit edilmedi (kod v5'te devam etti)
- **Klasor:** `experiments/v3_soften_and_chunk/`
- **Degisiklik:** (1) Iki dalli ret kurali — baglamda kismi/dolayli bilgi varsa
  cevap ver. (2) `MAX_CHUNK_CHARS` 1500 -> 2900, `MAX_CONTEXT_CHARS` 6000 -> 9000.
- **Sonuc (98 soru):** FN **10** (en iyi), F1 32.1, ROUGE-L 27.9, Semantik 75.6,
  EM 3.1, Soft 12.2, Negatif FP **8/32**
- **Neden production'a alinmadi — iki bagimsiz sebep:**
  1. **F1/ROUGE-L/EM gerilemesi.** Cevap uzunlugu medyan 19 -> 48 kelimeye cikti;
     token-F1 uzunlugu cezaladigi icin F1 39.6 -> 32.1 dustu. Bu bir olcum
     artefakti AMA ayni zamanda gercek bir kullanici deneyimi maliyeti.
  2. **Halusinasyon artisi.** Negatif FP 7 -> 8; yeni FP tam olarak
     "Yanlis On Kabul" kategorisinde (#224), yani iki dalli kural modeli
     yanlis oncullu tuzak sorularda daha savunmasiz birakti.
  3. **Kirpma degisikligi ayrica geri alindi:** context ~8700 karaktere cikinca
     Foundry Local 8GB VRAM'de cokuyor (test_2'de 30 sorunun 8'i "Connection
     error"). Olculen kazanc marjinaldi (6 sondadan 1'i).
- **Durum:** ❌ Production'a alinmadi; (1) numarali degisiklik v5'te kisalik
  kisitiyla birlikte korundu, (2) numarali degisiklik tamamen geri alindi.

## v4 — Basarisiz Kosu
⚠️ **Gecersiz, sonuc yok.** Foundry Local servisi kosu sirasinda uc kez coktu:
once `test_4`'un 10 sorusu, sonra `test_2`'nin 4 ve tekrar denemede 8 sorusu
"Connection error" aldi. Skorlayici hata satirlarini ret olarak tanimadigi icin
bunlari **TP sayip** metrikleri yapay olarak iyi gosterdi (F1 39.6, FN 12) —
bu rakamlar kullanilmamalidir. Cokmelerin sebebi v3'un kirpma degisikligiydi.
Klasor: `archive/reports_old/report_v4_invalid/`, `archive/reports_old/results_v4_invalid/`

## v5 — Yumusatma + Kisalik Kisiti (FINAL / production onerisi)
- **Commit:** `9858227`
- **Klasor:** `experiments/v5_soften_and_brevity/`
- **Degisiklik:** Iki dalli ret kurali (baglamda kismi bilgi varsa en iyi cevabi
  ver; yalnizca hic ilgili bilgi yoksa ret) + kisalik kisiti (soruyu/baglami
  tekrar etme, giris cumlesi kurma, ozet ekleme). v3'un kirpma degisikligi
  geri alindi.
- **Sonuc (98 soru):** FN 23->13, F1 39.6->40.0, ROUGE-L 36.6->35.5,
  Semantik 73.9->77.5, EM 6.1->6.1, Soft 9.2->12.2,
  Negatif set FP 7/32->7/32 (degismedi, kategori dagilimi da ayni)
- **Takas:** Cevap uzunlugu 19 -> 28 kelime, ROUGE-L -1.1. Kisalik kisiti
  FN'i v3'un 10'undan 13'e cikardi — 3 FN karsiliginda F1'de ~8 puan ve
  FP'de 1 birim kazanildi; takas bilincli.
- **Durum:** ✅ Commit edildi, aktif kod

---

## Kalan is

**13 FN'in tamami "retrieval iskasi" grubunda:** dogru chunk top-16'da bile yok,
dolayisiyla prompt tarafinda cozulemez. Ornek: `test_4#91` ("kutuphanenin adi?")
— cevabin gectigi paragrafta soru terimi ("Alis") hic gecmiyor, yani multi-hop /
coreference sorunu. Cozum chunking veya embedding tarafinda aranmali.

**Olculup curutulen hipotezler** (tekrar denenmeden once bu notlara bakin):
- *Lost-in-the-middle:* context zaten yalnizca 3 chunk ve dogru dokuman 1. sirada.
- *Chunk sayisini artirma:* 3 -> 8'de referans kapsamasi medyan 0.130 -> 0.154;
  context 4 katina ciksa bile kazanc yok.
- *Dokuman-dengeli aday havuzu:* `#91`'de `test1.txt` zaten top-16'nin 7'sini
  aliyor — sorun `728_profiles.json`'in havuzu bogmasi degil.
- *Aday havuzunu buyutme:* `top_k` 8/32/64'te oracle chunk final-3'e 0/5 girdi.

## Bilinen sorunlar

- **`test_2#43` ve `test_2#53`** kronik GPU bellek hatasi veriyor (en agir
  code_interpreter sorulari; 5 denemede de 500/BFCArena). Karsilastirmalarda
  iki taraftan da cikarilir. Ilk teshis kosusunda da ayni iki soru hata vermisti,
  yani prompt degisiklikleriyle ilgisiz.
- **`retrieval_match` metrigi yaniltici:** `compute_retrieval_rank` dosya adi
  duzeyinde eslesme yapiyor, chunk duzeyinde degil. Korpusta 10 dokuman var ve
  `test1.txt` 9 chunk — o dosyadan gelen herhangi 3 chunk otomatik "Evet, sira=1"
  veriyor. "Retrieval %99 dogru" rakami bu yuzden chunk isabetini olcmez.
- **Skorlayici hata satirlarini TP sayiyor:** `HATA: ...` ile baslayan cevaplar
  ret kalibina uymadigi icin TP'ye yaziliyor. Kosu sonrasi
  `d.cevap.str.startswith('HATA').sum()` ile kontrol edin.
- **`benchmark_eval.py --all` varsayilan olarak kok dizinden okur.** Yeni bir
  kosuyu skorlarken `results_dir` vermezseniz sessizce eski CSV'leri skorlar:
  `evaluate_all(output_dir=..., results_dir='...')`.

## Yeni deney nasil eklenir

1. Kosuyu `experiments/vN_kisa_aciklama/` altina yaz: `results/` (ham cevaplar
   + loglar) ve `report/` (skorlanmis CSV + summary JSON). Kokte klasor birakma.
2. Skorlarken `results_dir`'i acikca ver ve once hata satirlarini kontrol et.
3. Negatif seti **tam 32 soruyla** kos — orneklem yeterli degil. Izole A/B
   testleri modelin nondeterminizmi yuzunden yaniltici olabiliyor (v3'te tam
   olarak bu oldu: izole testte FP 7/32 cikti, tam kosuda 8/32).
4. `EXPERIMENTS.md`'ye ayni sablonla bir bolum ve ozet tabloya bir satir ekle.
5. Kosu gecersiz/kirli ciktiysa (altyapi hatasi, yarim kalma) hemen
   `archive/reports_old/` altina tasi ve "gecersiz" olarak isaretle — kokte
   birakma, cunku bir sonraki kisi rakamlari gecerli sanabilir (v4 tam boyleydi).
6. Ayni anda birden fazla degisken degistirme; degistirdiysen hangisinin neyi
   etkiledigini ayiramazsin.
