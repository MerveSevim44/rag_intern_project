import gc
import numpy as np
import ollama

# Projedeki TEK embedding modeli kaynağı.
# ingest ve retrieval bu sabiti kullanmalı: farklı modeller farklı vektör
# boyutu üretir (bge-m3=1024, nomic-embed-text=768) ve cosine similarity
# "shapes not aligned" hatası verir.
EMBED_MODEL = "bge-m3"

# ─── Ollama keep_alive Ayarı ─────────────────────────────────────────────────
# Varsayılan "5m" (5 dakika) modeli bellekte tutar ve 16GB RAM'de diğer
# modellerle çakışır. "0" her çağrıdan sonra otomatik unload eder.
# İngest sırasında batch'ler art arda gittiği için model zaten sıcak kalır;
# sorgu zamanında ~2-3 sn ek yükleme maliyeti getirir ama bellek tasarrufu
# 16GB ortamda çok daha kritiktir.
OLLAMA_KEEP_ALIVE = "0"

# ─── Reranker Ayarları ───────────────────────────────────────────────────────
# Reranker artık CPU'da çalışıyor: VRAM tamamen LLM'e ayrılır.
# Her çağrıda yüklenir ve sonrasında bellekten temizlenir (lazy-load + cleanup).
RERANKER_DEVICE = "cpu"
RERANKER_BATCH_SIZE = 4  # Büyük aday listelerinde parçalı işleme


def _load_reranker(model_name='BAAI/bge-reranker-v2-m3'):
    """
    Reranker modelini CPU'da yükler.

    Her çağrıda taze yüklenir — modül seviyesinde cache tutulmaz.
    Bu sayede model kullanılmadığında bellekte yer kaplamaz.
    """
    from sentence_transformers import CrossEncoder
    return CrossEncoder(model_name, device=RERANKER_DEVICE)


def _cleanup_reranker():
    """
    Reranker modelini bellekten temizler.

    ÖNEMLİ: Bu fonksiyon modeli PARAMETRE OLARAK ALMAZ. Aldığı sürüm
    (`def _cleanup_reranker(model): del model`) etkisizdi — `del` yalnızca
    fonksiyonun kendi yerel adını siler; çağıranın `model` değişkeni gc.collect()
    çalışırken hâlâ modele referans tuttuğu için model toplanamazdı.
    Doğru kullanım, çağıranın kendi referansını bırakmasıdır:

        finally:
            model = None
            _cleanup_reranker()

    gc.collect() Python tarafındaki (döngüsel referanslar dahil) nesneleri
    toplar. torch.cuda.empty_cache() GPU cache'ini boşaltır (CPU modelde
    etkisiz ama gelecekte device değişirse güvenlik ağı olarak kalır).
    """
    gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass


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

def get_embedding(text, model=EMBED_MODEL, keep_alive=OLLAMA_KEEP_ALIVE):
    """
    Verilen metin için Ollama kullanarak vektör (embedding) üretir.

    Args:
        text: Embedding üretilecek metin.
        model: Kullanılacak embedding modeli.
        keep_alive: Model bellekte kalma süresi. Varsayılan "0" her çağrıdan
                    sonra unload eder. İngest sırasında "5m" geçilerek model
                    batch'ler arasında sıcak tutulur.
    """
    response = ollama.embed(model=model, input=text, keep_alive=keep_alive)
    return response.embeddings[0]

def get_embeddings(texts, model=EMBED_MODEL, batch_size=16, keep_alive=OLLAMA_KEEP_ALIVE):
    """
    Verilen metin listesi için Ollama kullanarak toplu vektör (embedding) üretir.

    Args:
        texts: Embedding üretilecek metin listesi.
        model: Kullanılacak embedding modeli.
        batch_size: Tek seferde işlenecek metin sayısı.
        keep_alive: Model bellekte kalma süresi. Varsayılan "0" her çağrıdan
                    sonra unload eder. İngest sırasında "5m" geçilerek model
                    batch'ler arasında sıcak tutulur.
    """
    if not texts:
        return []
    
    embeddings = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        response = ollama.embed(model=model, input=batch, keep_alive=keep_alive)
        embeddings.extend(response.embeddings)
    return embeddings

def rerank_indices(query, documents, model_name='BAAI/bge-reranker-v2-m3',
                   batch_size=RERANKER_BATCH_SIZE):
    """
    rerank() ile aynı işi yapar ama doküman metni yerine dokümanın
    `documents` listesindeki indeksini döndürür.

    İki chunk'ın metni birebir aynı olduğunda metne göre eşleştirme
    yapmak yanlış kaynak/sayfa bilgisine yol açar; indeks bu belirsizliği
    tamamen ortadan kaldırır.

    Model her çağrıda CPU'ya yüklenir ve işlem bitince bellekten temizlenir.
    Büyük aday listeleri batch_size parçalarla işlenir.

    Returns:
        list of tuple: (skor, indeks) şeklinde azalan sırada liste.
    """
    if not documents:
        return []

    model = _load_reranker(model_name)
    try:
        pairs = [[query, doc] for doc in documents]

        # Büyük aday listelerini parçalı işle
        if len(pairs) <= batch_size:
            scores = model.predict(pairs)
        else:
            import numpy as _np
            all_scores = []
            for i in range(0, len(pairs), batch_size):
                batch = pairs[i:i + batch_size]
                all_scores.extend(model.predict(batch))
            scores = _np.array(all_scores)

        results = list(zip(scores, range(len(documents))))
        results.sort(key=lambda x: x[0], reverse=True)
        return results
    finally:
        # Çağıranın referansını da bırak — aksi halde gc.collect() modeli
        # toplayamaz (bkz. _cleanup_reranker docstring).
        model = None
        _cleanup_reranker()

def rerank(query, documents, model_name='BAAI/bge-reranker-v2-m3',
           batch_size=RERANKER_BATCH_SIZE):
    """
    Cross-Encoder kullanarak dokümanları sorguya göre yeniden sıralar.
    
    Model her çağrıda CPU'ya yüklenir ve işlem bitince bellekten temizlenir.
    Büyük aday listeleri batch_size parçalarla işlenir.

    Args:
        query (str): Arama sorgusu.
        documents (list of str): Sıralanacak dokümanlar.
        model_name (str): Kullanılacak Cross-Encoder modeli.
        batch_size (int): Reranker'a tek seferde gönderilecek çift sayısı.
        
    Returns:
        list of tuple: (skor, doküman) şeklinde sıralanmış liste (büyükten küçüğe).
    """
    if not documents:
        return []
        
    model = _load_reranker(model_name)
    try:
        pairs = [[query, doc] for doc in documents]

        # Büyük aday listelerini parçalı işle
        if len(pairs) <= batch_size:
            scores = model.predict(pairs)
        else:
            import numpy as _np
            all_scores = []
            for i in range(0, len(pairs), batch_size):
                batch = pairs[i:i + batch_size]
                all_scores.extend(model.predict(batch))
            scores = _np.array(all_scores)
        
        # Skorları ve dokümanları eşleştirip azalan sırada sırala
        results = list(zip(scores, documents))
        results.sort(key=lambda x: x[0], reverse=True)
        return results
    finally:
        # Çağıranın referansını da bırak — aksi halde gc.collect() modeli
        # toplayamaz (bkz. _cleanup_reranker docstring).
        model = None
        _cleanup_reranker()
