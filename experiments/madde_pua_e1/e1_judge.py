"""
E1 judge alt kumesi: E1'in 'esle' kosusundaki yeni cevaplari, ESLENMIS context'e gore puanlar (judge cevabi
'kayitli' context'e gore degerlendirir). evaluation/ DEGISMEZ; judge modeli calisma zamaninda callback ile sarilir
(token kullanimi Groq yanitindan, org kimligi maskeli). Kullanim (kokten): python experiments/madde_pua_e1/e1_judge.py
"""
import csv, json, re, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT / "evaluation"), str(ROOT / "src"), str(ROOT), str(ROOT / "experiments" / "madde34_ingilizce_ret")]
csv.field_size_limit(10**9)
IDS = "62,69,73,83,85,74,71,61,76,80,81,86,88".split(",")

src = (HERE / "e1.py").read_text(encoding="utf-8")
ns = {}
exec("import sys, collections\n" + src[src.index("EK = {"):src.index("def main")], ns)
esle = ns["esle"]

yeni = {}
for l in open(HERE / "sonuc.jsonl", encoding="utf-8"):
    d = json.loads(l)
    if d["kosul"] == "esle":
        yeni[d["id"]] = d["cevap"]

with open(ROOT / "experiments/madde39_tam_kosu/head_test_3/birlesik.csv", encoding="utf-8-sig") as f:
    rd = csv.DictReader(f)
    alanlar = rd.fieldnames
    rows = {r["id"]: r for r in rd}
girdi = HERE / "e1_judge_girdi.csv"
with open(girdi, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=alanlar)
    w.writeheader()
    for i in IDS:
        r = dict(rows[i])
        r["cevap"] = yeni[i]
        r["context"] = esle(r["context"])[0]
        w.writerow(r)


def main():
    import llm_as_judge as J
    from langchain_core.callbacks import BaseCallbackHandler
    log = HERE / "judge_kullanim_e1.jsonl"

    def kaydet(**k):
        with open(log, "a", encoding="utf-8") as f:
            f.write(json.dumps({"t": time.strftime("%H:%M:%S"), **k}, ensure_ascii=False) + "\n")

    class K(BaseCallbackHandler):
        def __init__(self):
            self.cagri = []

        def on_llm_error(self, error, **kw):
            kaydet(hata=type(error).__name__, mesaj=re.sub(r"org_[A-Za-z0-9]+", "org_<maskeli>", str(error))[:500])

        def on_llm_end(self, response, **kw):
            u = (response.llm_output or {}).get("token_usage") or {}
            if not u:
                for g in response.generations:
                    for x in g:
                        m = getattr(getattr(x, "message", None), "usage_metadata", None) or {}
                        u = {"prompt_tokens": m.get("input_tokens"), "completion_tokens": m.get("output_tokens"),
                             "total_tokens": m.get("total_tokens")}
            self.cagri.append(u)
            kaydet(**{a: u.get(a) for a in ("prompt_tokens", "completion_tokens", "total_tokens")})

    k = K()
    orj = J.load_judge_model
    J.load_judge_model = lambda *a, **kw: orj(*a, **kw).with_config(callbacks=[k])
    J.REBUILD_CONTEXT = False
    bas = time.time()
    J.run_judge_evaluation(sonuc_csv=str(girdi), output_csv=str(HERE / "judge_e1.csv"), ground_truth_path=None,
                           judge_model=J.JUDGE_MODEL, only_ids=IDS)
    t = lambda a: sum((c.get(a) or 0) for c in k.cagri)
    print("\nTOKEN ÖLÇÜMÜ:", json.dumps({"satir": len(IDS), "groq_cagri": len(k.cagri), "prompt": t("prompt_tokens"),
          "completion": t("completion_tokens"), "total": t("total_tokens"), "sure_sn": round(time.time() - bas)}))


main()
