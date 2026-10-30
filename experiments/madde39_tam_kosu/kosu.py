"""
Madde 39 — güncel sistemle tam koşu, tek set (her set ayrı süreç ve klasör; sıralı
koşulur, paralel değil: Foundry + Ollama + reranker 8 GB VRAM'i zaten dolduruyor).

Koşudan önce durur: src/, evaluation/ veya ingest.py'de commit'lenmemiş değişiklik
varsa, rag.db özeti beklenenden farklıysa.
Ortam sabit: RAG_EMBED_NUM_GPU=99, RAG_DENSE_FORCE_TOP_N=0 (src'deki tüm ayarlanabilir
değişkenler; bayrak varsayılanı madde 32'de kapalı). Süreçler arası embedding kaymasını
yakalamak için sabit bir metnin embedding özeti her set öncesi ve sonrası kaydedilir.

sonuclari.csv yoksa set koşulur (başarı çıkış koduna göre değil satır sayısına göre:
madde 35). Sonra HATA alan sorular BİR kez yeniden koşulur (hata_tekrar.csv); asıl
sonuç dosyası değişmez, altyapı hatası gerçek ölçümden ayrı kalır.

Kullanım (kökten): python -u experiments/madde39_tam_kosu/kosu.py SET
Çıktı: SET/sonuclari.csv, SET/log.txt, SET/ortam.json, varsa SET/hata_tekrar.csv
"""
import csv
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ORTAM = {"RAG_EMBED_NUM_GPU": "99", "RAG_DENSE_FORCE_TOP_N": "0", "PYTHONIOENCODING": "utf-8"}
DB_OZET = "757e97059abb"
NOBET_METIN = "Bağlamdan bağımsız dilbilgisi için türetme ağacı nedir?"
NOBET = ("import sys,json,hashlib;sys.path.insert(0,'src');from embedder import get_embedding;"
         f"print(hashlib.sha256(json.dumps(get_embedding({NOBET_METIN!r})).encode()).hexdigest()[:16])")
NOBET_BEKLENEN = "d16e556d14284ac8"  # tam GPU (25/25) vektörü; kayma.py ile doğrulandı
MIN_BOS_RAM_GB = 7.5  # Foundry ~5 + Ollama 1.1 + python/reranker ve pay
HATA_ON = "HATA"


def komut(args, **kw):
    return subprocess.run(args, cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", **kw).stdout.strip()


def nobet(env):
    return komut([sys.executable, "-c", NOBET], env=env, timeout=300).split("\n")[-1]


def uc_nokta():
    m = re.search(r"http://127\.0\.0\.1:\d+", komut(["foundry", "service", "status"], timeout=120))
    sys.exit("Foundry servisi ayakta değil") if not m else None
    return m.group(0)


def calistir(sorular, cikti, log, env):
    with open(log, "a", encoding="utf-8") as f:
        f.write(f"\n=== {sorular} -> {cikti}\n")
        f.flush()
        return subprocess.run([sys.executable, "-u", "evaluation/run_tests.py", str(sorular), str(cikti)],
                              cwd=ROOT, stdout=f, stderr=subprocess.STDOUT, env=env).returncode


def satirlar(yol):
    with open(yol, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def bos_ram_gb():
    cikti = komut(["powershell", "-NoProfile", "-Command",
                   "(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory"], timeout=60)
    return int(cikti) / 1024 ** 2


def ollama_cpu_yuklemeleri(bas):
    """server.log'da `bas` (epoch) sonrası tam GPU olmayan yüklemeler. RAM yetmeyince Ollama
    num_gpu=99'a rağmen sessizce CPU'ya düşüyor (0/25), vektör değişiyor (madde 29 kayması)."""
    log = Path.home() / "AppData/Local/Ollama/server.log"
    t, bulunan = None, []
    for s in log.read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.search(r"time=(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)", s)
        if m:
            t = time.mktime(time.strptime(m.group(1), "%Y-%m-%dT%H:%M:%S"))
        k = re.search(r"offloaded (\d+)/(\d+) layers", s)
        if k and t and t >= bas and k.group(1) != k.group(2):
            bulunan.append(f"{time.strftime('%H:%M:%S', time.localtime(t))} {k.group(1)}/{k.group(2)}")
    return bulunan


def main():
    set_ = sys.argv[1]
    csv.field_size_limit(10**9)
    if bos_ram_gb() < MIN_BOS_RAM_GB:
        sys.exit(f"Boş RAM {bos_ram_gb():.1f} GB < {MIN_BOS_RAM_GB} GB; LLM yüklenince embedding "
                 "yüklenemiyor ya da CPU'ya düşüyor. Koşu başlatılmadı.")
    kirli = komut(["git", "status", "--porcelain", "--", "src", "evaluation", "ingest.py"])
    if kirli:
        sys.exit(f"Commit'lenmemiş kod değişikliği var:\n{kirli}")
    db = hashlib.sha256((ROOT / "rag.db").read_bytes()).hexdigest()[:12]
    if db != DB_OZET:
        sys.exit(f"rag.db özeti {db}, beklenen {DB_OZET}")

    env = {**os.environ, **ORTAM, "FOUNDRY_LOCAL_ENDPOINT": uc_nokta()}
    out = HERE / set_
    out.mkdir(exist_ok=True)
    kaynak = ROOT / "evaluation/datasets" / f"{set_}.csv"
    n = len(satirlar(kaynak))
    sonuc, log = out / "sonuclari.csv", out / "log.txt"
    bilgi = {"set": set_, "commit": komut(["git", "rev-parse", "--short", "HEAD"]), "rag_db": db,
             "ortam": ORTAM, "endpoint": env["FOUNDRY_LOCAL_ENDPOINT"], "nobet_once": nobet(env)}

    bas = time.time()
    if not sonuc.exists():
        bilgi["cikis_kodu"] = calistir(kaynak, sonuc, log, env)
    bilgi["sure_sn"] = round(time.time() - bas)
    kayit = satirlar(sonuc) if sonuc.exists() else []
    bilgi["satir"], bilgi["beklenen_satir"] = len(kayit), n

    hatali = {r["id"] for r in kayit if r["cevap"].startswith(HATA_ON)}
    bilgi["hata_ilk"] = sorted(hatali, key=int)
    if hatali:
        alt = out / "sorular_hata.csv"
        kaynak_satir = [r for r in satirlar(kaynak) if r["id"] in hatali]
        with open(alt, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(kaynak_satir[0]))
            w.writeheader()
            w.writerows(kaynak_satir)
        calistir(alt, out / "hata_tekrar.csv", log, env)
        tekrar = satirlar(out / "hata_tekrar.csv") if (out / "hata_tekrar.csv").exists() else []
        bilgi["hata_tekrar_kalan"] = sorted((r["id"] for r in tekrar if r["cevap"].startswith(HATA_ON)), key=int)

    bilgi["nobet_sonra"] = nobet(env)
    bilgi["ollama_cpu_yukleme"] = ollama_cpu_yuklemeleri(bas)
    bilgi["temiz"] = (not bilgi["ollama_cpu_yukleme"] and bilgi["nobet_once"] == bilgi["nobet_sonra"]
                      and bilgi["nobet_once"] == NOBET_BEKLENEN)
    (out / "ortam.json").write_text(json.dumps(bilgi, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(bilgi, ensure_ascii=False))
    if len(kayit) != n:
        sys.exit(f"Eksik sonuç: {len(kayit)}/{n}")


if __name__ == "__main__":
    main()
