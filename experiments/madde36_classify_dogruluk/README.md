# Madde 36 — `classify_answer` etiketi gerçek doğrulukla ne sıklıkla çelişiyor?

## Küme

Madde 32 Adım 2 (`uretim_n{0,0_tekrar11,1,3,5}`) ve madde 33 Adım 1 (#91 oracle'ları)
cevaplarının tekil (set, id, cevap) çiftleri: **73 çift, 45 soru** (pozitif 52,
negatif 21). Sınıf güncel GT ile (#214 düzeltmesi sonrası). `ciftler.json`.

**Not:** bu cevapların hepsi önceden elle incelenmiş değildi. Madde 32/33'te
yalnız sınıfı değişen sorulara (#79, #82, #214, #222, #226, #11) ve #91
oracle'larına bakılmıştı; "TP→TP" kalanların doğruluğu bu ölçümde ilk kez
değerlendirildi.

## Yöntem

Doğruluk etiketi elle, soru + GT referansıyla (2026-10-29, **tek değerlendirici:
Claude**; ikinci göz yok). `D` doğru · `K` kısmen (çekirdek kısmen doğru, eksik
ya da içinde yanlış iddia) · `Y` yanlış · `R` ret · `B` bozuk (yarım cümle,
iddia yok). Etiketler `olcum.py` içinde (`J`), sonuç `degerlendirme.json`.

## Sonuç (`sonuc_olcum.txt`)

| Etiket | Sayı | Elle doğruluk |
|---|---|---|
| FN | 5 | R=5 → **0 çelişki** |
| TN | 17 | R=17 → **0 çelişki** |
| FP | 4 | Y=3, B=1 → 1 çelişki (#222 yarım cümle, uydurma yok) |
| TP | 47 | **D=16, K=16, Y=15** → 15 çelişki (%32) |

- **Ret tespiti güvenilir:** FN/TN'de çelişki yok; FP'de tek sınır vakası #222
  (madde 25/26 ailesi, bilinen).
- **TP doğruluk demek değil:** `classify_answer` tasarım gereği yalnız "ret mi,
  cevap mı" ayrımı yapıyor. TP'lerin üçte biri yanlış, üçte biri kısmen doğru.
  Yanlış örnekler: #44 "-1.95 saat farkıyla ayırt edilirler" (anlamsız
  code_interpreter çıktısı), #45 uydurma slug kuralı, #60 histogram eğilimi
  yanlış, #87 N3/N5 "genlik sabit", #98 03.14 zamanlamasını ters kurmuş,
  #91 G4 başlığı kütüphane adı sanıyor, #29 N0 Çince sızıntı + yanlış gerekçe.

## Madde 32 Adım 2'ye etkisi (TP→TP kalan pozitiflerde doğruluk, N0'a göre)

| N | Kötüleşen | İyileşen |
|---|---|---|
| 1 | 0 | 0 |
| 3 | 1 (#87 K→Y) | 2 (#11 K→D, #78 K→D) |
| 5 | 2 (#30 K→Y, #87 K→Y) | 6 (#11, #26, #29, #41, #76, #78) |

- **N=1 önerisi geçerli kalıyor:** doğrulukta da değişim yok.
- **"Pozitiflerde yan etki yok (TP→FN 0)" ifadesi N=3/5 için eksikti:** sınıf
  aynı kalırken doğruluk iki yönde de değişiyor. Bağlam değişikliği ölçümleri
  sınıf geçişiyle yetinmemeli.
