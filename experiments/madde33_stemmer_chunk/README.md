# Madde 33 Adım 1 — #91'in iki nedeni ayrı ayrı

Soru: test_4 #91 "Alis'in çalıştığı kütüphanenin adı nedir?" → "Gümüş Yaprak".
Cevap paragraf 1'de (4227: "… devasa bir kütüphane yükselirdi: Gümüş Yaprak."),
"Alis" paragraf 2'de (4228: "Alis, bu kütüphanede çalışan …").

## Varyantlar (`varyant.py`; `src/` ve `rag.db` değişmez, süreç içi)

| Varyant | Ne değişti |
|---|---|
| V0 | mevcut sistem |
| S | yalnız stemmer: `_stem` çıktısında `kütüpha`/`kütüphanes` → `kütüphane` (oracle, yalnız bu aile) |
| M | yalnız chunk birleştirme: paragraf 1+2 tek chunk (`"\n\n"` ile), embedding ingest'in yolundan (`get_embeddings`); paragraf 2 chunk'ı silinir |
| SM | ikisi birlikte |
| G2 / G4 | üretim tavanı: V0 bağlamına paragraf 1 AYRI chunk olarak 2. / 4. sıraya zorla konur (S'nin reranker engelini aştığı durum) |

Yöntem sağlaması: paragraf 1'in mevcut metni yeniden gömüldüğünde DB vektörüyle
cosine **1.000000**. Her varyantta havuz rerank ilk-4 == `retrieve()` çıktısı.

## Retrieval (`katman.py` → `sonuc_katman.txt`)

| | BM25 ham / sıra | Dense sıra | Hibrit sıra | Havuz (8) | Rerank skor / havuz içi | Nihai bağlamda |
|---|---|---|---|---|---|---|
| V0 | 0 / — | 12 | 34 | hayır | 0.0034 / 5. (olsaydı) | **hayır** |
| S | 10.6 / 4 | 12 | **7** | **evet** | 0.0034 / **5.** (eşik 0.0037) | **hayır** |
| M | 31.2 / 1 | 2 | 1 | evet | **0.980 / 1.** | **evet, 1.** |
| SM | 32.7 / 1 | 2 | 1 | evet | 0.980 / 1. | evet, 1. |

- **S tek başına:** stemmer düzeltmesi paragraf 1'i havuza sokuyor (hibrit 34→7) ama
  reranker 5. sıraya koyuyor; paragraf 1 "Alis"i içermediği için cross-encoder
  soruyla ilişkilendiremiyor. Nihai bağlam V0 ile **aynı**.
- **M tek başına:** birleşik chunk her katmanda 1.; stemmer gerekmiyor (paragraf 2'deki
  "kütüphanede"/"kütüphanenin" zaten `kutuphane` stem'ine iniyor).

## Üretim (`uretim91.py` → `sonuc_uretim91.txt`; Foundry qwen2.5-7b, temperature=0, 2 tekrar, tekrarlar birebir aynı)

| | Bağlam | Cevap | `classify_answer` | Doğru mu ("Gümüş Yaprak")? |
|---|---|---|---|---|
| V0 | p2, p7, p3, p8 | "Bu bilgi dokümanlarda bulunamadı." | FN | hayır |
| S | (V0 ile aynı) | aynı | FN | hayır |
| M | **p1-2**, p7, p3, p8 | "Alis'in çalıştığı kütüphanenin adı Gümüş Yaprak. …" | TP | **evet** |
| G2 | p2, **p1**, p7, p3 | "Unutulmuş Parşömen'in Gümüş Yaprak kütüphanesi." | TP | kısmen (ad doğru, başlıkla karışık) |
| G4 | p2, p7, p3, **p1** | "Unutulmuş Parşömen Kaynak: test1.txt, paragraf 1" | TP | **hayır** (başlığı ad sanıyor) |

`classify_answer` yalnız ret / ret değil ayrımı yapar; G4 "TP" sayılıyor ama cevap yanlış.

## Sonuç — #91 için

| Müdahale | Kazanç |
|---|---|
| Yalnız stemmer | **0**: havuza giriyor, reranker eliyor; bağlam ve cevap değişmiyor |
| Yalnız chunk birleştirme | **tam**: bağlamda 1., cevap doğru |
| İkisi birlikte | birleştirme ile aynı; stemmer katkı yok |
| (Tavan) iki ayrı chunk, ikisi bağlamda | sıraya bağlı: 2.'de kısmen doğru, 4.'de yanlış; eşgönderim ayrı chunk'larda kırılgan |

**Belirleyici neden cevabın iki chunk'a bölünmesi.** Stemmer tutarsızlığı gerçek
(BM25'i sıfırlıyor) ama #91'de tek başına sonuç değiştirmiyor; reranker kapısı
paragraf 1'i "Alis" olmadan kabul etmiyor. Ayrı chunk'lar bağlama girse bile
model paragraf 1'in başlığını ("Unutulmuş Parşömen") ad sanabiliyor.

Ölçülmeyen (müdahale seçiminden sonra): birleştirme/stemmer politikasının **genel**
hâlinin (ör. tüm .txt paragraflarına komşu birleştirme; genel stemmer düzeltmesi)
tam benchmark + negatif setteki yan etkisi. Buradaki oracle'lar yalnız #91'in
çiftine / ailesine dokunuyor.
