"""
A1 duzen testinin (experiments/madde_grupA_duzen/duzen_testi.py) otomatik-cikarma kolu. src/ ve evaluation/ DEGISMEZ.
Ayni model, uretimle ayni ask(), her kosul x soru N tekrar. Kosullar:
  orijinal  : head_test_1/birlesik.csv context'i BIREBIR (kontrol)
  otomatik  : cevabi tasiyan sayfa bloklari (#19 s20, #20 s21) sutun_bol.sutunlu_metin(page, 0.10) ciktisiyla degistirilir
              (diger bloklar birebir) -- ELLE TEMIZLEME YOK
Kullanim (kokten): FOUNDRY_LOCAL_ENDPOINT=... python experiments/madde_grupA_sutun/otomatik_test.py KOSUL N CIKTI.jsonl
"""
import csv, json, os, re, sys, time
from pathlib import Path

os.environ.setdefault("RAG_EMBED_NUM_GPU", "99")
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT / "evaluation"), str(ROOT / "src"), str(ROOT), str(HERE)]
csv.field_size_limit(10**9)
KOSUL, N, OUT = sys.argv[1], int(sys.argv[2]), Path(sys.argv[3])
HEDEF = {"19": "20", "20": "21"}  # soru id -> degistirilecek sayfa


def otomatik(id_, ctx):
    import pdfplumber
    from sutun_bol import sutunlu_metin
    sayfa = HEDEF[id_]
    with pdfplumber.open(ROOT / "data/8-Baglamdan_bagimsiz_dilbilgisi.pdf") as pdf:
        yeni, eski, bilgi = sutunlu_metin(pdf.pages[int(sayfa) - 1], 0.10)
    assert bilgi and not bilgi.get("reddedildi") and yeni != eski, "bolme uygulanmadi"
    out, degisti = [], False
    for p in re.split(r"\n\n(?=\[\d+\] Kaynak:)", ctx.strip()):
        bas = p.split("\n", 1)[0]
        if bas.endswith(f"sayfa {sayfa}") and "8-Baglamdan" in bas:
            p, degisti = bas + "\n" + yeni, True
        out.append(p)
    assert degisti, "sayfa blogu bulunamadi"
    return "\n\n".join(out)


def main():
    import run_tests as T
    from llm_client import ask
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    rows = {r["id"]: r for r in csv.DictReader(open(ROOT / "experiments/madde39_tam_kosu/head_test_1/birlesik.csv", encoding="utf-8-sig"))}
    llm = T.load_model()
    for id_ in ("19", "20"):
        r = rows[id_]
        ctx = r["context"] if KOSUL == "orijinal" else otomatik(id_, r["context"])
        for i in range(N):
            t = time.time()
            y = ask(llm, ctx, r["soru"])
            k = {"kosul": KOSUL, "id": id_, "tekrar": i + 1, "cevap": y, "sure": round(time.time() - t, 1), "ctx_krk": len(ctx)}
            with open(OUT, "a", encoding="utf-8") as f:
                f.write(json.dumps(k, ensure_ascii=False) + "\n")
            print(json.dumps(k, ensure_ascii=False)[:420], flush=True)


main()
