# Madde 21 — judge, pozitif sorulardaki retleri ödüllendiriyor

Plan: [docs/implementation_plan_madde21_judge_ret.md](../../docs/implementation_plan_madde21_judge_ret.md)

| Dosya | Ne |
|---|---|
| `kapsam.py` → `sonuc_kapsam.txt` | Adım 1: mevcut 3 judge koşusu (baz/v7/v8), LLM çağrısı yok |
| `yeniden_kos.py` | Adım 3: 5 soruyu (`sorular_5.csv`) güncel sistemde koşar: `run_tests.py` + `llm_as_judge.py`, ayrı süreçler |
| `kosu_1/`, `kosu_2/` | İki bağımsız koşu: `sonuclari.csv`, `sonuclari_judge.csv` (`siniflandirma` sütunu dahil), loglar |
| `karsilastir.py` → `sonuc_yeniden_kosu.txt` | İki koşu + v8 karşılaştırması, cevabın bağlamda olup olmadığı |

Kod: `c587b2c` (classify_answer + judge FN raporu). Tarih: 2026-10-27.

Koşu notları:
- `kosu_1`: judge adımı oturum kesilince 4/5'te durdu; aynı komut kaldığı
  yerden (#91) tamamladı (`log_judge.txt` yalnız devam koşusunu içeriyor).
- `kosu_2`: ilk deneme Foundry servisi kapalı olduğu için `load_model`'de
  düştü. Servis yeniden başlatıldı (madde 15 deseni: `start` dönmedi, `status`
  yeni portu gösterdi) ve koşu baştan yapıldı.
- Üretici ve judge `temperature=0`: iki koşunun birebir aynı çıkması
  tekrarlanabilirliği gösteriyor; örnekleme varyansı ölçülmüyor.

Sonuç: #56, #79, #82, #91 iki koşuda da FN ve judge ödüllendiriyor (5/4/4/5);
#50 iki koşuda da TP (ifade "bulunmamaktadır" → "yoktur"), cevap hâlâ yanlış.
