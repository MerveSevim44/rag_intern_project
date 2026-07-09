import numpy as np
import ollama
from sentence_transformers import CrossEncoder

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

def get_embedding(text, model="bge-m3"):
    """
    Verilen metin için Ollama kullanarak vektör (embedding) üretir.
    """
    response = ollama.embeddings(model=model, prompt=text)
    return response['embedding']

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