# Madde 24 Adım 2 — görev notu A/B (2026-10-11/12)

## Ölçülen kod durumu
- Commit `b387c3c` (`kod_durumu.txt`; koşu sırasında `src/`/`evaluation/` temiz).
  Görev notu `6bdc21e`'de girdi; `task_notes=False` kontrol kolu.
- DB: 916 chunk (`rag.db`, Adım 0 ile aynı).
- Model qwen2.5-7b-instruct-cuda-gpu:4 (Foundry Local, CUDA), embedding bge-m3
  (Ollama 0.21.2), reranker bge-reranker-v2-m3. `HF_HUB_OFFLINE=1`. k=5.

## Koşu
`python -u experiments/madde24_ocr_alistirma/run_ab.py` (log: `log_ab.txt`,
ham: `ab_sonuclari.jsonl`). 128 iş, 51.6 dk, HATA 0.
- Faz 1: Adım 0 etki kümesi (16 soru) × 3 tekrar × 2 kol, aynı oturum, kol
  sırası tekrardan tekrara değişti.
- Faz 2: tam negatif set (32) × 1, kol açık.

Analiz: `python experiments/madde24_ocr_alistirma/analiz_ab.py` → `sonuc_ab.txt`.
Referans cevaplar ve v8 sınıfı: `experiments/v8_bm25_stopword/report/genel_scored.csv`
(sınıflar bugünkü skorlayıcıyla yeniden hesaplandı).

## Koşu sağlığı
- Açık kolda 48/48 bağlamda not var, kapalı kolda 0/48 — retrieval bu oturumda
  kaymadı, etki kümesi Adım 0 tahminiyle aynı çıktı.
- Faz 2'de Adım 0 kümesi dışında not alan negatif soru 0.

## Sonuç (plan §4)
| Ölçüt | Sonuç |
|---|---|
| 1. #224, test_5 #103 FP → TN | **KALDI** — iki kolda da 3/3 FP |
| 2. #217, test_5 #102 TN kalır | geçti (iki kolda 3/3 TN) |
| 3. test_1 11 soru bozulmaz | geçti — 11/11 iki kolda TP; ort. F1 farkı (açık−kapalı) −0.3 |
| 4. Tam negatif sette FP artmaz, tripwire 0 | geçti — 2/32 (v8: 2/32; #224, #232), tripwire 0 |

Gözlemler:
- **Üretim kol içinde tam deterministik:** her soru × kol için 3 tekrarın 3'ü
  bayt bayt aynı cevap. Daha önce "LLM nondeterminizmi"ne atfedilen
  koşular arası farkların en azından bir kısmı bağlam farkından (retrieval
  kayması, backlog madde 29) geliyor olabilir.
- **#224: not cevabı hiç değiştirmedi** — açık ve kapalı kolda cevap bayt bayt
  aynı (sayfa 18'in yararsız değişken adımları "CNF adımları" diye sunuluyor).
- **#103: cevap değişti ama uydurma kaldı;** açık kolda sonu "Bu bilgi belgede
  açık olarak verilmemiştir." — madde 28'in melez biçimi. Ret kapısında
  "verilmemiştir" olmadığı için FP sayılıyor (plan §6 kararı burada da geçerli).
- **test_1 F1 farkları uzunluktan:** en büyük düşüşler #25 −18.9, #24 −8.8,
  #26 −4.9; en büyük artış #2 +14.7. #25'te iki kolun cevabı da yanlış küme
  (doğru cevap Cevap 6 sayfasında; madde 22), açık kol daha uzun açıklama
  ekliyor. Sınıf değişimi yok.
- Kapsam dışı test_5 #101: iki kolda FP.

Sonuç: yön C'nin ilk aşaması (yalnız bağlam notu, prompt değişmeden) ölçüt
1'i karşılamıyor. Plan §5 Adım 3 (system prompt kuralı) ayrı karar.

# Adım 3 izole testi — system prompt'a görev notu kuralı (2026-10-12)

`src/` değişmedi: kural yalnız deney sürecinde `src.llm_client.ChatPromptTemplate`
sarmalanarak system mesajının sonuna eklendi (`run_adim3.py`; metin `RULE`).
Görev notu iki kolda da açık. 16 soru × 2 kol × 1 tekrar, aynı oturum, kol sırası
sorudan soruya değişti. 32 iş, 11.3 dk, HATA 0; kural kural-açık kolda 16/16
prompt'ta, kapalı kolda 0/16; bağlamda not 32/32.

Koşu öncesi Foundry ve Ollama kapalıydı (gece). `foundry service start` askıda
kaldı (madde 15), servis yine de yeni portta ayağa kalktı; Ollama elle başlatıldı.
İlk deneme servis yokken HATA ürettiği için silindi; script'e 3 ardışık hata
sınırı eklendi. Kod: `b387c3c` + bu dizindeki script'ler.

Analiz: `analiz_adim3.py` → `sonuc_adim3.txt`.

| Ölçüt | Sonuç |
|---|---|
| 1. #224, #103 FP → TN | **kaldı** — #103 TN ("Bu bilgi dokümanlarda bulunamadı."); #224 skorda FP |
| 2. #217, #102 TN kalır | geçti |
| 3. test_1 11 soru bozulmaz | **kaldı** — #24, #25, #26, #29 TP → FN (dördü de saf ret); ort. F1 −11.5 |

- **#224 ve #101 anlamca ret oldu ama skorda FP:** "Ret. Chomsky normal formuna
  dönüştürme adımları belgede açıkça anlatılmamıştır." Model kuraldaki "ret
  cümlesi" ifadesini sabit cümle yerine "Ret." diye aktarıyor; "anlatılmamıştır"
  ret kapısında yok. Uydurma içerik yok. (Kapıyı genişletmek plan §6 ve madde 28
  gereği ayrı karar.)
- **Bedel:** kural tam olarak alıştırmanın kendisini soran pozitif soruları
  (#24–#29 grubu) reddettiriyor — "küme tanımı nedir" sorusu "kavramın nasıl
  tanımlandığı" diye okunuyor.

Sonuç: yön C (not + prompt kuralı) ölçüt 3'ü bozmadan ölçüt 1'i karşılamıyor.

# Geri alma (2026-10-12)

Görev notu (`6bdc21e`) ölçülen faydası olmadığı için geri alındı. `run_ab.py` ve
`run_adim3.py` `run_single_test(..., task_notes=...)` parametresine dayanıyor;
yeniden koşmak için `6bdc21e`–`40345f1` aralığındaki kod gerekir. Ham sonuçlar
(`ab_sonuclari.jsonl`, `adim3_sonuclari.jsonl`) bağlamları da içerdiği için
koddan bağımsız olarak yeniden analiz edilebilir.
