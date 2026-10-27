# Madde 32 — doğru dosya geliyor, doğru chunk gelmiyor

Adım 1, yalnız ölçüm (LLM/Groq/Foundry yok; Ollama bge-m3 + reranker). Tarih: 2026-10-27.

| Dosya | Ne |
|---|---|
| `katman.py` → `sonuc_katman.txt`, `katman.jsonl` | 3 FN sorusunda cevap chunk'ının her katmandaki sırası ve skoru |
| `kapsam.py` → `sonuc_kapsam.txt`, `kapsam.jsonl`, `log_kapsam.txt` | Tam benchmark pozitif soruları (100; semantic_rag 87) üzerinde kaba kapsam |

## Cevap chunk'ları (elle, GT referansı + anahtar kelimelerle)

- #79 → 4183, Fourier sayfa 10 "Ölçekleme (Scaling)": *Extent in time domain is inversely proportional to extent in freq…*
- #82 → 4185, Fourier sayfa 12 "Sinuzoidal Genlik Modülasyonu": *Multiplication in the time domain is convolution in the frequency domain*
- #91 → 4227, test1.txt paragraf 1: *… devasa bir kütüphane yükselirdi: Gümüş Yaprak.*

## Katman sonucu

Sağlama: havuzun rerank sonrası ilk 4'ü, normal `retrieve()` çıktısıyla üç soruda da birebir aynı.

| | Dense | BM25 | Hibrit (RRF) | Havuz (TOP_K=8) | Reranker (havuzda olsaydı) |
|---|---|---|---|---|---|
| #79 | **1/911** (0.654) | 0 | 12. (0.500; eşik 0.520) | dışında | **1.** (0.658; havuzun en iyisi 0.015) |
| #82 | **1/911** (0.503) | 0 | 17. (0.500; eşik 0.606) | dışında | **1.** (0.015; 4. eşik 0.0016) |
| #91 | 12/911 (0.423) | 0 | 34. (0.423; eşik 0.657) | dışında | 5. (0.0034; 4. eşik 0.0037) |

- **#79/#82: kayıp RRF birleştirmesinde.** Dense ve reranker doğru chunk'ı açık ara
  buluyor. BM25=0 olan chunk RRF'ten BM25 katkısı almıyor (`bm25_contrib`), bu
  yüzden normalize skoru en fazla 0.5 oluyor. İki listede de orta sırada olan chunk'lar
  onu geçiyor (#79: dense'te 348. ama BM25'te 7. bir profil havuza giriyor). BM25'in
  0 olmasının nedeni Türkçe sorunun İngilizce slayt gövdesiyle hiç token
  paylaşmaması.
- **#91 farklı:** (1) stemmer tutarsızlığı: "kütüphane"→`kutupha`, "kütüphanenin"→`kutuphane`
  (madde 6 Sorun B ailesi) → BM25=0; (2) cevap iki chunk'a bölünmüş: paragraf 1'de
  "Gümüş Yaprak" var ama "Alis" yok, Alis–kütüphane bağı paragraf 2'de. Havuza
  girse bile reranker eşiğin hemen altında bırakıyor. RRF düzeltmesi tek başına çözmez.

## Kapsam

- **B (GT'den bağımsız, mekanizma): dense #1 chunk havuz dışında ve BM25=0 → yalnız
  #79 ve #82.** B'deki diğer 3 soru (test_1 #29, test_2 #36, #38) BM25>0; dense #1
  orada başka bir chunk, bu mekanizma değil.
- **A (GT terimi): beklenen dosya bağlamda, GT terimlerinin hiçbiri yok → 14 soru,
  gürültülü.** 11'i v8'de TP. 11'i Fourier PDF'inden: GT terimleri Türkçe
  parafraz, PDF metni İngilizce ve semboller Symbol fontundan bozuk (``…);
  doğru chunk gelse de terim eşleşmiyor. v8'de FN olan 3'ü tam olarak #79, #82, #91.
  #24/#28 OCR'lı alıştırma sayfaları (madde 31 ailesi).
- Sonuç: bugünkü benchmark'ta RRF mekanizmasının kapsamı **2 soru**; #91 ayrı.
