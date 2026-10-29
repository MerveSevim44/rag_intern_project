"""
Madde 33 Adım 2 — genel birleştirme politikası: .txt paragraflarını en az MIN
karakterlik chunk'lara açgözlü birleştir; .txt dosyalarının bu politikayla yeniden
ingest edilmesini süreç içinde simüle eder (src/ ve rag.db değişmez).

Kural (ingest.extract_chunks_from_txt'in paragrafları üzerinde):
  sırayla paragraf ekle, birikmiş metin >= MIN karakter olunca chunk'ı kapat;
  sonda MIN'in altında kalan artık bir önceki chunk'a eklenir.
  Birleştirme ayırıcısı "\n\n" (ingest'in paragraf ayırıcısı), page_info
  "paragraf i-j". MIN=0 -> bugünkü davranış (her paragraf ayrı).

Yalnız .txt etkilenir: paragraf chunker'ı yalnız onlarda; pdf/docx/json değişmez.
Embedding ingest ile aynı yoldan (embedder.get_embeddings); birleşik chunk'ın id'si
ilk paragrafının id'si.
"""
import json
import sqlite3
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
TXT = ["data/test1.txt", "data/test2.txt"]
_emb = {}


def birlestir(paragraflar, minc):
    """[(metin, 'paragraf k')] -> [(metin, 'paragraf i-j', [k...])]"""
    out, buf, nums = [], [], []
    for metin, info in paragraflar:
        buf.append(metin)
        nums.append(int(info.split()[-1]))
        if minc <= 0 or len("\n\n".join(buf)) >= minc:
            out.append(["\n\n".join(buf), nums])
            buf, nums = [], []
    if buf:
        if out:
            out[-1][0] += "\n\n" + "\n\n".join(buf)
            out[-1][1] += nums
        else:
            out.append(["\n\n".join(buf), nums])
    return [(m, f"paragraf {n[0]}" if len(n) == 1 else f"paragraf {n[0]}-{n[-1]}", n) for m, n in out]


def kur(mod, minc, db_path=None):
    """retrieval modülünün cache'ini politika MIN=minc ile yeniden kurar (0 = bugünkü)."""
    from embedder import get_embeddings
    from ingest import extract_chunks_from_txt

    c = mod._cache
    c.invalidate()
    c.load(db_path or mod.DB_PATH)
    if minc <= 0:
        return
    rows = list(c._rows)
    for src in TXT:
        eski = [r for r in rows if r[1] == src]
        id_of = {int(r[4].split()[-1]): r[0] for r in eski}
        paragraflar = extract_chunks_from_txt(ROOT / src)
        # Sağlama: DB'deki paragraflar ingest'in bugünkü çıktısıyla aynı olmalı
        assert sorted((r[2], r[4]) for r in eski) == sorted(paragraflar), src
        yeni = birlestir(paragraflar, minc)
        eksik = [m for m, _, _ in yeni if m not in _emb]
        if eksik:
            for m, e in zip(eksik, get_embeddings(eksik)):
                _emb[m] = e
        # Yeni chunk'lar dosyanın ilk satırının yerine (sıra bağımlı eşitlik bozmaları değişmesin)
        ilk = next(i for i, r in enumerate(rows) if r[1] == src)
        yeni_rows = [(id_of[n[0]], src, m, json.dumps(_emb[m]), info) for m, info, n in yeni]
        diger = [r for r in rows if r[1] != src]
        rows = diger[:ilk] + yeni_rows + diger[ilk:]
    c._rows = rows
    c._views = {}
    c._embedding_matrix = np.array([json.loads(r[3]) for r in rows], dtype=np.float32)
    c._embedding_norms = np.linalg.norm(c._embedding_matrix, axis=1)
    c._corpus_tokens = [mod._tokenize(r[2]) for r in rows]
    c._bm25 = mod.BM25Okapi(c._corpus_tokens)
    c._key_tokens = [mod._key_field_tokens(r[2]) for r in rows]


if __name__ == "__main__":
    import sys
    sys.path[:0] = [str(ROOT / "src")]
    from ingest import extract_chunks_from_txt
    for src in TXT:
        p = extract_chunks_from_txt(ROOT / src)
        for minc in (500, 800, 1200):
            print(src, minc, [(i, len(m)) for m, i, _ in birlestir(p, minc)])
