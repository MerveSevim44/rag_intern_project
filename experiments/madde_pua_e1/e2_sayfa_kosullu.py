"""
E2: E1'in aynisi (SAKLANAN context, ayni ask(), tek degisken) ama PUA->Unicode eslemesi YALNIZ Fourier PDF'inin (H8)
sayfa 3/5/9 chunk'larina uygulanir; diger chunk'lar oldugu gibi kalir. Amac: "sayfa-kosullu esleme #62/#69'u duzeltip
digerlerini bozmaz mi?" sorusunu olcmek. src/ ve evaluation/ DEGISMEZ.
Kullanim (kokten): FOUNDRY_LOCAL_ENDPOINT=... python experiments/madde_pua_e1/e2_sayfa_kosullu.py cevap|judge
"""
import csv, json, os, re, sys, time
from pathlib import Path

os.environ.setdefault("RAG_EMBED_NUM_GPU", "99")
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT / "evaluation"), str(ROOT / "src"), str(ROOT), str(ROOT / "experiments" / "madde34_ingilizce_ret")]
csv.field_size_limit(10**9)
IZIN = {"3", "5", "9"}
BIRLESIK = ROOT / "experiments/madde39_tam_kosu/head_test_3/birlesik.csv"
OUT = HERE / "sonuc_e2.jsonl"
GIRDI = HERE / "e2_judge_girdi.csv"

src = (HERE / "e1.py").read_text(encoding="utf-8")
ns = {}
exec("import sys, collections\n" + src[src.index("EK = {"):src.index("def main")], ns)
esle = ns["esle"]


def kosullu_esle(ctx):
    parcalar = re.split(r"(\n?\[\d+\] Kaynak: )", ctx)
    out, haritalanan = [parcalar[0]], []
    for k in range(1, len(parcalar), 2):
        baslik, govde = parcalar[k], parcalar[k + 1]
        ilk = govde.split("\n", 1)[0]
        m = re.search(r"sayfa (\d+)", ilk)
        if "H8_FourierTransform" in ilk and m and m.group(1) in IZIN:
            govde = esle(govde)[0]
            haritalanan.append(m.group(1))
        out += [baslik, govde]
    return "".join(out), haritalanan


def hedefler(rows):
    ids = []
    for i, r in rows.items():
        if kosullu_esle(r["context"])[1]:
            ids.append(i)
    return sorted(ids, key=int)


def cevap():
    import run_tests as T
    from llm_client import ask
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ids24 = {json.loads(l)["id"] for l in open(HERE / "sonuc.jsonl", encoding="utf-8")}
    rows = {r["id"]: r for r in csv.DictReader(open(BIRLESIK, encoding="utf-8-sig")) if r["id"] in ids24}
    llm = T.load_model()
    for i in hedefler(rows):
        r = rows[i]
        ctx, hrt = kosullu_esle(r["context"])
        t = time.time()
        y = ask(llm, ctx, r["soru"])
        k = {"id": i, "cevap": y, "uretim_cevabi": r["cevap"], "haritalanan_sayfalar": hrt, "sure": round(time.time() - t, 1)}
        with open(OUT, "a", encoding="utf-8") as f:
            f.write(json.dumps(k, ensure_ascii=False) + "\n")
        print(f"#{i} map={hrt} ({k['sure']} sn) -> {y[:200]}", flush=True)


def judge():
    import llm_as_judge as J
    sonuc = {json.loads(l)["id"]: json.loads(l) for l in open(OUT, encoding="utf-8")}
    e1 = {}
    for l in open(HERE / "sonuc.jsonl", encoding="utf-8"):
        d = json.loads(l)
        if d["kosul"] == "orijinal":
            e1[d["id"]] = d["cevap"]
    ids = [i for i, d in sonuc.items() if d["cevap"].strip() != e1[i].strip()]
    if len(sys.argv) > 2:
        ids = [i for i in ids if i in sys.argv[2].split(",")]
    print("judge'a girecek (cevabi orijinal kosuya gore degisen):", ids, "| degismeyen:", [i for i in sonuc if i not in ids])
    with open(BIRLESIK, encoding="utf-8-sig") as f:
        rd = csv.DictReader(f)
        alanlar = rd.fieldnames
        rows = {r["id"]: r for r in rd}
    with open(GIRDI, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=alanlar)
        w.writeheader()
        for i in ids:
            r = dict(rows[i])
            r["cevap"] = sonuc[i]["cevap"]
            r["context"] = kosullu_esle(r["context"])[0]
            w.writerow(r)
    J.REBUILD_CONTEXT = False
    J.run_judge_evaluation(sonuc_csv=str(GIRDI), output_csv=str(HERE / (sys.argv[3] if len(sys.argv) > 3 else "judge_e2.csv")), ground_truth_path=None,
                           judge_model=J.JUDGE_MODEL, only_ids=ids)


{"cevap": cevap, "judge": judge}[sys.argv[1]]()
