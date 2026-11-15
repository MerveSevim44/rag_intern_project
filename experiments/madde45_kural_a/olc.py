"""
Kural A (UNIVERSAL_CODE_RULES) yeniden yazimi icin UC BOYUTLU olcum (backlog #45 / DUZELTME 2026-11-12).
code_interpreter rotasina giden 23 soru (test_2: 13, test_5: 3, test_negative: 7), gercek pipeline (run_tests.py).
  (a) success   : sandbox 3 denemede sonuc uretti mi  (log: "[CodeInterpreter] Basarili" vs "deneme basarisiz oldu")
  (b) validation: dogrulama_durumu (ok/objection/failed/not_run; sandbox sonucu yoksa bos)
  (c) icerik    : cevabin yolu (sandbox / yedek) ve eski kosuya (madde39 head_test_*) gore cevap degisti mi
Temiz kosu kurali: log'da Foundry/baglanti hatasi gorulurse o set GECERSIZ sayilir ve yeniden koşulur.
Kullanim (kokten): python -u experiments/madde45_kural_a/olc.py kos [ETIKET] | rapor [ETIKET]
"""
import csv, json, os, re, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
IDS = {"test_2": ["32", "35", "37", "39", "42", "43", "44", "45", "51", "52", "53", "57", "60"],
       "test_5": ["107", "108", "109"],
       "test_negative": ["211", "212", "218", "225", "228", "231", "232"]}
BASE = {s: ROOT / "experiments/madde39_tam_kosu" / f"head_{s}" for s in IDS}
KIRLI = re.compile(r"OpenAIConnectionError|LLM COKTU|Foundry servisi bulunamad|Connection error")
csv.field_size_limit(10**9)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def okuyucu(p):
    return {r["id"]: r for r in csv.DictReader(open(p, encoding="utf-8-sig"))}


def log_bloklari(log):
    """soru id -> (sandbox_basarili: bool|None, kirli: bool)"""
    out, cur, buf = {}, None, []
    def kapat():
        if cur is not None:
            t = "\n".join(buf)
            ci = "[CodeInterpreter]" in t
            out[cur] = ((ci and "Basarili" in t and "deneme basarisiz oldu" not in t) if ci else None, bool(KIRLI.search(t)))
    for l in Path(log).read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.match(r"\[(\d+)\] Soruluyor", l)
        if m:
            kapat(); cur, buf = m.group(1), []
        else:
            buf.append(l)
    kapat()
    return out


def kos(etiket):
    from importlib.util import spec_from_file_location, module_from_spec
    spec = spec_from_file_location("kosu", ROOT / "experiments/madde39_tam_kosu/kosu.py")
    kosu = module_from_spec(spec); spec.loader.exec_module(kosu)
    out = HERE / etiket
    out.mkdir(exist_ok=True)
    if not kosu.ollama_saglikli():
        kosu.ollama_yeniden_baslat()
        assert kosu.ollama_saglikli(), "Ollama yanit vermiyor"
    env = {**os.environ, **kosu.ORTAM, "FOUNDRY_LOCAL_ENDPOINT": kosu.uc_nokta()}
    for s, ids in IDS.items():
        girdi, sonuc, log = out / f"{s}_girdi.csv", out / f"{s}_sonuclari.csv", out / f"{s}_log.txt"
        for deneme in (1, 2):
            satirlar = [r for r in csv.DictReader(open(ROOT / f"evaluation/datasets/{s}.csv", encoding="utf-8-sig")) if r["id"] in ids]
            with open(girdi, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.DictWriter(f, fieldnames=list(satirlar[0])); w.writeheader(); w.writerows(satirlar)
            sonuc.unlink(missing_ok=True); log.unlink(missing_ok=True)
            with open(log, "w", encoding="utf-8") as f:
                subprocess.run([sys.executable, "-u", "evaluation/run_tests.py", str(girdi), str(sonuc)], cwd=ROOT, stdout=f, stderr=subprocess.STDOUT, env=env)
            kirli = [i for i, (_, k) in log_bloklari(log).items() if k]
            print(f"{s} deneme {deneme}: kirli sorular={kirli}", flush=True)
            if not kirli:
                break
            if "OpenAIConnectionError" in log.read_text(encoding="utf-8", errors="replace"):
                env["FOUNDRY_LOCAL_ENDPOINT"] = kosu.uc_nokta()
        (out / f"{s}_temiz.json").write_text(json.dumps({"kirli": kirli}), encoding="utf-8")


def rapor(etiket):
    out = HERE / etiket
    degisen, kotu, toplam = [], [], 0
    print("soru | (a) success eski->yeni | (b) dogrulama eski->yeni | (c) yol eski->yeni | cevap ayni")
    for s, ids in IDS.items():
        b_log, y_log = log_bloklari(BASE[s] / "log.txt"), log_bloklari(out / f"{s}_log.txt")
        b, y = okuyucu(BASE[s] / "sonuclari.csv"), okuyucu(out / f"{s}_sonuclari.csv")
        kirli = json.loads((out / f"{s}_temiz.json").read_text())["kirli"]
        for i in ids:
            toplam += 1
            sa, sb = b_log.get(i, (None,))[0], y_log.get(i, (None,))[0]
            va, vb = b[i].get("dogrulama_durumu", ""), y[i].get("dogrulama_durumu", "")
            ya = "sandbox" if "code_interpreter" in b[i]["bulunan_kaynaklar"] else "yedek"
            yb = "sandbox" if "code_interpreter" in y[i]["bulunan_kaynaklar"] else "yedek"
            ayni = b[i]["cevap"].strip() == y[i]["cevap"].strip()
            kt = []
            if sa and not sb: kt.append("success True->False")
            if va == "ok" and vb == "objection": kt.append("ok->objection")
            if i in kirli: kt.append("KIRLI KOSU")
            print(f"#{i} | {sa}->{sb} | {va or '-'}->{vb or '-'} | {ya}->{yb} | {'ayni' if ayni else 'DEGISTI'}{'  <-- ' + ', '.join(kt) if kt else ''}")
            if not ayni: degisen.append(i)
            if kt: kotu.append((i, kt))
    print(f"\ntoplam={toplam} cevabi degisen={len(degisen)} {degisen}\nREGRESYON: {kotu or 'YOK'}")


{"kos": kos, "rapor": rapor}[sys.argv[1]](sys.argv[2] if len(sys.argv) > 2 else "kural_a_v2")
