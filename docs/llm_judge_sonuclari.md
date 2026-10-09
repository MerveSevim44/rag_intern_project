# LLM-as-a-Judge Sonuçları (test_1 – test_5)

Bu rapor, RAG sisteminin 115 test sorusuna verdiği cevapların bir LLM hakem
(judge) tarafından puanlanmasının sonuçlarını özetler.

- **Judge modeli:** `openai/gpt-oss-120b` (Groq API) — cevapları üreten
  `qwen2.5-7b`'den farklı bir model, böylece model kendi cevabını puanlamıyor.
- **Değerlendirme tarihi:** test_1 3 Ekim 2026; test_2–test_5 4–5 Ekim 2026.
- **Kapsam:** 115 sorudan 113'ü puanlandı. test_2'deki #43 ve #53 `HATA:`
  satırı (code_interpreter servisi yanıt veremedi) olduğu için judge'a
  gönderilmedi.

## Sonuç dosyaları nerede?

| Set | Konu (beklenen kaynak) | Cevaplar (git'te) | Judge skorları (yalnızca lokal) |
|---|---|---|---|
| test_1 | Bağlamdan bağımsız dilbilgisi PDF | `evaluation/datasets/test_1_sonuclari.csv` | `evaluation/datasets/test_1_sonuclari_judge.csv` |
| test_2 | `728_profiles.json` | `evaluation/datasets/test_2_sonuclari.csv` | `evaluation/datasets/test_2_sonuclari_judge.csv` |
| test_3 | Fourier Transform PDF | `evaluation/datasets/test_3_sonuclari.csv` | `evaluation/datasets/test_3_sonuclari_judge.csv` |
| test_4 | `test1.txt` / `test2.txt` | `evaluation/datasets/test_4_sonuclari.csv` | `evaluation/datasets/test_4_sonuclari_judge.csv` |
| test_5 | Negatif (dokümanda olmayan) sorular | `evaluation/datasets/test_5_sonuclari.csv` | `evaluation/datasets/test_5_sonuclari_judge.csv` |

Judge dosyaları `.gitignore`'daki `*_judge.csv` kuralı yüzünden **repoda
değil, yalnızca bu bilgisayarda** duruyor. VS Code'da doğrudan açılabilirler.

Her judge satırında şu sütunlar var: `id, soru, cevap, judge_model,
context_kaynagi, faithfulness_score, answer_relevance_score,
task_performance_score, alignment_score, reasoning`. `reasoning`, judge'ın
Türkçe gerekçesidir; bir puanın nedenini anlamak için en faydalı sütun budur.

## Puanlama boyutları (her biri 1–5)

| Boyut | Ne ölçer |
|---|---|
| **Faithfulness (F)** | Cevaptaki her iddia, cevabın üretildiği bağlamda destekleniyor mu? Halüsinasyon var mı? |
| **Answer relevance (AR)** | Cevap sorulan şeyi doğrudan yanıtlıyor mu? |
| **Task performance (TP)** | Cevap öz ve kullanılabilir mi? Bağlamı gereksiz tekrar etme / şişirme burada cezalandırılır. |
| **Alignment (AL)** | Cevap sorunun kapsamında mı, istenmeyen varsayım ya da ek var mı? |

İki kural sonuçları okurken önemli:

- **Doğru ret kuralı:** Bağlamda cevap gerçekten yoksa ve sistem "Bu bilgi
  dokümanlarda bulunamadı" diyorsa, judge AR = 4 ve TP = 4 verir. Yani doğru
  bir ret için beklenen "tam puan" **5/4/4/5**'tir, 5/5/5/5 değil.
- **Bağlam:** Judge, cevabın üretildiği bağlamı görür (`run_tests.py`'nin
  kaydettiği `context` sütunu; tüm satırlarda `context_kaynagi = kayitli`).
  Ground truth referans cevabı ise prompt'ta **kullanılmıyor**. Bu yüzden
  faithfulness "bağlama sadakat" ölçer, "referans cevaba göre doğruluk"
  değil. O ölçüm `benchmark_eval.py`'nin EM/F1/ROUGE metriklerindedir.

## Genel sonuç

| | F | AR | TP | AL |
|---|---|---|---|---|
| **Ortalama (113 soru)** | **3.97** | **4.30** | **3.93** | **4.96** |

Puan dağılımı (soru sayısı):

| Boyut | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| Faithfulness | 11 | 16 | 10 | 4 | 72 |
| Answer relevance | 3 | 5 | 12 | 28 | 65 |
| Task performance | 4 | 17 | 15 | 24 | 53 |
| Alignment | 0 | 0 | 0 | 5 | 108 |

**Kısaca:** Soruların yaklaşık üçte ikisinde cevap bağlama tam sadık
(F = 5, 72 soru). Ama **27 soruda (yaklaşık dörtte bir) faithfulness 1–2**:
bunlar ya bağlamla çelişen ya da bağlamda olmayan bilgi içeren cevaplar.
Sistemin en zayıf noktası bu.

## Set bazında

| Set | Puanlanan | F | AR | TP | AL | F ≤ 2 olan | 5/5/5/5 alan |
|---|---|---|---|---|---|---|---|
| test_1 (dilbilgisi PDF) | 30/30 | 3.90 | 4.30 | 4.03 | 4.97 | 9 | 16 |
| test_2 (JSON profiller) | 28/30 | 4.04 | 4.54 | 4.11 | 4.93 | 6 | 13 |
| test_3 (Fourier PDF) | 30/30 | 3.93 | 4.47 | 3.93 | 4.97 | 6 | 15 |
| test_4 (metin dosyaları) | 10/10 | **2.90** | **3.60** | **3.10** | 5.00 | **5** | 2 |
| test_5 (negatif) | 15/15 | 4.80 | 4.00 | 3.93 | 4.93 | 1 | 1 |

- **test_4 açık ara en zayıf set.** 10 sorunun yarısında faithfulness 1–2.
  İki soruda (#92, #100) bilgi bağlamda olduğu halde sistem "bulunamadı"
  dedi.
- **test_5'in AR/TP ortalaması 4.0 civarında, ama bu büyük ölçüde iyi bir
  sonuç.** Negatif sorularda doğru ret 5/4/4/5 alır; 13/15 soru tam bu puanı
  aldı. İki istisna var: #101 (ret yerine kısmi cevap, F = 2) ve #107
  (aşağıda, "dikkat" bölümünde).
- test_1, test_2 ve test_3 birbirine yakın: F ≈ 4, her birinde 6–9 düşük
  faithfulness'lı soru.

## Zorluk derecesine göre

| Zorluk | Soru | F | AR | TP | AL |
|---|---|---|---|---|---|
| Kolay | 28 | 4.21 | 4.36 | 4.07 | 4.93 |
| Orta | 63 | 3.97 | 4.51 | 4.08 | 5.00 |
| Zor | 22 | 3.68 | 3.64 | 3.32 | 4.86 |

Beklendiği gibi zor sorularda tüm boyutlar düşüyor. Ama kolay sorularda da
6 soru F ≤ 2 aldı (test_1 #1, test_3 #62, #65, #66, test_4 #92, test_5
#101), yani sorun yalnızca zor sorulara özgü değil.

## Ret ("bulunamadı") cevapları

Puanlanan 113 cevabın 23'ü ret cevabı:

| Durum | Sayı | Puan (F/AR/TP/AL) |
|---|---|---|
| **Doğru ret:** bağlamda bilgi gerçekten yok | 21 | hepsi 5/4/4/5 |
| **Yanlış ret:** bilgi bağlamda var ama sistem "bulunamadı" dedi | 2 | ikisi de 1/1/1/5 |

Yanlış retler: **test_4 #92** (anlatıcının oda kiraladığı şehir ve mevsim,
bağlamda "İstanbul" ve "Kasım" geçiyor) ve **test_4 #100**.

Doğru ret kuralı amaçlandığı gibi çalışıyor: 21 doğru ret birebir aynı puanı
aldı, yanlış retler ise ayırt edilip düşük puanlandı.

## Düşük faithfulness alan sorular (F ≤ 2, 27 soru)

Bunlar sistemin hatalı ya da uydurma bilgi verdiği cevaplar. Gerekçeler
judge'ın açıklamasından kısaltılmıştır; tamamı judge CSV'lerindeki
`reasoning` sütununda.

| Soru | F/AR/TP/AL | Sorun (judge gerekçesi, özet) |
|---|---|---|
| test_1 #1 (Kolay) | 2/5/3/5 | G4.1 sorusuna G4.7 örneğindeki bilgiyle cevap verilmiş |
| test_1 #18 | 2/2/2/5 | Algoritma 4.6'nın amacı yanlış: "yararsız değişkenler" değil, "ulaşılabilir değişkenler" |
| test_1 #19 | 1/3/2/5 | TD = {S, A, B} denmiş; bağlamda {S, A, B, E, F} |
| test_1 #20 | 1/3/1/5 | TU = {S, B, A, F} denmiş; bağlamda {S, B} |
| test_1 #21 | 2/3/3/5 | Bağlamda olmayan, mantıksız bir kural ("S=> B \| B") |
| test_1 #23 | 1/3/2/5 | Türetme adımları bağlamla uyuşmuyor, tekrarlı |
| test_1 #27 (Zor) | 2/2/2/5 | "1'den büyük" diyerek yanlış uzunluk kısıtı eklenmiş |
| test_1 #28 (Zor) | 1/3/2/5 | Verilen kural ve açıklama bağlamda yok |
| test_1 #30 (Zor) | 2/3/2/4 | Bağlamda olmayan "c harfleri a'dan fazla" iddiası |
| test_2 #37 | 2/5/3/5 | Profil sayısı yanlış (32 yerine 40) |
| test_2 #38 | 2/5/3/5 | Değerler doğru ama bağlamda olmayan gerekçeler eklenmiş |
| test_2 #41 | 1/3/2/5 | `searchKeywords` alanı bağlamda yok, iddialar desteklenmiyor |
| test_2 #45 | 1/2/2/5 | Slug oluşturma süreci yanlış anlatılmış |
| test_2 #47 | 1/5/2/5 | `publicContact` hakkında bağlamla çelişen iddia |
| test_2 #50 | 2/5/4/5 | Haftalık müsaitlik özeti bağlamla tam örtüşmüyor |
| test_3 #62 (Kolay) | 1/1/1/4 | 1/2π çarpanının yeri yanlış; "x(t)=1 için" gibi uydurma ek |
| test_3 #65 (Kolay) | 2/5/2/5 | Sifting özelliği açıklaması bağlamda yok |
| test_3 #66 (Kolay) | 2/3/2/5 | Mutlak integrallenebilirlik eksik/hatalı tanımlanmış |
| test_3 #86 | 2/5/2/5 | Katsayı (1/2) yanlış verilmiş |
| test_3 #87 (Zor) | 2/4/3/5 | Re{a}/Im{a}'nın fiziksel yorumu bağlamda yok |
| test_3 #89 (Zor) | 2/2/2/5 | Spektrumun konumu yanlış yorumlanmış |
| test_4 #92 (Kolay) | 1/1/1/5 | Yanlış ret: şehir ve mevsim bağlamda var |
| test_4 #95 | 2/3/2/5 | Anahtar ile tıkırtı kodu ilişkisi bağlamla kanıtlanmıyor |
| test_4 #98 | 1/3/2/5 | Bağlamda geçen 03.14 bilgisi "belirtilmemiş" denmiş |
| test_4 #99 (Zor) | 2/4/3/5 | Bağlamda olmayan iddia (Magnus'un geleceği görmesi) |
| test_4 #100 (Zor) | 1/1/1/5 | Yanlış ret: bilgi bağlamda var |
| test_5 #101 (Kolay) | 2/3/2/4 | Negatif soruda ret yerine kısmen bağlama dayanan bir cevap verilmiş |

Tekrar eden iki örüntü:

1. **Küme / formül değerleri yanlış aktarılıyor** (test_1 #19, #20; test_3
   #62, #86; test_2 #37). Doğru bağlam geliyor ama cevapta sayılar ya da küme
   elemanları değişiyor.
2. **Doğru cevaba bağlamda olmayan açıklama ekleniyor** (test_2 #38; test_3
   #65, #87; test_4 #99). Ana bilgi doğru, ama eklenen gerekçe uydurma.

## Sonuçları yorumlarken dikkat

- **Judge referans cevabı görmüyor.** Bağlamın kendisi yanlışsa (retrieval
  yanlış chunk getirdiyse ya da hesaplama yanlışsa) ama cevap o bağlama
  sadıksa, judge yüksek puan verir. Somut örnek: **test_5 #107** ("profillerin
  ortalama randevu ücreti kaç TL?") negatif bir soru (`dokumanda_var_mi =
  Hayır`). Code interpreter yine de "45.12" diye bir sonuç hesapladı, sistem
  bunu cevap olarak verdi ve judge **5/5/5/5** puanladı, çünkü cevap bağlama
  birebir sadık. Judge sorunun negatif olduğunu bilmiyor; bu hatayı ancak
  `benchmark_eval.py`'nin sınıflandırması (FP) yakalar. Doğruluk için judge
  sonuçları EM/F1 ve TP/TN/FP/FN ile birlikte okunmalı. Not: `ground_truth/test_5.json`'daki 15 sorunun referansı
  bilerek boş bırakıldı; template referansı kullanmaya başlamadan önce elle
  gözden geçirilecek.
- **Alignment neredeyse hiç ayırt etmiyor.** 113 sorunun 108'i 5 aldı. Bu
  ya sistemin gerçekten hiç kapsam dışına çıkmadığını ya da boyutun bu test
  setleri için fazla geniş tanımlandığını gösteriyor.
- **Yanlış ret, faithfulness'ta 1 alıyor.** Judge bunu "bağlamla çelişen
  iddia" olarak puanlıyor. Bilgiyi uydurmaktan farklı bir hata türü olduğu
  için, retleri ayrıca saymak daha net bir tablo verir (yukarıdaki bölüm).
- **Tek bir judge, tek bir çalıştırma.** Sıcaklık 0 olsa da puanlar tek
  çalıştırmanın sonucu; aynı cevap tekrar puanlanınca 1 puan oynayabilir.
  Doğru ret kuralı bunu retler için sabitledi; diğer cevaplar için tutarlılık
  ölçülmedi.
- **test_1, test_2–5'ten bir gün önce puanlandı.** O sırada template'te doğru
  ret kuralı yoktu; kural eklenince yalnızca test_1'in 3 ret cevabı (#25,
  #26, #29) `--only-ids` ile yeniden puanlandı. test_1'deki diğer cevaplar
  ret olmadığı için kuraldan etkilenmiyor.
- **Veri gizliliği:** Sorular, bağlam (ders PDF'lerinden parçalar) ve
  cevaplar Groq sunucularına gönderildi. Groq'un ücretsiz katmanında
  gizlilik garantisi (privacy SLA) yok.

## Yeniden çalıştırmak için

```bash
# 1) Cevapları üret (lokal: Foundry + Ollama çalışıyor olmalı, Groq kotası harcamaz)
python evaluation/run_tests.py datasets/test_1.csv evaluation/datasets/test_1_sonuclari.csv

# 2) Judge ile puanla (GROQ_API_KEY proje kökündeki .env'de olmalı)
python evaluation/llm_as_judge.py datasets/test_1_sonuclari.csv \
    --output evaluation/datasets/test_1_sonuclari_judge.csv
```

- Judge çıktı dosyası zaten varsa yalnızca eksik ya da hatalı satırları
  tamamlar (resume). Baştan puanlatmak için dosyayı silin.
- Belirli soruları yeniden puanlatmak için: `--only-ids 25,26,29`.
- Groq'un ücretsiz katmanı günde yaklaşık 200k token veriyor; bu da günde
  yaklaşık 30 soru eder. Günlük limit dolunca script durur ve ne zaman
  devam edilebileceğini yazar. Aynı komut ertesi gün kaldığı yerden sürer.
