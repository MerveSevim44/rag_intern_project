# Plan: madde 21 — judge, pozitif sorulardaki retleri "dürüst ret" diye ödüllendiriyor

Tarih: 2026-10-27. Kapsam ölçümü: [experiments/madde21_judge_ret/](../experiments/madde21_judge_ret/)
(`kapsam.py`, çıktı `sonuc_kapsam.txt`). Yeni LLM/judge çağrısı yapılmadı;
yalnız mevcut sonuç + judge CSV'leri okundu.

## 1. Sorun

Judge prompt'undaki "Doğru Ret" kuralı (`evaluation/llm_as_judge.py`,
`JUDGE_PROMPT_TEMPLATE`) yalnız BAĞLAMA bakar: bağlamda cevap yoksa ret
cevabına AR=4, TP=4 verilir. Referans cevap `judge_single`'a geçiyor ama
template'te kullanılmıyor. Sonuç: cevabı ground truth'ta olan bir soruda
retrieval doğru chunk'ı getirmezse, ret judge'dan yüksek puan alır ve judge
raporunda bu FN hiçbir yerde görünmez. (`benchmark_eval` FN'yi zaten
sayıyor; kör nokta judge raporunda.)

## 2. Kapsam ölçümü sonucu

FN tanımı `benchmark_eval`'in kendi kuralı (`check_is_not_found` + GT
negatiflik kuralı); v7/v8'de madde 27 sonrası yeniden skorlanmış CSV'lerle
çapraz kontrol: **0 uyuşmazlık**. "Ödül" = AR≥4 ve TP≥4.

| Koşu | Pozitif | FN (pozitifte ret) | Judge ödüllendirdi |
|---|---|---|---|
| baz (2026-10-03, OCR öncesi) | 98 | 10 | 8 |
| v7 | 100 | 13 | 5 |
| **v8 (en güncel tam judge koşusu, madde 19 sonrası)** | 97 | 6 | 5 |

**v8'in 6 FN'si:**

| Soru | Judge F/AR/TP/AL | Cevap bağlamda mı (v8 kayıtlı context) | Not |
|---|---|---|---|
| test_2 #56 | 5/4/4/5 ÖDÜL | çıkarım sorusu (Zor), `$.metadata` geldi | sınırda |
| test_3 #79 | 5/4/4/5 ÖDÜL | hayır ("dar/geniş/ölçekleme" yok) | chunk düzeyinde retrieval kaçırması |
| test_3 #82 | 5/4/4/5 ÖDÜL | hayır ("konvolüsyon/çarpım" yok) | chunk düzeyinde retrieval kaçırması |
| test_4 #91 | 5/4/4/5 ÖDÜL | hayır ("Gümüş Yaprak" yok; dosyanın 1. paragrafında) | chunk düzeyinde retrieval kaçırması |
| test_4 #100 | 1/1/1/5 | evet | judge doğru cezalandırdı |
| test_2 #50 | 5/5/5/5 | — | **ret değil**: skorlayıcının yanlış FN'si (bkz. §6) |

- **Gerçek kapsam: 4 soru** (#56, #79, #82, #91). Dördü de üç koşunun
  ÜÇÜNDE de ödüllendirilmiş — gürültü değil, yapısal.
- Judge körü körüne ödüllendirmiyor: bağlamda cevap varsa reti cezalandırıyor
  (v8 #100; v7'de test_1 #25/#26/#29 hepsi 1/1/1). Kör nokta tam olarak
  **chunk düzeyinde retrieval kaçırması**.
- **Orijinal örnek (test_1 #24–#29) güncelliğini yitirdi:** v8'de altısı da
  TP (ret değil); madde 22 ölçümünde de hem yedek hem yeni DB'de TP. Yalnız
  baz koşuda (OCR öncesi) ödüllendirilmişlerdi.
- **Madde 19/22/29/20 sonrası durum:** v8 madde 19 sonrası. Madde 22'nin etki
  alanı (18 soru) bu 4 soruyu içermiyor. Madde 20'nin kapsam verisi (güncel
  DB, GPU embedding, top_k 5 vs 8): #79 ve #91'in bağlamı birebir aynı, #56
  ve #82'de yalnız dolgu chunk değişiyor → bağlam bu 4 soruda pratikte
  değişmedi. **Çekince:** güncel boru hattıyla LLM+judge yeniden koşulmadı;
  "hâlâ FN" bağlamın değişmemesinden çıkarım, ölçüm değil (bkz. §7).
- Ortalama etkisi küçük: v8 pozitif AR 4.32 (4 ödül 1 sayılsa 4.20), TP 4.04
  (3.92). Sorun büyüklük değil, görünmezlik.

## 3. Karar

**Raporlama düzeltmesi, prompt değişikliği DEĞİL.** Judge'ın her satırına
benchmark'ın sınıflandırması eklenir ve özette FN'ler judge skorundan
bağımsız raporlanır. Judge prompt'una dokunulmaz.

Reddedilen alternatif — referansı judge'a vermek / prompt'a "GT'de cevap var"
demek: (1) judge'ın rolünü "bağlama sadakat"ten "doğruluk"a çevirir, tüm
skorlar anlam değiştirir; (2) geçmiş koşularla karşılaştırma kırılır; (3) tüm
setleri Groq kotasıyla yeniden judge'lamak gerekir; (4) bugünkü kapsam 4 soru.

## 4. Yapılacak değişiklikler (Adım 2, onaydan sonra)

- `evaluation/benchmark_eval.py`: döngü içindeki negatiflik kuralı
  (`is_negative` / `label_conflict` / `has_reference`) davranışı birebir
  korunarak bir yardımcıya çıkarılır, ör. `classify_answer(row, gt) -> "TP"|"TN"|"FP"|"FN"`
  (+ negatiflik yardımcısı). Döngü bu yardımcıyı kullanır — kural tek yerde
  kalır, judge ile benchmark ayrışamaz (`_REFUSAL_FRAME_WORDS` ile aynı ilke).
- `evaluation/llm_as_judge.py`:
  - Her judge satırına `siniflandirma` sütunu (sonuç CSV'si + GT'den hesaplanır;
    LLM çağrısı yok, mevcut CSV'lerde de geriye dönük doldurulur).
  - `print_summary`: "Pozitif soruda ret (FN): N — judge'ın ödüllendirdiği
    (AR≥4 ve TP≥4): M [id listesi]" satırı + AR/TP ortalamalarının FN hariç
    hâli. Mevcut ortalamalar aynen kalır (karşılaştırılabilirlik).
  - Prompt (`JUDGE_PROMPT_TEMPLATE`) DEĞİŞMEZ.

## 5. Doğrulama

1. Refactor eşdeğerliği: v8 sonuç CSV'leri değişiklik öncesi/sonrası
   `benchmark_eval` ile skorlanır → `*_summary.json` ve `*_scored.csv` birebir
   aynı olmalı.
2. `llm_as_judge.py` mevcut v8 judge CSV'leri üzerinde (hepsi tamam olduğu
   için Groq çağrısı yapılmaz) → özet FN=6, ödüllendirilen=5 olmalı
   (`kapsam.py` ile aynı).
3. Birim test: sentetik satırlarla `classify_answer` + özet sayacı.
4. `pytest` tamamı.

## 6. Kapsam dışı yan bulgular (backlog'a not)

- **test_2 #50 — skorlayıcının yanlış FN'si:** "Hayır, … Pazartesi-Cuma …
  aktif görünmektedir. Hafta sonu çalışan profil örneği bulunmamaktadır."
  bir içerik cevabı (ve yanlış: GT'ye göre 248 profil Cumartesi açık), ama
  "bulunmamaktadır" + soruda geçmeyen yeni iddia olmadığı için ret sayılıyor
  (madde 28 ailesi). Judge 5/5/5/5 verdi: bağlamda yalnız 4 profil vardı —
  kısmi bağlama sadık ama yanlış cevabı ödüllendirmek, madde 21'in kardeş kör
  noktası.
- **FN kırılımı yanlış atfediyor:** `retrieval_match` dosya adı düzeyinde.
  #79/#82/#91'de doğru DOSYA geldi ama doğru CHUNK gelmedi; `benchmark_eval`
  bunları "doğru kaynak geldi ama cevap yok" (üretim sorunu) sayıyor, oysa
  retrieval sorunu.

## 7. Açık soru

Güncel boru hattıyla bu 5 soruyu (`--only-ids`) yeniden koşup judge'lamak
"hâlâ FN" çıkarımını ölçüme çevirir (Foundry + Ollama + Groq gerekir). Bu
değişiklik yalnız raporlama olduğu için ön koşul değil; yapılırsa Adım 2'nin
doğrulamasına eklenir.

## 8. Geri dönüş

Yalnız `evaluation/` altında raporlama; üretim kodu ve judge prompt'u
değişmiyor. `git revert` yeterli.
