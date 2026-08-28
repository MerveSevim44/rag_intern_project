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
    from src.memory_profiler import MemoryProfiler
except ImportError:
    from embedder import get_embedding, cosine_similarity, cosine_similarity_batch, rerank_indices, EMBED_MODEL
    from router import classify_query, QueryIntent
    from data_engine import query_tabular_data
    from memory_profiler import MemoryProfiler

# ─── Varsayılan Ayarlar ───
from pathlib import Path
ROOT_DIR = Path(__file__).resolve().parent.parent
DB_PATH = str(ROOT_DIR / "rag.db") if (ROOT_DIR / "rag.db").exists() else "rag.db"
# rule_engine / code_interpreter sonuçları doküman değil, HESAPLANMIŞ cevaptır.
# Varsayılan synthesizer prompt'u "bağlamda ilgili bilgi yoksa 'bulunamadı' de"
# kuralını uyguladığı için tek cümlelik hesap sonucunu bazen doküman sanmayıp
# eliyor ve doğru hesaplanmış sayı kullanıcıya "bulunamadı" olarak dönüyordu.
COMPUTED_RESULT_INSTRUCTION = (
    "Bağlamdaki '[KESİN HESAPLAMA SONUCU]' bloğu, veri seti üzerinde pandas ile "
    "çalıştırılmış ve doğruluğu garanti edilmiş NİHAİ cevaptır. Bu sonucu "
    "kullanıcının sorusuna doğrudan cevap verecek şekilde tek bir akıcı Türkçe "
    "cümleyle aktar. Sayıları, oranları ve isimleri asla değiştirme. "
    "Bu bloğu görmezden gelme ve 'bulunamadı' deme. "
    "Para birimi uydurma: 'TL', 'lira', '₺', '$' veya 'dolar' yazma. Birim yalnızca hesaplama "
    "sonucunda açıkça geçiyorsa kullanılır ve HARFİ HARFİNE aktarılır — 'USD' gördüysen "
    "'USD' yaz, sembole ('$') çevirme. Sonuçta birim yoksa sayıyı birimsiz aktar."
)

TOP_K = 8             # Hibrit arama ile seçilecek aday chunk sayısı
RERANK_TOP_N = 3      # Reranker sonrası döndürülecek nihai sonuç sayısı
BM25_WEIGHT = 0.35    # Hibrit skorda BM25 ağırlığı (0.0 = Sadece Vektör, 1.0 = Sadece BM25)


def _tokenize(text: str) -> List[str]:
    """Metni küçük harfe çevirip kelimelerine ayırır (Türkçe uyumlu)."""
    return re.findall(r"\w+", text.lower())


def _normalize_source(source: Optional[str]) -> str:
    """
    Kaynak adini karsilastirilabilir hale getirir: yol ayraclari atilir,
    kucuk harfe cevrilir. Boylece "data/x.pdf" ile "x.pdf" ayni sayilir.
    """
    if not source:
        return ""
    return Path(str(source)).name.strip().lower()


def _resolve_dataset_name(source_filter: str) -> Optional[str]:
    """
    Seçilen kaynağın data_engine'de yüklü tablosal bir dataset'e karşılık gelip
    gelmediğini söyler. Karşılığı varsa engine'in tanıdığı dosya adını, yoksa
    None döner (bu durumda tablosal rota atlanır).
    """
    try:
        try:
            from data_engine import get_data_engine
        except ImportError:
            from src.data_engine import get_data_engine
        target = _normalize_source(source_filter)
        for name in get_data_engine().get_schemas().keys():
            if _normalize_source(name) == target:
                return name
    except Exception as e:
        print(f"[retrieval] dataset adi cozumlenemedi: {e}")
    return None


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
        # source_filter -> (indices, matrix, norms, bm25) — dokuman bazli alt indeks
        self._views = {}

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
        self._views = {}

    def load(self, db_path: str):
        """DB'den chunk'ları yükler, embedding matrisini ve BM25 indeksini oluşturur."""
        if self.is_loaded and self._db_path == db_path:
            return

        self._views = {}

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

    def get_view(self, source_filter: Optional[str]) -> Dict[str, Any]:
        """
        Tek bir dokumana ait alt indeksi (satir indeksleri + embedding matrisi +
        BM25) dondurur. Ilk cagrida hesaplanip cache'lenir.

        source_filter, tam kaynak yolu ("data/x.pdf") veya yalnizca dosya adi
        ("x.pdf") olabilir. Eslesme yoksa bos bir view doner.
        """
        key = _normalize_source(source_filter)
        cached = self._views.get(key)
        if cached is not None:
            return cached

        indices = [
            i for i, row in enumerate(self.rows)
            if _normalize_source(row[1]) == key
        ]
        if not indices:
            view = {"indices": [], "matrix": None, "norms": None, "bm25": None}
            self._views[key] = view
            return view

        idx_arr = np.asarray(indices, dtype=np.int64)
        matrix = self._embedding_matrix[idx_arr]
        # BM25 indeksi yalnizca bu dokumanin chunk'lari uzerinde kurulur:
        # idf degerleri de dokuman ici dagilima gore hesaplanir.
        bm25 = BM25Okapi([self._corpus_tokens[i] for i in indices])
        view = {
            "indices": indices,
            "matrix": matrix,
            "norms": np.linalg.norm(matrix, axis=1),
            "bm25": bm25,
        }
        self._views[key] = view
        return view

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
             llm: Optional[Any] = None,
             source_filter: Optional[str] = None,
             debug: bool = False) -> List[Dict[str, Any]]:
    """
    Kullanıcı sorusuna en alakalı yanıt/chunk'ları 3 kademeli akıllı rota ve hibrit arama ile bulur.

    Akış:
    1. Router (rule_engine -> code_interpreter -> semantic_rag)
    2. Tabular/Sandbox çalıştırması (rule_engine veya code_interpreter)
    3. Semantik arama (Vektör + BM25 + Reranker)

    Args:
        source_filter: Verilirse arama YALNIZCA bu dokümanın chunk'ları üzerinde
            yapılır (BM25 indeksi, cosine matrisi ve reranker adayları filtrelenir).
            "data/x.pdf" veya "x.pdf" biçiminde olabilir. None ise tüm koleksiyon
            taranır (varsayılan, geriye dönük uyumlu davranış).

    Performans:
    - Chunk verileri, embedding matrisi ve BM25 indeksi ilk sorguda cache'lenir.
    - Cosine similarity vektörize numpy matris çarpımıyla hesaplanır.
    - source_filter verildiğinde alt indeks de cache'lenir; arama uzayı küçüldüğü
      için hem hibrit skorlama hem reranker belirgin şekilde hızlanır.
    """
    try:
        from router import RouteTarget, META_QUERY_SYNTH_SUFFIX
        from data_engine import get_data_engine
    except ImportError:
        from src.router import RouteTarget, META_QUERY_SYNTH_SUFFIX
        from src.data_engine import get_data_engine

    # ── ADIM 1: Soru Rotalama (4 Kademeli Router) ──
    # Router'a yüklü TÜM dataset şemalarını veriyoruz; aksi hâlde has_dataset_signal
    # yalnızca genel ipuçlarından hesaplanır ve yeni dataset'ler görünmez olur.
    try:
        df_schema = get_data_engine().get_schemas()
    except Exception:
        df_schema = None

    classification = classify_query(query, df_schema=df_schema, debug=debug)
    route = classification["target"]
    # meta_query dışındaki rotalarda None kalır. Router'ın sözleşme metnine
    # (META_QUERY_INSTRUCTION) synthesizer'ın uygulayabileceği biçim iskeleti eklenir.
    synth_instruction = classification.get("synthesizer_instruction")
    if synth_instruction:
        synth_instruction += META_QUERY_SYNTH_SUFFIX

    if debug:
        print(f"[retrieval] route={route} ({classification['reason']}) | "
              f"complexity={classification['has_complexity']} "
              f"dataset_signal={classification['has_dataset_signal']} | "
              f"schema_cols={classification['matched_schema_columns'][:6]}")

    # ── ADIM 2: RULE_ENGINE veya CODE_INTERPRETER İse Veri Motorunu / Sandbox'ı Çalıştır ──
    if route in (RouteTarget.RULE_ENGINE.value, RouteTarget.CODE_INTERPRETER.value):
        # Kullanıcı bir doküman seçtiyse veri motoru da doğrudan o dosya üzerinden
        # çalışsın. Seçilen dosya tablosal bir dataset DEĞİLSE (ör. bir PDF),
        # başka bir dataset'e kaymak yerine tablosal rotayı tamamen atlayıp
        # semantik aramaya düşeriz.
        tabular_filename = None
        if source_filter:
            tabular_filename = _resolve_dataset_name(source_filter)
            if tabular_filename is None:
                agg_result = None
            else:
                agg_result = query_tabular_data(query, llm=llm, filename=tabular_filename)
        else:
            agg_result = query_tabular_data(query, llm=llm)
        if agg_result and agg_result.get("summary"):
            source_file = agg_result.get("source_file") or tabular_filename or "728_profiles.json"
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
                "route": agg_result.get("route", route),
                "synthesizer_instruction": COMPUTED_RESULT_INSTRUCTION,
                "selected_dataset": agg_result.get("selected_dataset", agg_result.get("source_file", "")),
                "match_score": agg_result.get("match_score"),
                "selection_debug": agg_result.get("selection_debug") if debug else None,
                "route_debug": classification.get("debug") if debug else None,
                "source_filter": source_filter,
            }]


    # ── ADIM 2b: META_QUERY İçin Kaynak Dosya Sabitleme ──
    # Meta sorular ("bu ilişki doğrudan belirtilmiş midir?") semantik olarak
    # zayıf sinyal taşır; hibrit arama kolayca alakasız bir dosyaya kayar.
    # Soruyla en çok örtüşen dataset'i bulup o kaynağın chunk'larını öne çekiyoruz.
    # source_filter zaten tek kaynağa kilitlendiği için meta sabitlemeye gerek yok.
    meta_source_hint = None
    if route == RouteTarget.META_QUERY.value and not source_filter:
        try:
            selection = get_data_engine().select_dataset(query)
            if selection["match_score"] and selection["match_score"] > 0:
                meta_source_hint = selection["selected_dataset"]
            if debug:
                print(f"[retrieval] meta_query kaynak sabitleme: {meta_source_hint} "
                      f"(score={selection['match_score']}, {selection['reason']})")
        except Exception as e:
            print(f"[retrieval] meta_query dataset secimi basarisiz: {e}")

    # ── ADIM 3: Veritabanından Chunk'ları Yükle (Cache) ──
    _cache.load(db_path)
    rows = _cache.rows

    if not rows:
        print("[retrieval] Veritabaninda hic chunk bulunamadi.")
        return []

    # ── ADIM 3b: Kaynak Filtresi (Metadata Filtering) ──
    # Belirli bir doküman seçildiyse arama uzayını o dokümanın chunk'larına
    # daraltıyoruz: hem daha hızlı hem de alakasız kaynaklardan gelen gürültü sıfır.
    active_indices = None
    search_matrix = _cache.embedding_matrix
    search_norms = _cache.embedding_norms
    search_bm25 = _cache.bm25

    if source_filter:
        view = _cache.get_view(source_filter)
        if not view["indices"]:
            print(f"[retrieval] '{source_filter}' icin chunk bulunamadi — filtre yok sayilmadi, bos donuluyor.")
            return []
        active_indices = view["indices"]
        search_matrix = view["matrix"]
        search_norms = view["norms"]
        search_bm25 = view["bm25"]
        if debug:
            print(f"[retrieval] source_filter='{source_filter}' -> {len(active_indices)}/{len(rows)} chunk")

    # ── Bellek Profiling (debug modunda) ──
    profiler = MemoryProfiler() if debug else None

    # ── ADIM 4: Dense (Vektör) Embedding — Sorgu Vektörü ──
    try:
        if profiler:
            # verify="ollama": adım sonunda `ollama ps` ile keep_alive="0"
            # ayarının modeli gerçekten unload ettiği doğrulanır.
            with profiler.measure("embedding", verify="ollama"):
                query_embedding = get_embedding(query, model=model)
        else:
            query_embedding = get_embedding(query, model=model)
    except Exception as e:
        raise ConnectionError(f"Embedding olusturulamadi: {e}") from e

    # Embedding boyutu kontrolu
    if search_matrix.shape[1] != len(query_embedding):
        raise ValueError(
            f"Embedding boyutu uyusmuyor: DB={search_matrix.shape[1]}, "
            f"Model={len(query_embedding)}."
        )

    # ── ADIM 5: Vektörize Cosine Similarity (Toplu Hesaplama) ──
    # Önceki: for döngüsü ile tek tek json.loads() + cosine_similarity()
    # Şimdi:  numpy matris çarpımı ile toplu hesaplama (~5-10x hızlı)
    dense_scores = cosine_similarity_batch(
        query_embedding, search_matrix, norms=search_norms
    )

    # ── ADIM 6: BM25 (Anahtar Kelime Eşleştirme) — Cache'li İndeks ──
    query_tokens = _tokenize(query)
    bm25_scores = search_bm25.get_scores(query_tokens)

    # BM25 skorlarını [0..1] aralığına normalize et
    max_bm25 = max(bm25_scores) if len(bm25_scores) > 0 and max(bm25_scores) > 0 else 1.0
    bm25_norm = bm25_scores / max_bm25

    # ── ADIM 7: Hibrit Skorlama ve Şema Önceliklendirme ──
    # Filtre varsa yalnızca seçilen dokümanın satırları üzerinde dönülür;
    # skor dizileri (dense/bm25) zaten bu alt küme için hesaplandı.
    iter_rows = (
        [(pos, rows[i]) for pos, i in enumerate(active_indices)]
        if active_indices is not None
        else list(enumerate(rows))
    )

    scored_chunks = []
    for idx, (chunk_id, source, content, _embedding_json, page_info) in iter_rows:
        dense_score = float(dense_scores[idx])
        sparse_score = float(bm25_norm[idx])

        # Hibrit skor formülü
        hybrid_score = (1.0 - bm25_weight) * dense_score + bm25_weight * sparse_score

        # ŞEMA SORGUSU İSE: fieldGuide, safetyAndDataQuality, statistics bölümlerini öne çıkar
        page_str = (page_info or "").lower()
        if any(k in page_str for k in ["fieldguide", "safetyanddataquality", "statistics", "metadata"]):
            hybrid_score += 0.35

        # META_QUERY: soruyla eşleşen dataset'in chunk'larını öne çek
        if meta_source_hint and meta_source_hint in (source or ""):
            hybrid_score += 0.50

        scored_chunks.append({
            "id": chunk_id,
            "source": source,
            "content": content,
            "page_info": page_info,
            "score": hybrid_score,
            "dense_score": dense_score,
            "bm25_score": sparse_score,
            "intent": route.upper(),
            "route": route,
            # META_QUERY rotasında synthesizer'a "açık bilgi vs. çıkarım" talimatı taşınır;
            # diğer rotalarda None kalır ve prompt değişmez.
            "synthesizer_instruction": synth_instruction,
            "source_filter": source_filter,
        })


    # Skora göre sırala ve ilk top_k adayı al
    scored_chunks.sort(key=lambda x: x["score"], reverse=True)
    top_candidates = scored_chunks[:top_k]

    # ── ADIM 8 (Opsiyonel): Cross-Encoder Reranker ile Sırala ──
    if use_reranker and top_candidates:
        documents = [c["content"] for c in top_candidates]
        if profiler:
            with profiler.measure("reranking"):
                reranked = rerank_indices(query, documents)
        else:
            reranked = rerank_indices(query, documents)

        final_results = []
        for score, original_idx in reranked[:rerank_top_n]:
            chunk = top_candidates[original_idx]
            chunk_copy = dict(chunk)
            chunk_copy["rerank_score"] = float(score)
            final_results.append(chunk_copy)

        if profiler:
            profiler.print_report()
        return final_results

    if profiler:
        profiler.print_report()
    return top_candidates[:rerank_top_n]


# Geriye dönük uyumluluk için alias — retrieve() ile birebir aynı imzayı taşır
# (source_filter dâhil), mevcut çağrılar parametresiz çalışmaya devam eder.
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
