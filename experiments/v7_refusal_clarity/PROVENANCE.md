# v7 — Ret Netligi + Servis Hatasi Ayrimi

## Olculen kod durumu
- **Commit:** `27214ff` (`feat: implement code interpreter, data engine, and
  retrieval modules for RAG pipeline`)
- Calisma agaci bu commit'te TEMIZ idi; kosu sirasinda hicbir kaynak dosya
  degistirilmedi.

## UYARI: bu kosuda IKI bagimsiz degisiklik var — ayristirilamaz

Commit `27214ff` tek bir degisiklik degil, iki tanesini birlikte tasiyor:

1. **Ret netligi (madde 14 — asil hedef).** Uc ret durumu artik kullaniciya
   AYNI cumleyi degil, ayri gerekceli cumleler donduruyor:
   - `EMPTY_RESULT_INSTRUCTION` -> "...bulunamadi; belirtilen kosullara uyan kayit yok."
   - `UNVERIFIED_RESULT_INSTRUCTION` -> "...bulunamadi; sonuc dogrulanamadigi icin aktarilmadi."
   - **Yeni ucuncu dal** `SERVICE_FAILURE_INSTRUCTION` (`[ISLENEMEDI]`) ->
     "...bulunamadi; soru su an islenemedi, tekrar denenebilir."
     Bunu tasiyan bayrak `code_interpreter.service_failure` ->
     `data_engine.SERVICE_FAILURE_SUMMARY` -> `retrieval`.
   Her cumle bir `_REFUSAL_MARKERS` isaretiyle BASLIYOR ve soruda gecmeyen
   sayi/kod/ozel isim EKLEMIYOR; yani `check_is_not_found(pred, question)`
   acisindan hala TN olarak skorlanmalari beklenir.

2. **`RERANK_TOP_N` 3 -> 4** (`src/retrieval.py:138`). Bu degisiklik `docs/`
   icinde hicbir planda gecmiyor ve ret mantigiyla ilgisi yok, ama **tum
   setlerdeki her soruyu** etkiler: synthesizer'a giden baglam 3 yerine 4
   parca.

**Sonuc:** v6 -> v7 arasindaki metrik farki bu iki degisiklige BIRLIKTE
aittir. Tek bir farki (1)'e veya (2)'ye atfetmek bu kosunun verisiyle
mumkun DEGILDIR. Ayristirma istenirse `RERANK_TOP_N = 3` ile ayri bir kosu
gerekir. Kapsam karari bilinctir: HEAD neyse o olculdu.

## Kosu bicimi
- Her set **ayri bir surecte** kosuldu (v6 ile ayni yaklasim).
- Kosu araci: `run_tests.py`'nin KENDI fonksiyonlari (`load_model`,
  `run_single_test`, `free_gpu_memory`) **degistirilmeden** import edildi.
  Surucudeki tek iki fark:
  1. her satir uretilir uretilmez diske yazilir (`run_tests.main` hepsini
     sonda yazar; kosu ortasinda servis coktugunde her sey kaybolurdu),
  2. `--min-id/--max-id` id araligi filtresi (negatif setin iki segmenti icin).
  RAG davranisi degismedi.
- Cikti tamponlanmadi (`python -u`) — bkz. `docs/INFRASTRUCTURE_NOTES.md`
  pratik kural 1.
- Servisler: Ollama (embedding) 127.0.0.1:11434, Foundry Local 127.0.0.1:58806.

## Setler
v6'dan farkli olarak **test_5 de kosuldu**. EXPERIMENTS.md'deki ozet tablo
98 soruluk temiz set (test_1..test_4 eksi `test_2#43`, `test_2#53`) uzerinden
oldugu icin test_5 o tabloya GIRMEZ; ayri raporlanir.

## Kosu sagligi — TEMIZ
Hicbir sette altyapi hatasi YOK. 147 sorunun 147'si cevaplandi; `HATA:` ile
baslayan satir 0, bos cevap 0 (`INFRASTRUCTURE_NOTES.md` pratik kural 3).

| Set | Soru | HATA satiri | Sure |
|---|---|---|---|
| test_1 | 30 | 0 | 16.1 dk |
| test_2 | 30 | 0 | 36.9 dk |
| test_3 | 30 | 0 | 18.2 dk |
| test_4 | 10 | 0 | 4.1 dk |
| test_5 | 15 | 0 | 11.0 dk |
| negatif seg A (201-215) | 15 | 0 | 9.2 dk |
| negatif seg B (216-232) | 17 | 0 | 14.2 dk |

`log_2.txt` sonundaki `RuntimeError: main thread is not in main loop`
**kosudan SONRA** gelen bir matplotlib `atexit` temizligidir (30 satirin
tamami yazilmisti, cikis kodu 0). Veriye etkisi yok.

Gozlem: `#215` — v5'te 267.26 sn surup servisi dusuren soru — bu kosuda
**66.3 sn** surdu ve cokme olmadi. Tek gozlem; bu kosunun verisiyle sebebi
kanitlanamaz (ayrica asagidaki iki-degisiklik sorunu var).

## Sonuclar — 98 soruluk temiz set (v6 ile karsilastirilabilir)
`test_1..test_4` eksi `test_2#43`, `test_2#53`.

| | v6 | **v7** | fark |
|---|---|---|---|
| FN | 13 | **11** | -2 |
| F1 | 40.0 | 38.6 | -1.4 |
| ROUGE-L | 35.5 | 34.1 | -1.4 |
| Semantik | 77.5 | 77.7 | +0.2 |
| EM | 6.1 | 6.1 | 0 |
| Soft | 12.2 | 12.2 | 0 |
| Negatif FP (tam kosu) | 2/32 | **1/32** | -1 |

### Cevaplarin 75'i / 98'i DEGISTI
v5 -> v6 gecisinde 98 cevabin 98'i karakter karakter ozdesti. v6 -> v7'de
**75 cevap degisti**. Ret netligi degisikligi ana sette neredeyse hic
tetiklenmiyor (test_1/3/4'te 0 ret varyanti, test_2'de 3); yani bu genis
kayma buyuk olcude **`RERANK_TOP_N` 3 -> 4**'ten geliyor. Bu, yukaridaki
"iki degisiklik ayristirilamaz" uyarisinin somut olcusudur: F1/ROUGE-L
gerilemesini ve FN kazancini ret netligine ATFEDEMEYIZ.

Sinif degisen 8 soru: FN->TP `36, 46, 48, 90, 97` (5); TP->FN `44, 56, 92` (3).
Net FN 13 -> 11.

## Sonuclar — negatif set (32/32, tam kosu)
FP **2/32 -> 1/32**.

- **`#224` kapandi** (v6 FP -> v7 TN). v6'da Chomsky normal formu hakkinda
  uydurma bir prosedur anlatiyordu; v7'de "Bu bilgi dokumanlarda bulunamadi."
  **Dikkat:** `#224` sandbox rotasinda DEGIL (v6 kaydinda "yanlis on kabul"
  olarak siniflanmisti), yani ret netligi degisikligi bu soruya hic
  dokunmuyor. Kapanmasinin en olasi sebebi `RERANK_TOP_N = 4` — ama bu
  kosunun verisiyle KANITLANMADI.
- **`#232` aciklinigini koruyor** (FP). Cevap v6 ile **birebir ayni**:
  "Hawaii, veri setinde en son eyalet siniri degisikligi kaydedilen
  eyalettedir." v6'da kaydedildigi gibi bu bos filtre degil, YANLIS SUTUN
  okuma (`founded`.idxmax) — ayri bir hata sinifi, bu deneyin kapsami disi.

## Ret varyantlarinin gercek kosuda tetiklenmesi
Madde 14'un uc dali da canli kosuda gozlendi:

| Varyant | Nerede | Kac kez |
|---|---|---|
| `[ISLENEMEDI]` "...soru su an islenemedi, tekrar denenebilir." | test_2 | 3 (`#43`, `#53` dahil) |
| `[KAYIT BULUNAMADI]` "...belirtilen kosullara uyan kayit yok." | negatif set | 6 |
| `[DOGRULANAMAYAN SONUC]` "...sonuc dogrulanamadigi icin aktarilmadi." | test_5 | 1 |

### `#43`/`#53` — skorlama acisindan ONEMLI yan etki
Bu iki soru v5 ve v6'da `HATA: Connection error` satiriydi ve kosudan
CIKARILMISTI. v7'de LLM servisi bu sorularda hala yanit veremiyor (degisiklik
servisi duzeltmiyor, oyle bir iddiasi da yoktu) ama cevap artik:

> "Bu bilgi dokumanlarda bulunamadi; soru su an islenemedi, tekrar denenebilir."

Bu satir `HATA:` ile BASLAMIYOR, bir `_REFUSAL_MARKERS` isareti iceriyor ve
soruda gecmeyen sayi/isim eklemiyor. Dolayisiyla skorlayici bunlari hata
satiri olarak TANIMIYOR, **ret** olarak skorluyor. Ikisinin de ground truth'u
"dokumanda var" oldugu icin sete dahil edilirlerse **v7'ye 2 FN eklerler**
(tam ana set n=100: FN 13). v6 ile karsilastirmanin gecerli kalmasi icin
yukaridaki tablo yine 98 soruluk temiz set uzerindendir.

Bu, `INFRASTRUCTURE_NOTES.md` pratik kural 3'u de etkiler: `HATA:` satiri
saymak artik servis coktugunu tespit etmek icin YETERLI DEGIL; servis hatasi
bir ret cumlesi olarak gorunebiliyor.

## test_5 (v6 baseline'i YOK)
15 soru, FP 2 (`#101`, `#107`), TN 13. v6 test_5'i kosmadigi icin
karsilastirma noktasi yok; EXPERIMENTS.md ozet tablosuna GIRMEZ.

## Uretilen dosyalar
- `results/` — ham cevaplar (`test_*_sonuclari.csv`, `neg_seg_A/B.csv`,
  birlestirilmis `test_negative_sonuclari.csv`) ve kosu loglari.
- `report/` — `*_scored.csv`, `*_summary.json`, `genel_scored.csv`,
  `genel_summary.json`, `benchmark_charts/`.
