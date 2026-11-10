"""
E1: yalniz U+F0xx (Symbol-font PUA) -> Unicode eslemesi, SAKLANAN context uzerinde. Tek degisken.
Duzen, retrieval, chunk secimi, elle temizleme YOK; src/ ve evaluation/ DEGISMEZ. Ayni model, uretimle ayni ask().
Esleme tablosu: experiments/madde34_ingilizce_ret/varyant.py::SYMBOL (madde 34) + bu PDF'lerde gorulen ve o tabloda
olmayan kodlar icin STANDART Adobe Symbol karsiliklari (asagida EK). Tabloda olmayan kod noktasi oldugu gibi kalir
ve raporlanir (kapsam disi).
Kullanim (kokten): FOUNDRY_LOCAL_ENDPOINT=... python experiments/madde_pua_e1/e1.py KOSUL KIMLIKLER CIKTI.jsonl
  KOSUL: orijinal | esle ; KIMLIKLER: virgullu id listesi (test_3)
"""
import csv, json, os, sys, time, collections
from pathlib import Path

os.environ.setdefault("RAG_EMBED_NUM_GPU", "99")
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "evaluation"), str(ROOT / "src"), str(ROOT), str(ROOT / "experiments" / "madde34_ingilizce_ret")]
csv.field_size_limit(10**9)
KOSUL, IDS, OUT = sys.argv[1], [i for i in sys.argv[2].split(",") if i], Path(sys.argv[3])

EK = {0x20: " ", 0x5B: "[", 0x5D: "]", 0x7B: "{", 0x7D: "}", 0xAB: "↔", 0xDB: "⇔", 0xB7: "•", 0x3C: "<", 0x3E: ">", 0x2F: "/", 0xFB: "",
      **{0x30 + d: str(d) for d in range(10)}}


def esle(metin):
    from varyant import SYMBOL
    tablo = {**SYMBOL, **EK}
    kapsam_disi = collections.Counter()
    out = []
    for ch in metin:
        if 0xF000 <= ord(ch) <= 0xF0FF:
            k = ord(ch) - 0xF000
            if k in tablo:
                out.append(tablo[k])
            else:
                kapsam_disi[hex(ord(ch))] += 1
                out.append(ch)
        else:
            out.append(ch)
    return "".join(out), kapsam_disi


def main():
    import run_tests as T
    from llm_client import ask
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    rows = {r["id"]: r for r in csv.DictReader(open(ROOT / "experiments/madde39_tam_kosu/head_test_3/birlesik.csv", encoding="utf-8-sig"))}
    llm = T.load_model()
    for id_ in IDS:
        r = rows[id_]
        ctx, kd = (r["context"], {}) if KOSUL == "orijinal" else esle(r["context"])
        # context'i app/run_tests ile ayni sekilde extra_instruction'siz veriyoruz (test_3 sorulari semantic_rag)
        t = time.time()
        y = ask(llm, ctx, r["soru"])
        k = {"kosul": KOSUL, "id": id_, "cevap": y, "uretim_cevabi": r["cevap"], "sure": round(time.time() - t, 1),
             "ctx_krk": len(ctx), "kapsam_disi_pua": dict(kd)}
        with open(OUT, "a", encoding="utf-8") as f:
            f.write(json.dumps(k, ensure_ascii=False) + "\n")
        print(f"[{KOSUL}] #{id_} ({k['sure']} sn) kapsam_disi={dict(kd)}\n   -> {y[:350]}", flush=True)


main()
