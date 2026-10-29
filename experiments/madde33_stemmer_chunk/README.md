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

# Madde 33 Adım 2 — genel .txt birleştirme politikası (MIN sweep)

Politika (`politika.py`): `.txt` paragraflarını, birikmiş metin en az MIN karakter
olana kadar komşularıyla birleştir; sondaki artık öncekine eklenir. `.txt`'nin
yeniden ingest'i süreç içinde simüle edilir (embedding ingest yolundan; `src/`
ve `rag.db` değişmez). Yalnız `.txt` (19 chunk) etkilenir. Duman testi:
`sonuc_duman_adim2.txt`.

| MIN | test1.txt (9 p.) | test2.txt (10 p.) |
|---|---|---|
| 500 | 1-2, 3-4, 5-9 | 1-2, 3-4, 5-10 |
| 800 | 1-3, 4-9 | 1-3, 4-10 |
| 1200 | 1-9 | 1-10 |

## Faz A — nihai bağlam (`havuz2.py` → `sonuc_havuz2.txt`; 147 soru, LLM yok)

Sağlama: MIN=0 == madde 32 Adım 2 n0 kaydı, **147/147**.

| MIN | Bağlamı değişen | .txt kaynaklı | Dolaylı | #91 "Gümüş Yaprak"+"Alis" aynı chunk'ta |
|---|---|---|---|---|
| 500 | 13 (12 poz + neg #221) | 13 | 0 | evet |
| 800 | 15 | 13 | test_2 #35, #46 | evet |
| 1200 | 15 | 13 | test_2 #35, #46 | evet |

Dolaylı değişim: test_2 #35/#46'nın bağlamında yalnız `728_profiles.json`
kayıtları yer değiştiriyor; `.txt` chunk sayısı düşünce BM25 korpus istatistikleri
(IDF, ortalama uzunluk) kayıyor. İki sorunun cevap metni üç MIN'de birebir aynı.

## Faz B — üretim, sınıf + doğruluk (`uretim2.py` → `sonuc_uretim2.txt`, `dogruluk_adim2.txt`)

Foundry qwen2.5-7b, temperature=0, tek koşu; doğruluk elle (madde 36 kuralı;
tek değerlendirici). Raporlarda pozitif soruda "cevap verdi" / "ret".

| MIN | Sınıf (pozitif) | Doğrulukta iyileşen | Doğrulukta bozulan | Negatif |
|---|---|---|---|---|
| 500 | ret→cevap verdi 1 (#91) | #91 R→D, #98 K→D | **0** | 3/3 ret |
| 800 | ret→cevap verdi 2 (#91, #100) | #91 R→D, #97 K→D, #100 R→K | **#96 D→K** (sınıf aynı; "yarının tarihi" yerine test2.txt'ten "28 Mart") | 3/3 ret |
| 1200 | ret→cevap verdi 1 (#100), cevap verdi→ret 2 (#95, #96) | #100 R→K | #95, #96 →R; **#97 K→Y, #94 D→K** (sınıf aynı) | 3/3 ret |

- **MIN=1200** (dosya başına tek chunk) #91'i düzeltmiyor ve 4 soruyu bozuyor;
  ikisi sınıfa yansımıyor. Eleniyor.
- **MIN=800** bir soruyu sessizce bozuyor (#96: iki hikâyenin büyük chunk'ları
  bağlamda yan yana → tarih karışması) ve iki ilgisiz soruda bağlamı dolaylı kaydırıyor.
- **MIN=500**: #91 düzeliyor, #98 iyileşiyor, sessiz bozulma yok, dolaylı etki yok,
  negatifler korunuyor. En küçük ayak izi.

Sınırlar: tek koşu, tek değerlendirici; 13–15 soruluk küçük örnek, yalnız 2 `.txt`
dosyası (iki kısa öykü). Bulgu "500 bu korpusta güvenli", genel bir eşik değil.
