# Madde 22 Adım 3 — LLM ölçümü: yedek DB vs birleşik (yeniden ingest) DB (2026-10-13)

## Ölçülen kod durumu
- Commit `2e65d7e` (`kod_durumu_adim3.txt`; koşu sırasında `src/` temiz). Birleştirme
  kodu `5b494b2`.
- DB'ler: yedek `rag.db.bak_madde22_2026-10-12` (916 chunk, `f61f7119a6c8`) ve
  yeniden ingest edilmiş `rag.db` (911 chunk, `8745706f7e44`).
- Model qwen2.5-7b-instruct-cuda-gpu:4 (Foundry Local, CUDA), embedding bge-m3
  (Ollama 0.21.2), reranker bge-reranker-v2-m3. `HF_HUB_OFFLINE=1`. k=5.

## Koşu
`python -u experiments/madde22_ornek_cevap/run_adim3.py` (log: `log_adim3.txt`,
`log_adim3_devam.txt`; ham: `adim3_sonuclari.jsonl`). 68 iş:
- Faz 1: Adım 2'de kaynak listesi değişen 18 soru × 2 DB × 1 tekrar, aynı oturum,
  DB sırası sorudan soruya değişti (`run_tests.get_top_chunks` db_path sabitlenmiş
  sarmalayıcıyla; `run_tests` fonksiyonları değişmedi).
- Faz 2: tam negatif set (32) × yeni DB.

Analiz: `python experiments/madde22_ornek_cevap/analiz_adim3.py` → `sonuc_adim3.txt`.
Sınıf bugünkü skorlayıcıyla; F1 v8 referanslarına karşı.

## Koşu sağlığı
- Servisler koşu öncesi kapalıydı; Ollama elle, Foundry `foundry service start`
  ile başlatıldı — `start` yine askıda kaldı ama servis ayağa kalktı (madde 15,
  bu oturumda 2. kez).
- Faz 2'nin 62. işinden sonra **Foundry bozuldu** (GPU bellek hatası →
  "Model yanıt veremedi", code_interpreter 500): #227, #228, #229 HATA, script 3
  ardışık hatada durdu (madde 15'in "OOM sonrası servis bozuk kalıyor" sınıfı).
  HATA satırları silindi, Foundry stop/kill/start ile yeniden başlatıldı (yeni
  port), kalan 6 iş (`log_adim3_devam.txt`) aynı DB ile koşuldu. Faz 1 bu kesintiden
  önce tamamlanmıştı (A/B aynı oturum koşulu korunuyor).
- Son durum: 68 satır, HATA 0.

## Sonuç (plan §4)

| Ölçüt | Sonuç |
|---|---|
| 1. Retrieval: hedef 5/5 Cevap bağlamda, simülasyonla aynı | geçti (Adım 2: 0/147 fark) |
| 2. Hedef 5: TP→FN yok, F1 ≥ 3/5 artar | geçti — TP→FN 0; F1 artan 3/5 (#25, #26, #28) |
| 3. 18 sorunun regresyonu | geçti — pozitif TP→başka 0, negatif TN→FP 0; #101/#103/#224 FP kaldı (kapsam dışı) |
| 4. Yeni dolgu | geçti — tek çapraz-doküman dolgu test_3 #87 (24-25 chunk'ı); TP kaldı (F1 32.6 → 35.2), cevap gramer içeriğine atıf yapmıyor |
| 5. Tam negatif set + tripwire | geçti — FP 2/32 (#224, #232; taban ile aynı), tripwire 0 |

## Hedef 5 sorunun elle incelemesi (F1 tek başına yetmez)

| Soru | F1 yedek → yeni | İçerik | OCR hasarı |
|---|---|---|---|
| #24 | 55.0 → 51.6 | İki DB'de de **yanlış** küme ({aⁿbᵐcᵏdᵖ…}); Cevap sayfası kullanılamadı | **Evet** — s.23 okunamaz ("(aa) (cc)m b c b\|", koşullar "m20. k211") |
| #25 | 40.7 → 64.7 | **Gerçek iyileşme:** eskisi {aⁿbⁿ} (tamamen yanlış); yenisi doğru yapı (aⁿ b aᵐ b aᵏ), Cevap OCR'ı aynen kopyalanmış | **Evet** — üst simgeler düz, koşul bozuk ("n21") |
| #26 | 31.9 → 37.3 | **İyileşme:** kurallar artık doğru (S→aaSd\|aaAd, A→bAcc\|bcc); açıklama kısmen yanlış | Kısmen — "\|" yerine "I" ("aaSdIaaAd") |
| #28 | 32.5 → 45.9 | **Kısmi iyileşme:** kurallar Cevap sayfasından, ama "A => aAccbBc" ("\|" kayıp) ve B kuralı yanlışlıkla a) şıkkından (G_S.4.7.1) | **Evet** — "\|" kaybı |
| #29 | 41.7 → 31.9 | **Kötüleşme:** cevap Çinceye kayıyor, akıl yürütme yanlış ("b, d'den 2 fazla") | Belirsiz; asıl sorun Çince sızıntısı |

- Doğru Cevap sayfasının bağlama girmesi **3 soruda** (#25, #26, #28) içeriği
  gerçekten düzeltti.
- **OCR hasarı 4/5 soruda gerçekleşti** (#24, #25, #26, #28): #24'te Cevap sayfası
  hiç kullanılamadı; diğerlerinde model bozuk OCR metnini kopyalıyor (düz üst
  simgeler, kayıp "|"). Birleştirmeden bağımsız, ayrı backlog maddesi.
- **#29 Çince sızıntısı:** `llm_client._strip_foreign_script_fragments` tasarım
  gereği devreye girmedi — temizlik Latin harflerin %40'ından azını bırakacağı için
  cevaba dokunmuyor ("bozuk ama görünür" kuralı). Bilinen ve kabul edilmiş sınır.
- Sınıflar 5/5 TP kaldı; TP yalnız "ret değil" demek (#24 iki DB'de de yanlış).

## Karar
Plan §4 ölçütlerinin hepsi geçti → birleştirme kalıcı; geri dönüş (§3) uygulanmadı.
Yedek `rag.db.bak_madde22_2026-10-12` kökte duruyor.
