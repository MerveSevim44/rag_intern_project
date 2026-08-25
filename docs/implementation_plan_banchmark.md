# Otomatik Skorlama & Benchmark Raporlama Uygulama Planı

Bu plan, `test_sonuclari.csv` çıktılarının otomatik doğruluk skorlaması (**Exact Match**, **Token-level F1**, **Retrieval Accuracy**, **Negatif/Halüsinasyon Tespiti** ve **Gecikme/Latency**) yapılarak elde edilen grafik ve metriklerin `TEKNIK_RAPOR.md` dosyasına entegre edilmesini kapsar.

---

## 1. Mimari ve Bileşenler

```
test_sonuclari.csv + ground_truth.json
               │
               ▼
   [ benchmark_eval.py ]
   ├─ Türkçe Normalizasyon (küçük harf, noktalama, Türkçe karakter eşleme: İ/i, I/ı)
   ├─ Exact Match (EM) Hesaplama (Karakter & Anlamsal Eşleşme)
   ├─ Token-level F1 Hesaplama (Precision, Recall, F1)
   ├─ Retrieval Doğruluk & Negatif Soru Rejection Analizi
   └─ Süre / Gecikme (Latency) İstatistikleri
               │
               ├─────────────────────────┐
               ▼                         ▼
   [ benchmark_charts/ ]       [ benchmark_results.json ]
   ├─ Doğruluk & F1 Grafiği   [ benchmark_scored.csv ]
   ├─ Yanıt Süreleri Grafiği
   └─ Kategori Dağılımı
               │
               ▼
     [ TEKNIK_RAPOR.md ]
     (Grafikler, Skor Tabloları, Hata Analizi)
```

---

## 2. Yapılacak Değişiklikler

### Modül 1: Benchmark ve Skorlama Motoru (`benchmark_eval.py` & `ground_truth.json`)
- **`ground_truth.json` [YENİ]**: 30 soruluk standart test seti için beklenen doğru referans cevapları ve anahtar kalıpları içerir.
- **`benchmark_eval.py` [YENİ]**:
  - `normalize_text_tr(text)`: Türkçe uyumlu metin temizleyici (büyük-küçük harf, noktalama, boşluk temizleme).
  - `compute_exact_match(prediction, ground_truths)`: Tam eşleşme (0 veya 100%).
  - `compute_f1_score(prediction, ground_truths)`: Token seviyesinde Precision, Recall ve F1 skoru (0.0 - 1.0).
  - `evaluate_csv(results_csv, ground_truth_file)`: Tüm soruları zorluk kategorisine (`Kolay`, `Orta`, `Zor`, `Negatif`), kaynak doğruluğuna ve süresine göre değerlendirir.
  - `generate_benchmark_charts(summary_df, output_dir)`: `matplotlib` kullanarak modern, yüksek çözünürlüklü 3 adet görsel grafik üretir:
    1. `benchmark_accuracy_f1.png`: Zorluk seviyelerine göre Exact Match, F1 Skoru ve Retrieval Doğruluğu.
    2. `benchmark_latency.png`: Kategori bazında yanıt süreleri (Ortalama, Min, Max dağılımı).
    3. `benchmark_metrics_radar.png` / `benchmark_overall_summary.png`: Genel sistem başarı karnesi (Doğruluk, F1, Negatif Test, Retrieval, Halüsinasyon Kontrolü).

### Modül 2: Teknik Rapor Güncellemesi (`TEKNIK_RAPOR.md`)
- **[GÜNCELLE] [TEKNIK_RAPOR.md](file:///c:/Users/merve/Desktop/rag_project/TEKNIK_RAPOR.md)**:
  - Bölüm 5'in altına **5.4 Otomatik Skorlama & Benchmark Metrikleri (Exact Match / F1)** alt başlığı eklenir.
  - Üretilen 3 görsel grafik markdown içine gömülür.
  - Detaylı Exact Match, F1, Precision, Recall ve Gecikme metrik tabloları eklenir.
  - Token-level Türkçe F1 ve EM hesaplama metodolojisi açıklanır.
  - 30 sorunun detaylı skorlama karnesi sunulur.

### Modül 3: Paket Bağımlılıkları ve Doğrulama
- `requirements.txt` dosyasına `matplotlib` kontrolü ve eklenmesi.

---

## 3. Doğrulama Planı

### Otomatik Testler:
1. `python benchmark_eval.py` komutu çalıştırılarak:
   - `test_sonuclari.csv` skorlanacak.
   - `report/benchmark_charts/` klasörüne grafikler oluşturulacak.
   - `report/benchmark_summary.json` ve `report/test_sonuclari_scored.csv` çıktıları üretilecek.
2. Üretilen görsellerin (`.png`) dosya boyutları ve içerikleri doğrulanacak.
3. `TEKNIK_RAPOR.md` dosyası kontrol edilerek tabloların ve grafik bağlantılarının eksiksiz çalıştığı doğrulanacak.
