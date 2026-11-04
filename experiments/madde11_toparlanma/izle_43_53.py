"""Adım 1 doğrulaması: #43/#53 güncel kodla; her call_llm_text çağrısının prompt/yanıt boyutu. src/ DEĞİŞMEZ."""
import csv, json, os, sys, time
from pathlib import Path

os.environ.setdefault("RAG_EMBED_NUM_GPU", "99")
os.environ.setdefault("RAG_DENSE_FORCE_TOP_N", "0")
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "evaluation"), str(ROOT / "src"), str(ROOT)]
OUT = Path(sys.argv[1])
ids = sys.argv[2:]


def main():
    import run_tests as T
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    rows = {r["id"]: r for r in csv.DictReader(open(ROOT / "evaluation/datasets/test_2.csv", encoding="utf-8-sig"))}
    llm = T.load_model()
    CI = sys.modules.get("code_interpreter") or __import__("code_interpreter")
    gercek = CI.call_llm_text
    cagri = []

    def sarmal(l, p):
        k = {"prompt_krk": len(p), "t": round(time.time(), 1)}
        cagri.append(k)
        try:
            y = gercek(l, p)
            k["yanit_krk"] = len(y)
            return y
        except Exception as e:
            k["istisna"] = f"{type(e).__name__}: {str(e)[:160]}"
            raise

    CI.call_llm_text = sarmal
    with open(OUT, "a", encoding="utf-8") as f:
        for i in ids:
            cagri.clear()
            try:
                r = T.run_single_test(llm, rows[i]["soru"])
                cevap = r["cevap"][:1500]
            except Exception as e:
                cevap = f"ISTISNA {type(e).__name__}: {str(e)[:160]}"
            kayit = {"id": i, "cagrilar": list(cagri), "cevap": cevap}
            f.write(json.dumps(kayit, ensure_ascii=False) + "\n"); f.flush()
            print(json.dumps(kayit, ensure_ascii=False), flush=True)


main()
