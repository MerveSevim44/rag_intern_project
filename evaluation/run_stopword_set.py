"""
run_stopword_set.py — test_stopword setini chunk seviyesinde ölçer (backlog madde 19).

Doküman seviyesindeki retrieval_match bu sette işe yaramaz: 12 sorunun hepsi
728_profiles.json'dan. Bunun yerine DOĞRU PROFİLİN hangi aşamada kaldığı ölçülür:

  1. hibrit sıra   : tüm corpus üzerinde (reranker yok) hedefin en iyi sırası,
                     dense ve BM25 sırasıyla birlikte — kelimenin düşmesi BM25
                     sırasını mı bozuyor, yoksa dense de mi kaçırıyor?
  2. aday (top_k)  : reranker'a giden ilk k aday içinde hedef var mı?
                     (k=5 benchmark, k=8 arayüz/retrieval.TOP_K)
  3. final         : reranker sonrası LLM'e giden RERANK_TOP_N parçada hedef var mı?
  4. cevap         : arayüz akışıyla (k=TOP_K) üretilen cevapta ground truth
                     anahtar kelimelerinin oranı.

İsim sorularında (karistirici_profiller dolu) her aşamada aynı soyadlı başka
kişilerin de gelip gelmediği raporlanır: "ikisi de geliyor (sıralama sorunu)"
ile "hedef hiç gelmiyor (eksik chunk)" ayrımı buradan çıkar.

Kullanım:
    python evaluation/run_stopword_set.py --out-dir experiments/stopword_baseline
    python evaluation/run_stopword_set.py --no-llm     # yalnız retrieval aşamaları
"""

import argparse
import csv
import json
import re
import sys
import time
import unicodedata
from pathlib import Path

_eval_dir = Path(__file__).resolve().parent
_root_dir = _eval_dir.parent
for _p in [str(_root_dir / "src"), str(_eval_dir), str(_root_dir)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    from src.retrieval import retrieve, _tokenize, TOP_K, RERANK_TOP_N
    from src.llm_client import load_model, ask
except ImportError:
    from retrieval import retrieve, _tokenize, TOP_K, RERANK_TOP_N
    from llm_client import load_model, ask
from run_tests import build_context

GT_FILE = _eval_dir / "ground_truth" / "test_stopword.json"
CANDIDATE_KS = (5, TOP_K)
_PROFILE_RE = re.compile(r"^\$\.profiles\[\d+\]")


def profile_path(page_info):
    m = _PROFILE_RE.match(page_info or "")
    return m.group(0) if m else None


def _fold(text):
    text = unicodedata.normalize("NFKD", text.replace("İ", "i").replace("I", "ı").lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.replace("ı", "i")


def keyword_recall(answer, keywords):
    folded = _fold(answer or "")
    hits = [k for k in keywords if _fold(k) in folded]
    return len(hits) / len(keywords), hits


def positions(chunks, wanted):
    """chunks listesinde wanted profillerinin 1 tabanlı sıraları."""
    return [i for i, c in enumerate(chunks, 1) if profile_path(c.get("page_info")) in wanted]


def name_case(target_in, confuser_in):
    if target_in and confuser_in:
        return "ikisi de geliyor"
    if target_in:
        return "yalnız hedef"
    if confuser_in:
        return "hedef yok, karıştırıcı var"
    return "ikisi de yok"


def measure(qid, gt, llm):
    q = gt["soru"]
    targets, confusers = set(gt["hedef_profiller"]), set(gt["karistirici_profiller"])
    row = {"id": qid, "soru": q, "dusen": " ".join(gt["dusen_kelimeler"]),
           "bm25_tokenlari": " ".join(_tokenize(q)), "hedef_sayisi": len(targets)}

    # 1. Tüm corpus hibrit sıralaması (reranker yok)
    ranking = retrieve(q, top_k=100000, use_reranker=False, rerank_top_n=100000)
    t_pos = positions(ranking, targets)
    best = ranking[t_pos[0] - 1] if t_pos else None
    row["hibrit_sira"] = t_pos[0] if t_pos else None
    row["hedef_dense_sira"] = best["score_debug"]["dense_rank"] if best else None
    row["hedef_bm25_sira"] = best["score_debug"]["bm25_rank"] if best else None
    if confusers:
        c_pos = positions(ranking, confusers)
        row["karistirici_hibrit_sira"] = c_pos[0] if c_pos else None
        row["karistirici_onde"] = sum(1 for p in c_pos if t_pos and p < t_pos[0])

    # 2-3. Aday ve final aşamaları
    final_for_answer = None
    for k in CANDIDATE_KS:
        cands = ranking[:k]
        row[f"aday{k}_hedef"] = len(positions(cands, targets))
        final = retrieve(q, top_k=k, use_reranker=True)
        f_pos = positions(final, targets)
        row[f"final{k}_hedef"] = len(f_pos)
        row[f"final{k}_ilk_hedef_sira"] = f_pos[0] if f_pos else None
        row[f"final{k}_profiller"] = " ".join(profile_path(c.get("page_info")) or c.get("page_info", "")
                                               for c in final)
        if confusers:
            row[f"aday{k}_karistirici"] = len(positions(cands, confusers))
            row[f"final{k}_karistirici"] = len(positions(final, confusers))
            row[f"aday{k}_durum"] = name_case(row[f"aday{k}_hedef"], row[f"aday{k}_karistirici"])
            row[f"final{k}_durum"] = name_case(row[f"final{k}_hedef"], row[f"final{k}_karistirici"])
        if k == TOP_K:
            final_for_answer = final

    # 4. Cevap (arayüz akışı)
    if llm is not None:
        ctx = build_context(final_for_answer, q)
        extra = next((c.get("synthesizer_instruction") for c in final_for_answer
                      if c.get("synthesizer_instruction")), None)
        answer = ask(llm, ctx, q, extra_instruction=extra)
        recall, hits = keyword_recall(answer, gt["anahtar_kelimeler"])
        row.update(cevap=answer, anahtar_recall=round(recall, 3), tam_dogru=recall == 1.0,
                   bulunan_anahtarlar=" | ".join(hits))
    return row


def main(argv=None):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default=str(_root_dir / "experiments" / "stopword_baseline"))
    parser.add_argument("--no-llm", action="store_true", help="Cevap üretme; yalnız retrieval aşamaları")
    args = parser.parse_args(argv)

    gt = json.loads(GT_FILE.read_text(encoding="utf-8"))
    llm = None if args.no_llm else load_model()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    rows, t0 = [], time.perf_counter()
    for qid, entry in gt.items():
        row = measure(qid, entry, llm)
        rows.append(row)
        print(f"#{qid} hibrit={row['hibrit_sira']} (dense {row['hedef_dense_sira']}, "
              f"bm25 {row['hedef_bm25_sira']}) | final{TOP_K} hedef={row[f'final{TOP_K}_hedef']}"
              + (f" | {row.get(f'final{TOP_K}_durum')}" if entry["karistirici_profiller"] else "")
              + (f" | recall={row['anahtar_recall']}" if "anahtar_recall" in row else ""), flush=True)

    fields = list(dict.fromkeys(k for r in rows for k in r))
    with open(out_dir / "sonuclar.csv", "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"\n{len(rows)} soru, {time.perf_counter() - t0:.0f} sn -> {out_dir / 'sonuclar.csv'}")


if __name__ == "__main__":
    main()
