"""
retrieval.py — Hibrit (BM25 + Vektör) Arama ve Akıllı Yönlendirme Modülü

Akış:
  1. Router ile sorunun niyetini belirle (AGGREGATION, SCHEMA, SEMANTIC)
  2. AGGREGATION ise: Doğrudan data_engine (Pandas) ile kesin matematiksel sonucu üret
  3. SCHEMA ise: Şema ve meta chunk'larına (fieldGuide, safetyAndDataQuality) öncelik ver
  4. SEMANTIC ise: BM25 (anahtar kelime) + BGE-M3 (vektör benzerliği) ile hibrit adayları bul
  5. Cross-Encoder Reranker ile en alakalı nihai chunk'ları sıralayıp döndür

Performans:
  - Chunk verileri ve BM25 indeksi ilk sorguda cache'lenir, sonraki sorgularda DB'ye gidilmez.
  - Cosine similarity numpy matris çarpımıyla toplu hesaplanır (döngü yerine vektörize).
  - Cache, yeni doküman eklendiğinde otomatik olarak invalidate edilir.
"""

import json
import re
import sqlite3
from contextlib import closing
from typing import List, Dict, Any, Optional

import numpy as np
from rank_bm25 import BM25Okapi

try:
    from src.embedder import get_embedding, cosine_similarity, cosine_similarity_batch, rerank_indices, EMBED_MODEL
    from src.router import classify_query, QueryIntent
    from src.data_engine import query_tabular_data
except ImportError:
    from embedder import get_embedding, cosine_similarity, cosine_similarity_batch, rerank_indices, EMBED_MODEL
    from router import classify_query, QueryIntent
    from data_engine import query_tabular_data

# ─── Varsayılan Ayarlar ───
from pathlib import Path
ROOT_DIR = Path(__file__).resolve().parent.parent
DB_PATH = str(ROOT_DIR / "rag.db") if (ROOT_DIR / "rag.db").exists() else "rag.db"
TOP_K = 8             # Hibrit arama ile seçilecek aday chunk sayısı
RERANK_TOP_N = 3      # Reranker sonrası döndürülecek nihai sonuç sayısı
BM25_WEIGHT = 0.35    # Hibrit skorda BM25 ağırlığı (0.0 = Sadece Vektör, 1.0 = Sadece BM25)


def _tokenize(text: str) -> List[str]:
    """Metni küçük harfe çevirip kelimelerine ayırır (Türkçe uyumlu)."""
    return re.findall(r"\w+", text.lower())


# ─── Chunk & BM25 Cache ─────────────────────────────────────────────────────
# İlk semantik sorguda DB'den yüklenir, sonraki sorgularda tekrar okunmaz.
# Yeni doküman eklendiğinde invalidate_cache() çağrılarak temizlenir.

class _RetrievalCache:
    """
    Veritabanından okunan chunk'ları, embedding matrisini ve BM25 indeksini
    bellek içinde tutar. Her sorguda DB'ye gitmek yerine cache kullanılır.

    invalidate() çağrılınca cache temizlenir ve bir sonraki sorguda
    güncel veri yeniden yüklenir.
    """
    def __init__(self):
        self._rows = None
        self._embedding_matrix = None
        self._embedding_norms = None
        self._bm25 = None
        self._corpus_tokens = None
        self._db_path = None

    @property
    def is_loaded(self) -> bool:
        return self._rows is not None

    def invalidate(self):
        """Cache'i temizler — bir sonraki retrieve() çağrısı DB'den taze veri yükler."""
        self._rows = None
        self._embedding_matrix = None
        self._embedding_norms = None
        self._bm25 = None
        self._corpus_tokens = None

    def load(self, db_path: str):
        """DB'den chunk'ları yükler, embedding matrisini ve BM25 indeksini oluşturur."""
        if self.is_loaded and self._db_path == db_path:
            return

        with closing(sqlite3.connect(db_path, timeout=30.0)) as conn:
            conn.execute("PRAGMA busy_timeout=30000")
            cursor = conn.cursor()
            cursor.execute("SELECT id, source, content, embedding, page_info FROM chunks")
            self._rows = cursor.fetchall()

        self._db_path = db_path

        if not self._rows:
            self._embedding_matrix = np.array([], dtype=np.float32).reshape(0, 0)
            self._embedding_norms = np.array([], dtype=np.float32)
            self._bm25 = None
            self._corpus_tokens = []
            return

        # Embedding matrisini bir kez oluştur (N chunk x D boyut)
        embeddings = [json.loads(row[3]) for row in self._rows]
        self._embedding_matrix = np.array(embeddings, dtype=np.float32)
        self._embedding_norms = np.linalg.norm(self._embedding_matrix, axis=1)

        # BM25 indeksini bir kez oluştur
        self._corpus_tokens = [_tokenize(row[2]) for row in self._rows]
        self._bm25 = BM25Okapi(self._corpus_tokens)

        print(f"[retrieval] Cache yuklendi: {len(self._rows)} chunk, "
              f"embedding matrisi {self._embedding_matrix.shape}")

    @property
    def rows(self):
        return self._rows or []

    @property
    def embedding_matrix(self):
        return self._embedding_matrix

    @property
    def embedding_norms(self):
        return self._embedding_norms

    @property
    def bm25(self):
        return self._bm25


# Modul seviyesinde tek instance
_cache = _RetrievalCache()


def invalidate_cache():
    """
    Retrieval cache'ini temizler.

    Yeni dokuman yuklendiginde veya silindiginde cagrilmalidir,
    boylece bir sonraki sorgu guncel veriyle calisir.
    """
    _cache.invalidate()


def retrieve(query: str, db_path: str = DB_PATH, model: str = EMBED_MODEL,
             top_k: int = TOP_K, use_reranker: bool = True,
             rerank_top_n: int = RERANK_TOP_N,
             bm25_weight: float = BM25_WEIGHT,
             llm: Optional[Any] = None) -> List[Dict[str, Any]]:
    """
    Kullanıcı sorusuna en alakalı yanıt/chunk'ları 3 kademeli akıllı rota ve hibrit arama ile bulur.

    Akış:
    1. Router (rule_engine -> code_interpreter -> semantic_rag)
    2. Tabular/Sandbox çalıştırması (rule_engine veya code_interpreter)
    3. Semantik arama (Vektör + BM25 + Reranker)

    Performans:
    - Chunk verileri, embedding matrisi ve BM25 indeksi ilk sorguda cache'lenir.
    - Cosine similarity vektörize numpy matris çarpımıyla hesaplanır.
    """
    from router import route_query, RouteTarget

    # ── ADIM 1: Soru Rotalama (3 Kademeli Router) ──
    route = route_query(query)

    # ── ADIM 2: RULE_ENGINE veya CODE_INTERPRETER İse Veri Motorunu / Sandbox'ı Çalıştır ──
    if route in (RouteTarget.RULE_ENGINE.value, RouteTarget.CODE_INTERPRETER.value):
        agg_result = query_tabular_data(query, llm=llm)
        if agg_result:
            source_file = agg_result.get("source_file", "728_profiles.json")
            if not source_file.startswith("data/"):
                source_file = f"data/{source_file}"
            return [{
                "id": 0,
                "source": source_file,
                "page_info": f"{agg_result.get('route', 'data_engine')} ({agg_result['operation']})",
                "content": f"[KESİN HESAPLAMA SONUCU]\n{agg_result['summary']}",
                "score": 1.0,
                "intent": agg_result.get("route", "code_interpreter").upper(),
                "code": agg_result.get("code", ""),
                "raw_result": agg_result.get("result", None),
                "data_points": agg_result.get("data_points", agg_result.get("result", None)),
                "operation": agg_result.get("operation", ""),
            }]


    # ── ADIM 3: Veritabanından Chunk'ları Yükle (Cache) ──
    _cache.load(db_path)
    rows = _cache.rows

    if not rows:
        print("[retrieval] Veritabaninda hic chunk bulunamadi.")
        return []

    # ── ADIM 4: Dense (Vektör) Embedding — Sorgu Vektörü ──
    try:
        query_embedding = get_embedding(query, model=model)
    except Exception as e:
        raise ConnectionError(f"Embedding olusturulamadi: {e}") from e

    # Embedding boyutu kontrolu
    if _cache.embedding_matrix.shape[1] != len(query_embedding):
        raise ValueError(
            f"Embedding boyutu uyusmuyor: DB={_cache.embedding_matrix.shape[1]}, "
            f"Model={len(query_embedding)}."
        )

    # ── ADIM 5: Vektörize Cosine Similarity (Toplu Hesaplama) ──
    # Önceki: for döngüsü ile tek tek json.loads() + cosine_similarity()
    # Şimdi:  numpy matris çarpımı ile toplu hesaplama (~5-10x hızlı)
    dense_scores = cosine_similarity_batch(
        query_embedding, _cache.embedding_matrix, norms=_cache.embedding_norms
    )

    # ── ADIM 6: BM25 (Anahtar Kelime Eşleştirme) — Cache'li İndeks ──
    query_tokens = _tokenize(query)
    bm25_scores = _cache.bm25.get_scores(query_tokens)

    # BM25 skorlarını [0..1] aralığına normalize et
    max_bm25 = max(bm25_scores) if len(bm25_scores) > 0 and max(bm25_scores) > 0 else 1.0
    bm25_norm = bm25_scores / max_bm25

    # ── ADIM 7: Hibrit Skorlama ve Şema Önceliklendirme ──
    scored_chunks = []
    for idx, (chunk_id, source, content, _embedding_json, page_info) in enumerate(rows):
        dense_score = float(dense_scores[idx])
        sparse_score = float(bm25_norm[idx])

        # Hibrit skor formülü
        hybrid_score = (1.0 - bm25_weight) * dense_score + bm25_weight * sparse_score

        # ŞEMA SORGUSU İSE: fieldGuide, safetyAndDataQuality, statistics bölümlerini öne çıkar
        page_str = (page_info or "").lower()
        if any(k in page_str for k in ["fieldguide", "safetyanddataquality", "statistics", "metadata"]):
            hybrid_score += 0.35

        scored_chunks.append({
            "id": chunk_id,
            "source": source,
            "content": content,
            "page_info": page_info,
            "score": hybrid_score,
            "dense_score": dense_score,
            "bm25_score": sparse_score,
            "intent": route.upper(),
        })


    # Skora göre sırala ve ilk top_k adayı al
    scored_chunks.sort(key=lambda x: x["score"], reverse=True)
    top_candidates = scored_chunks[:top_k]

    # ── ADIM 8 (Opsiyonel): Cross-Encoder Reranker ile Sırala ──
    if use_reranker and top_candidates:
        documents = [c["content"] for c in top_candidates]
        reranked = rerank_indices(query, documents)

        final_results = []
        for score, original_idx in reranked[:rerank_top_n]:
            chunk = top_candidates[original_idx]
            chunk_copy = dict(chunk)
            chunk_copy["rerank_score"] = float(score)
            final_results.append(chunk_copy)
        return final_results

    return top_candidates[:rerank_top_n]


# Geriye dönük uyumluluk için alias
get_top_chunks = retrieve


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

    print("=" * 70)
    print("HiBRiT ARAMA VE AKILLI RETRIEVAL TESTi")
    print("=" * 70)

    test_queries = [
        "Veri setindeki toplam profil sayisi kactir?",
        '"profileCode" alani ne icin kullanilir?',
        "Bir profildeki hizmet modlari (serviceModes) hangi uc degerden birini alabilir?",
        '"Saglik" sektorunde kac profil bulunmaktadir?',
        "Baglamdan bagimsiz dilbilgisi kac elemanli bir yapidir?",
        "Summer School programi kac haftaliktir?",
    ]

    for q in test_queries:
        print(f"\\nSorgu: {q}")
        results = retrieve(q)
        for i, r in enumerate(results, 1):
            print(f"  [{i}] Kaynak: {r['source']} ({r['page_info']}) | Skor: {r['score']:.4f} | Rota: {r.get('intent')}")
            print(f"      Icerik: {r['content'][:140]}...")
