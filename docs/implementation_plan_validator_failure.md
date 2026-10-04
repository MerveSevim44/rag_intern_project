# Semantik doğrulayıcının sessiz çökmesi — A aşaması: görünürlük + ölçüm

İlgili: [backlog_retrieval.md](backlog_retrieval.md) madde 11 (servis çökmesi),
madde 14 (`service_failure` ayrımı). Bu doküman A aşamasının planıdır;
davranış değişikliği (B) ölçüm sonucuna göre ayrıca kararlaştırılacak.

## 1. Sorun

`code_interpreter._semantic_check` ([code_interpreter.py:685-688](../src/code_interpreter.py#L685-L688)):

```python
try:
    verdict = call_llm_text(llm, prompt).strip()
except Exception:
    return None
```

`None` = "itiraz yok". Doğrulayıcının LLM çağrısı patlarsa sonuç **doğrulanmış
gibi** döner ve retrieval onu `[KESİN HESAPLAMA SONUCU]` etiketiyle
synthesizer'a verir. Üç durum bugün log'da birbirinden ayırt edilemiyor:

| Durum | Log izi | Dönüş |
|---|---|---|
| Doğrulayıcı "TAMAM" dedi | yok | `None` |
| Doğrulayıcı emin değil, prompt gereği "TAMAM" dedi | yok | `None` |
| **Doğrulayıcı çöktü** | **yok** | `None` |

Ek (tasarım gereği, bu planda değişmiyor): `attempt < max_retries` koşulu
yüzünden **son denemenin sonucu hiç doğrulanmaz**. Yani `KESİN` etiketi
bugün de "doğrulandı" garantisi değil. A bunu da görünür kılar.

## 2. A'nın kapsamı

**Davranış değişmez.** Context etiketi, synthesizer talimatı ve kullanıcının
gördüğü cevap aynı kalır. Yalnızca her sandbox sonucunun doğrulama durumu
kaydedilir, log'a yazılır ve eval sonuç CSV'sine taşınır. Amaç: B kararını
(unverified mi, retry mı) gerçek sıklığa dayandırmak.

## 3. Tasarım

### 3.1 Durum alanı: `validation_status`

Dönen sandbox sonucunun doğrulama durumu:

| Değer | Anlamı |
|---|---|
| `ok` | Doğrulayıcı çalıştı, itiraz etmedi |
| `objection` | Doğrulayıcı itiraz etti, düzeltme tutmadı; dönen sonuç `fallback_result` (bugünkü `validation_warning` yolu) |
| `failed` | **Doğrulayıcının LLM çağrısı istisna fırlattı; sonuç doğrulanmadan döndü** |
| `not_run` | Doğrulama hiç çağrılmadı (son deneme ya da `self_check=False`) |

`failed` durumunda ek alan: `validation_error` = `"<IstisnaTipi>: <mesajın ilk 150 karakteri>"`.

### 3.2 Değişecek yerler (ürün kodu)

1. **code_interpreter.py**
   - `_semantic_check(..., info=None)`: `safe_execute(info=exec_meta)` ile aynı
     kalıp. İstisnada `info["error"] = ...` doldurulur, dönüş yine `None`
     (davranış aynı). İmza geriye uyumlu.
   - Çağıran taraf `check_meta`'ya bakıp durumu belirler; başarılı dönüşe ve
     `fallback_result`'a `validation_status` (+ gerekiyorsa `validation_error`)
     eklenir.
   - Çökmede `verbose`'dan bağımsız log satırı (bkz. 3.3).
2. **data_engine.py** (~663, sandbox başarı dalı): `validation_status` ve
   `validation_error` dönüş sözlüğüne aynen geçirilir. `unverified` hesabına
   **dokunulmaz** (o B'nin işi).
3. **retrieval.py** (~600, sandbox chunk'ı): chunk sözlüğüne
   `"validation_status": agg_result.get("validation_status")` ve
   `"validation_error": agg_result.get("validation_error")`. Etiket seçimi aynı.

Tahmini boyut: 3 dosya, ~20-25 satır.

### 3.3 Log formatı

**code_interpreter** (her çökmede, `verbose`'dan bağımsız; soru id'sini
bilmez, soru metninin başını yazar):

```
[CodeInterpreter] DOGRULAYICI CALISMADI (deneme 1/3): OpenAIAPIError: Error code: 500 - ... | soru="Emre Korkmaz ve Umut Aslan profillerinin..." -> sonuc dogrulanmadan KESIN etiketiyle donuyor
```

**run_tests.py** — soru bazında (yalnızca `ok` dışındaki durumlarda):

```
[44] Soruluyor: appointmentSettings içindeki ...
    ! doğrulama: failed (OpenAIAPIError: Error code: 500) — context [1] [KESİN HESAPLAMA SONUCU] doğrulanmadı
    → 41.3 sn
```

Run sonunda özet (sandbox sonucu dönen sorular üzerinden):

```
Semantik doğrulama (11 sandbox sorusu): ok=7 objection=1 failed=1 not_run=2
  failed : #44 (OpenAIAPIError)
  not_run: #57, #60
```

**Sonuç CSV'si:** yeni sütun `dogrulama_durumu`. Sandbox dışı satırlarda boş;
sandbox satırlarında `ok` / `objection` / `not_run` /
`failed (OpenAIAPIError: Error code: 500)`. Etkilenen context alanı her zaman
tektir: code_interpreter'ın döndürdüğü `[1]` bloğu. Sütun, soru id'sini o
bloğun etiketine (`KESİN` / `DOĞRULANAMAYAN`) bağlar.
`llm_as_judge` ve `benchmark_eval` sütunları adla okuduğu için ek sütun
onları etkilemez (testte doğrulanacak).

## 4. Ölçüm: 13 aday satırın yeniden koşulması

Mevcut sonuçlarda `[KESİN HESAPLAMA SONUCU]` context'i alan 13 satır, bu
sorundan etkilenmiş olabilecek **tek** satırlar:

- test_2: 32, 35, 37, 39, 42, 44, 45, 51, 52, 57, 60
- test_5: 107, 108 (negatif set)

**Evet, yeniden koşulacaklar**, A kodu yerleştikten sonra. Kurallar:

- **Ayrı çıktıya yazılır**: `evaluation/datasets/olcum_validator_A.csv`. Ana
  sonuç CSV'leri ölçüm yüzünden değişmez. Birleştirme ayrı bir karar.
- **İki geçiş.** Madde 11'in çökme eşiği deterministik değil; tek geçişte
  `failed=0` görmek "hiç olmuyor" demek değil.
- **Sınır, açıkça:** Bu ölçüm, **bugünkü** sıklığı izole koşulda gösterir. Eski
  22:39 koşusunda ne olduğunu geri getiremez; o bilgi hiç kaydedilmedi. Ayrıca
  izole tekrar, tam koşudaki "önceki soru Foundry'yi bozdu, sonraki sorunun
  doğrulayıcısı çöktü" zincirini (madde 11) üretmez. Gerçekçi sayı, A
  yerleştikten sonraki ilk **tam test_2 koşusundan** gelir. Bu da ölçümün
  parçası.
- Yeniden koşulan cevaplar değişeceği için bu satırların judge skoru da
  yeniden alınmalı. Groq günlük limiti 200k token; 13 satır ≈ 45-50k.

## 5. Ek doğrulama katmanı: ground truth'a göre doğruluk

Faithfulness bu sorunu **yakalayamaz**: doğrulanmamış yanlış sayı context'te
`KESİN` olarak duruyorsa cevap onu sadakatle tekrarlar ve F=5 alır. Bu yüzden
13 satır için ek olarak `benchmark_eval` doğruluk metrikleri kullanılır.

- `benchmark_eval` test_2 ve test_5 için çalıştırılır. 13 satır satır bazlı
  skor dosyasından (`report/<set>_scored.csv`) çekilir: F1, ROUGE-L, semantik
  benzerlik. 107/108 negatif olduğu için onlarda TN/FP sınıflandırması.
- Hem **mevcut** cevaplar hem **ölçüm** cevapları için yapılır, yan yana.
- Okuma kuralı:

| Judge F | Doğruluk (GT) | `dogrulama_durumu` | Yorum |
|---|---|---|---|
| yüksek | yüksek | herhangi | Sorun yok |
| yüksek | **düşük** | `failed` | **Bu bug: doğrulanmamış yanlış hesap KESİN olarak geçti** |
| yüksek | **düşük** | `ok` | Doğrulayıcı çalıştı ama kaçırdı (gevşek "emin değilsen TAMAM"). Ayrı sorun |
| yüksek | **düşük** | `not_run` | Son deneme sonucu, hiç doğrulanmadı. Ayrı sorun |
| düşük | — | — | Cevap context'ten saptı (ör. #37, #45). Bu bug değil |

Mevcut cevaplar için `dogrulama_durumu` sütunu yok. Orada "yüksek F + düşük
doğruluk" yalnızca **aday** listesi verir; nedeni (çöktü / kaçırdı / son
deneme) ayırt edilemez. Önceden şüpheli görünenler: #44 (kavramsal soruya
sayısal fark), #57 (sorulan oranla verilen oran uyuşmuyor), #51 (context
yalnızca "true doğrulandı").

## 6. Testler

`tests/test_semantic_check_failure.py` (sahte LLM ile, servis gerekmez):

1. Doğrulayıcı çağrısı istisna fırlatır → `validation_status == "failed"`,
   `validation_error` dolu, log satırı basılır, **dönen sonuç bugünküyle aynı**
   (davranış değişmedi).
2. "TAMAM" → `ok`.
3. "SORUN: ..." + düzeltme tutmaz → `objection`.
4. Son deneme / `self_check=False` → `not_run`.
5. `data_engine` ve retrieval chunk'ı alanı taşır; etiket hâlâ `KESİN`.
6. run_tests: sahte chunk ile `dogrulama_durumu` sütunu ve özet satırı.
   Ek sütunlu CSV `llm_as_judge` / `benchmark_eval` tarafından okunabiliyor.

Mevcut test paketi (`pytest tests/`) yeşil kalmalı.

## 7. Commit sırası (her biri ayrı onayla)

1. `feat(code_interpreter): semantik doğrulayıcı durumunu (validation_status) kaydet ve taşı`
   → code_interpreter + data_engine + retrieval + testler + bu plan dokümanı
   + backlog'a madde 16 kaydı (15 zaten servis süreç yönetimine ait).
2. `feat(eval): run_tests'e dogrulama_durumu sütunu ve özet satırı`
3. `chore(eval): validator A ölçümü — 13 aday satır, 2 geçiş + benchmark karşılaştırması`
   (ölçüm CSV'si + sonuç notu bu dokümana eklenir)

## 8. Kapsam dışı: B aşaması

Ölçümden sonra karar verilecek:

- `failed` → `unverified_result` yoluna bağlamak (`[DOĞRULANAMAYAN SONUÇ]`;
  kullanıcı "doğrulanamadı" görür). Bu daha dürüst; skorların bir miktar
  düşmesi beklenir ve kabul edilmiştir. Bu bir regresyon değil, ölçümün
  doğrulaşmasıdır.
- ya da doğrulayıcıyı bir kez yeniden denemek.
- Karar ölçütü: `failed` çoğunlukla madde 11 zincirinin ardından geliyorsa
  (servis bozuk) retry işe yaramaz, `unverified` doğru olur. İzole ve geçici
  ise tek retry yeterli olabilir.
- `not_run` (son denemenin doğrulanmaması) ayrı bir soru olarak kalır.
