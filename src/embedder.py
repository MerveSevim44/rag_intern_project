import numpy as np
import ollama
from sentence_transformers import CrossEncoder

# Projedeki TEK embedding modeli kaynağı.
# ingest ve retrieval bu sabiti kullanmalı: farklı modeller farklı vektör
# boyutu üretir (bge-m3=1024, nomic-embed-text=768) ve cosine similarity
# "shapes not aligned" hatası verir.
EMBED_MODEL = "bge-m3"

# Cache for CrossEncoder models to avoid reloading on every function call
_reranker_cache = {}

def get_reranker_model(model_name='BAAI/bge-reranker-v2-m3'):
    """
    Reranker modelini önbellekten alır, yoksa yükler.
    """
    if model_name not in _reranker_cache:
        _reranker_cache[model_name] = CrossEncoder(model_name)
    return _reranker_cache[model_name]

def cosine_similarity(v1, v2):
    """
    İki vektör arasındaki kosinüs benzerliğini hesaplar.
    """
    v1 = np.array(v1)
    v2 = np.array(v2)
    return np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))


def cosine_similarity_batch(query_vec, embedding_matrix, norms=None):
    """
    Tek bir sorgu vektörü ile embedding matrisindeki TÜM satırlar arasındaki
    kosinüs benzerliğini vektörize şekilde hesaplar.

    Döngü yerine numpy matris çarpımı kullanır → N chunk için ~5-10× hızlı.

    Args:
        query_vec: 1-D numpy array (sorgu embedding'i).
        embedding_matrix: 2-D numpy array (N×D), her satır bir chunk embedding'i.
        norms: Önceden hesaplanmış satır normları (cache için). None ise hesaplanır.

    Returns:
        1-D numpy array: Her chunk için kosinüs benzerlik skoru.
    """
    query_vec = np.asarray(query_vec, dtype=np.float32)
    query_norm = np.linalg.norm(query_vec)
    if query_norm == 0:
        return np.zeros(len(embedding_matrix), dtype=np.float32)

    if norms is None:
        norms = np.linalg.norm(embedding_matrix, axis=1)

    # Sıfır normlu satırları koru (bölme hatasını engelle)
    safe_norms = np.where(norms == 0, 1.0, norms)

    scores = embedding_matrix @ query_vec / (safe_norms * query_norm)
    return scores

def get_embedding(text, model=EMBED_MODEL):
    """
    Verilen metin için Ollama kullanarak vektör (embedding) üretir.
    """
    response = ollama.embed(model=model, input=text)
    return response.embeddings[0]

def get_embeddings(texts, model=EMBED_MODEL, batch_size=16):
    """
    Verilen metin listesi için Ollama kullanarak toplu vektör (embedding) üretir.
    """
    if not texts:
        return []
    
    embeddings = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        response = ollama.embed(model=model, input=batch)
        embeddings.extend(response.embeddings)
    return embeddings

def rerank_indices(query, documents, model_name='BAAI/bge-reranker-v2-m3'):
    """
    rerank() ile aynı işi yapar ama doküman metni yerine dokümanın
    `documents` listesindeki indeksini döndürür.

    İki chunk'ın metni birebir aynı olduğunda metne göre eşleştirme
    yapmak yanlış kaynak/sayfa bilgisine yol açar; indeks bu belirsizliği
    tamamen ortadan kaldırır.

    Returns:
        list of tuple: (skor, indeks) şeklinde azalan sırada liste.
    """
    if not documents:
        return []

    model = get_reranker_model(model_name)
    pairs = [[query, doc] for doc in documents]
    scores = model.predict(pairs)

    results = list(zip(scores, range(len(documents))))
    results.sort(key=lambda x: x[0], reverse=True)
    return results

def rerank(query, documents, model_name='BAAI/bge-reranker-v2-m3'):
    """
    Cross-Encoder kullanarak dokümanları sorguya göre yeniden sıralar.
    
    Args:
        query (str): Arama sorgusu.
        documents (list of str): Sıralanacak dokümanlar.
        model_name (str): Kullanılacak Cross-Encoder modeli.
        
    Returns:
        list of tuple: (skor, doküman) şeklinde sıralanmış liste (büyükten küçüğe).
    """
    if not documents:
        return []
        
    model = get_reranker_model(model_name)
    pairs = [[query, doc] for doc in documents]
    scores = model.predict(pairs)
    
    # Skorları ve dokümanları eşleştirip azalan sırada sırala
    results = list(zip(scores, documents))
    results.sort(key=lambda x: x[0], reverse=True)
    return results
