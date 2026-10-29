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
