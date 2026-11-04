"""
Madde 11 toparlanma — kapı deneyi 2: Foundry'nin KALICI bozulmasını yeniden üretme denemesi.

Soru: tek bir OOM sonrası (backlog katman 2) servis sonraki istekler için bozuk kalıyor mu ve
kademe 2 (unload_model + load_model) bunu düzeltiyor mu? Tek bir OOM taze serviste kalıcı bozulma
bırakmadı (kapi_k2.py); burada istek sayısı + art arda OOM birikimi denenir. src/ DEĞİŞMEZ.

Her mod AYRI süreçtir ve dışarıdan `timeout 90` ile koşulur (sert zaman aşımı; asılırsa kill).
  snap            durum görüntüsü + gerçekçi (9 KB) prob
  wear            ~60 sn boyunca normal 9 KB istekler (istek sayısı birikimi)
  cycle BOYUT     5 normal istek, ardından BOYUT karakterlik büyük istek (OOM denemesi),
                  hemen + 5 sn sonra 9 KB prob, durum görüntüsü
  tier2           kademe 2 (unload + load) ve sonrasında 9 KB prob
Prob "bozuk" sayılır: HTTP != 200, istisna ya da > 40 sn.
Kullanım (kökten): FOUNDRY_LOCAL_ENDPOINT=... timeout 90 python experiments/madde11_toparlanma/repro.py MOD [BOYUT] CIKTI.jsonl
"""
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import psutil

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]
EP = os.environ["FOUNDRY_LOCAL_ENDPOINT"].rstrip("/")
MOD = sys.argv[1]
BOYUT = int(sys.argv[2]) if MOD == "cycle" else None
OUT = Path(sys.argv[-1])
SORU53 = ("Aynı occupation'a (Yetenek Yönetimi Uzmanı) sahip Sinem Arslan, Umut Aslan ve Emre Korkmaz "
          "profillerinin appointmentSettings değerlerini (minimumNoticeHours, cancellationNoticeHours, "
          "autoApproveRequests) gruplu bir çubuk grafikle karşılaştırdığınızda ortaya çıkan varyasyon "
          "veri setinin gerçekçilik tasarımına nasıl katkı sağlamaktadır?")
KOD = ("sub = df[df['occupation'] == 'Yetenek Yönetimi Uzmanı']\n"
       "pivot = sub.pivot_table(index='professionalName', values=['appointmentSettings.minimumNoticeHours'], aggfunc='mean')\n"
       "percent_change = (pivot - pivot.mean()) / pivot.mean() * 100\nresult = percent_change.to_dict()\n")


def log(**k):
    k["t"] = time.strftime("%H:%M:%S")
    with open(OUT, "a", encoding="utf-8") as f:
        f.write(json.dumps(k, ensure_ascii=False) + "\n")
    print(json.dumps(k, ensure_ascii=False), flush=True)


def http(prompt, max_tokens, model_id, timeout=40):
    body = json.dumps({"model": model_id, "messages": [{"role": "user", "content": prompt}],
                       "max_tokens": max_tokens}).encode()
    req = urllib.request.Request(f"{EP}/v1/chat/completions", body, {"Content-Type": "application/json"})
    t = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            r.read()
            return [r.status, "", round(time.time() - t, 2)]
    except urllib.error.HTTPError as e:
        return [e.code, e.read()[:160].decode("utf-8", "replace"), round(time.time() - t, 2)]
    except Exception as e:
        return [None, f"{type(e).__name__}: {str(e)[:100]}", round(time.time() - t, 2)]


def bozuk(p):
    return p[0] != 200 or p[2] > 40


def durum():
    rss, n = 0, 0
    for pr in psutil.process_iter(["name", "memory_info"]):
        ad = (pr.info.get("name") or "").lower()
        if "inference.service.agent" in ad or "foundry" in ad:
            n += 1
            rss += pr.info["memory_info"].rss if pr.info.get("memory_info") else 0
    gpu = None
    try:
        gpu = subprocess.run(["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader"],
                             capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:
        pass
    return {"foundry_surec": n, "foundry_rss_gb": round(rss / 1024 ** 3, 2),
            "bos_ram_gb": round(psutil.virtual_memory().available / 1024 ** 3, 2), "gpu_mib": gpu}


def prompt_9k(df):
    import code_interpreter as CI
    return CI.build_code_gen_prompt(SORU53, df)


def main():
    import llm_client as L
    import data_engine
    df = data_engine.get_data_engine()._cache["728_profiles.json"][0]
    base = prompt_9k(df)
    model_id, _ = L._resolve_model_id(EP, L.DEFAULT_MODEL_ID)

    if MOD == "snap":
        log(adim="snap", prompt_krk=len(base), prob_9k=http(base, 1, model_id), **durum())
    elif MOD == "wear":
        n, bas, hata = 0, time.time(), 0
        while time.time() - bas < 60:
            p = http(base, 100, model_id)
            n += 1
            hata += bozuk(p)
        log(adim="wear", istek=n, hata=hata, prob_9k=http(base, 1, model_id), **durum())
    elif MOD == "cycle":
        normal = [http(base, 30, model_id) for _ in range(5)]
        ek = "\n=== ONCEKI BASARISIZ DENEMELER (tekrarlama!) ===\n"
        buyuk_prompt = base + ek + (KOD * 100)[:max(BOYUT - len(base) - len(ek), 0)]
        buyuk = http(buyuk_prompt, 50, model_id)
        p1 = http(base, 1, model_id)
        time.sleep(5)
        p2 = http(base, 1, model_id)
        log(adim=f"cycle_{BOYUT}", buyuk_krk=len(buyuk_prompt), normal_5=[x[0] for x in normal], buyuk=buyuk,
            prob_hemen=p1, prob_5sn=p2, BOZUK=bool(bozuk(p1) or bozuk(p2)), **durum())
    elif MOD == "tier2":
        log(adim="tier2_basta", prob_9k=http(base, 1, model_id), **durum())
        t = time.time()
        L.unload_model(model_id=model_id)
        log(adim="tier2_unload", sure=round(time.time() - t, 1), prob_9k=http(base, 1, model_id))
        t = time.time()
        L.load_model()
        log(adim="tier2_load", sure=round(time.time() - t, 1))
        p = http(base, 1, model_id)
        log(adim="tier2_sonra", prob_9k=p, DUZELDI=not bozuk(p), **durum())


main()
