# Otomatik Skorlama & Benchmark Raporlama — Walkthrough

`test_sonuclari.csv` çıktılarının otomatik doğruluk skorlaması (**Exact Match**, **Token-level F1**, **Retrieval Accuracy**, **Negatif Test / Halüsinasyon Tespiti** ve **Gecikme/Latency**) yapılmış, modern grafikler üretilerek [TEKNIK_RAPOR.md](file:///c:/Users/merve/Desktop/rag_project/TEKNIK_RAPOR.md) içerisine entegre edilmiştir.

---

## 1. Geliştirilen Bileşenler

| Dosya / Bileşen | Açıklama |
| :--- | :--- |
| [ground_truth.json](file:///c:/Users/merve/Desktop/rag_project/ground_truth.json) | 30 soruluk standart test seti için beklenen doğru referans cevaplar, varyasyonlar ve anahtar kelimeler. |
| [benchmark_eval.py](file:///c:/Users/merve/Desktop/rag_project/benchmark_eval.py) | Türkçe uyumlu metin normalizasyonu (İ/i, I/ı), Exact Match, Token F1, Precision, Recall, Sınıflandırma (TP/TN/FP/FN), Latency analizi ve grafik üretim motoru. |
| [TEKNIK_RAPOR.md](file:///c:/Users/merve/Desktop/rag_project/TEKNIK_RAPOR.md) | **Bölüm 5.4** altında detaylı benchmark metrikleri, tablolar ve üretilen 3 grafik entegre edildi. |
| [requirements.txt](file:///c:/Users/merve/Desktop/rag_project/requirements.txt) | `matplotlib>=3.9.0` görselleştirme bağımlılığı eklendi. |
| [README.md](file:///c:/Users/merve/Desktop/rag_project/README.md) | Otomatik skorlama ve benchmark çalıştırma talimatları güncellendi. |

---

## 2. Üretilen Benchmark Grafikleri

1. **Zorluk Seviyesine Göre Doğruluk & F1 Skoru:**  
   `report/benchmark_charts/benchmark_accuracy_f1.png`
2. **Kategori Bazında Yanıt Süreleri ve Gecikme Dağılımı:**  
   `report/benchmark_charts/benchmark_latency.png`
3. **Genel Sistem Başarı Karnesi & Sınıflandırma Dağılımı:**  
   `report/benchmark_charts/benchmark_overall_summary.png`

---

## 3. Özet Benchmark Metrikleri

| Metrik | Skor | Açıklama |
| :--- | :---: | :--- |
| **Exact Match (EM)** | **%53.3** | Birebir doğru/hedef bilgi kalıbı eşleşmesi (Kolay: %85.7, Negatif: %83.3, Zor: %60.0) |
| **Token F1 Skoru** | **%61.8** | Kelime seviyesinde kapsam ve kesinlik harmonik ortalaması (Kolay: %93.6, Negatif: %83.3) |
| **Retrieval Doğruluğu** | **%100.0** | İlgili kaynak dokümanların ilk 3 chunk içerisinde yakalanması |
| **Doğru Yanıt (TP + TN)** | **26 / 30 (%86.7)** | Sistemin genel karar ve yanıt verme doğruluğu |
| **Halüsinasyon (FP)** | **1 / 30 (%3.3)** | Negatif soruların yalnızca 1 tanesinde çapraz doküman sızıntısı |
| **Ortalama Yanıt Süresi** | **15.97 sn** | Medyan: 10.27 sn, Min: 4.80 sn, Max: 44.48 sn |

---

## 4. Nasıl Çalıştırılır?

Tek bir komutla tüm sonuçları skorlayabilir, CSV ve JSON çıktıları ile grafikleri yenileyebilirsiniz:

```bash
python benchmark_eval.py test_sonuclari.csv ground_truth.json --output-dir report
```
