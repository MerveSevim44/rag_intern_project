# Plan: madde 24 — alıştırma/talimat parçalarını bağlamda işaretlemek (yön C)

Tarih: 2026-10-11. Taban: `bc68b84`. Ölçüm altyapısı:
[experiments/madde24_ocr_alistirma/](../experiments/madde24_ocr_alistirma/README.md).

## 1. Sorun (özet)

`dffb6a5` ile OCR'lanan Örnek sayfaları (gramer PDF'i 22, 24, 26, 28, 30)
okuyucuya verilen **görev** taşıyor ("…Chomsky normal biçimine (CNF)
dönüştürünüz", "…dilbilgisi tanımlayınız"), konu anlatımı değil. Negatif
sorularda bağlama giriyorlar ve synthesizer prompt'unun (a) dalı ("kısmen ilgili
olsa bile kullan") modeli bu görevi "belgede anlatılan konu" gibi okumaya itiyor:

- **#224:** sayfa 22 dense/BM25/rerank'te 1. (rerank 0.60). Belgede "CNF" geçen
  tek yer bir ödev talimatı. Model sayfa 18'deki yararsız değişken algoritmasını
  "CNF adımları" diye sunuyor. v7'de sayfa 22 yokken aynı sayfalarla TN.
- **test_5 #103:** sayfa 24/28 dolgu olarak giriyor (rerank < 0.04). Model
  pompalama lemması uyduruyor.

Retrieval doğru çalışıyor (sayfa 22 gerçekten en alakalı parça). Eksik olan,
modele parçanın **türünü** söylemek.

## 2. İşaretin formatı ve yeri

**Yer: bağlam kurulurken (`build_context`), chunk metnine/DB'ye değil.**

| Seçenek | Retrieval etkisi | Yeniden ingest | Karar |
|---|---|---|---|
| Chunk metnine önek (ingest) | Embedding + BM25 değişir; #24–#29 retrieval'ı da kayar | Gerekir | Hayır: iki değişkeni birden oynatır |
| `page_info`'ya etiket | Kaynak gösterimi, `bulunan_kaynaklar`, ölçüm regex'leri bozulur | Gerekir | Hayır |
| **`build_context` başlığının altına not satırı** | **Yok** (retrieval bayt bayt aynı) | Gerekmez | **Evet** |

Bu yerin ölçüm açısından avantajı: işaret almayan chunk'lar için LLM'e giden
bağlam **bayt bayt aynı** kalır. Değişikliğin etki alanı deterministik olarak
hesaplanabilir (bkz. §5 Adım 0).

Format (başlık satırının hemen altında, chunk metninden önce):

```
[3] Kaynak: 8-Baglamdan_bagimsiz_dilbilgisi.pdf, sayfa 22
[Not: Bu parça okuyucuya verilen bir görev/alıştırma içerir ("dönüştürünüz").
Görevde adı geçen işlemin belgede ANLATILDIĞINI göstermez; parçadaki tanımlar
(dilbilgisi, küme vb.) yine kullanılabilir.]
4.5.2. Örnek 2 ...
```

- Tırnak içindeki fiil, parçada bulunan ilk emir fiilinin **gerçek yüzey biçimi**:
  model notun neye dayandığını görür.
- "Tanımlar yine kullanılabilir" cümlesi bilinçli: test_1 #24–#29 tam olarak
  Örnek sayfalarındaki dilbilgilerini soruyor. Not "bu parçayı kullanma"
  dememeli.
- Uzunluk ~220 karakter. Yalnız işaretli chunk'lara ekleniyor, bugün en fazla
  5 parça. `MAX_CONTEXT_CHARS` sınırına etkisi ihmal edilebilir; yine de
  `truncate_context` notu kesebilir, birim testte kontrol edilir.

**Kod yeri:** `src/llm_client.py` içinde tek fonksiyon:
`task_instruction_note(text) -> str | None`. Hem `src/app.py::build_context`
hem `evaluation/run_tests.py::build_context` bunu çağırır. İkisi bugün ayrı
kopya; benchmark arayüzle aynı bağlamı ölçmeli. **Synthesizer system prompt'una
dokunulmaz** (ilk aşamada; bkz. §5 Adım 3).

## 3. Tespit kuralı (genel, belgeye özel değil)

**Kural:** aksanı katlanmış metinde, **cümle ya da satır sonunda** biten, 2.
çoğul şahıs emir kipi bir fiil: `-(y)ınız / -(y)iniz / -(y)unuz / -(y)ünüz`,
ardından `. : ; ! ? )` ya da satır sonu.

```python
_TASK_VERB_RE = re.compile(
    r"\b([a-z]{3,}?y?(?:in|un)(?:iz|uz))\s*(?=[.:;!?)\n]|$)", re.M)   # _fold_tr sonrası
```

- Belge adı, sayfa numarası, "Örnek N" başlığı ya da OCR bayrağı **kullanılmaz**.
  Kural düz metin sayfalarındaki alıştırmalara da uygulanır.
- **Cümle sonu şartı** iyelik ekli ortaç / isimleri dışarıda tutar:
  "kullanacağınız", "oluşturduğunuz" (sayfa 22'de geçiyor, cümle ortasında) ve
  "evrakınız" gibi profil metinleri.
- **Korpus ölçümü (916 chunk, 2026-10-11):**
  - Herhangi bir yerde `-iniz/-unuz` geçen 5 chunk var, hepsi Örnek sayfası.
  - Cümle sonu kuralı **tam 5 Örnek sayfasını** (22, 24, 26, 28, 30) işaretliyor.
  - Cevap sayfaları, 728 profil, diğer PDF'ler, JSON ve docx için 0 yanlış
    pozitif.
- **Bilinen genellik riski:** profil benzeri metinde "Randevu için arayınız."
  da işaretlenir. Not metni bu yüzden "alıştırma" değil **"görev/talimat"**
  diyor. "Arayınız" için de doğru bir ifade bu ve zararsız. Bugün korpusta
  böyle bir örnek yok; yeni veri eklenince Adım 0 script'i yeniden çalıştırılır.

## 4. Başarı ölçütleri ve regresyon kontrolü

**Başarı (hepsi gerekli):**
1. #224 ve test_5 #103: FP → TN.
2. #217 ve test_5 #102 (OCR sayfası bağlamda, bugün TN): TN kalır.
3. Etki alanındaki **11 pozitif test_1 sorusu** (#1, #2, #4, #8, #9, #24, #25,
   #26, #28, #29, #30; Adım 0 sonucu) bozulmaz: v8'deki FN→TP kazanımları (#25,
   #26, #29) korunur, judge ve F1'de belirgin düşüş olmaz. İlk taslak yalnız
   #24–#29'u sayıyordu; Adım 0, Örnek sayfalarının G4.1/G4.3 gibi başka
   sorularda da dolgu olarak bağlama girdiğini gösterdi.
4. Tam negatif sette (32) FP artmaz; tripwire
   (`experiments/madde25_ret_tespiti/uzun_ret_tripwire.py`) 0 eşleşme.

**Kapsam dışı:** test_5 #101. v7'de de FP'ydi (OCR yokken sayfa 18/19'dan aynı
CNF uydurması), OCR'a atfedilmez. TN olursa bonus; FP kalırsa başarısızlık
sayılmaz.

**Nondeterminizm:** `llm_client.py`'deki not, izole A/B'nin modelin
nondeterminizmi yüzünden yanılttığını kaydediyor. Etkilenen sorular **3 tekrar**
koşulur; sınıf, 3'te en az 2 olarak raporlanır.

## 5. Adımlar (her biri ayrı commit, adım sonunda durulur)

**Adım 0 — etki alanı (kod değişikliği yok, servis: Ollama + reranker).**
`experiments/madde24_ocr_alistirma/etkilenen_set.py`:
- Tüm benchmark soruları (test_1..5 + negatif) için `retrieve(top_k=5)`.
- Nihai bağlamında §3 kuralına uyan chunk olan soruları listeler.

Bu küme dışındaki sorularda LLM prompt'u bayt bayt değişmez. Plan dosyası bu
adımla commit edilir.

*Sonuç (2026-10-11, `sonuc_etkilenen_set.txt`):*
- **Korpus:** 916 chunk'ın 5'i işaretli, beklenmeyen 0. Liste fiillerle
  birlikte çıktıda; yeni veri geldiğinde aynı çıktıyla karşılaştırılır.
- **Etkilenen sorular:** 147 sorudan 16'sı.
  - test_1: 11 (#1, #2, #4, #8, #9, #24, #25, #26, #28, #29, #30)
  - test_5: #101, #102, #103
  - negatif: #217, #224
- **v8 kaynak listesinden farklı çıkanlar: 26.**
  - 23'ü `code_interpreter` rotasında. Script LLM'siz koştuğu için bu fark
    beklenen; bu sorular PDF'e gitmiyor.
  - 3'ü `semantic_rag` rotasında: test_2 #36, test_4 #93, negatif #217.
    Bugün 3/3 tekrarda kararlı.
  - Fark hep son sıralarda ve hibrit sıralamanın neredeyse eşit skorlu
    sınırında. #217'de 5–7. sıranın RRF skorları 0.9307 / 0.9303 / 0.9250:
    v8'de sayfa 17 içerideydi, bugün sayfa 28 giriyor.
  - Hipotez (doğrulanmadı): Ollama bge-m3 embedding'i oturumlar arasında
    küçük sayısal kayma gösteriyor (madde 25 Adım 2'deki `semantic_sim`
    ±0.1–0.2 gürültüsüyle aynı aile). Benchmark sırasında Foundry GPU'dayken
    Ollama'nın farklı bir cihaz/bölüşümde koşması olası bir kaynak.
- **Sonuç:** Adım 0 kümesi bir **tahmin**. Gerçek koşuda sınırdaki sorular
  kayabilir. Etki alanı Adım 2'de koşunun **kendi kaydettiği bağlamdan**
  yeniden hesaplanır.

**Adım 1 — `task_instruction_note` + iki `build_context` + birim testler.**
`build_context(..., task_notes=True)`: arayüz her zaman açık kullanır,
parametre yalnız Adım 2'nin A/B'si için. `etkilenen_set.py` kendi kural
kopyası yerine `task_instruction_note`'u kullanacak şekilde değiştirilir ve
korpus listesinin aynı çıktığı doğrulanır.
`tests/test_task_instruction_note.py`:
- 5 Örnek sayfası işaretlenir (gerçek metinler).
- Cevap sayfaları işaretlenmez.
- Cümle ortası "kullanacağınız" işaretlenmez.
- İşaretsiz chunk'ta bağlam önceki çıktıyla bayt bayt aynıdır.
- Not, `truncate_context` sonrası bozulmaz.

**Adım 2 — ölçüm (Foundry).**
- Adım 0 kümesi × 3 tekrar, **işaret açık ve kapalı, aynı oturumda**. Bunun
  için `build_context`'e varsayılanı açık bir parametre gerekir (Adım 1'de
  eklenir). Gerekçe: Adım 0 retrieval'ın oturumlar arasında sınırda kaydığını
  gösterdi. v8 ile karşılaştırma işaretin etkisini retrieval kaymasıyla
  karıştırır; aynı oturumdaki A/B karıştırmaz.
- Etki alanı koşunun kaydettiği `context` sütunundan yeniden hesaplanır: hangi
  soruların bağlamında not satırı var.
- Tam 32 soruluk negatif set × 1 (prompt'a dokunan değişiklikler için koyulan
  kural; burada yalnız işaretli sorularda değişiyor, yine de koşulur).
- Tripwire.

Sonuçlar §4'e göre raporlanır, `experiments/madde24_ocr_alistirma/` altına
PROVENANCE ile kaydedilir.

**Adım 3 — yalnız Adım 2 yetmezse:** system prompt'a tek kural satırı
("[Not: …görev…] işaretli parça, konunun anlatıldığına kanıt değildir").
Bu tüm prompt'ları değiştirir: tam benchmark (test_1..5 + negatif) gerekir.
Ayrı karar.

## 6. Denenip reddedilen alternatif: ret kapısını genişletmek

Öneri: "verilmemiştir" gibi ifadeleri `check_is_not_found` kapısına eklemek;
#103 ingest/prompt değişikliği olmadan TN olabilir mi?

**Ölçüldü (2026-10-11):** "verilmemis" kapıya eklenince v8 #103
`check_is_not_found` → **True** (TN). Yeni iddia süzgeci boş.

**Reddedildi, çünkü bu bir düzeltme değil, ölçüm hatası olur.**
- #103'ün cevabı uydurma içerik taşıyor: "pompalama lemması, bir dilin bağlamdan
  bağımsız olduğunu göstermek için kullanılan bir yöntemdir… her parçasının hâlâ
  dilin bir üyesi olduğunu garantiler". Bu bilgi bağlamda yok, üstelik yanlış:
  lemma bir dilin bağlamdan bağımsız **olmadığını** göstermek için kullanılır.
  Cevabın sonundaki "doğrudan bilgi verilmemiştir, bu nedenle:" bir sonradan
  çekince.
- TN saymak, kullanıcıya görünen bir halüsinasyonu skorda gizler. Bu tam olarak
  madde 28'in tarif ettiği melez "ret + uydurma" biçimi; tripwire bu yüzden kondu.
- #224'te ret ifadesi hiç yok; kapı değişikliği onu etkilemez.

Sonuç: "verilmemiştir" kapıya **eklenmemeli**, en azından madde 28 (ikinci
aşamaya içerik miktarı kontrolü) çözülmeden. Kapı genişletmesi ileride
yapılırsa v8 #103 bir **negatif test vakası** olarak kullanılmalı: genişletilmiş
kapı onu ret saymamalı.

## 7. Kritik dosyalar

- `src/llm_client.py`: yeni `task_instruction_note`; prompt'a dokunulmaz (Adım 3 hariç).
- `src/app.py::build_context`, `evaluation/run_tests.py::build_context`: not satırı.
- `tests/test_task_instruction_note.py`: yeni.
- `experiments/madde24_ocr_alistirma/`: `etkilenen_set.py`, Adım 2 sonuçları, PROVENANCE.
