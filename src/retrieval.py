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
import unicodedata
from contextlib import closing
from typing import List, Dict, Any, Optional

import numpy as np
from rank_bm25 import BM25Okapi

try:
    from src.embedder import get_embedding, cosine_similarity, cosine_similarity_batch, rerank_indices, EMBED_MODEL
    from src.router import classify_query, QueryIntent
    from src.data_engine import query_tabular_data, _tr_normalize
    from src.memory_profiler import MemoryProfiler
except ImportError:
    from embedder import get_embedding, cosine_similarity, cosine_similarity_batch, rerank_indices, EMBED_MODEL
    from router import classify_query, QueryIntent
    from data_engine import query_tabular_data, _tr_normalize
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
BM25_WEIGHT = 0.35    # (Geriye dönük uyumluluk için korunur — RRF'de kullanılmaz)
RRF_K = 60            # RRF sabiti: düşük değer üst sıraları güçlendirir (standart: 60)


# ─── BM25 Metin Normalizasyonu ──────────────────────────────────────────────
# Aynı katman hem corpus'a (indeks kurulurken) hem sorguya uygulanır; iki taraf
# simetrik kaldığı sürece eşleşme tutarlıdır.

# Eş anlamlı / halk ağzı terimler → corpus'ta geçen kanonik ifade.
# Alan-agnostiktir: hangi JSON alanında geçtiğine bakılmaz, yalnızca metin
# düzeyinde çalışır. Yeni terim çifti eklemek için buraya bir satır yeter.
# Anahtarın SON kelimesi önek olarak eşleşir → Türkçe ekler de yakalanır
# ("dişçisi", "dişçiye" → "diş hekimi").
#
# TODO: Bu sözlük GEÇİCİ bir çözümdür ve elle bakım ister — listede olmayan her
# halk ağzı terim / ek varyantı ("kuaförcü", "çocuğum" ↔ "çocuk") BM25'te yine
# sıfır eşleşir. Kalıcı çözüm: gerçek bir Türkçe morfolojik normalizasyon
# (stemmer/lemmatizer, ör. zemberek-nlp veya TurkishStemmer) corpus'a ve sorguya
# simetrik uygulanmalı; sözlük yalnızca morfolojinin çözemediği gerçek eş
# anlamlılara (dişçi → diş hekimi, cildiye → dermatoloji) indirgenmeli.
TERM_SYNONYMS = {
    "dişçi": "diş hekimi",
    "göz doktoru": "göz hekimi",
    "çocuk doktoru": "çocuk sağlığı uzmanı",
    "kbb": "kulak burun boğaz",
    "cildiye": "dermatoloji",
}

# İşlev kelimeleri ve sorgu kalıpları. Bunlar corpus'un tamamında geçtiği için
# (ör. "için" 728 profilin hepsinde) BM25 sırasına yalnızca uzunluk gürültüsü
# katar. Özel isim / konum / meslek adı buraya EKLENMEZ.
TURKISH_STOPWORDS = {
    "acaba", "ama", "ancak", "bana", "bazı", "belki", "ben", "beni", "benim",
    "bir", "biraz", "biz", "bize", "bu", "buna", "bunu", "bunun", "da", "daha",
    "de", "değil", "diye", "en", "gibi", "hem", "her", "için", "ile", "ise",
    "kadar", "ki", "mi", "mı", "mu", "mü", "ne", "neden", "nasıl", "o", "ona",
    "onu", "onun", "olan", "olarak", "sen", "siz", "şu", "ve", "veya", "ya",
    "yani", "çok",
    # sorgu kalıpları
    "arıyorum", "istiyorum", "lazım", "bul", "bulur", "öner", "önerir",
    "musun", "misin", "müsün", "mısın",
}


def _base_tokens(text: str) -> List[str]:
    """
    Türkçe-güvenli küçük harf + aksan katlama + kelimelere ayırma.

    str.lower() "İ" harfini "i" + U+0307 (birleşik nokta) yapar; U+0307 \\w
    sayılmadığından "İstanbul" → ["i", "stanbul"] diye bölünüyordu.
    _tr_normalize önce İ→i, I→ı dönüşümünü yapıp sonra aksanları katlar
    (ç→c, ş→s, ı→i…); böylece aksansız yazılan sorgular da eşleşir.
    NFC, ayrışık (NFD) gelen "I + U+0307" dizisini tek "İ" harfine birleştirir.
    """
    text = unicodedata.normalize("NFC", text or "")
    return re.findall(r"\w+", _tr_normalize(text))


# Sözlükler bir kez, aynı normalizasyondan geçirilerek derlenir.
# Uzun anahtarlar önce denenir ("göz doktoru" tek kelimelik anahtarlardan önce).
_SYNONYM_RULES = sorted(
    ((tuple(_base_tokens(k)), _base_tokens(v)) for k, v in TERM_SYNONYMS.items()),
    key=lambda rule: len(rule[0]), reverse=True,
)
_STOPWORDS = {t for w in TURKISH_STOPWORDS for t in _base_tokens(w)}


def _apply_synonyms(tokens: List[str]) -> List[str]:
    """Token dizisindeki eş anlamlı ifadeleri kanonik karşılıklarıyla değiştirir."""
    out: List[str] = []
    i = 0
    while i < len(tokens):
        for key, canonical in _SYNONYM_RULES:
            n = len(key)
            window = tokens[i:i + n]
            if (len(window) == n and window[:-1] == list(key[:-1])
                    and window[-1].startswith(key[-1])):
                out.extend(canonical)
                i += n
                break
        else:
            out.append(tokens[i])
            i += 1
    return out


def _tokenize(text: str) -> List[str]:
    """BM25 token'ları: Türkçe normalizasyon → eş anlamlılar → stopword filtresi."""
    return [t for t in _apply_synonyms(_base_tokens(text)) if t not in _STOPWORDS]


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
    bm25_raw = search_bm25.get_scores(query_tokens)

    # ── ADIM 6b: Reciprocal Rank Fusion (RRF) ──────────────────────────────
    # Linear combination (ağırlıklı toplam) yerine sıra tabanlı füzyon kullanılır.
    # Avantajları:
    #   - Ölçek bağımsız: dense [0.6–0.8] ile BM25 [0–∞] farklı ölçektedir;
    #     RRF yalnızca sıra kullandığı için bu ölçek farkından etkilenmez.
    #   - Şema-agnostik: yeni embedding modeli veya veri seti eklendiğinde
    #     BM25_WEIGHT sabiti ayarlamak gerekmez, kendiliğinden ölçeklenir.
    n = len(dense_scores)
    # Her skor için sıra pozisyonunu hesapla (0 = en iyi)
    dense_ranks = np.empty(n, dtype=np.float32)
    dense_ranks[np.argsort(-dense_scores)] = np.arange(n, dtype=np.float32)
    bm25_ranks = np.empty(n, dtype=np.float32)
    bm25_ranks[np.argsort(-bm25_raw, kind="stable")] = np.arange(n, dtype=np.float32)
    # Her kaynaktan gelen sıra katkısı toplanır. BM25 skoru 0 olan chunk'larda
    # sorgu kelimesi hiç geçmiyor; argsort'un eşitlikleri keyfi sıralaması
    # gürültü katmasın diye bu chunk'lar BM25'ten katkı almaz.
    bm25_contrib = np.where(bm25_raw > 0, 1.0 / (RRF_K + bm25_ranks), 0.0)
    rrf_scores = 1.0 / (RRF_K + dense_ranks) + bm25_contrib
    # [0..1]'e normalize et (teorik maksimum: iki listede de 1. sıra = 2/RRF_K).
    # Aşağıdaki boost'lar ve UI skor çubuğu bu ölçeği varsayar.
    rrf_scores = rrf_scores / (2.0 / RRF_K)

    # Debug / UI için normalize edilmiş BM25 skorları (eski davranış korunur)
    max_bm25 = float(bm25_raw.max()) if bm25_raw.max() > 0 else 1.0
    bm25_norm = bm25_raw / max_bm25

    # ── ADIM 7: Hibrit Skorlama ve Şema Önceliklendirme ──
    # Filtre varsa yalnızca seçilen dokümanın satırları üzerinde dönülür;
    # skor dizileri (dense/bm25/rrf) zaten bu alt küme için hesaplandı.
    iter_rows = (
        [(pos, rows[i]) for pos, i in enumerate(active_indices)]
        if active_indices is not None
        else list(enumerate(rows))
    )

    scored_chunks = []
    for idx, (chunk_id, source, content, _embedding_json, page_info) in iter_rows:
        dense_score = float(dense_scores[idx])
        sparse_score = float(bm25_norm[idx])   # normalize BM25 (debug/UI)

        # RRF skoru temel hibrit skoru olarak kullanılır
        hybrid_score = float(rrf_scores[idx])

        # ── Keyword Hit Boost (şema-agnostik) ────────────────────────────────
        # BM25 yüksek & dense düşükse: sorgu kelimesi metinde birebir eşleşti
        # ama vektörel anlam yakalanmadı. Terminoloji uyumsuzluklarını giderir
        # (örn. "dişçi" sorgusu ↔ "Diş Hekimi" chunk'ı) alan adı bilmeden.
        bm25_local = float(bm25_raw[idx])
        rrf_base = hybrid_score
        keyword_boost = 0.0
        if bm25_local > 0 and sparse_score > 0.5 and dense_score < 0.70:
            keyword_boost = 0.08 / (1.0 + dense_score)
            hybrid_score += keyword_boost

        # ── Meta/Şema Chunk Boost ─────────────────────────────────────────────
        # Mevcut veri setiyle geriye dönük uyumluluk korunur.
        # Ek olarak: "$.meta" path'i de yakalanır → yeni veri setlerinin meta
        # bölümleri otomatik tanınır, listeye elle ekleme gerekmez.
        page_str = (page_info or "").lower()
        is_meta_chunk = (
            any(k in page_str for k in ["fieldguide", "safetyanddataquality",
                                         "statistics", "metadata"])
            or page_str.startswith("$.meta")  # _roots_from_object'in ürettiği path
        )
        meta_boost = 0.35 if is_meta_chunk else 0.0
        hybrid_score += meta_boost

        # META_QUERY: soruyla eşleşen dataset'in chunk'larını öne çek
        hint_boost = 0.50 if (meta_source_hint and meta_source_hint in (source or "")) else 0.0
        hybrid_score += hint_boost

        scored_chunks.append({
            "id": chunk_id,
            "source": source,
            "content": content,
            "page_info": page_info,
            "score": hybrid_score,
            "dense_score": dense_score,
            "bm25_score": sparse_score,
            # Katman katman skor dökümü — hangi katmanın sıralamayı bozduğunu
            # görmek için (bkz. _print_score_breakdown). Rank'lar 1 tabanlı.
            "score_debug": {
                "dense_raw": dense_score,
                "bm25_raw": bm25_local,
                "dense_rank": int(dense_ranks[idx]) + 1,
                "bm25_rank": int(bm25_ranks[idx]) + 1 if bm25_local > 0 else None,
                "rrf": rrf_base,
                "keyword_boost": keyword_boost,
                "meta_boost": meta_boost,
                "hint_boost": hint_boost,
            },
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

        if debug:
            rerank_by_idx = {i: float(s) for s, i in reranked}
            _print_score_breakdown(query, query_tokens, top_candidates, rerank_by_idx)
        if profiler:
            profiler.print_report()
        return final_results

    if debug:
        _print_score_breakdown(query, query_tokens, top_candidates, None)
    if profiler:
        profiler.print_report()
    return top_candidates[:rerank_top_n]


def _print_score_breakdown(query: str, query_tokens: List[str],
                           candidates: List[Dict[str, Any]],
                           rerank_by_idx: Optional[Dict[int, float]]) -> None:
    """
    Hibrit aramanın her aday için ara skorlarını tablo olarak basar:
    ham dense, ham BM25, iki listedeki sıra, RRF, boost'lar, final ve rerank.
    """
    print(f"\n[retrieval] SKOR DOKUMU — sorgu: {query!r} | BM25 token'lari: {query_tokens}")
    header = (f"{'#':>2} {'id':>5} {'page_info':<18} {'dense':>7} {'d_rank':>6} "
              f"{'bm25':>7} {'b_rank':>6} {'rrf':>7} {'kw_bst':>7} {'meta':>5} "
              f"{'hint':>5} {'final':>7} {'rerank':>8}  kimlik")
    print(header)
    print("-" * len(header))
    for pos, c in enumerate(candidates):
        d = c["score_debug"]
        b_rank = "-" if d["bm25_rank"] is None else str(d["bm25_rank"])
        rr = "" if rerank_by_idx is None else f"{rerank_by_idx.get(pos, float('nan')):.4f}"
        ident = next((ln.strip() for ln in c["content"].splitlines()
                      if ln.lower().startswith(("occupation:", "name:", "title:"))),
                     c["content"][:40].replace("\n", " "))
        print(f"{pos + 1:>2} {c['id']:>5} {str(c['page_info'])[:18]:<18} "
              f"{d['dense_raw']:>7.4f} {d['dense_rank']:>6} {d['bm25_raw']:>7.3f} {b_rank:>6} "
              f"{d['rrf']:>7.4f} {d['keyword_boost']:>7.4f} {d['meta_boost']:>5.2f} "
              f"{d['hint_boost']:>5.2f} {c['score']:>7.4f} {rr:>8}  {ident[:40]}")
    print()


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
