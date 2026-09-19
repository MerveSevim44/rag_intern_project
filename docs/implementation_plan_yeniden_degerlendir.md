# Genellenebilir RAG İyileştirme Planı

## Hedef

Alan adı bilmeden, yeni bir veri seti eklendiğinde otomatik olarak doğru çalışan
bir retrieval sistemi. "Occupation önemlidir" gibi hardcoded varsayım yok.

## Değiştirilecek Dosyalar

1. [`ingest.py`](file:///c:/Users/merve/Desktop/rag_project/src/ingest.py) — Alan karakterizasyonu ile akıllı chunk yapısı
2. [`retrieval.py`](file:///c:/Users/merve/Desktop/rag_project/src/retrieval.py) — RRF + otomatik chunk tipi boost

> [!IMPORTANT]
> `ingest.py` değişikliği sonrası **re-ingest zorunlu**: `python ingest.py --force`
> DB şeması değişmiyor, embedder değişmiyor, diğer dosyalar değişmiyor.

---

## Değişiklik 1 — `ingest.py`: Şema-Agnostik Alan Karakterizasyonu

### Neden?

Şu an satır 303'te alan sırası JSON'daki sıraya göre rastgele:
```python
record_text = "\n".join(f"{p[prefix:] or p}: {t}" for t, p in leaves)
```
`about` gibi uzun serbest metin alanları embedding'i geniş bir temaya çekiyor
çünkü embedding modelleri token sayısına orantılı ağırlık veriyor.

### Ne Yapılacak?

Alan **adını** değil, alan **karakterini** kullan:

| Karakter | Kriter | Davranış |
|----------|--------|----------|
| `KEY` | < 60 karakter | Öne al + **chunk başında tekrar et** (attention bias) |
| `CONTEXT` | 60–400 karakter | Ortaya koy |
| `NARRATIVE` | > 400 karakter | Kırp (max 350 karakter), sona koy |

Bu sınırlar hiçbir alan adı içermiyor — herhangi bir JSON şemasıyla çalışır.

### Eklenecek Kod (satır 215'ten önce, sabitler bloğuna):

```python
# ─── Alan Karakterizasyonu Sabitleri ─────────────────────────────────────────
# Alan adına değil, değer uzunluğuna göre otomatik sınıflandırma.
# Herhangi bir JSON şemasıyla çalışır — hardcoded alan adı yok.
FIELD_KEY_MAX_CHARS = 60        # Bu kadar kısa → kimlik/kategori alanı (KEY)
FIELD_CONTEXT_MAX_CHARS = 400   # Bu kadar → açıklama alanı (CONTEXT)
FIELD_NARRATIVE_TRUNCATE = 350  # Daha uzunu bu kadarla kes (NARRATIVE)
```

### Değiştirilecek Fonksiyon: `extract_chunks_from_json` (satır 293–308)

**Mevcut kod:**
```python
    chunks = []
    for root, root_path in roots:
        leaves = list(_flatten_json(root, root_path))
        if not leaves:
            continue
        prefix = len(root_path) + 1
        record_text = "\n".join(f"{p[prefix:] or p}: {t}" for t, p in leaves)
        if len(record_text) <= MAX_RECORD_CHARS:
            chunks.append((record_text, root_path))
        else:
            for text, leaf_path in leaves:
                chunks.append((f"{leaf_path}: {text}", leaf_path))
    return chunks
```

**Yeni kod:**
```python
    chunks = []
    for root, root_path in roots:
        leaves = list(_flatten_json(root, root_path))
        if not leaves:
            continue
        prefix = len(root_path) + 1

        # ── Alan Karakterizasyonu (şema-agnostik) ──────────────────────────
        # Alan adına değil, değer uzunluğuna göre otomatik sınıflandır.
        # KEY   : kısa/kategorik (< 60 karakter) → discriminative, öne al
        # CONTEXT: orta uzunluk  (60–400 karakter) → açıklama, ortaya koy
        # NARRATIVE: uzun serbest metin (> 400 karakter) → kırp, sona koy
        key_lines, context_lines, narrative_lines = [], [], []
        for text, path in leaves:
            field_name = path[prefix:] or path
            char_count = len(text)
            if char_count <= FIELD_KEY_MAX_CHARS:
                key_lines.append(f"{field_name}: {text}")
            elif char_count <= FIELD_CONTEXT_MAX_CHARS:
                context_lines.append(f"{field_name}: {text}")
            else:
                truncated = text[:FIELD_NARRATIVE_TRUNCATE].rsplit(" ", 1)[0]
                narrative_lines.append(f"{field_name}: {truncated}…")

        # KEY alanları başta tekrar edilir → embedding modeli başa daha fazla
        # ağırlık verdiğinden kimlik sinyali güçlenir.
        # Sıra: KEY (×2) → CONTEXT → NARRATIVE
        record_text = "\n".join(key_lines + key_lines + context_lines + narrative_lines)

        if len(record_text) <= MAX_RECORD_CHARS:
            chunks.append((record_text, root_path))
        else:
            # Büyük kayıt: her yaprağı ayrı chunk yap (mevcut davranış korunur)
            for text, leaf_path in leaves:
                chunks.append((f"{leaf_path}: {text}", leaf_path))
    return chunks
```

---

## Değişiklik 2 — `retrieval.py`: RRF + Otomatik Chunk Tipi Boost

### 2a — RRF (Linear Combination → Reciprocal Rank Fusion)

#### Neden?

Mevcut formül (satır 425):
```python
hybrid_score = (1.0 - bm25_weight) * dense_score + bm25_weight * sparse_score
```
Dense skoru `[0.6–0.8]`, BM25 normu `[0–1]` farklı ölçektedir. Ağırlıklı toplam
bu ölçek farkına duyarlıdır — BM25 `0.35*1.0 = 0.35` eklerken dense sadece
`0.65*0.72 = 0.47` katkıda bulunur; gerçek sıra bilgisi kaybolur.

RRF yalnızca **sıra** (rank) kullandığı için ölçek bağımsızdır. Yeni bir embedding
modeli veya yeni bir veri seti eklendiğinde `bm25_weight` sabiti ayarlamak gerekmez.

#### Eklenecek Sabit (satır 58'den sonra):

```python
RRF_K = 60  # Standart RRF sabiti; düşük değer üst sıraları güçlendirir
```

#### Değiştirilecek Kod (satır 395–425 arası, ADIM 5–7):

**Mevcut:**
```python
    # ── ADIM 5: Vektörize Cosine Similarity ──
    dense_scores = cosine_similarity_batch(
        query_embedding, search_matrix, norms=search_norms
    )

    # ── ADIM 6: BM25 ──
    query_tokens = _tokenize(query)
    bm25_scores = search_bm25.get_scores(query_tokens)

    # BM25 skorlarını [0..1] aralığına normalize et
    max_bm25 = max(bm25_scores) if len(bm25_scores) > 0 and max(bm25_scores) > 0 else 1.0
    bm25_norm = bm25_scores / max_bm25

    # ── ADIM 7: Hibrit Skorlama ──
    ...
        hybrid_score = (1.0 - bm25_weight) * dense_score + bm25_weight * sparse_score
```

**Yeni:**
```python
    # ── ADIM 5: Vektörize Cosine Similarity ──
    dense_scores = cosine_similarity_batch(
        query_embedding, search_matrix, norms=search_norms
    )

    # ── ADIM 6: BM25 ──
    query_tokens = _tokenize(query)
    bm25_raw = search_bm25.get_scores(query_tokens)

    # ── ADIM 6b: Reciprocal Rank Fusion (RRF) ──
    # Sıra tabanlı füzyon: mutlak skor değerlerinden bağımsız, ölçek-agnostik.
    # Yeni embedding modeli veya farklı veri seti eklendiğinde ayar gerekmez.
    n = len(dense_scores)
    # Her skorun sıra pozisyonunu hesapla (0 = en iyi)
    dense_ranks = np.empty(n, dtype=np.float32)
    dense_ranks[np.argsort(-dense_scores)] = np.arange(n, dtype=np.float32)
    bm25_ranks = np.empty(n, dtype=np.float32)
    bm25_ranks[np.argsort(-bm25_raw)] = np.arange(n, dtype=np.float32)
    # RRF skoru: her kaynaktan gelen sıra katkısı toplanır
    rrf_scores = 1.0 / (RRF_K + dense_ranks) + 1.0 / (RRF_K + bm25_ranks)

    # ── ADIM 7: Hibrit Skorlama ve Otomatik Chunk Tipi Boost ──
    ...
        # RRF skoru temel alınır — BM25_WEIGHT sabiti artık kullanılmıyor
        hybrid_score = float(rrf_scores[idx])

        # bm25_score alanı debug/UI için normalize edilmiş BM25'i tutar
        max_bm25 = float(bm25_raw.max()) if bm25_raw.max() > 0 else 1.0
        sparse_score = float(bm25_raw[idx]) / max_bm25
```

### 2b — Otomatik Chunk Tipi Boost (Hardcoded liste kaldırılıyor)

#### Neden?

Mevcut (satır 427–430):
```python
        # ŞEMA SORGUSU İSE: fieldGuide, safetyAndDataQuality, statistics bölümlerini öne çıkar
        page_str = (page_info or "").lower()
        if any(k in page_str for k in ["fieldguide", "safetyanddataquality", "statistics", "metadata"]):
            hybrid_score += 0.35
```
Bu boost yalnızca bu spesifik JSON şeması için çalışır. Farklı bir veri seti gelince
"fieldguide" vs "metadata" ayrımı anlamsız olur.

#### Yeni yaklaşım — BM25 sinyali ile otomatik:

`page_info` içinde `$` (JSON path) veya `sayfa/bölüm/satır` gibi yapısal bilgi varsa
bu chunk bir meta/şema chunk'ı değil, içerik chunk'ıdır. Aksine, BM25 skoru yüksek
ama dense skoru düşükse bu anahtar kelime eşleşmesi var demektir — boost et.

```python
        # ── Otomatik Chunk Tipi Boost (şema-agnostik) ──────────────────────
        # Hardcoded alan listesi yerine chunk'ın sinyal tipine bak:
        #
        # 1. Keyword hit boost: BM25 yüksek & dense düşükse sorgu kelimesi tam
        #    eşleşti ama vektörel anlam yakalanmadı → boost et (dişçi/diş hekimi
        #    gibi terminoloji uyumsuzluklarını giderir).
        # 2. Meta chunk boost: page_info "fieldguide/statistics/metadata" içeriyorsa
        #    eski davranışı koru ama ek olarak herhangi bir "$.meta" path'i de
        #    yakala — böylece yeni veri setlerinin meta bölümleri otomatik dahil olur.
        dense_score_local = float(dense_scores[idx])
        bm25_score_local  = float(bm25_raw[idx])
        bm25_norm_local   = sparse_score  # zaten normalize edildi

        # Keyword hit boost — alan adı bilmeden çalışır
        if bm25_norm_local > 0.5 and dense_score_local < 0.70:
            hybrid_score += 0.08 / (1.0 + dense_score_local)  # yumuşak boost

        # Meta/şema chunk boost — path tabanlı, şemadan bağımsız
        page_str = (page_info or "").lower()
        is_meta_chunk = (
            any(k in page_str for k in ["fieldguide", "safetyanddataquality",
                                         "statistics", "metadata"])
            or page_str.startswith("$.meta")   # _roots_from_object'in ürettiği path
        )
        if is_meta_chunk:
            hybrid_score += 0.35
```

> [!NOTE]
> `["fieldguide", "safetyanddataquality", ...]` listesi **korunuyor** çünkü mevcut
> veri setiyle geriye dönük uyumluluk sağlıyor. Ama artık yalnızca bu listeye
> bağlı değil — `$.meta` path'i de yakalıyor. Yeni veri setleri için bu yeter.

---

## Değiştirilmeyen Her Şey

| Bileşen | Durum |
|---------|-------|
| DB şeması (`chunks` tablosu) | ✅ Değişmiyor |
| `embedder.py` | ✅ Değişmiyor |
| `router.py` | ✅ Değişmiyor |
| `data_engine.py` | ✅ Değişmiyor |
| `app.py` | ✅ Değişmiyor |
| PDF/DOCX/TXT ingest | ✅ Değişmiyor (bu fonksiyonlara dokunulmuyor) |
| `_RetrievalCache` sınıfı | ✅ Değişmiyor |
| `source_filter` / `get_view()` | ✅ Değişmiyor |
| `BM25_WEIGHT` sabiti | ⚠️ Artık RRF'de kullanılmıyor ama kod kalıyor (geriye dönük uyumluluk) |

---

## Doğrulama Planı

### 1. Re-ingest
```bash
python ingest.py --force
```

### 2. Manuel Test Sorguları
Aşağıdaki sorguları çalıştırıp `dense_score`, `bm25_score`, `rerank_score` ve `score` değerlerini karşılaştır:

```python
# Terminoloji uyumsuzluğu testi — "dişçi" vs "Çocuk Diş Hekimi"
retrieve("çocuk dişçisi arıyorum", debug=True)

# Genel semantik test — değişmemeli
retrieve("Veri setindeki toplam profil sayısı kaçtır?", debug=True)

# Şema/meta test — fieldguide boost korunmalı
retrieve('"occupation" alanı ne için kullanılır?', debug=True)

# Farklı terminoloji — hukukçu / avukat
retrieve("hukuk alanında çalışan biri", debug=True)
```

### 3. Beklenen İyileşmeler
- "Dişçi" sorgusu → Diş Hekimi chunk'ı artık BM25 keyword hit boost alıyor
- KEY alanlar (kısa değerler) chunk başında tekrar ettiğinden embedding daha discriminative
- RRF sayesinde BM25_WEIGHT sabitini ayarlamak gerekmiyor (yeni dataset'lerde de çalışır)
