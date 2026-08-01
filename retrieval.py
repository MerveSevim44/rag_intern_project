"""
retrieval.py — Soru gelince SQLite'tan doğru chunk'ları bulur.

Akış:
  1. Kullanıcının sorusunu embed et  (bge-m3 → vektör)
  2. Veritabanındaki tüm chunk embedding'lerini çek
  3. Cosine similarity ile en yakın chunk'ları bul (top_k)
  4. (Opsiyonel) Reranker ile sonuçları tekrar sırala
  5. En alakalı chunk'ları döndür
"""

import json
import sqlite3
from embedder import get_embedding, cosine_similarity, rerank_indices

# ─── Varsayılan ayarlar ───
DB_PATH = "rag.db"
EMBED_MODEL = "bge-m3"
TOP_K = 5            # Cosine similarity ile kaç aday çekelim
RERANK_TOP_N = 3     # Reranker'dan sonra kaç sonuç döndürelim


def retrieve(query: str, db_path=DB_PATH, model=EMBED_MODEL,
             top_k=TOP_K, use_reranker=True, rerank_top_n=RERANK_TOP_N) -> list[dict]:
    """
    Kullanıcı sorusuna en alakalı chunk'ları veritabanından bulur.

    Args:
        query:         Kullanıcının sorduğu soru (str).
        db_path:       SQLite veritabanı yolu.
        model:         Embedding modeli adı (Ollama'da yüklü olmalı).
        top_k:         Cosine similarity ile kaç aday chunk seçilecek.
        use_reranker:  True ise sonuçlar Cross-Encoder ile tekrar sıralanır.
        rerank_top_n:  Reranker sonrası döndürülecek nihai sonuç sayısı.

    Returns:
        list[dict]: Her biri {"source", "content", "score"} içeren sözlük listesi.
    """

    # ── ADIM 1: Soruyu vektöre çevir ──────────────────────────────
    # Aynı modeli kullanıyoruz (bge-m3), böylece soru vektörü ile
    # chunk vektörleri aynı uzayda oluyor → karşılaştırma anlamlı olur.
    try:
        query_embedding = get_embedding(query, model=model)
    except Exception as e:
        raise ConnectionError(
            f"Embedding oluşturulamadı (Ollama çalışıyor mu? '{model}' modeli yüklü mü?): {e}"
        ) from e

    # ── ADIM 2: Veritabanından tüm chunk'ları çek ────────────────
    # Her chunk'ın source (dosya adı), content (metin) ve
    # embedding (JSON string olarak saklanan vektör) bilgisini alıyoruz.
    # timeout: ingest sırasında yazma kilidi varsa hemen hata vermek yerine bekle.
    with sqlite3.connect(db_path, timeout=30.0) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, source, content, embedding, page_info FROM chunks")
        rows = cursor.fetchall()

    if not rows:
        print("Veritabanında hiç chunk bulunamadı. Önce ingest.py çalıştırın.")
        return []

    # ── ADIM 3: Cosine similarity hesapla ─────────────────────────
    # Her chunk'ın embedding'ini sorunun embedding'i ile karşılaştır.
    # Skor 1.0'a ne kadar yakınsa, chunk o kadar alakalıdır.
    scored_chunks = []
    for chunk_id, source, content, embedding_json, page_info in rows:
        # Embedding veritabanında JSON string olarak saklanıyor → listeye çevir
        chunk_embedding = json.loads(embedding_json)

        # İki vektör arasındaki benzerliği hesapla (0..1 arası)
        score = cosine_similarity(query_embedding, chunk_embedding)

        scored_chunks.append({
            "id": chunk_id,
            "source": source,
            "content": content,
            "page_info": page_info,
            "score": float(score)
        })

    # Skora göre büyükten küçüğe sırala, ilk top_k tanesini al
    scored_chunks.sort(key=lambda x: x["score"], reverse=True)
    top_candidates = scored_chunks[:top_k]

    # ── ADIM 4 (Opsiyonel): Reranker ile tekrar sırala ───────────
    # Cosine similarity hızlı ama kaba bir filtredir.
    # Reranker (Cross-Encoder), soru-cevap çiftini birlikte değerlendirip
    # daha hassas bir skor verir. Bu yüzden top_k adayı reranker'a gönderip
    # en iyi rerank_top_n tanesini seçiyoruz.
    if use_reranker and top_candidates:
        documents = [c["content"] for c in top_candidates]

        # rerank_indices() → [(skor, indeks), ...] döndürür.
        # Metin yerine indeks üzerinden eşleştiriyoruz: iki chunk'ın metni
        # birebir aynı olsa bile her sonuç kendi kaynağını/sayfasını korur.
        reranked = rerank_indices(query, documents)

        final_results = []
        for score, idx in reranked[:rerank_top_n]:
            chunk = top_candidates[idx]
            final_results.append({
                "id": chunk["id"],
                "source": chunk["source"],
                "content": chunk["content"],
                "score": float(score),
                "page_info": chunk["page_info"],
            })
        return final_results

    # Reranker kullanılmıyorsa, cosine similarity sonuçlarını döndür
    return top_candidates[:rerank_top_n]


# Alias for compatibility with app.py imports
get_top_chunks = retrieve


# ─── Test: Doğrudan çalıştırılırsa örnek sorgu yap ───────────────
if __name__ == "__main__":
    # Windows konsolu varsayılan olarak cp1254 kullanır ve dokümanlardaki
    # Yunanca/matematik karakterlerinde UnicodeEncodeError verir.
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

    test_query = "Bağlamdan bağımsız dilbilgisi nedir?"
    print(f"Sorgu: {test_query}\n")

    results = retrieve(test_query)

    if not results:
        print("Sonuc bulunamadi.")
    else:
        for i, r in enumerate(results, 1):
            print(f"--- Sonuc {i} (skor: {r['score']:.4f}) ---")
            print(f"Kaynak: {r['source']} ({r['page_info']})")
            # Icerik ilk 200 karakterini goster
            print(f"Icerik: {r['content'][:200]}...")
            print()
