# Madde 22 — Örnek/Cevap sayfa birleştirme: kapsam ölçümü (2026-10-12)

Kod: `1b6a180` (`kod_durumu.txt`). Gerçek `rag.db`'ye dokunulmadı: birleştirme
scratchpad'deki bir kopyada simüle edildi (`simulasyon.py`). Retrieval:
`retrieve(top_k=5)` (benchmark ayarı), iki DB aynı süreçte (madde 29 kayması
karışmasın).

| Dosya | Ne yapar |
|---|---|
| `simulasyon.py` → `simulasyon.jsonl`, `cevap_sirasi.txt` | Kural R ile sim DB kurar; 147 soru × 2 DB; hedef soruların Cevap sayfası hibrit sırası |
| `analiz.py` → `sonuc_simulasyon.txt` | A) hedef sorular, B) #103 kesişimi, C) etki alanı |
| `llm_103.py` → `llm_103.jsonl` | #103 için iki DB ile birer LLM çağrısı (aynı oturum) |
| `rerank_dagilimi.py` → `sonuc_rerank_dagilimi.txt` | Madde 24 (D) ön verisi: en yüksek rerank skorunun eşiklere göre pozitif/negatif kırılımı |

## Birleştirme kuralı R (belgeye özel değil)

Sayfa OCR'lanmışsa (metin katmanı < `OCR_MAX_TEXT_CHARS` ve resim var) **ve**
başlığındaki bölüm numarası (`4.5.2.`) önceki sayfanınkiyle aynıysa önceki
sayfanın chunk'ına eklenir. Üç PDF'in taraması: tam 5 çift (gramer PDF'i 22+23,
24+25, 26+27, 28+29, 30+31). Fourier/Z PDF'lerinde OCR sayfası yok; gramer 18/19
aynı numaralı (4.3.4.1) ama OCR değil → birleşmez. Sim DB 916 → 911 chunk;
birleşen chunk'lar ingest'in `get_embeddings`'iyle yeniden embed edildi,
page_info "sayfa N-M".

## B) Madde 24 kesişimi — test_5 #103 (pompalama lemması, belgede yok)

| | Bağlama giren 4 parça (rerank) | LLM (`llm_103.jsonl`) |
|---|---|---|
| Bugün | s.16 (0.036), s.2 (0.032), s.24 (0.010), s.28 (0.006) | FP — bilinen uydurma |
| Birleşik | s.16 (0.036), s.2 (0.032), s.28-29 (0.011), s.22-23 (0.009) | **FP — daha uzun uydurma** (lemmanın biçimsel ifadesini model kendi bilgisinden yazıyor) |

**Birleştirme #103'ü çözmüyor.** Dolgu yerinde: 24 → 22-23, 28 → 28-29. Birleşen
chunk'lar uzadığı için BM25 düştü (22.5 → 20.1) ama ilk 5'ten çıkmaya yetmedi.

Kanıt (madde 24 D planı için): reranker iki DB'de de **tüm adaylara 0.04 altı**
skor veriyor, yani "hiçbiri alakalı değil" diyor; `RERANK_TOP_N=4` bu sinyali
dinlemeden her durumda 4 parça geçiriyor. D (eşik) teorik olarak doğru yönde.

**Karşı veri (aynı ölçümden, `sonuc_rerank_dagilimi.txt`):** "en yüksek rerank
eşiğin altındaysa bağlam boş" kuralı 0.04'te 22/34 negatif semantik soruyu
kapsıyor ama **5/87 pozitifi de** (3'ü bugün TP: test_2 #58 0.010, test_3 #62
0.031, test_4 #97 0.008). Negatif tarafta kurtarılacak FP yalnız #103 (#222 o
listede v8'in kayıtlı sınıfıyla FP görünüyor; bugünkü skorlayıcıyla zaten TN).
Yani bu biçimiyle D: **1 FP kazancı için 3 TP kaybı** — D planı bunu çözmeden
ilerlememeli.

## A) Hedef sorular — doğru Cevap sayfası bağlamda mı

| Soru | Cevap sayfası | Bugün (hibrit sıra) | Birleşik |
|---|---|---|---|
| test_1 #24 | s.23 | yok (> 40) | **var** (22-23, rerank 0.98) |
| test_1 #25 | s.27 | yok (10.) | **var** (26-27, 0.99) |
| test_1 #26 | s.25 | yok (12.; yanlış Cevap s.27 geliyor) | **var** (24-25, 0.75) |
| test_1 #28 | s.29 | yok (7.; yanlış Cevap s.27 geliyor) | **var** (28-29, 0.61) |
| test_1 #29 | s.31 | yok (**2.**, reranker eliyor) | **var** (30-31, 0.73) |

5/5. Not: Cevap OCR'ı bazı sayfalarda bozuk (s.23: "Ls.42 = { (aa) (cc)m b c b|";
üst simgeler düz). Bağlama girmesi cevabın doğru çıkacağını garanti etmez —
LLM ölçümü gerekir.

## C) Etki alanı

147 sorudan **18'inin** kaynak listesi değişiyor; hepsinde gramer PDF'i var, rota
değişen 0. Bilinen 16'ya ek: test_1 #21 (s.19 → s.16; birleşen chunk yok,
BM25 IDF kayması) ve **test_3 #87** (Fourier sorusu: 3. sıraya birleşik 24-25
dolgu olarak giriyor, rerank 0.001 — yeni çapraz-doküman dolgusu). test_5
#102'de s.22 düşüp yerine bir profil chunk'ı giriyor (rerank 0.0005).

## Adım 2 — yedek + yeniden ingest + retrieval doğrulaması (2026-10-12)

Kod `5b494b2`. Yedek `rag.db.bak_madde22_2026-10-12` (916 chunk, parmak izi
`f61f7119a6c8`, dosya sha1 `rag.db` ile aynı; `.gitignore` `rag.db.bak*`).
Plandan sapma: `delete_source` ayrıca çağrılmadı — `ingest_single_file` eski
chunk'ları aynı transaction'da siliyor (atomik).

`adim2_reingest.py` → `sonuc_adim2_reingest.txt`:
- 911 chunk; gramer PDF'i dışındaki 885 chunk id/içerik/page_info/embedding aynen.
- Birleşik 5 chunk = yedekteki Örnek + "\n" + Cevap (yeniden OCR deterministik).
- Birleşmeyen 21 sayfa: içerik aynı, yeniden üretilen embedding'lerle cosine
  min = max = 1.000000 (10 Ekim'deki embedding'le aynı — doküman tarafında
  oturumlar arası kayma yok; madde 29 için not).
- Yeni parmak izi `8745706f7e44`.

`adim2_retrieval.py` → `sonuc_adim2_retrieval.txt` (147 soru, yedek vs yeni, aynı süreç):
- yeni DB = simülasyonun "birleşik" sonucu: kaynak listesi farkı **0/147**,
  rerank skoru farkı 0.
- yedek DB = simülasyonun "bugün" sonucu: fark **0/147**.
- Değişen 18 soru simülasyondakiyle aynı → Adım 3'ün LLM kümesi bu 18 soru.
