# Madde 32 Adım 2 — dense güvenlik slotu (`RAG_DENSE_FORCE_TOP_N`)

Değişiklik: RRF havuzunun (TOP_K=8) dışında kalan dense ilk-N chunk'ı reranker
havuzunun sonuna eklenir; nihai 4'ü reranker seçer
(`src/retrieval.py: _add_dense_force`). Varsayılan 0 = kapalı.

## Yöntem

Madde 20 `kapsam_topk.py` disiplini: tek değişken, nihai (reranker sonrası)
4 chunk'ın imzası karşılaştırılır; yalnız bağlamı değişen sorular LLM'e gider.

| Faz | Script | Ne |
|---|---|---|
| A | `havuz.py` | 147 soru (test_1..5 + test_negative) × N=0/1/3/5 retrieve; LLM yok |
| B | `uretim.py kos N` | Bağlamı değişen sorular `run_tests.py` ile; sınıf `classify_answer` |
| B | `uretim.py rapor` | N=0 referansına göre sınıf geçişleri → `sonuc_uretim.txt` |

Üretici temperature=0 (madde 21: 2 koşu birebir aynı); bağlamı değişmeyen soru
aynı girdiyi alır, koşulmadı.

## Faz A — bağlam (`sonuc_havuz.txt`)

- **Bayrak kapalıyken davranış aynı:** N=0 nihai listesi madde 20 kaydıyla
  **147/147** aynı.
- #79 (chunk 4183) ve #82 (chunk 4185) cevap chunk'ı N=1, 3, 5'te nihai
  bağlamda; N=0'da yok.

| N | Bağlamı değişen | Pozitif setler | test_negative |
|---|---|---|---|
| 1 | 13 | 5 | 8 |
| 3 | 32 | 17 | 15 |
| 5 | 44 | 29 | 15 |

## Faz B — cevap sınıfı (`sonuc_uretim.txt`)

| N | FN→TP | TP→FN | TN→FP | Diğer |
|---|---|---|---|---|
| 1 | #79 | 0 | #214 | — |
| 3 | #79 | 0 | #214, #222 | — |
| 5 | #79 | 0 | #214, #222, #226 | — |

- **#79: FN → TP** her N'de; cevap ölçekleme özelliğini doğru veriyor.
- **#82: FN kalıyor.** Cevap chunk'ı bağlamda 1. sırada (sayfa 12, "Multiplication
  in the time domain is convolution in the frequency domain"), model yine
  reddediyor. Retrieval kısmı çözüldü; kalan sorun üretim tarafı (İngilizce,
  sembolleri bozuk PDF metni; soru "hangi türetme" diye soruyor).
- **Pozitiflerde sınıfta yan etki yok:** bağlamı değişen 29 pozitif-set sorusunun
  hiçbiri sınıf kaybetmedi (TP→FN 0). **Düzeltme (madde 36, 2026-10-29):** sınıf
  doğruluk değil; elle doğruluk kontrolünde N=1'de değişim yok, N=3'te #87,
  N=5'te #30 ve #87 sınıf aynı kalırken kısmen doğrudan yanlışa döndü (6
  iyileşmenin yanında). Bkz. [madde 36](../madde36_classify_dogruluk/README.md).
- `test_1 #11` raporda HATA→TP görünüyor: N=0 koşusunda Ollama embedding
  hatası (status 500). `uretim_n0_tekrar11/` ile N=0 yeniden koşuldu: **TP**.
  Gerçek geçiş TP→TP.

### Negatif setteki 3 yeni FP — tek tek

| Soru | İlk N | Bağlama giren | Değerlendirme |
|---|---|---|---|
| #214 "airports.json'daki Türkiye havaalanlarının IATA kodları" | 1 | `airports[13]` | **GT etiketi yanlış.** `data/airports.json` içinde `IST`, country `TR` var; N=1 cevabı "IST" doğru. N=0'daki ret yanlıştı. |
| #222 "Z-Dönüşümü 12. hafta konu başlığı" | 3 | `profiles[302]` (ilgisiz) | Dense chunk bilgi getirmiyor; N=0 ve N=3 cevapları da yarım cümle ("…bilgi bulunmadığından" / "12. hafta konu başlığına ilişkin bilgi"). Sınıf, ret kalıbının eşleşip eşleşmemesinden değişiyor. Bağlam pertürbasyonu gürültüsü, gerçek uydurma değil. |
| #226 "mock-transactions'ta 2023'ün en yüksek harcaması" | 5 | `transactions[0,7,3]` | **Gerçek FP.** Veri 2024 (12/12 kayıt); model yıl uyumsuzluğunu yakalamadan "Entertainment / Netflix" diyor. N=3'te aynı dosyadan 2 chunk girmiş, model hâlâ reddediyor. |

## Sonuç

- **N=1** amaca yeterli: #79 TP oluyor, pozitiflerde kayıp yok (sınıfta ve doğrulukta). Tek "FP" (#214)
  bir GT etiketi hatası.
- **N=3** bir gürültü-FP (#222) ekliyor; #79/#82 için N=1'e göre kazanç yok.
- **N=5** gerçek bir uydurma ekliyor (#226, zamansal uyumsuzluk). Asıl risk
  N büyüdükçe ortaya çıkıyor.

## Dosyalar

- `havuz.py`, `havuz.jsonl`, `sonuc_havuz.txt`, `log_havuz.txt`, `log_havuz_1.txt`
  (Faz A; kesintiden sonra kaldığı yerden devam edildi: ilk 43 kayıt 1. koşudan)
- `uretim.py`, `uretim_n{0,1,3,5}/` (`sorular.csv`, `sonuclari.csv`, log),
  `uretim_n0_tekrar11/`, `sonuc_uretim.txt`
- N=0 `run_tests.py` 44/44 yazdıktan sonra kapanışta 0xC0000005 ile çıktı
  (sonuç dosyası tam: 44 satır, elle doğrulandı).
  Kapanış çökmesi aralıklı (N=1/3/5'te çıkış kodu 0); `uretim.py` artık
  başarıyı çıkış koduna değil, `sonuclari.csv`'deki satır sayısına bakarak
  doğruluyor (N=1/3/5 bu sürümle koşuldu).
