# Madde 24 — OCR'lı alıştırma sayfaları negatif sette FP üretiyor (2026-10-11)

Kod: `9555d64`. Girdi: v7 (`v7_refusal_clarity`) ve v8 (`v8_bm25_stopword`)
kayıtlı sonuçları, negatif set (32) + test_5 (15) = 47 soru. Sınıflar bugünkü
skorlayıcıyla yeniden hesaplanır. Servis gerektirmez.

| Dosya | Ne yapar |
|---|---|
| `kapsam.py` → `sonuc_kapsam.txt` | Gramer PDF'i / OCR sayfası (22–31) bağlama giren negatif sorular ve sınıfları; sonda madde 28 tripwire'ı |
| `../madde25_ret_tespiti/uzun_ret_tripwire.py` → `../madde25_ret_tespiti/sonuc_uzun_ret_tripwire.txt` | Negatif sette ret sayılan ve 120 karakterden uzun cevaplar (madde 28 koruması); taban: tek eşleşme v5 #231 |

## OCR değişikliği (`dffb6a5`) ne yaptı

`extract_chunks_from_pdf`: metin katmanı 50 karakterden kısa **ve** resim
taşıyan sayfa OCR'lanır, metin sayfanın kendi başlığının altına eklenir (bir
sayfa = bir chunk). Kurala yalnız 8-Baglamdan_bagimsiz_dilbilgisi.pdf sayfa
22–31 uydu: Örnek/Cevap 2, 5, 6, 7, 8. Hem Örnek hem Cevap sayfaları
**kasıtlı** OCR'landı (amaç test_1 #24–#29'u cevaplanabilir yapmaktı); "sızma"
yok. Örnek sayfaları alıştırma talimatı taşıyor ("…CNF'ye dönüştürünüz",
"…dilbilgisi tanımlayınız"), açıklama değil.

## Mekanizma (retrieval debug, top_k=5)

- **#224 (CNF adımları):** sayfa 22 dense 1., BM25 1., rerank 0.60 — her katmanda
  en alakalı. Belgede "Chomsky"/"CNF" geçen **tek** sayfa bu ve yalnız bir
  ödev talimatı. Retrieval hatalı değil, içerik türü yanlış. v7'de aynı
  18/2/16 sayfalarıyla ret (TN); sayfa 22 eklenince model sayfa 18'in yararsız
  değişken algoritmasını "CNF adımları" diye sunuyor.
- **#103 (pompalama lemması):** belgede lemma yok. Sayfa 24/28 BM25 2./3. sırada
  (kısa metinde "bağlamdan bağımsız … dilbilgisi" tekrarı). Rerank skorlarının
  hepsi < 0.04 — reranker hiçbir adayı alakalı bulmuyor ama `RERANK_TOP_N=4`
  her zaman 4 parça geçiriyor (dolgu).
- Chunk'lama karışması yok: her OCR sayfası ayrı chunk.

## Kapsam (`sonuc_kapsam.txt`)

47 negatif sorudan 6'sında gramer PDF'i bağlamda; v8'de 5'ine OCR sayfası
giriyor (#217, #224, test_5 #101, #102, #103). Sınıf değişen 2: #224, #103
TN → FP. #217, #102 TN kaldı. **#101 v7'de de FP** (OCR yokken sayfa 18/19'dan
aynı CNF uydurması) → OCR'a atfedilmez; zayıflık OCR'dan bağımsız da var.

## Tripwire (madde 28)

v7, v8: 0 eşleşme. Not: v8 #103 cevabı zaten melez biçimde ("…doğrudan bilgi
verilmemiştir, bu nedenle:") — FP sayılıyor, çünkü "verilmemiştir" ret
listesinde/çerçevesinde yok. Liste genişletilirse bu cevap tripwire'a düşer.
