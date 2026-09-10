# v6 — Sandbox Bos-Sonuc Korumasi

## Kosu bicimi
Negatif set **iki segmentte** kosuldu (201-215 ve 216-232), ayri Foundry
oturumlarinda. Sebep tek geçişte #215->#216 sirasinin servisi deterministik
olarak dusurmesi (bkz. docs/INFRASTRUCTURE_NOTES.md). Ana set (test_1..test_4)
set basina ayri surecte kosuldu.

Kosu araci: run_tests.py'nin KENDI fonksiyonlari (run_single_test,
free_gpu_memory) degistirilmeden import edildi; tek fark her satirin aninda
diske yazilmasi ve id araligi filtresi. RAG davranisi degismedi.

## Haric tutulanlar
- **test_2#43, test_2#53** — kronik 500/BFCArena. v5 kosusunda da AYNI iki
  soru hata verdi; karsilastirma iki taraftan da bunlar cikarilarak
  **98 soru** uzerinden yapildi (EXPERIMENTS.md'deki mevcut kural).
- Negatif sette v6'da hata YOK: 32/32 cevap alindi. v5 tarafinda #216
  altyapi hatasi verdigi icin **karsilastirma n=31 uzerinden** raporlanir;
  v6'nin kendi tam sayisi 2/32'dir.

## Skorlayici degisikligi uyarisi
Bu deneyde `check_is_not_found` de degisti (Gorev 2B). Karsilastirmanin
gecerli olmasi icin v5 negatif kosusu **yeni skorlayiciyla yeniden
skorlandi**; asagidaki tabloda her iki skorlayici da ayri gosterilir.

|  | eski skorlayici | yeni skorlayici |
|---|---|---|
| v5 negatif FP (n=31) | 7 | 6 |
| v6 negatif FP (n=31) | 2 | 2 |

Yani 7->6 duseusu YALNIZCA skorlayicidan (#231), 6->2 duseusu YALNIZCA
kod duzeltmesinden (2A) geliyor.
