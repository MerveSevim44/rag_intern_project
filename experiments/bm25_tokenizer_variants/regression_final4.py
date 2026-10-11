"""
regression_final4.py — regresyon katman 1 (implementation_plan_bm25_stopword.md §5).

Her soru için ESKİ (v0_tokenizer.v0_tokenize, doğrulanmış kopya) ve YENİ
(src/retrieval.py'deki _tokenize) tokenizer ile, deterministik olarak:

  aday_k   : reranker'a giden ilk k aday (k=5 benchmark, k=8 arayüz)
  final_k  : reranker sonrası LLM'e giden RERANK_TOP_N parça (reranker HER
             durumda gerçekten çalıştırılır; "aday kümesi aynıysa final de
             aynıdır" varsayımına dayanılmaz)
  baglam_k : LLM'e giden bağlam metni (run_tests.build_context biçimi). Soruya
             duyarlı kırpma da _tokenize kullandığı için final aynı olsa bile
             bağlam değişebilir.

Bağlamı aynı kalan soruda LLM'e giden girdi bayt bayt aynıdır: o soruda cevap
farkı yalnız nondeterminizmdir. Değişen her soru `degisenler.md`'ye ayrıntısıyla
(çıkan/giren parça) yazılır, elle incelenir.

Tablosal rotalar (rule_engine/code_interpreter) LLM'siz koşuda veri motoruna
gidemediği için atlanır; rota router'da belirlenir ve tokenizer'dan bağımsızdır.

Kullanım:
    python experiments/bm25_tokenizer_variants/regression_final4.py
"""
import contextlib
import csv
import io
import json
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(HERE))

# DİKKAT: retrieve()'i çağırdığımız modül nesnesiyle yamaladığımız aynı olmalı.
# `src.retrieval` ile `retrieval` ayrı modül nesneleridir; burada yalnız
# `retrieval` (src/ yolu) kullanılır, llm_client de kırpmada onu import eder.
import retrieval as R  # noqa: E402
import llm_client as L  # noqa: E402
from v0_tokenizer import v0_tokenize  # noqa: E402

NEW_TOKENIZE = R._tokenize
TOKENIZERS = {"eski": v0_tokenize, "yeni": NEW_TOKENIZE}
KS = (5, R.TOP_K)
SETS = [f"test_{n}" for n in range(1, 6)] + ["test_negative", "test_stopword"]
_PROFILE_RE = re.compile(r"^\$\.profiles\[\d+\]")

_emb_cache = {}
_orig_emb = R.get_embedding


def _memo_emb(text, model=R.EMBED_MODEL, **kw):
    if text not in _emb_cache:
        _emb_cache[text] = _orig_emb(text, model=model, **kw)
    return _emb_cache[text]


R.get_embedding = _memo_emb


def quiet(fn, *a, **k):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*a, **k)


def build_context(chunks, question):
    """evaluation/run_tests.build_context ile aynı biçim."""
    parts = []
    for i, c in enumerate(chunks, 1):
        content = L.truncate_chunk_text(c["content"], query=question)
        parts.append(f"[{i}] Kaynak: {Path(c['source']).name}, {c.get('page_info', '')}\n{content}")
    return L.truncate_context("\n\n".join(parts))


def rerank(question, cands):
    reranked = quiet(R.rerank_indices, question, [c["content"] for c in cands])
    return [cands[i] for _, i in reranked[:R.RERANK_TOP_N]]


def load_questions():
    gt_stop = json.loads((ROOT / "evaluation/ground_truth/test_stopword.json").read_text(encoding="utf-8"))
    out = []
    for s in SETS:
        with open(ROOT / f"evaluation/datasets/{s}.csv", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                if row.get("id", "").strip().isdigit():
                    out.append(dict(set=s, id=row["id"], q=row["soru"],
                                    src=(row.get("beklenen_kaynak") or "").strip(),
                                    targets=set(gt_stop.get(row["id"], {}).get("hedef_profiller", []))
                                    if s == "test_stopword" else set()))
    return out


def measure(question):
    """Yüklü tokenizer ile tek soru: rota, adaylar, finaller, bağlamlar."""
    ranking = quiet(R.retrieve, question["q"], top_k=max(KS), use_reranker=False, rerank_top_n=max(KS))
    route = ranking[0].get("route") if ranking else None
    res = {"route": route}
    if route != "semantic_rag":
        return res
    for k in KS:
        cands = ranking[:k]
        final = rerank(question["q"], cands)
        # Ara kayıt (jsonl) için parçaların yalnız raporda gereken alanları tutulur.
        slim = [dict(id=c["id"], source=c["source"], page_info=c.get("page_info", ""),
                     content=(c["content"] or "").strip().split("\n", 1)[0][:200]) for c in final]
        res[str(k)] = dict(aday=[c["id"] for c in cands], final=[c["id"] for c in final],
                           final_chunks=slim, baglam=build_context(final, question["q"]))
    return res


# Ara kayıt: her soru bitince diske yazılır; yeniden başlatılan koşu kaldığı
# yerden devam eder (ilk koşu servis kapanınca 80/159'da kayboldu).
CACHE = HERE / "regresyon_cache.jsonl"


def load_cache():
    if not CACHE.exists():
        return {}
    with open(CACHE, encoding="utf-8") as f:
        return {rec["key"]: rec["res"] for rec in map(json.loads, f) if rec}


def append_cache(key, res):
    with open(CACHE, "a", encoding="utf-8") as f:
        f.write(json.dumps({"key": key, "res": res}, ensure_ascii=False) + "\n")


def src_in(chunks, src):
    return any(Path(c["source"]).name == src for c in chunks) if src and src != "-" else None


def target_in(chunks, targets):
    return sum(1 for c in chunks if (_PROFILE_RE.match(c.get("page_info") or "") or [None])[0] in targets)


def describe(c):
    first = (c["content"] or "").strip().split("\n", 1)[0][:90]
    return f"`{c['id']}` {Path(c['source']).name} {c.get('page_info', '')} — {first}"


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    questions = load_questions()
    cache = load_cache()
    print(f"ara kayıttan yüklenen: {len(cache)}", flush=True)
    results = {}
    t0 = time.perf_counter()
    for name, fn in TOKENIZERS.items():
        R._tokenize = fn
        R.invalidate_cache()
        assert L._query_aware_truncate.__module__ == "llm_client"
        for i, q in enumerate(questions, 1):
            key = f"{name}|{q['set']}|{q['id']}"
            if key not in cache:
                cache[key] = measure(q)
                append_cache(key, cache[key])
            results[(name, q["set"], q["id"])] = cache[key]
            if i % 20 == 0:
                print(f"  {name}: {i}/{len(questions)} ({time.perf_counter() - t0:.0f} sn)", flush=True)
        print(f"bitti: {name}", flush=True)
    R._tokenize = NEW_TOKENIZE
    R.invalidate_cache()

    rows, changed = [], []
    for q in questions:
        old, new = results[("eski", q["set"], q["id"])], results[("yeni", q["set"], q["id"])]
        row = dict(set=q["set"], id=q["id"], route_eski=old["route"], route_yeni=new["route"])
        if old["route"] != "semantic_rag" or new["route"] != "semantic_rag":
            row["not"] = "tablosal rota, atlandı"
            rows.append(row)
            continue
        for k in KS:
            o, n = old[str(k)], new[str(k)]
            row[f"aday{k}_ayni"] = set(o["aday"]) == set(n["aday"])
            row[f"final{k}_ayni"] = set(o["final"]) == set(n["final"])
            row[f"final{k}_sira_ayni"] = o["final"] == n["final"]
            row[f"baglam{k}_ayni"] = o["baglam"] == n["baglam"]
            row[f"kaynak{k}_eski"] = src_in(o["final_chunks"], q["src"])
            row[f"kaynak{k}_yeni"] = src_in(n["final_chunks"], q["src"])
            if q["targets"]:
                row[f"hedef{k}_eski"] = target_in(o["final_chunks"], q["targets"])
                row[f"hedef{k}_yeni"] = target_in(n["final_chunks"], q["targets"])
            if not row[f"baglam{k}_ayni"]:
                changed.append((q, k, o, n, row[f"final{k}_ayni"]))
        rows.append(row)

    fields = list(dict.fromkeys(k for r in rows for k in r))
    with open(HERE / "regresyon_final4.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    sem = [r for r in rows if "not" not in r]
    lines = ["# Regresyon katman 1 — final 4 parça / bağlam karşılaştırması", "",
             f"Soru: {len(rows)} (semantic_rag: {len(sem)}, tablosal atlanan: {len(rows) - len(sem)}); "
             f"süre {time.perf_counter() - t0:.0f} sn.", "",
             "| k | aday kümesi değişen | final kümesi değişen | final sırası değişen | bağlam değişen | "
             "beklenen kaynağı final'den KAYBEDEN | kazanan |", "|---|---|---|---|---|---|---|"]
    for k in KS:
        lost = [f"{r['set']}#{r['id']}" for r in sem if r[f"kaynak{k}_eski"] and r[f"kaynak{k}_yeni"] is False]
        won = [f"{r['set']}#{r['id']}" for r in sem if r[f"kaynak{k}_eski"] is False and r[f"kaynak{k}_yeni"]]
        lines.append(f"| {k} | {sum(not r[f'aday{k}_ayni'] for r in sem)} | {sum(not r[f'final{k}_ayni'] for r in sem)} | "
                     f"{sum(not r[f'final{k}_sira_ayni'] for r in sem)} | {sum(not r[f'baglam{k}_ayni'] for r in sem)} | "
                     f"{', '.join(lost) or '0'} | {', '.join(won) or '0'} |")
    lines += ["", "## test_stopword — hedef profil final'de (eski → yeni)", "",
              "| # | " + " | ".join(f"k={k}" for k in KS) + " |", "|---|" + "---|" * len(KS)]
    for r in sem:
        if r["set"] == "test_stopword":
            lines.append(f"| {r['id']} | " + " | ".join(f"{r[f'hedef{k}_eski']} → {r[f'hedef{k}_yeni']}" for k in KS) + " |")
    lines += ["", "## Bağlamı değişen sorular (elle inceleme)", ""]
    for q, k, o, n, same_final in changed:
        out_ids, in_ids = set(o["final"]) - set(n["final"]), set(n["final"]) - set(o["final"])
        lines.append(f"### {q['set']} #{q['id']} (k={k}) — {q['q']}")
        lines.append(f"- beklenen kaynak: {q['src'] or '-'} | final aynı küme: {same_final}")
        for c in o["final_chunks"]:
            if c["id"] in out_ids:
                lines.append(f"- ÇIKAN: {describe(c)}")
        for c in n["final_chunks"]:
            if c["id"] in in_ids:
                lines.append(f"- GİREN: {describe(c)}")
        if same_final:
            lines.append("- yalnız bağlam metni değişti (sıra ya da soruya duyarlı kırpma)")
        lines.append("")
    (HERE / "regresyon_final4.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:12]))


if __name__ == "__main__":
    main()
