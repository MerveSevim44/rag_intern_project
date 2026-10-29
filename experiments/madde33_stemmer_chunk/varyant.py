"""
Madde 33 — #91'in iki nedenini birbirinden bağımsız simüle eden varyantlar.

src/ ve rag.db değişmez; her şey süreç içi (retrieval modülü + bellekteki cache):
  V0  mevcut sistem
  S   stemmer oracle: _stem çıktısında "kütüpha"/"kütüphanes" -> "kütüphane"
      (Adım 1'de tespit edilen aile; yalnız bu aile — genel bir stemmer
      düzeltmesinin üst sınırı değil, bu nedenin #91'e katkısını izole eder)
  M   chunk birleştirme oracle: test1.txt paragraf 1 + 2 tek chunk (ingest'in
      paragraf ayırıcısı "\n\n" ile), embedding ingest ile aynı yoldan
      (embedder.get_embeddings) yeniden hesaplanır; paragraf 2 chunk'ı silinir
  SM  ikisi birlikte

kur(mod, varyant) retrieval modülünü (mod) varyanta getirir; V0'a dönmek için de
kullanılır. Birleşmiş chunk id'si 4227 kalır (page_info "paragraf 1-2").
"""
import json
import sqlite3

import numpy as np

P1, P2 = 4227, 4228  # test1.txt paragraf 1 (cevap: "Gümüş Yaprak") / 2 ("Alis, bu kütüphanede…")
S_AILE = {"kütüpha": "kütüphane", "kütüphanes": "kütüphane"}
VARYANTLAR = ["V0", "S", "M", "SM"]

_orig_stem = {}
_birlesik_emb = {}


def _stem_s(orig):
    def stem(token):
        s = orig(token)
        return S_AILE.get(s, s)
    return stem


def _birlestir(mod):
    """Cache satırlarında P1+P2'yi tek chunk yapar ve tüm indeksleri yeniden kurar."""
    from embedder import get_embeddings

    c = mod._cache
    rows = list(c._rows)
    i1 = next(i for i, r in enumerate(rows) if r[0] == P1)
    i2 = next(i for i, r in enumerate(rows) if r[0] == P2)
    metin = rows[i1][2] + "\n\n" + rows[i2][2]
    if metin not in _birlesik_emb:
        _birlesik_emb[metin] = get_embeddings([metin])[0]
    rows[i1] = (P1, rows[i1][1], metin, json.dumps(_birlesik_emb[metin]), "paragraf 1-2")
    del rows[i2]

    c._rows = rows
    c._views = {}
    c._embedding_matrix = np.array([json.loads(r[3]) for r in rows], dtype=np.float32)
    c._embedding_norms = np.linalg.norm(c._embedding_matrix, axis=1)
    c._corpus_tokens = [mod._tokenize(r[2]) for r in rows]
    c._bm25 = mod.BM25Okapi(c._corpus_tokens)
    c._key_tokens = [mod._key_field_tokens(r[2]) for r in rows]


def kur(mod, varyant, db_path=None):
    """retrieval modülünü varyanta getirir (cache yeniden kurulur)."""
    if id(mod) not in _orig_stem:
        _orig_stem[id(mod)] = mod._stem
    orig = _orig_stem[id(mod)]
    mod._stem = _stem_s(orig) if "S" in varyant else orig
    mod._cache.invalidate()
    mod._cache.load(db_path or mod.DB_PATH)
    if "M" in varyant:
        _birlestir(mod)


def saglama_embedding(mod):
    """Yöntem sağlaması: P1'in mevcut metni yeniden gömülünce DB'deki vektörle aynı mı?"""
    from embedder import get_embeddings

    with sqlite3.connect(mod.DB_PATH) as conn:
        metin, emb = conn.execute("SELECT content, embedding FROM chunks WHERE id=?", (P1,)).fetchone()
    a = np.array(json.loads(emb), dtype=np.float32)
    b = np.array(get_embeddings([metin])[0], dtype=np.float32)
    return float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b)))
