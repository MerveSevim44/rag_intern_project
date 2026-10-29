# Madde 34 Adım 1 — #82: cevap chunk'ı bağlamda 1., model neden reddediyor?

Soru: test_3 #82 "Zamanda çarpımın frekansta konvolüsyona karşılık geldiği özellik
hangi türetme ile gösterilmiştir?" Cevap chunk'ı 4185 (Fourier sayfa 12 "Sinuzoidal
Genlik Modülasyonu"), `RAG_DENSE_FORCE_TOP_N=1` ile nihai bağlamda 1. sırada.

## 1a — Kapsam (`kapsam.py` → `sonuc_kapsam.txt`; LLM yok)

"Bozuk semboller" rastgele bozulma değil: **Symbol fontunun Private Use Area kod
noktaları** (U+F028 `(`, U+F077 `ω`, U+F064 `δ`, U+F0F2 `∫` …). Mekanik olarak
eşlenebiliyorlar (`varyant.pua_esle`; 4185'te tablo dışı kod noktası 0). Ayrıca
büyük parantezler ayrı satıra kaymış (düzen sorunu).

| Kaynak | chunk | EN gövde | PUA'lı | EN + PUA |
|---|---|---|---|---|
| lsarSist-H8_FourierTransform.pdf | 14 | 8 | 13 | 8 |
| lsarSist-H9_ZTransform.pdf | 19 | 14 | 11 | 8 |
| diğer tüm kaynaklar | 865 | 13 | 0 | 0 |

- Desen #82'ye özel değil, **Fourier/Z PDF'lerinin geneli**. test_3'ün 30 sorusunun
  hepsinin bağlamında EN chunk var; 20'sinde 1. sıradaki chunk EN.
- Bu 20 sorunun v8 sınıfı (en son tam koşu, ESKİ sistem; kaba gösterge):
  **18 TP**, 2 FN (#79 — retrieval, madde 32'de çözüldü; #82).
- **Aynı chunk 4185** bağlamında olan #83 (1. sırada), #84 ve #89 v8'de TP;
  bugünkü bağlamla yeniden koşuldu (1b), üçü de TP.
- Sonuç: "İngilizce gövde + PUA sembol + Türkçe soru" modelin genelde başa çıktığı
  bir durum; #82'nin retini tek başına açıklaması beklenmiyor.

## 1b — İzole varyantlar (`uretim82.py`, `varyant.py` → `sonuc_uretim82*.txt`)

Foundry qwen2.5-7b, temperature=0, her biri 2 tekrar (tekrarlar 20/20 birebir aynı).
Bağlam: `retrieve(soru, dense_force_n=1)` = [4185 s.12, 4187 s.14, **4333
dilbilgisi s.7 "4.2 Türetme Ağacı"**, 4184 s.11]. Varyantlarda yalnız belirtilen
şey değişir; `src/` ve `rag.db` değişmez.

| Varyant | Ne değişti | Sınıf | Cevap |
|---|---|---|---|
| V0 | — | FN | "Bu bilgi dokümanlarda bulunamadı." |
| A1 | 4185: PUA → Symbol glifi (mekanik), satır düzeni aynı | FN | ret |
| A2 | 4185: formüller elle kurulmuş, gövde İngilizce | FN | ret |
| B | 4185: gövde Türkçe, formüller bozuk | FN | ret |
| C | 4185: Türkçe + formüller elle (tavan) | FN | ret |
| A1T | (ek) mekanik eşleme bağlamdaki tüm chunk'lara | FN | ret |
| **X3** | (ek) 3. chunk (4333 "Türetme Ağacı") çıkarıldı, bağlam 3 chunk | **TP** | "… Sinüzoidal Genlik Modülasyonu türetmesi ile gösterilmiştir." |
| **X3R** | (ek, X3'ün kontrolü) 4333 yerine rerank 5.'si (4341, dilbilgisi s.15 — o da konu dışı), bağlam 4 chunk | **TP** | "Multiplication in the time domain is convolution … Y(ω) = F(ω) ∗ (πδ(ω+ω0) + πδ(ω−ω0)) …" |
| kontrol #83 / #84 / #89 | bugünkü N=1 bağlamı (4185 içinde) | TP / TP / TP | — |

- **Dil (B) ve sembol (A1/A2/A1T) değişikliklerinin hiçbiri reti kaldırmıyor; ikisi
  birlikte (C, tavan) de kaldırmıyor.**
- **Reti kaldıran tek değişiklik 4333'ün bağlamdan çıkması.** X3R, etkinin "daha az
  chunk" olmadığını gösteriyor: yerine başka bir konu dışı dilbilgisi chunk'ı gelince
  de cevap geliyor. Belirleyici olan sorudaki "türetme" kelimesini taşıyan, başka
  alandaki ("türetme ağacı", formal diller) bir chunk.
- Doğruluk (elle, tek değerlendirici; madde 36 kuralı gereği not): X3 **kısmen**
  (doğru örneği adlandırıyor, konvolüsyon/δ adımı yok); X3R **kısmen** (özelliği ve
  konvolüsyon formülünü veriyor, 1/2π yerleşimi bozuk, örneği "türetme" diye adlandırmıyor).
- 4333 bayrak kapalıyken (n0) de #82'nin bağlamında; test_1'de 4 soruda (#5, #11, #13,
  #27) kendi alanında meşru olarak bağlama giriyor.

## Ölçülmeyen

- Mekanizmanın **kapsamı**: kaç pozitif soruda, sorudaki bir terimle eşleşen ama başka
  kaynaktan/alandan gelen chunk bağlamda ve ret tetikliyor? (#56 adayı.)
- Neden ret: model "türetme"yi formal dil anlamıyla eşleyip 4185'i "türetme değil"
  sayıyor olabilir; prompt'a bakılmadı.
- Müdahale adayları (karar yok): bağlamda beklenen kaynaktan farklı kaynak/alan
  chunk'larını eleme (ör. kaynak tutarlılığı / rerank skor eşiği — madde 24 bağıl eşik
  ile ilişkili), prompt'ta "konu dışı parçaları yok say" talimatı. Hepsi madde 32/33
  disipliniyle tam benchmark + negatif sette ölçülmeli.
- PUA eşlemesi #82'yi çözmüyor ama ayrı bir temizlik olarak (gösterim, madde 31 B ile
  aynı aile) değerlendirilebilir; etkisi ölçülmedi.

## Not — koşu ortamı

İlk koşu, Foundry LLM yüklüyken Ollama embedding runner'ı çöktüğü için (madde 32 #11
ile aynı hata) üretime gelmeden düştü. Script bağlamları LLM yüklenmeden önce kuruyor;
`num_gpu=0` vektörleri değiştirdiği için (madde 29) kullanılmadı. X3R koşusundan önce
önceki koşudan kalan Foundry modeli boşaltıldı (sistem RAM'i yetmiyordu).

# Madde 34 Adım 2 — genelleme: desen başka FN'lerde de var mı?

## 2a — Tarama (`genelleme.py` → `sonuc_genelleme.txt`; LLM yok)

Bugünkü sistemle tam pozitif koşu yok; FN evreni = v8 tam koşu ∪ madde 32 n0 ∪ madde
33 prod (yalnız pozitif): test_2 #50, #56; test_3 #79, #82; test_4 #91, #100. 115
pozitifin bugünkü bağlamı canlı kuruldu (N=0 ve N=1). Aday ölçütü: kaynak
`beklenen_kaynak`'tan farklı + soruyla ≥1 ortak stem + BM25 > 0.

| FN | Durum |
|---|---|
| #50 | desen yok (bağlam aynı kaynak, konuyla ilgili) |
| #56 | ölçüt göremiyor (tek JSON); cevap `$.metadata` 1. (rerank 0.317), 2–4. konu dışı profiller (0.0003–0.0005; ortak `alan`, `ver`) → **aynı kaynak içi aday** |
| #79 | N=0'da cevap chunk'ı yok (retrieval, madde 32); N=1'de TP → aday değil |
| #82 | 4333 (Adım 1'de doğrulandı) |
| #91 | madde 33 sonrası cevap 0.98 ile 1.; "aday" yalnız `in` paylaşıyor → aday değil |
| #100 | cevap 4358 1. (0.563); 3./4. test1.txt 4353 (0.0043, `merak`, `sayfa`), 4355 (0.0014, `sayfa`) → **aday** |

**Taban oranı:** v8'de TP olan 91 pozitifin 16'sının bağlamında da aday chunk var.
Ölçüt tek başına ret öngörmüyor (Adım 1'deki 4341 de `türetme` paylaşıyordu, zararsızdı).

## 2b — X / XR doğrulaması (`dogrulama.py` → `sonuc_dogrulama.txt`)

N=0 bağlamı, 2 tekrar (18/18 birebir aynı). X = şüpheli çıkarılır; XR = yerine aynı
havuzun rerank sırasındaki sonraki chunk'ı (uzunluk aynı).

| Soru | V0 | Şüpheli | X | XR |
|---|---|---|---|---|
| #56 | FN | 3777+3773+3775 (profiller) | **TP** | **TP** (yerine 3779, 3778 profil + 4345 dilbilgisi) |
| #100 | FN | 4353 | FN | FN |
| #100 | | 4355 | **TP** | **TP** |
| #100 | | 4353+4355 | **FN** (bağlam yalnız 4358+4357) | TP |

- **#56: kurala göre doğrulandı.** Ama XR'de yerine gelenler de benzer konu dışı
  profiller; zararlı olan "anahtar kelime eşleşmesi" değil, o belirli chunk'lar.
  Doğruluk (elle): X/XR cevapları genel geçer ve "hangi alanlarda belirtilmemiş"
  diyor; GT somut alanlar istiyor (publicContact, hafta sonu kuralları …) →
  **yanlış** (`classify_answer` TP sayıyor; madde 36).
- **#100: kırılgan, doğrulanmış sayılmamalı.** 4355 tek başına X/XR testini geçiyor,
  ama iki şüpheli birlikte çıkarılınca (yalnız test2.txt chunk'ları kalınca) yine
  ret. Ret, "dikkat dağıtıcı var/yok" ile monoton değil; yorum isteyen soruda model
  sınırda. Doğruluk: TP cevapları kısmen (X[4355]'te test1.txt'ten karışma var).
- **Doğrulanan:** #82 (Adım 1) ve #56 → 2 soru. Ortak nokta: zararlı chunk'ların
  rerank skoru cevap chunk'ına göre düşük (#82: 0.0032 / 0.0149 = 0.22; #56: ≤0.0005 /
  0.317 ≈ 0.001), ama XR'de onların yerine gelen zararsız chunk'lar daha da düşük.
  Mutlak eşik ayırmaz; bağıl eşik (madde 24) aday — ölçülmedi.

# Madde 34 Adım 3 — (a) bağıl rerank eşiği ön-testi (`on_test.py` → `sonuc_on_test.txt`)

Sweep değil, tek senaryo. #82 N=1 bağlamında rerank / ilk chunk oranı: 4185 1.000,
4187 0.297, **4333 0.216**, 4184 0.206. 4333'ü eleyen her eşik 4184'ü de eler
(4184 daha düşük). Eşik 0.25 → bağlam [4185, 4187].

- Sınıf: **TP** (2/2, birebir aynı). 4184 olmadan da ret yok.
- İçerik (elle, GT'yle): **kısmen.** "Sinüzoidal Genlik Modülasyonu türetmesiyle
  gösterilmiştir" (sorunun asıl sorduğu kısım doğru), ama eklenen formül yanlış:
  `Y(ω) = F(ω+ω0) * F(ω−ω0)` (doğrusu ½F(ω+ω0) + ½F(ω−ω0)). X3 ile aynı seviye.

**Karar: sweep yapılmadı, madde 34 kapatıldı.** Ön-test kapısı "doğru geliyorsa sweep"
idi; cevap kısmen. Getiri tavanı tek soru (#82, kısmen) ve yalnız
`RAG_DENSE_FORCE_TOP_N=1` açıkken (varsayılan kapalı); #56'nın kazancı gerçek değil
(madde 38). Bağıl eşik bulgusu madde 24'e girdi olarak bırakıldı.
