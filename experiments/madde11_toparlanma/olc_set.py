"""Madde 11 C önce/sonra: test_5 + test_2; her call_llm_text çağrısının prompt/yanıt boyutu ve sınıf.
#43/#53 en sonda (OOM sonraki soruları bozmasın). src/ DEĞİŞMEZ. Kullanım: olc_set.py ETIKET"""
import csv, json, os, sys, time
from pathlib import Path

os.environ.setdefault("RAG_EMBED_NUM_GPU", "99")
os.environ.setdefault("RAG_DENSE_FORCE_TOP_N", "0")
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "evaluation"), str(ROOT / "src"), str(ROOT)]
SCR = Path(__file__).resolve().parent
ETIKET = sys.argv[1]
csv.field_size_limit(10**9)


def main():
    import run_tests as T
    from benchmark_eval import classify_answer
    from gt_utils import load_ground_truth
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    gt = load_ground_truth()
    llm = T.load_model()
    CI = sys.modules.get("code_interpreter") or __import__("code_interpreter")
    gercek = CI.call_llm_text
    cagri = []

    def sarmal(l, p):
        k = {"prompt_krk": len(p)}
        cagri.append(k)
        try:
            y = gercek(l, p)
            k["yanit_krk"] = len(y)
            return y
        except Exception as e:
            k["istisna"] = f"{type(e).__name__}"
            raise

    CI.call_llm_text = sarmal
    isler = []
    for set_ in ("test_5", "test_2"):
        rows = list(csv.DictReader(open(ROOT / f"evaluation/datasets/{set_}.csv", encoding="utf-8-sig")))
        son = [r for r in rows if set_ == "test_2" and r["id"] in ("43", "53")]
        isler += [(set_, r) for r in rows if r not in son] if set_ == "test_5" else \
                 [(set_, r) for r in rows if r not in son]
        if set_ == "test_2":
            isler += [(set_, r) for r in son]
    out = SCR / f"olc_{ETIKET}.jsonl"
    out.write_text("", encoding="utf-8")
    for set_, row in isler:
        cagri.clear()
        t0 = time.time()
        try:
            r = T.run_single_test(llm, row["soru"])
            cevap, sinif = r["cevap"], classify_answer({**row, "set": set_, "cevap": r["cevap"]}, gt)
        except Exception as e:
            cevap, sinif = f"HATA: {type(e).__name__}: {str(e)[:120]}", "HATA"
        k = {"set": set_, "id": row["id"], "sinif": sinif, "cevap": cevap[:300], "cagrilar": list(cagri),
             "sure_sn": round(time.time() - t0, 1)}
        with open(out, "a", encoding="utf-8") as f:
            f.write(json.dumps(k, ensure_ascii=False) + "\n")
        print(set_, row["id"], sinif, [c["prompt_krk"] for c in cagri], flush=True)


main()
