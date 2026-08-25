"""
retrieval.py — Hibrit (BM25 + Vektör) Arama ve Akıllı Yönlendirme Modülü

Akış:
  1. Router ile sorunun niyetini belirle (AGGREGATION, SCHEMA, SEMANTIC)
  2. AGGREGATION ise: Doğrudan data_engine (Pandas) ile kesin matematiksel sonucu üret
  3. SCHEMA ise: Şema ve meta chunk'larına (fieldGuide, safetyAndDataQuality) öncelik ver
  4. SEMANTIC ise: BM25 (anahtar kelime) + BGE-M3 (vektör benzerliği) ile hibrit adayları bul
  5. Cross-Encoder Reranker ile en alakalı nihai chunk'ları sıralayıp döndür
"""

import json
import re
import sqlite3
from contextlib import closing
from typing import List, Dict, Any, Optional

import numpy as np
from rank_bm25 import BM25Okapi

from embedder import get_embedding, cosine_similarity, rerank_indices, EMBED_MODEL
from router import classify_query, QueryIntent
from data_engine import query_tabular_data

# ─── Varsayılan Ayarlar ───
DB_PATH = "rag.db"
TOP_K = 8             # Hibrit arama ile seçilecek aday chunk sayısı
RERANK_TOP_N = 3      # Reranker sonrası döndürülecek nihai sonuç sayısı
BM25_WEIGHT = 0.35    # Hibrit skorda BM25 ağırlığı (0.0 = Sadece Vektör, 1.0 = Sadece BM25)


def _tokenize(text: str) -> List[str]:
    """Metni küçük harfe çevirip kelimelerine ayırır (Türkçe uyumlu)."""
    return re.findall(r"\w+", text.lower())


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
        # Eğer hesaplanamazsa veya hata alınırsa aşağıya (Semantik RAG Fallback) devam eder.


    # ── ADIM 3: Veritabanından Chunk'ları Yükle ──
    with closing(sqlite3.connect(db_path, timeout=30.0)) as conn:
        conn.execute("PRAGMA busy_timeout=30000")
        cursor = conn.cursor()
        cursor.execute("SELECT id, source, content, embedding, page_info FROM chunks")
        rows = cursor.fetchall()

    if not rows:
        print("[retrieval] Veritabanında hiç chunk bulunamadı.")
        return []

    # ── ADIM 4: Dense (Vektör) Embedding ve Kosinüs Benzerliği ──
    try:
        query_embedding = get_embedding(query, model=model)
    except Exception as e:
        raise ConnectionError(f"Embedding oluşturulamadı: {e}") from e

    # Embedding boyutu kontrolü
    sample_dim = len(json.loads(rows[0][3]))
    if sample_dim != len(query_embedding):
        raise ValueError(
            f"Embedding boyutu uyuşmuyor: DB={sample_dim}, Model={len(query_embedding)}."
        )

    # ── ADIM 5: BM25 (Anahtar Kelime Eşleştirme) İndeksi ──
    corpus_tokens = [_tokenize(row[2]) for row in rows]
    bm25 = BM25Okapi(corpus_tokens)
    query_tokens = _tokenize(query)
    bm25_scores = bm25.get_scores(query_tokens)

    # BM25 skorlarını [0..1] aralığına normalize et
    max_bm25 = max(bm25_scores) if len(bm25_scores) > 0 and max(bm25_scores) > 0 else 1.0
    bm25_norm = [s / max_bm25 for s in bm25_scores]

    # ── ADIM 6: Hibrit Skorlama ve Şema Önceliklendirme ──
    scored_chunks = []
    for idx, (chunk_id, source, content, embedding_json, page_info) in enumerate(rows):
        chunk_embedding = json.loads(embedding_json)
        dense_score = float(cosine_similarity(query_embedding, chunk_embedding))
        sparse_score = float(bm25_norm[idx])

        # Hibrit skor formülü
        hybrid_score = (1.0 - bm25_weight) * dense_score + bm25_weight * sparse_score

        # ŞEMA SORGUSU İSE: fieldGuide, safetyAndDataQuality, statistics bölümlerini öne çıkar
        page_str = (page_info or "").lower()
        if any(k in page_str for k in ["fieldguide", "safetyanddataquality", "statistics", "metadata"]):
            hybrid_score += 0.35  # Şema chunk'larına belirgin öncelik ver

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

    # ── ADIM 7 (Opsiyonel): Cross-Encoder Reranker ile Sırala ──
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
    print("HİBRİT ARAMA VE AKILLI RETRIEVAL TESTİ")
    print("=" * 70)

    test_queries = [
        "Veri setindeki toplam profil sayısı kaçtır?",
        '"profileCode" alanı ne için kullanılır?',
        "Bir profildeki hizmet modları (serviceModes) hangi üç değerden birini alabilir?",
        '"Sağlık" sektöründe kaç profil bulunmaktadır?',
        "Bağlamdan bağımsız dilbilgisi kaç elemanlı bir yapıdır?",
        "Summer School programı kaç haftalıktır?",
    ]

    for q in test_queries:
        print(f"\nSorgu: {q}")
        results = retrieve(q)
        for i, r in enumerate(results, 1):
            print(f"  [{i}] Kaynak: {r['source']} ({r['page_info']}) | Skor: {r['score']:.4f} | Rota: {r.get('intent')}")
            print(f"      İçerik: {r['content'][:140]}...")
