# Dinamik Text-to-Pandas Sandbox & 3 Kademeli Router Uygulama Planı

Bu plan, LLM tabanlı Dinamik Text-to-Pandas Sandbox mimarisini adım adım kurmayı, 3 kademeli akıllı yönlendiriciyi (Router) entegre etmeyi, hata düzeltme (self-correction retry) döngüsünü eklemeyi ve farklı JSON veri setlerinde (%100 genelleştirilebilir biçimde) test etmeyi hedefler.

## Kullanıcı İncelemesi Gereken Konular

> [!IMPORTANT]
> **Windows Uyumluluğu & Timeout**: Python'da `signal.SIGALRM` yalnızca Unix tabanlı işletim sistemlerinde çalışır. Windows ortamında kilitlenmeleri ve sonsuz döngüleri güvenle yakalamak için `concurrent.futures` / `threading` tabanlı bir zaman aşımı (timeout) mekanizması kullanılacaktır.

> [!TIP]
> **Veri Güvenliği & Yan Etki Önleme**: Kod çalıştırılırken orijinal DataFrame'in bozulmaması için DataFrame kopyası (`df.copy()`) üzerinde işlem yapılacak ve `__builtins__` kısıtlanacaktır.

---

## Mimarinin 5 Temel Bileşeni

```
                                  [ Kullanıcı Sorusu ]
                                           │
                                           ▼
                             ┌───────────────────────────┐
                             │    3 KADEMELİ ROUTER      │
                             │ (router.py / route_query) │
                             └─────────────┬─────────────┘
                                           │
         ┌─────────────────────────────────┼─────────────────────────────────┐
         │ (Basit Kalıp)                   │ (Karmaşık/Hesaplama)             │ (Kavramsal/Metin)
         ▼                                 ▼                                 ▼
┌──────────────────┐             ┌───────────────────┐             ┌───────────────────┐
│ 1. Rule Engine   │             │2. Code Interpreter│             │ 3. Semantic RAG   │
│ (Hızlı Regex /   │             │   & Safe Sandbox  │             │ (Vektör + BM25    │
│  Ön Tanımlı)     │             │(LLM + Retry Loop) │             │  + Reranker)      │
└──────────────────┘             └─────────┬─────────┘             └───────────────────┘
                                           │
                                           ├─► Hata durumunda (3 Deneme) ──► [Fallback -> Semantic RAG]
                                           ▼
                                ┌─────────────────────┐
                                │ Natural Language    │
                                │ Synthesizer (Türkçe)│
                                └─────────────────────┘
```

---

## Önerilen Değişiklikler ve Yeni Modüller

### 1. [NEW] `sandbox.py` (Güvenli Kod Çalıştırma Motoru)
- **Yasaklı İfade Filtresi**: `import`, `open(`, `exec(`, `eval(`, `__`, `os.`, `sys.`, `subprocess`, `globals`, `locals`, `getattr`, `setattr`, `delattr`, `compile`, `breakpoint` vb. tehlikeli token'ları derleme öncesi engelleme.
- **Kısıtlı Namespace**: Yalnızca `df` (DataFrame kopyası), `pd` (pandas), `np` (numpy) ve güvenli yerleşik fonksiyonlar (örn. `len`, `range`, `sum`, `min`, `max`, `round`, `int`, `float`, `str`, `dict`, `list`, `set`, `bool`).
- **Cross-Platform Timeout**: Windows ve Linux uyumlu `ThreadPoolExecutor` zaman aşımı sarmalayıcısı (varsayılan: 5 saniye).
- **Sonuç Güvenliği**: Kodun `result` değişkenine atanan çıktısını alma ve doğrulaması.

### 2. [NEW] `code_interpreter.py` (Text-to-Pandas & Retry Döngüsü)
- **`build_code_gen_prompt(question, df)`**:
  - DataFrame'in gerçek şeması (`df.dtypes`), sütun listesi ve ilk 2 satır örnek kayıtlarını dinamik olarak prompt'a enjekte eder.
  - Sadece pandas/numpy kullanımı ve sonucu `result` değişkenine atama talimatı verir. Markdown kod bloklarını (` ```python ... ``` `) temizler.
- **`code_interpreter_with_retry(question, df, llm, max_retries=3)`**:
  - LLM'den kod üretir, `sandbox.safe_execute` ile çalıştırır.
  - Hata oluşursa (SyntaxError, KeyError, TypeError, Timeout vb.), hata mesajını ve hatalı kodu LLM'e geri gönderip düzeltmesini ister.
  - 3 denemede de çözülemezse `error` döner ve Semantic RAG'e fallback yapılır.
- **`result_to_natural_language(question, result, llm)`**:
  - Pandas hesaplama sonucunu (Series, DataFrame, scalar değer veya dict) Türkçe, akıcı, sayıları bozmayan doğal dil cümlesine dönüştürür.

### 3. [MODIFY] `router.py`
- **3 Kademeli Yönlendirme**:
  1. `rule_engine`: Sık kullanılan basit tekil şablonlar (örn. toplam profil sayısı, basit min/max).
  2. `code_interpreter`: Çoklu filtreler, groupby, oran hesapları, yüzdeler, ortalama, dağılım, sıralama, karşılaştırma.
  3. `semantic_rag`: Kavramsal açıklamalar, PDF/Word dokümanları veya şema anlam tanımları.
- `route_query(question, df_schema=None)` fonksiyonu eklenecektir.

### 4. [MODIFY] `retrieval.py` & `data_engine.py`
- `retrieval.py` içinde `code_interpreter` rotasını devreye alma ve fallback mantığını güçlendirme.
- `data_engine.py`'nin hem `728_profiles.json` hem de `airports.json` veya diğer JSON veri setlerini dinamik olarak DataFrame olarak `code_interpreter`'a sunabilmesi.

### 5. [NEW] `test_sandbox_and_datasets.py`
- İzole testler:
  1. **Sandbox İzole Testi**: Doğru kodların başarıyla çalışması, yasaklı kodların (`os.system`, `open`) reddedilmesi, timeout testi.
  2. **Code Generator & Retry Testi**: Şema tabanlı prompt üretimi ve hatalı kodun self-correction ile düzeltilmesi.
  3. **Profil Veri Seti Testi**: `728_profiles.json` zor sorularının dinamik pandas üretimi ile çözülmesi.
  4. **Farklı JSON Veri Seti Testi**: `data/airports.json` (veya yeni bir e-ticaret/ürün JSON'u) üzerinde önceden tanımlı hiçbir kural olmaksızın dinamik soruların (örn: *"Hangi ülkede kaç havaalanı var?", "En yüksek enlemdeki ilk 3 havaalanı", "ABD'deki havaalanlarının ortalama boylamı"* vb.) sıfır hata ile çözülmesi.

---

## Doğrulama Planı

### Otomatik Testler
- `python test_sandbox_and_datasets.py` çalıştırılarak tüm aşamaların (Sandbox güvenliği, Retry mekanizması, `728_profiles.json` ve `airports.json` dinamik sorguları) doğrulanması.

```bash
python test_sandbox_and_datasets.py
```

### Karşılaştırmalı ve Uçtan Uca Test
- `run_tests.py` ile zor JSON sorularının ve genel RAG sorularının test edilmesi.
