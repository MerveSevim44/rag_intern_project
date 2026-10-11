"""
Planlama deneyi (docs/implementation_plan_bm25_stopword.md §4): tokenizer
varyantlarının hibrit sıralamaya etkisi. Reranker YOK, deterministik. Varyantlar
retrieval._tokenize yerine bellek içinde yamalanır; src/ değişmez.

Sonuçlar: sonuc_V0_V1_V2.txt, sonuc_V0_V1_V3.txt (2026-10-10, kod 2ef9487).
Koşu sırasında V0 = o anki src/retrieval.py idi; düzeltme sonrası yeniden
koşulabilsin diye V0 ve varyantların tabanı doğrulanmış kopyaya
(v0_tokenizer.py) bağlandı.

Not: V3'ün buradaki deney sürümü stem kontrolünü _apply_synonyms ÇIKTISINI
girdiyle sıra sıra eşleyerek yapar; eş anlamlı kural çok token ürettiğinde (kbb)
hizasız kalır. Ürün kodu kontrolü token başına yapar ve soru eklerini (nedir,
nelerdir...) stopword listesine ekler — ürün kodu regression_final4.py ile ölçülür.
"""
import csv, json, re, sys, io, contextlib
from collections import Counter
from pathlib import Path
ROOT = str(Path(__file__).resolve().parents[2])
sys.path.insert(0, ROOT + r"\src")
sys.path.insert(0, str(Path(__file__).resolve().parent))
import retrieval as r
from v0_tokenizer import v0_tokenize, V0_TURKISH_STOPWORDS, V0_STOPWORDS, _v0_apply_synonyms

SURF_STOP = {r._accent_fold(w) for w in r._base_tokens(" ".join(V0_TURKISH_STOPWORDS))}
ORIG = v0_tokenize
_emb_cache = {}
_orig_emb = r.get_embedding
def _memo_emb(text, model=r.EMBED_MODEL, **kw):
    if text not in _emb_cache:
        _emb_cache[text] = _orig_emb(text, model=model, **kw)
    return _emb_cache[text]
r.get_embedding = _memo_emb


def v1_surface_stop(text):
    """Stopword filtresi stem ÖNCESİ yüzey biçimine; stem'i stopword'e denk gelen gerçek kelime kalır."""
    natural = r._base_tokens(text)
    keep = [i for i, t in enumerate(natural) if r._accent_fold(t) not in SURF_STOP]
    natural = [natural[i] for i in keep]
    folded = [r._accent_fold(t) for t in natural]
    return _v0_apply_synonyms(folded, natural)


def v2_surface_stop_short_guard(text):
    """V1 + stem 3 harften kısaysa yüzey biçimi (fold'lu) kullanılır: damla/data -> 'da' çakışmasın."""
    natural = r._base_tokens(text)
    natural = [t for t in natural if r._accent_fold(t) not in SURF_STOP]
    out = []
    for t in natural:
        s = r._accent_fold(r._stem(t))
        out.append(s if len(s) >= 3 or t.isdigit() else r._accent_fold(t))
    return out


def v3_surface_stop_collision_guard(text):
    """V1 + yalnız stem'i bir stopword stem'ine denk gelen kelimede fold'lu yüzey biçimi kullanılır."""
    natural = r._base_tokens(text)
    natural = [t for t in natural if r._accent_fold(t) not in SURF_STOP]
    folded = [r._accent_fold(t) for t in natural]
    out = []
    for t, s in zip(folded, _v0_apply_synonyms(folded, natural)):
        out.append(t if s in V0_STOPWORDS else s)
    return out


VARIANTS = {"V0_mevcut": ORIG, "V1_yuzey_stop": v1_surface_stop, "V3_yuzey_stop+carpisma_korumasi": v3_surface_stop_collision_guard}

gt = json.load(open(ROOT + r"\evaluation\ground_truth\test_stopword.json", encoding="utf-8"))
bench = []
for s in [f"test_{n}" for n in range(1, 6)] + ["test_negative"]:
    for row in csv.DictReader(open(ROOT + rf"\evaluation\datasets\{s}.csv", encoding="utf-8-sig")):
        if row.get("id", "").strip().isdigit():
            bench.append((s, row["id"], row["soru"], row.get("beklenen_kaynak", "").strip()))


def quiet(fn, *a, **k):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a, **k)


prof = re.compile(r"^\$\.profiles\[\d+\]")
results = {}
for name, fn in VARIANTS.items():
    r._tokenize = fn
    r.invalidate_cache()
    res = {"stop": {}, "bench": {}}
    for qid, e in gt.items():
        ranking = quiet(r.retrieve, e["soru"], top_k=100000, use_reranker=False, rerank_top_n=100000)
        tg, cf = set(e["hedef_profiller"]), set(e["karistirici_profiller"])
        pos = [i for i, c in enumerate(ranking, 1) if (prof.match(c["page_info"] or "") or [None])[0] in tg]
        best = ranking[pos[0] - 1]["score_debug"] if pos else {}
        cpos = [i for i, c in enumerate(ranking, 1) if (prof.match(c["page_info"] or "") or [None])[0] in cf]
        res["stop"][qid] = dict(hibrit=pos[0] if pos else None, bm25=best.get("bm25_rank"),
                                dense=best.get("dense_rank"), onde=sum(1 for p in cpos if pos and p < pos[0]),
                                tok=" ".join(fn(e["soru"])))
    for s, qid, q, src in bench:
        top = quiet(r.retrieve, q, top_k=8, use_reranker=False, rerank_top_n=8)
        ids = [c["id"] for c in top]
        srcs = [c["source"].split("/")[-1] for c in top]
        first = next((i for i, x in enumerate(srcs, 1) if src and x == src), None)
        res["bench"][(s, qid)] = dict(ids=ids, ids5=ids[:5], first=first, route=top[0].get("route") if top else None)
    results[name] = res
    print("bitti:", name, flush=True)
r._tokenize = ORIG

print("\n=== test_stopword: hedef hibrit sırası (bm25 sırası) | önde karıştırıcı")
for qid in gt:
    print(qid, " | ".join(f"{n[:2]} {results[n]['stop'][qid]['hibrit']} (bm25 {results[n]['stop'][qid]['bm25']}) k{results[n]['stop'][qid]['onde']}"
                         for n in VARIANTS), "|", results["V3_yuzey_stop+carpisma_korumasi"]["stop"][qid]["tok"])

base = results["V0_mevcut"]["bench"]
for n in list(VARIANTS)[1:]:
    cur = results[n]["bench"]
    sem = [k for k in base if base[k]["route"] == "semantic_rag"]
    changed8 = [k for k in sem if set(base[k]["ids"]) != set(cur[k]["ids"])]
    changed5 = [k for k in sem if set(base[k]["ids5"]) != set(cur[k]["ids5"])]
    worse = [k for k in sem if base[k]["first"] is not None and (cur[k]["first"] is None or cur[k]["first"] > base[k]["first"])]
    better = [k for k in sem if cur[k]["first"] is not None and (base[k]["first"] is None or cur[k]["first"] < base[k]["first"])]
    lost5 = [k for k in sem if base[k]["first"] and base[k]["first"] <= 5 and not (cur[k]["first"] and cur[k]["first"] <= 5)]
    print(f"\n=== benchmark {n}: semantic soru {len(sem)} | top8 aday kümesi değişen {len(changed8)} | top5 değişen {len(changed5)}")
    print("  beklenen kaynağın ilk sırası kötüleşen:", [(k, base[k]['first'], cur[k]['first']) for k in worse])
    print("  iyileşen:", [(k, base[k]['first'], cur[k]['first']) for k in better])
    print("  top5'ten beklenen kaynağı kaybeden:", lost5)
    print("  top8 kümesi değişenler:", changed8)
