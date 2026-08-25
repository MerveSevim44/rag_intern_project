# Performans & Yapı İyileştirme Planı

## Amaç

Mevcut RAG projesinde tespit edilen performans darboğazlarını gidermek ve bakım kolaylığı için `app.py`'yi yapısal olarak bölmek.

---

## Proposed Changes

### 1. Retrieval Performansı — Vektörize Cosine Similarity & Cache

#### [MODIFY] [`retrieval.py`](file:///c:/Users/merve/Desktop/rag_project/src/retrieval.py)

**Sorun:** Her sorguda tüm chunk embedding'leri `json.loads()` ile parse ediliyor ve tek tek cosine similarity hesaplanıyor (O(n) JSON parse + O(n) ayrı numpy dönüşümü).

**Çözüm:**
- **Chunk + BM25 Cache:** DB'den okunan chunk verileri ve BM25 indeksi modül seviyesinde cache'lenecek. İlk sorgu sonrası tekrar DB'ye gitmeyecek. Yeni doküman eklendiğinde cache invalidate olacak.
- **Numpy Matris Cosine Similarity:** Tüm embedding'ler tek bir numpy matrisine dönüştürülecek, cosine similarity matris çarpımıyla toplu hesaplanacak (döngü yerine vektörize işlem).

```python
# Önceki: Her chunk için ayrı JSON parse + cosine sim
for idx, (chunk_id, source, content, embedding_json, page_info) in enumerate(rows):
    chunk_embedding = json.loads(embedding_json)           # ← Yavaş
    dense_score = float(cosine_similarity(query_embedding, chunk_embedding))

# Sonraki: Tek matris çarpımıyla toplu hesaplama
embedding_matrix = np.array([json.loads(row[3]) for row in rows])  # Bir kez
norms = np.linalg.norm(embedding_matrix, axis=1)                   # Bir kez
query_vec = np.array(query_embedding)
dense_scores = embedding_matrix @ query_vec / (norms * np.linalg.norm(query_vec))
```

---

### 2. Embedder — Batch Cosine Similarity Fonksiyonu

#### [MODIFY] [`embedder.py`](file:///c:/Users/merve/Desktop/rag_project/src/embedder.py)

Mevcut `cosine_similarity()` sadece 2 vektör alıyor. Yeni bir `cosine_similarity_batch()` fonksiyonu eklenerek retrieval'ın vektörize hesaplama yapması desteklenecek.

---

### 3. App.py Yapısal Ayrıştırma — CSS & Bileşenler

#### [NEW] [`styles.py`](file:///c:/Users/merve/Desktop/rag_project/src/styles.py)
- `app.py`'deki ~290 satırlık CSS string'i `inject_custom_css()` fonksiyonuna taşınacak.

#### [NEW] [`components.py`](file:///c:/Users/merve/Desktop/rag_project/src/components.py)
- `render_doc_card()`, `render_source_card()`, `render_sources()`, `render_assistant_message()`, `empty_state()`, `render_ready_state()`, `suggested_questions()`, `score_visual()` gibi UI fonksiyonları buraya taşınacak.

#### [MODIFY] [`app.py`](file:///c:/Users/merve/Desktop/rag_project/src/app.py)
- CSS ve UI bileşen importları `styles.py` ve `components.py`'dan alınacak.
- `app.py` yalnızca sayfa yapılandırması, sidebar, sohbet akışı ve sorgu işleme mantığını barındıracak (~400 satır hedef).

---

## Verification Plan

### Manual Verification
- `python -c "from src.retrieval import retrieve; print('OK')"` — import kontrolü
- `python -c "from src.embedder import cosine_similarity_batch; print('OK')"` — yeni fonksiyon
- `python -c "from src.styles import inject_custom_css; print('OK')"` — styles modülü
- `python -c "from src.components import render_assistant_message; print('OK')"` — components modülü
- Streamlit uygulamasının çalıştığını doğrulamak için `streamlit run app.py` ile görsel kontrol

### Automated Tests
- Mevcut testler: `python -m pytest tests/ -v`
