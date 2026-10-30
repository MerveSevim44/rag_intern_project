# Madde 24 ön-test — bağıl rerank eşiği #103 FP'sini kaldırabilir mi?

Sweep değil, tek senaryo (`on_test103.py` → `sonuc_on_test103.txt`). Bağıl eşik en
yüksek chunk'ı her zaman tutar; üst sınır = yalnız o chunk'ın kaldığı eşik (0.944).
`--tarama` (115 pozitifte bağlam değişimi) koşulmadı: kapı geçilmedi.

| Senaryo | Bağlam (rerank) | Sonuç (2 tekrar, birebir aynı) |
|---|---|---|
| V0 | s.16 0.036, s.2 0.032, s.18 0.013, s.24-25 0.012 | **TN** |
| Üst sınır | s.16 | **TN** |

Madde 34'ün 0.25 eşiği hiçbir chunk'ı elemiyor (en düşük oran 0.347).

**Sonuç:** #103 FP'si bugünkü sistemde tekrar etmiyor; kaldırılacak FP yok. Son kayıtlı
FP madde 22 Adım 3'te (2026-10-13; bağlam s.16, s.2, s.28-29, s.22-23). Madde 32'nin
2026-10-28 kaydında bağlam bugünkü hâlinde. Kesin neden bilinmiyor, araştırılmadı.
Tek soru, tek koşu; test_5'in tamamı yeniden ölçülmedi.

Ortam: Foundry servisi ayaktayken `_discover_endpoint` onu bulamadı; adres
`FOUNDRY_LOCAL_ENDPOINT` ile verildi. Bilgisayar yeniden başladığı için önceki denemeler
Ollama/Foundry kapalı olduğundan sonuç üretmeden düştü.
