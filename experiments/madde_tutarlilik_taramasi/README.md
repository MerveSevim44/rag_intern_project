# Deterministik tutarlılık/groundedness taraması — NEGATİF SONUÇ (2026-11-10)

`src/` ve `evaluation/` bu çalışmayla DEĞİŞMEZ. Betik: [tarama.py](tarama.py) (yalnız pilot modu; 94 soruda ÇALIŞTIRILMADI).

## Fikir
LLM judge kullanmadan, final cevaptaki somut değerlerin (sayı, yüzde, özel ad) sentezleyiciye giden ham
bağlamda var olup olmadığını taramak. Ham bağlam için ek instrumentasyon gerekmez: `birlesik.csv`'deki
`context` sütunu semantik RAG'de chunk metnini, code_interpreter'da `[KESİN HESAPLAMA SONUCU]` doğal dil
özetini (`result_to_natural_language` çıktısı, sandbox'ın ham sonucu değil) taşır.

Eşleşme: önce birebir (normalize sayı / ad alt-dizesi), sonra türetilmiş (bağlamdaki sayı çiftlerinin
toplam/fark/oran/yüzde-fark kombinasyonu, tolerans ±0,5 veya ±%1); ikisi de yoksa "şüpheli". 0/1/2/3/100
"düşük öncelik".

## Pilot (16 satır) — sıfır gerçek pozitif
Sentetik sağlık testinde (bağlamda olmayan sayı + ad) doğru işaretledi; yani yöntem bozuk değil. Ama bilinen
doğru ve bilinen yanlış 16 gerçek satırın **hepsi TEMİZ** çıktı:
test_2 #43, #44, #51, #53, #57, #41, #45, #47; test_4 #91; test_3 #78, #82, #83, #85, #87, #89; test_1 #19, #20, #28, #30.

## Neden: üç hata sınıfının hiçbiri "bağlamda olmayan değer" değil
1. **Yanlış atama (#53, madde 38/41):** "12" ve "4" bağlamda birebir var ("12-4 saat arasındadır"); sorun
   değerlerin yanlış kişi/alana bağlanması. Bag-of-values göremez.
2. **Bağlamın kendisi yanlış (madde 18: #44/#51/#57):** sandbox özeti baştan yanlış (33.09, 1.50);
   `ask()` sadakatle tekrarlıyor. Cevap bağlamla birebir uyuşur — judge'ın da bilinen kör noktası.
   Yalnız ground truth'a karşı yeniden hesapla yakalanır (`experiments/madde11_toparlanma/ayir_53.py` tarzı).
3. **Sembolik/kavramsal hatalar (Fourier #82/83/85/89/78/87, CFG #19/20/28/30, profil şema #41/45/47):**
   yanlış formül katsayısı, yanlış türetilmiş küme, çelişkili tanım. Taranacak "somut değer" yok.

## Neden kayda değer
Zor bulunan bir negatif sonuç: bu kod tabanındaki içerik hataları "model sayıyı uydurdu" değil, "var olanı
yanlış bağladı" ve "bağlam/hesap zaten yanlış" biçiminde. Ucuz deterministik tarama bu dağılıma uymuyor.

## Karar
Otomatik tarayıcı inşa edilmiyor. Triyaj mekanizması 147 satırlık LLM-judge skorlarıdır (+ elle gerçek
okuma). **Gündeme gelme koşulu:** 1. sınıf (yanlış atama, #53 tipi) örnek sayısı belirgin büyürse, alan-özel
bir (kişi, alan, değer) üçlü-çıkarma yaklaşımı yeniden değerlendirilebilir; regex'in ötesinde, soru tipine
özel bir ayrıştırıcıdır ve maliyeti o zaman örnek sayısıyla tartılmalıdır.
