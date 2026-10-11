"""
v0_tokenizer.py — madde 19 düzeltmesinden ÖNCEKİ BM25 tokenizer'ın birebir kopyası.

Kaynak: commit 2ef9487 src/retrieval.py (`_tokenize`, `_apply_synonyms`,
`TURKISH_STOPWORDS`, `_STOPWORDS`). Stopword filtresi STEM'e uygulanır; stem'i
bir stopword stem'ine denk gelen gerçek kelimeler ("deneyim" -> "de") düşer.

Regresyon karşılaştırması bu fonksiyonu retrieval._tokenize yerine bellek
içinde yamalar (retrieval.invalidate_cache() ile BM25 indeksi yeniden kurulur).
`verify_against_git()` kopyanın HEAD~ koduyla birebir aynı token'ları
ürettiğini corpus üzerinde doğrular.
"""
import sys
from pathlib import Path
from typing import List

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

import retrieval as _r  # noqa: E402

V0_TURKISH_STOPWORDS = {
    "acaba", "ama", "ancak", "bana", "bazı", "belki", "ben", "beni", "benim",
    "bir", "biraz", "biz", "bize", "bu", "buna", "bunu", "bunun", "da", "daha",
    "de", "değil", "diye", "en", "gibi", "hem", "her", "için", "ile", "ise",
    "kadar", "ki", "mi", "mı", "mu", "mü", "ne", "neden", "nasıl", "o", "ona",
    "onu", "onun", "olan", "olarak", "sen", "siz", "şu", "ve", "veya", "ya",
    "yani", "çok", "iyi", "var",
    "arıyorum", "istiyorum", "lazım", "bul", "bulur", "öner", "önerir",
    "musun", "misin", "müsün", "mısın",
}
V0_STOPWORDS = {t for w in V0_TURKISH_STOPWORDS for t in _r._tokenize_key(w)}


def _v0_apply_synonyms(folded: List[str], natural: List[str]) -> List[str]:
    out: List[str] = []
    i = 0
    while i < len(folded):
        for key, canonical in _r._SYNONYM_RULES:
            n = len(key)
            window = folded[i:i + n]
            if (len(window) == n and window[:-1] == list(key[:-1])
                    and window[-1].startswith(key[-1])):
                out.extend(canonical)
                i += n
                break
        else:
            out.append(_r._accent_fold(_r._stem(natural[i])))
            i += 1
    return out


def v0_tokenize(text: str) -> List[str]:
    natural = _r._base_tokens(text)
    folded = [_r._accent_fold(t) for t in natural]
    return [t for t in _v0_apply_synonyms(folded, natural) if t not in V0_STOPWORDS]


def verify_against_git(rev: str = "2ef9487", db_path: str = str(_ROOT / "rag.db")) -> int:
    """Kopyayı git'teki gerçek kodla tüm corpus + soru setlerinde karşılaştırır; farklı metin sayısını döner."""
    import csv
    import importlib.util
    import sqlite3
    import subprocess
    import tempfile

    src = subprocess.run(["git", "show", f"{rev}:src/retrieval.py"], cwd=_ROOT,
                         capture_output=True, check=True).stdout
    with tempfile.NamedTemporaryFile("wb", suffix="_retrieval_v0.py", delete=False) as f:
        f.write(src)
    spec = importlib.util.spec_from_file_location("retrieval_git_v0", f.name)
    git_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(git_mod)

    texts = [row[0] for row in sqlite3.connect(db_path).execute("SELECT content FROM chunks")]
    for p in sorted((_ROOT / "evaluation" / "datasets").glob("test_*.csv")):
        if p.stem.endswith("sonuclari"):
            continue
        with open(p, encoding="utf-8-sig") as fh:
            texts += [r["soru"] for r in csv.DictReader(fh) if r.get("soru")]
    return sum(1 for t in texts if git_mod._tokenize(t) != v0_tokenize(t))


if __name__ == "__main__":
    n = verify_against_git()
    print(f"v0_tokenize ile git 2ef9487 _tokenize arasında farklı metin: {n}")
    sys.exit(1 if n else 0)
