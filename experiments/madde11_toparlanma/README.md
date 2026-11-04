# Madde 11 — C ölçümleri ve toparlanma kapı deneyi (2026-11-04)

Backlog: [madde 11 kapanışı](../../docs/backlog_retrieval.md), [madde 15 §5](../../docs/backlog_retrieval.md),
madde 41 sonundaki #53 notu. `src/` bu betiklerle DEĞİŞMEZ (yalnız çalışma zamanında modül özniteliği sarılır).
Servis adresi her koşuda `FOUNDRY_LOCAL_ENDPOINT` ile verilir; port her başlatmada değişir.

## Betikler ve sonuçları
| Betik | Ne ölçer | Sonuç dosyası |
|---|---|---|
| `izle_43_53.py` | #53/#43'te her `call_llm_text` çağrısının prompt/yanıt boyutu (C'den ÖNCE ve sonra) | `izle_43_53_ilk.jsonl` (önce: #53 9.351→12.575→500; #43 servis bozuk), `tekrar_43_53.jsonl` (sonra: 5 koşu) |
| `olc_set.py` | test_5 + test_2 tam koşu, her çağrının prompt boyutu ve sınıf (C sonrası) | `olc_sonra.jsonl` |
| `ayir_53.py` | #53 yanlış sayı C'den bağımsız mı? `stub_ham` (kod üretimi atlanır), `C_10500`, `cap_11500` | `ayir_53.jsonl` |
| `kapi_k2.py` | Kademe 2 kapı deneyi, ilk tur (taze servis): A = #53'ü çöktür, B = unload+load | `kapi_A.jsonl`, `kapi_B.jsonl` |
| `repro.py` + `repro_surucu.sh` | Kalıcı bozulmayı yeniden üretme: istek birikimi + art arda OOM; her adım ayrı süreç, `timeout 90` | `repro.jsonl` |

## Bulgular (özet)
1. **C işe yarıyor (#43, #53):** düzeltme prompt'u 10.500'de kalıyor, çökme yok (#53 3/3, #43 2/2; çıktılar
   birebir tekrar ediyor). #43'ün cevabı pandas ile doğrulandı (doğru). #53'ün cevabı yanlış sayı içeriyor
   (Sinem iptal 4 / gerçek 12; Umut min 6 / gerçek 4).
2. **Yanlış sayı C'den bağımsız:** `ayir_53.py` `stub_ham` varyantında kod üretimi atlanıp sandbox'ın DOĞRU
   çıktısı doğrudan verildiğinde de aynı yanlış cevap çıkıyor. Zincir: `result_to_natural_language` bulanık
   cümle üretir ("12-4 saat arasındadır"), `ask()` bağlamında yalnız o cümle var (394 krk) ve ondan yanlış
   sayı uydurur (madde 41 notu).
3. **Toparlanma (kademe 2) kapı deneyi — kanıtsız:**
   - Taze servis (`kapi_k2.py`): çöküş 14.933 krk'ta yeniden üretildi, 12.575 krk bu kez geçti (eşik duruma
     bağlı); çöküşten sonra servis bozuk kalmadı. Kademe 2 mekanik olarak çalıştı (unload anında, load 6,5 sn).
   - ~30 dk açık örnek (`repro.py`): 29 normal istek + 4 OOM denemesi, GPU 7.9/8.2 GB dolu, boş RAM 0.7-1.5 GB.
     Yalnız **1 geçici** başarısızlık (9 KB prob, OOM'dan 5 sn sonra 500); ~1,5 dk sonra, kademe 2'den ÖNCE,
     kendiliğinden düzeldi. Bu yüzden `repro.jsonl`'deki `tier2_sonra.DUZELDI: true` **boş bir doğrulamadır**
     (servis zaten sağlıklıydı).
   - Karar kuralı gereği (kalıcı bozulma üretilemedi / kademe 2 düzeltmesi kanıtlanamadı) toparlanma UYGULANMADI.

## Sınırlar
- Saatler süren bir servis örneği simüle edilemedi; "süre/durum birikimi" yalnız istek sayısı, OOM sayısı ve
  bellek baskısıyla denendi. Süre birikimiyle ilişki **kanıtlanmadı**.
- Her koşu n=1 (prompt/çıktı tekrarları birebir aynı çıktığı için tekrarlar kopya, bağımsız örnek değil).
- Bozuk durumda hangi prob boyutunun (kısa / ~9 KB) başarısız olduğu ölçülemedi.
- `repro.py`'deki büyük istek, #53'ün gerçek temel prompt'u + kod metni olarak sentetik üretildi; pipeline değildir.
- Kademe 3 (`foundry service stop/start`) bilerek denenmedi (madde 15 §4: 3 kez askıda kalmış).
