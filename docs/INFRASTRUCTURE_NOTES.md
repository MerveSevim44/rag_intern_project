# Altyapi Notlari — Foundry Local / 8GB VRAM

Bu dosya, RAG hattinin KODUNDAN degil, uzerinde kostugu DONANIM ve
servisten kaynaklanan tekrarlayan sorunlari kaydeder. Amaci su soruya
hazir bir cevap birakmak: "negatif set kosulari neden bu kadar sik
basarisiz oluyor?"

## Yapisal kirilganlik: Foundry Local 8GB VRAM'de cokuyor

**Belirti:** Kosu ortasinda Foundry Local servisi tamamen duser. O andan
sonraki TUM sorular `HATA: Connection error.` doner ve servis kosu
bitene kadar geri gelmez. `foundry service status` "not running" der;
kurtarma icin `foundry service start` gerekir (servis yeni bir PORT'ta
acilir — kod endpoint'i dinamik bulundugu icin bu sorun degil).

**Bu ucuncu tekrar. Tesadufi bir hata degil:**

| Kosu | Ne oldu |
|---|---|
| v3 | `MAX_CHUNK_CHARS` 1500->2900 sonrasi context ~8700 karaktere cikti; `test_2`'de 30 sorunun 8'i "Connection error". Kirpma degisikligi bu yuzden geri alindi. |
| v4 | Servis uc kez coktu (`test_4`'un 10 sorusu, `test_2`'nin 4 ve tekrar denemede 8 sorusu). Tum kosu gecersiz sayildi. |
| v5 negatif (2026-08-31 22:29) | Soru #216'da coktu, #216-#232 arasi 17 soru kesintisiz basarisiz. Arsiv: `archive/reports_old/results_v5_neg_invalid_crash/` |

### DUZELTME: bu "rastgele kirilganlik" degil, DETERMINISTIK bir tetikleyici

Ilk teshiste bu "8GB VRAM'in ara sira tasmasi" diye yazilmisti. Iki bagimsiz
kosu bunu curuttu: **her ikisinde de tam olarak ayni yerde**, #215'in ardindan
#216'da coktu. Rastgele bir kaynak yetersizligi degil, belirli bir dizinin
tetikledigi bir hata.

Ayrica **olen bilesen sabit degil**: bir kosuda Foundry "Connection error"
verdi, digerinde Ollama'nin embedding sureci dustu ("llama runner process has
terminated"). Yani tek bir kirilgan servis yok; belirli bir anda BELLEK
BASINCI zirveye cikiyor ve o an kim bellek isterse o oluyor.

Zirve ani: **ust uste iki soru da 3 sandbox denemesini tuketip semantik RAG'e
dusuyor.** Fallback embedding gerektirdigi icin Foundry (LLM) + Ollama
(bge-m3) + reranker ayni anda bellekte kaliyor.

Taze servis uzerinde #216 tek basina kosuldugunda SORUNSUZ calisti — yani
#216 tek basina olumcul degil, #215'in biraktigi yuk belirleyici.

**Tetikleyici (v5 negatif kosusunda dogrudan gozlendi):** uzun
`code_interpreter` retry zincirleri. Soru #215 ("us-states ... her
eyaletin nufusu") 3 denemenin 3'unde de `KeyError: 'population'` aldi
ve TEK BASINA 267.26 sn surdu; servis hemen ardindan dustu. Yani yuk,
soru sayisindan cok tek bir sorunun ustuste bindirdigi LLM cagrisindan
geliyor: her retry bir kod uretme + bir semantik dogrulama cagrisi
demek, uc deneme kolayca 6+ cagriya cikiyor.

**Neden ozellikle negatif set:** negatif sorularin buyuk kismi veri
setinde KARSILIGI OLMAYAN varliklar soruyor. Bu sorular sandbox'ta ya
`KeyError` (olmayan sutun) ya bos sonuc uretiyor; ikisi de retry
zincirini sonuna kadar calistiriyor. Yani negatif set, en agir yuku
ureten set olmasi bakimindan yapisal olarak en kirilgan kosu.

## Pratik kurallar

1. **Kosu ciktisini tamponlatma:** `python -u ...` kullan. Tamponlanmis
   stdout'ta cokme ancak surec bitince gorunur — 20 dakika bosa gider.
2. **Canli izle:** kosu sirasinda `Connection error|HATA` icin log'u
   izle; ikinci cokmeyi saniyeler icinde yakala.
3. **Skorlamadan ONCE hata satirlarini say:**
   `d.cevap.str.startswith('HATA').sum()`. `benchmark_eval.py` `HATA:`
   satirlarini ret kalibina uymadigi icin **TP sayar** — kirli bir kosu
   skorlanirsa metrikler YAPAY olarak iyi cikar. v4 tam olarak boyle
   gecersiz sayildi.
4. **Kirli kosuyu hemen arsivle:** `archive/reports_old/` altina
   `PROVENANCE.md` ile tasi (EXPERIMENTS.md kural 5).
5. **Cokme sonrasi:** `foundry service start`, ardindan setin TAMAMINI
   yeniden kos. Kismi birlestirme yapilacaksa kod durumu degismemis
   olmali ve provenance'a acikca yazilmali.

## Gozlem: v6 kosusunda cokme olmadi

v6 (sandbox bos-sonuc korumasi) kosusunda negatif set 32/32 tamamlandi ve
#216 dahil hicbir soru altyapi hatasi vermedi. Makul bir aciklamasi var —
koruma, bos filtre durumunda `result_to_natural_language` cagrisini ve
dolayisiyla bir LLM turunu atliyor, ayrica bu sorularin semantik RAG
fallback'ine dusme olasiligini azaltiyor — AMA bu **tek bir gozlem**.
Kararlilik iyilesmesi olarak raporlanmamalidir; tekrarlanirsa buraya
olculmus bir bulgu olarak yazilir.

## Bilinen ikinci kaynak: bellek ayni anda uc surecte

VRAM'i dolduran bilesenler AYRI sureclerde: LLM (Foundry Local),
embedding modeli (Ollama/bge-m3) ve reranker (CrossEncoder/torch).
`run_tests.py:free_gpu_memory()` yalnizca KENDI surecini temizleyebilir;
Foundry ve Ollama'nin bellegine oradan mudahale edilemez. Asil kaldirac
baglami kisa tutmak (`llm_client.MAX_CHUNK_CHARS`) — v3'un kirpma
degisikliginin geri alinmasinin sebebi de buydu.
