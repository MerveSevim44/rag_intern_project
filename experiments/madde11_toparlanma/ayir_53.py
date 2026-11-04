"""#53 yanlış sayı: C kırpmasıyla ilişkili mi? Salt okunur; src/ DEĞİŞMEZ (yalnız modül özniteliği çalışma zamanında sarılır).
Varyantlar: stub_ham = kod üretimi atlanır, sandbox çıktısı (doğru) sentezleyiciye doğrudan gider (C devre dışı);
            C_10500 = olduğu gibi; cap_11500 = tavan geçici yükseltilir (yalnız ölçüm).
Kayıt: result_to_natural_language girdisi/çıktısı, ask() bağlamı/çıktısı, prompt boyutları."""
import csv, json, os, re, sys, time
from pathlib import Path

os.environ.setdefault("RAG_EMBED_NUM_GPU", "99")
os.environ.setdefault("RAG_DENSE_FORCE_TOP_N", "0")
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "evaluation"), str(ROOT / "src"), str(ROOT)]
OUT = Path(sys.argv[1])

HAM_KOD = ("result = {'AutoApproveRequests': {'Emre Korkmaz': 1.0, 'Sinem Arslan': 0.0, 'Umut Aslan': 1.0}, "
           "'CancellationNoticeHours': {'Emre Korkmaz': 24.0, 'Sinem Arslan': 12.0, 'Umut Aslan': 24.0}, "
           "'MinimumNoticeHours': {'Emre Korkmaz': 6.0, 'Sinem Arslan': 12.0, 'Umut Aslan': 4.0}}")
GERCEK = {"Sinem Arslan": (12, 12), "Umut Aslan": (4, 24), "Emre Korkmaz": (6, 24)}  # (min, iptal)
VARYANTLAR = [("stub_ham", 10500, True), ("stub_ham", 10500, True),
              ("C_10500", 10500, False), ("cap_11500", 11500, False)]


def puanla(metin):
    """Cevaptaki ad başına (min, iptal) sayılarını gerçekle karşılaştırır."""
    sonuc = {}
    for ad, (mn, ip) in GERCEK.items():
        m = re.search(re.escape(ad) + r"[^.]*?minimumNoticeHours:\s*(\d+)[^.]*?cancellationNoticeHours:\s*(\d+)", metin or "")
        sonuc[ad] = None if not m else {"min": int(m.group(1)), "iptal": int(m.group(2)),
                                       "dogru": (int(m.group(1)), int(m.group(2))) == (mn, ip)}
    return sonuc


def main():
    import run_tests as T
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    soru = next(r for r in csv.DictReader(open(ROOT / "evaluation/datasets/test_2.csv", encoding="utf-8-sig"))
                if r["id"] == "53")["soru"]
    llm = T.load_model()
    CI = sys.modules.get("code_interpreter") or __import__("code_interpreter")
    gercek_cagri, gercek_nl, gercek_ask = CI.call_llm_text, CI.result_to_natural_language, T.ask
    ORJ_CAP = CI.MAX_CORRECTION_PROMPT_CHARS
    rec = {}

    def nl(q, result, l):
        out = gercek_nl(q, result, l)
        rec["nl_girdi"], rec["nl_cikti"] = repr(result)[:1500], out
        return out

    def ask_sarmal(l, context, q, *a, **k):
        out = gercek_ask(l, context, q, *a, **k)
        rec["ask_baglam"], rec["ask_cikti"], rec["ask_ekstra"] = context, out, k.get("extra_instruction")
        return out

    CI.result_to_natural_language = nl
    T.ask = ask_sarmal
    for etiket, cap, stub in VARYANTLAR:
        rec.clear()
        cagri = []

        def sarmal(l, p, _stub=stub):
            k = {"prompt_krk": len(p)}
            cagri.append(k)
            kod_uretimi = "SADECE mantik denetimi" not in p and "Kullanıcı Sorusı" not in p
            try:
                if _stub and kod_uretimi:
                    k["stub"] = True
                    return HAM_KOD
                y = gercek_cagri(l, p)
                k["yanit_krk"] = len(y)
                return y
            except Exception as e:
                k["istisna"] = type(e).__name__
                raise

        CI.call_llm_text = sarmal
        CI.MAX_CORRECTION_PROMPT_CHARS = cap
        try:
            r = T.run_single_test(llm, soru)
            cevap = r["cevap"]
        except Exception as e:
            cevap = f"ISTISNA {type(e).__name__}: {str(e)[:150]}"
        finally:
            CI.call_llm_text = gercek_cagri
            CI.MAX_CORRECTION_PROMPT_CHARS = ORJ_CAP
        kayit = {"varyant": etiket, "cap": cap, "cagrilar": cagri, "cevap": cevap,
                 "puan_nl": puanla(rec.get("nl_cikti")), "puan_ask": puanla(rec.get("ask_cikti") or cevap), **rec}
        with open(OUT, "a", encoding="utf-8") as f:
            f.write(json.dumps(kayit, ensure_ascii=False) + "\n")
        print(etiket, cap, [c["prompt_krk"] for c in cagri],
              "nl:", {k: (v or {}).get("dogru") for k, v in kayit["puan_nl"].items()},
              "ask:", {k: (v or {}).get("dogru") for k, v in kayit["puan_ask"].items()}, flush=True)


main()
