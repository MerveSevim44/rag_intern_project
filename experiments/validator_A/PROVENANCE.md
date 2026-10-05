# Validator A — 13 aday satırın yeniden koşulması

Plan: [docs/implementation_plan_validator_failure.md](../../docs/implementation_plan_validator_failure.md)
(bölüm 4-5 ölçüm, bölüm 9 sonuç). Backlog madde 16 ve 18.

## Ölçülen kod durumu
- **Commit:** `39e7801` (`feat(eval): run_tests'e dogrulama_durumu sütunu ve özet satırı`)
- Çalışma ağacı temizdi; koşu sırasında hiçbir kaynak dosya değiştirilmedi.
- Tarih: 2026-10-05, Foundry Local (qwen2.5-7b-instruct-cuda-gpu:4),
  koşudan hemen önce yeniden başlatıldı.

## Koşu biçimi
- `sorular.csv`: test_2.csv ve test_5.csv'den alınan 13 soru (ana sonuçlarda
  `[KESİN HESAPLAMA SONUCU]` context'i alan satırların tamamı):
  test_2 #32, 35, 37, 39, 42, 44, 45, 51, 52, 57, 60; test_5 #107, 108.
- `evaluation/run_tests.py` **değiştirilmeden**, art arda iki ayrı süreçte:
  `python evaluation/run_tests.py sorular.csv results/gecis_N.csv`
  Çıktı `results/log_gecis_N.txt`.
- Her iki süreç de iş bittikten SONRA (sonuç CSV'si yazılmış, özet basılmış)
  **segfault (exit 139)** ile çıktı. Veri kaybı yok; büyük ihtimalle CUDA/torch
  kapanışı. Çıkış koduna bakan otomasyon bunu bilmeli.

## Doğruluk tablosu (`results/dogruluk_13.csv`)
- F1 / ROUGE-L / sınıflandırma: `evaluation/benchmark_eval.py`, ana sonuç
  CSV'leri (`evaluation/datasets/test_2_sonuclari.csv`, `test_5_sonuclari.csv`)
  üzerinden. Ölçüm cevapları ana cevaplarla **bayt bayt aynı** olduğu için
  ayrıca skorlanmadı.
- **Semantik benzerlik ölçülmedi**: Ollama kapalıydı, `benchmark_eval`
  semantik skoru devre dışı bıraktı (EM/F1/ROUGE-L etkilenmez). Sütun bu
  yüzden tabloya alınmadı.
- Judge skorları: `evaluation/datasets/test_{2,5}_sonuclari_judge.csv`
  (gpt-oss-120b, 2026-10-04/05). Cevaplar aynı olduğu için yeniden alınmadı.
