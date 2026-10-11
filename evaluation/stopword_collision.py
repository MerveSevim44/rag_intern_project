"""
stopword_collision.py — BM25 stem/stopword çakışması kapsam ölçümü (backlog madde 19)

Snowball Türkçe stemmer'ı bazı GERÇEK kelimeleri bir stopword'ün stem'ine
indiriyor ("deneyim" -> "de", "iş" -> "is", "ön" -> "on"). Ölçüm doğrudan
retrieval._tokenize ÇIKTISI üzerinden yapılır, böylece tokenizer'ın hangi
sürümü yüklüyse onu ölçer:

  1. Corpus'ta (rag.db) gerçek stopword olmadığı hâlde DÜŞEN kelimeleri ve
     çekimi olmayan başka bir kelimeyle aynı token'a BİRLEŞEN kelimeleri
     (deniz/deneyim -> "de") geçiş ve chunk sayılarıyla listeler.
  2. Test sorularında hangilerinin geçtiğini bulur.
  3. Etkilenen pozitif soruların F1 / faithfulness / retrieval sırasını
     (verilen skor ve judge dosyalarından) etkilenmeyenlerle karşılaştırır.

Ne zaman yeniden koşulmalı: stemmer, TURKISH_STOPWORDS ya da _tokenize
değiştiğinde ve corpus yeniden ingest edildiğinde.

Kullanım:
    python evaluation/stopword_collision.py
    python evaluation/stopword_collision.py --scored experiments/v7_refusal_clarity/report/genel_scored.csv
"""

import argparse
import csv
import sqlite3
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

_eval_dir = Path(__file__).resolve().parent
_root_dir = _eval_dir.parent
for _p in [str(_root_dir / "src"), str(_root_dir)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    import src.retrieval as retrieval
except ImportError:
    import retrieval

POSITIVE_SETS = [f"test_{n}" for n in range(1, 6)]
NEGATIVE_SET = "test_negative"

# Yüzey biçimi zaten stopword olanlar (ve, bu, için, nedir...) çakışma değildir.
# Liste tek kaynaktan gelir: retrieval.TURKISH_STOPWORDS.
_SURFACE_STOPWORDS = {retrieval._accent_fold(w)
                      for w in retrieval._base_tokens(" ".join(retrieval.TURKISH_STOPWORDS))}


def _candidate(word):
    """Ölçüme giren kelime: sayı/tek harf değil ve gerçek bir stopword değil."""
    return (not word.isdigit() and len(word) >= 2
            and retrieval._accent_fold(word) not in _SURFACE_STOPWORDS)


def _tokens(word):
    return tuple(retrieval._tokenize(word))


def _related(a, b, group):
    """
    İki fold'lu yüzey aynı kelimenin çekimi sayılır mı? Biri diğerinin önekiyse
    ya da gruptaki üçüncü bir yüzey ikisinin de önekiyse (oda -> odaya, odadaki).
    """
    return (a.startswith(b) or b.startswith(a)
            or any(a.startswith(c) and b.startswith(c) for c in group))


def _risky(word):
    """Snowball stem'i bir stopword stem'ine denk geliyor mu (madde 19 ailesi)?"""
    return retrieval._accent_fold(retrieval._stem(word)) in retrieval._STOPWORDS


def collect(words):
    """
    _tokenize ÇIKTISI üzerinden iki tür hasar:
      dropped : gerçek stopword olmadığı hâlde _tokenize'ın sildiği kelimeler
      merged  : risky bir kelimenin, çekimi OLMAYAN başka bir kelimeyle aynı
                token'a düşmesi (ör. yüzey filtresi + stem: deniz/deneyim -> "de")
    Hem düzeltme öncesi hem sonrası anlamlıdır; düzeltme sonrası beklenen 0/0.
    """
    dropped, by_token, risky_tokens = set(), defaultdict(set), set()
    for w in words:
        if not _candidate(w):
            continue
        toks = _tokens(w)
        if not toks:
            dropped.add(w)
            continue
        by_token[toks].add(retrieval._accent_fold(w))
        if _risky(w):
            risky_tokens.add(toks)
    merged = {}
    for toks in risky_tokens:
        surfaces = sorted(by_token[toks])
        unrelated = [(a, b) for i, a in enumerate(surfaces) for b in surfaces[i + 1:] if not _related(a, b, surfaces)]
        if unrelated:
            merged[" ".join(toks)] = surfaces
    return dropped, merged


def content_collisions(text, merged_surfaces=frozenset()):
    """Metinde düşen ya da başka kelimeyle birleşen içerik kelimeleri."""
    out = set()
    for w in retrieval._base_tokens(text):
        if not _candidate(w):
            continue
        if not _tokens(w) or retrieval._accent_fold(w) in merged_surfaces:
            out.add(w)
    return sorted(out)


def corpus_report(db_path):
    db = sqlite3.connect(db_path)
    rows = list(db.execute("SELECT id, source, content FROM chunks"))
    words_by_chunk = [(cid, src, retrieval._base_tokens(text)) for cid, src, text in rows]
    dropped, merged = collect({w for _, _, ws in words_by_chunk for w in ws})
    merged_surfaces = {s for surfaces in merged.values() for s in surfaces}

    freq, chunks, by_source = Counter(), defaultdict(set), Counter()
    for cid, src, ws in words_by_chunk:
        for w in ws:
            if w in dropped or (_candidate(w) and retrieval._accent_fold(w) in merged_surfaces):
                freq[w] += 1
                chunks[w].add(cid)
                by_source[Path(src).name] += 1

    print(f"Corpus ({len(rows)} chunk): {len(dropped)} kelime DÜŞÜYOR, "
          f"{len(merged)} token'da çekimi olmayan kelimeler BİRLEŞİYOR; "
          f"toplam {sum(freq.values())} geçiş")
    if merged:
        print("  Birleşen token'lar:", merged)
    print(f"  {'kelime':16} {'durum':8} {'geçiş':>6} {'chunk':>6}")
    for w, n in freq.most_common():
        print(f"  {w:16} {'düşüyor' if w in dropped else 'birleşik':8} {n:6} {len(chunks[w]):6}")
    if by_source:
        print("  Kaynağa göre:", dict(by_source.most_common()))
    return merged_surfaces


def load_questions(datasets_dir, name):
    """Soru dosyasını sütun ADINA göre okur (setler arasında sütun sırası farklı)."""
    with open(datasets_dir / f"{name}.csv", encoding="utf-8-sig") as f:
        return [(row["id"], row["soru"]) for row in csv.DictReader(f) if row.get("id", "").strip().isdigit()]


def load_by_key(path, set_col=None, set_name=None):
    if not path.exists():
        return {}
    with open(path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if set_col:
        return {(r[set_col], r["id"]): r for r in rows}
    return {(set_name, r["id"]): r for r in rows}


def _num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def question_report(datasets_dir, scored_path, judge_dir, merged_surfaces=frozenset()):
    scored = load_by_key(scored_path, set_col="test_seti")
    judge = {}
    for s in POSITIVE_SETS:
        judge.update(load_by_key(judge_dir / f"{s}_sonuclari_judge.csv", set_name=s))
    if not scored:
        print(f"\n[uyarı] Skor dosyası bulunamadı: {scored_path} — yalnızca sorular listelenir.")

    def rows_for(s):
        out = []
        for qid, q in load_questions(datasets_dir, s):
            sc, jd = scored.get((s, qid), {}), judge.get((s, qid), {})
            out.append(dict(set=s, id=qid, q=q, words=content_collisions(q, merged_surfaces),
                            f1=_num(sc.get("f1_score")), cls=sc.get("siniflandirma"),
                            faith=_num(jd.get("faithfulness_score")),
                            match=sc.get("retrieval_match"), rank=sc.get("retrieval_sira")))
        return out

    pos = [x for s in POSITIVE_SETS for x in rows_for(s)]
    neg = rows_for(NEGATIVE_SET)
    hit = [x for x in pos if x["words"]]
    print(f"\nPozitif sorular: {len(hit)}/{len(pos)} soruda düşen/birleşen içerik kelimesi var; "
          f"negatif: {sum(1 for x in neg if x['words'])}/{len(neg)}")
    for x in hit + [x for x in neg if x["words"]]:
        print(f"  {x['set']:13} #{x['id']:>3} {x['cls'] or '-':3} F1={x['f1']} faith={x['faith']} "
              f"retr={x['match']}/{x['rank']} {x['words']} | {x['q'][:80]}")

    def summary(group, label):
        f1 = [x["f1"] for x in group if x["f1"] is not None]
        fa = [x["faith"] for x in group if x["faith"] is not None]
        print(f"  {label:20} n={len(group):3}  "
              f"F1 ort={statistics.mean(f1) if f1 else float('nan'):5.1f}  "
              f"faith ort={statistics.mean(fa) if fa else float('nan'):4.2f}  "
              f"{dict(Counter(x['cls'] for x in group))}")

    print("\nKarşılaştırma (pozitif sorular):")
    summary(hit, "düşen/birleşen kelimeli")
    summary([x for x in pos if not x["words"]], "diğer")


def main(argv=None):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--db", default=str(_root_dir / "rag.db"))
    parser.add_argument("--datasets", default=str(_eval_dir / "datasets"))
    parser.add_argument("--scored", default=str(_root_dir / "experiments/v7_refusal_clarity/report/genel_scored.csv"),
                        help="benchmark_eval çıktısı (genel_scored.csv)")
    parser.add_argument("--judge-dir", default=str(_eval_dir / "datasets"),
                        help="test_N_sonuclari_judge.csv dosyalarının dizini")
    args = parser.parse_args(argv)

    merged_surfaces = corpus_report(args.db)
    question_report(Path(args.datasets), Path(args.scored), Path(args.judge_dir), merged_surfaces)


if __name__ == "__main__":
    main()
