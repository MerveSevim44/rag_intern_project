# Madde 25 — ret tespiti kapsam ölçümü (2026-10-11)

Kod: `334c3a5`. Girdi: `experiments/*/report*/genel_scored.csv` (7 skorlu koşu:
v2, v3, v5, v5+neg, v6, v7, v8; ~1000 satır). LLM/servis gerektirmez,
deterministik.

## Mevcut yöntem (`evaluation/benchmark_eval.check_is_not_found`)

1. **Kapı:** aksan katlanmış metinde 10 sabit alt dizgi (`_REFUSAL_MARKERS`:
   `bulunamadi`, `bulunmamaktadir`, `bulunmuyor`, `yer almamaktadir`,
   `belirtilmemistir`, `mevcut degildir`...). Yoksa ret değil.
2. **Yeni iddia süzgeci** (soru verildiğinde): ret kalıbı ve çerçeve kelimeleri
   düşüldükten sonra kalan metinde soruda GEÇMEYEN sayı / kod / özel isim varsa
   ret değil.

## Dosyalar

| Dosya | Ne yapar |
|---|---|
| `ret_tarama.py` → `sonuc_ret_tarama.txt` | A) kapıdan geçemeyen ama olumsuzluk taşıyan TP/FP cevaplar; B) kapıdan geçen ama "yeni iddia" süzgecinin ret saymadığı cevaplar |
| `kapi_varyantlari.py` → `sonuc_kapi_varyantlari.txt` | Kapı varyantlarıyla tüm koşuların yeniden sınıflandırılması: (a) naif liste genişletme, (b) ret çerçevesi kuralı |

## Elle sınıflandırma

**A — kapı kaçırıyor (50 farklı cevap metni):**
- 48'i gerçek içerik cevabı; olumsuzluk içeriğin parçası ("kardeşi
  bulunmamalıdır", "bu kümede yer almayan değişkenler", "hiçbir değeri yoktur").
  Doğru olarak TP.
- **Kaçırılan ret 2:**
  - **v8 negatif #222:** "…herhangi bir bilgi bulunmadığından" → yapay FP.
  - **v3 test_4 #95:** "…bir bağlantı belirtilmemiş. Bu nedenle:" → gizli FN
    (TP sayılmış). Bağlam sözcüğü taşımadığı için çerçeve kuralı da yakalamaz;
    kısmi cevap, kabul edilen sınır.

**B — süzgeç kaçırıyor (8):**
- **v3 test_1 #26, #29: saf ret, ama soruda `G_4.5.1` / `L_S.4.8.1` olarak geçen
  tanımlayıcı cevapta `G4.5.1` diye yazılınca "yeni iddia" sayılıyor** → gizli FN.
  Bugünkü kodda da yeniden üretildi (Kalıp B).
- v3 #28: ret + ardından uydurma içerik → TP doğru.
- v3 #50, #56; v7 #47; v8 #49: içerik cevabı → TP doğru.
- v5+neg #231: o koşunun eski skorlayıcısı; bugünkü kod TN veriyor (zaten düzeltilmiş).

## Varyant ölçümü (`sonuc_kapi_varyantlari.txt`)

| | Naif genişletme | **Ret çerçevesi** |
|---|---|---|
| v8 #222 FP → TN | ✅ | ✅ |
| Doğru içerik cevabını FN yapan | her koşuda 2–4 (#12, #13, #15, #50, #98) | **0** |
| Toplam değişen satır (7 koşu) | 18 | **1** (yalnız #222) |

Ret çerçevesi: olumsuzluk yüklemi (olumsuzluk eki zorunlu: `bulunma[dmyzs]…`,
`yer alma[dmyzs]…`, `belirtilme[dmyzs]…`, `gecme[dmyzs]…`, `mevcut degil…`,
`yok(tur)`) **ve** aynı cümlede bağlam sözcüğü (`bilgi`, `doküman`, `belge`,
`bağlam`, `metin`, `kaynak`, `ders not`). Mevcut listeye EK yol; liste aynen
kalır. İlk denemede `bulun(a)?ma\w*` olumlu "bulun**ma**ktadır"ı da yakaladı
(v3 #74'ü bozdu); olumsuzluk eki zorunlu yapılınca düzeldi.

## Üretim tarafı: cevap yarıda kalıyor mu?

Noktalamasız biten cevap: v2 9/100, v3 14/97, v5 9/98, v6 9/130, v7 11/147,
v8 9/144. Bunların neredeyse tamamı formül (`VT = {a, b, c, d}`) ya da kaynak
atfı ("Kaynak: …, sayfa 7") ile biten meşru cevap. v8'de **gerçekten yarım
kalan tek cevap #222.**
