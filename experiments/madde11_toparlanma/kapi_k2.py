"""Kademe 2 kapı deneyi. mod A: #53'ü çöktür (tavan geçici kaldırılır) ve sağlık probunu ölç.
mod B: kademe 2 (unload+load, projenin kendi uçları) dene, prob ile doğrula. src/ DEĞİŞMEZ.
Prob: 1 token'lık /v1/chat/completions (langchain yeniden denemesi yok), 15 sn zaman aşımı."""
import csv, json, os, sys, time, urllib.request, urllib.error
from pathlib import Path

os.environ.setdefault("RAG_EMBED_NUM_GPU", "99")
os.environ.setdefault("RAG_DENSE_FORCE_TOP_N", "0")
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "evaluation"), str(ROOT / "src"), str(ROOT)]
MOD, OUT = sys.argv[1], Path(sys.argv[2])
EP = os.environ["FOUNDRY_LOCAL_ENDPOINT"].rstrip("/")


def log(**k):
    k["t"] = time.strftime("%H:%M:%S")
    with open(OUT, "a", encoding="utf-8") as f:
        f.write(json.dumps(k, ensure_ascii=False) + "\n")
    print(json.dumps(k, ensure_ascii=False), flush=True)


def http(url, data=None, timeout=15):
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"} if data else {})
    t = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()[:300].decode("utf-8", "replace"), round(time.time() - t, 2)
    except urllib.error.HTTPError as e:
        return e.code, e.read()[:300].decode("utf-8", "replace"), round(time.time() - t, 2)
    except Exception as e:
        return None, f"{type(e).__name__}: {str(e)[:120]}", round(time.time() - t, 2)


def prob(model_id):
    body = json.dumps({"model": model_id, "messages": [{"role": "user", "content": "tamam"}],
                       "max_tokens": 1}).encode()
    return http(f"{EP}/v1/chat/completions", body, 15)


def main():
    import llm_client as L
    model_id, _ = L._resolve_model_id(EP, L.DEFAULT_MODEL_ID)
    if MOD == "A":
        import run_tests as T
        log(adim="A0_prob_once", prob=prob(model_id), status=http(f"{EP}/openai/status")[0])
        llm = T.load_model()
        CI = sys.modules.get("code_interpreter") or __import__("code_interpreter")
        CI.MAX_CORRECTION_PROMPT_CHARS = 10**7  # yalnız ölçüm: kırpma kapalı -> #53 eski çöküşü
        sizes = []
        gercek = CI.call_llm_text

        def sarmal(l, p):
            sizes.append(len(p))
            return gercek(l, p)

        CI.call_llm_text = sarmal
        soru = next(r for r in csv.DictReader(open(ROOT / "evaluation/datasets/test_2.csv", encoding="utf-8-sig"))
                    if r["id"] == "53")["soru"]
        try:
            T.run_single_test(llm, soru)
            sonuc = "CÖKMEDI"
        except Exception as e:
            sonuc = f"{type(e).__name__}: {str(e)[:100]}"
        log(adim="A1_cokus", prompt_krk=sizes, sonuc=sonuc)
        log(adim="A2_prob_sonra", prob=prob(model_id), status=http(f"{EP}/openai/status")[0])
    else:
        def buyuk():
            # gerçek kod-üretim prompt'u (~9.3 krk) boyutunda; 1 token üretir
            metin = "Aşağıdaki metni oku, sonra yalnız 'tamam' yaz.\n" + ("Profil kaydı alanı değeri örnek. " * 280)[:9300]
            body = json.dumps({"model": model_id, "messages": [{"role": "user", "content": metin}],
                               "max_tokens": 1}).encode()
            s = http(f"{EP}/v1/chat/completions", body, 40)
            return [s[0], s[1][:90], s[2]]

        log(adim="B0_basta", prob_kisa=prob(model_id)[::2], prob_9k=buyuk(), status=http(f"{EP}/openai/status")[0])
        t = time.time()
        L.unload_model(model_id=model_id)
        log(adim="B1_unload", sure=round(time.time() - t, 1), prob_kisa=prob(model_id)[::2])
        t = time.time()
        L.load_model()
        log(adim="B2_load", sure=round(time.time() - t, 1))
        log(adim="B3_sonra", prob_kisa=prob(model_id)[::2], prob_9k=buyuk())


main()
