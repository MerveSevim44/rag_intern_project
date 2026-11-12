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

Kullanım (kökten): python -u experiments/madde39_tam_kosu/kosu.py SET [--klasor K] [--min-ram X]
Çıktı: SET/sonuclari.csv, SET/log.txt, SET/ortam.json, varsa SET/hata_tekrar.csv
"""
import argparse
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
DB_OZET = "2eb2d68359e5"  # 2026-11-12: A1 re-ingest (CFG s13/20/21); eski 757e97059abb = rag.db.bak_a1_2026-11-12
NOBET_METIN = "Bağlamdan bağımsız dilbilgisi için türetme ağacı nedir?"
NOBET = ("import sys,json,hashlib;sys.path.insert(0,'src');from embedder import get_embedding;"
         f"print(hashlib.sha256(json.dumps(get_embedding({NOBET_METIN!r})).encode()).hexdigest()[:16])")
NOBET_BEKLENEN = "d16e556d14284ac8"  # tam GPU (25/25) vektörü; kayma.py ile doğrulandı
# C kararı (2026-11-01, madde 39 ön-ölçüm A): GPU/CPU düşmesi engellenecek bir şey değil,
# yalnız işaretlenecek (`temiz`) — üretim de aynı riski taşıyor, fark küçük (147 soruda
# %95.2 aynı bağlam). Bu eşik artık onu önlemeye çalışmıyor, yalnız gerçek Ollama yükleme
# hatasını önlüyor (ilk denemede ~750 MB boşta "model requires more system memory (1.1
# GiB)" ile 3 ardışık HATA, run_tests.py'yi durdurdu). 2.0 GB'ta da iki kez TAM HANG görüldü
# (Ollama embed isteğine hiç yanıtsız kaldı — CPU'ya düşmekten farklı, daha ciddi). Servis
# `stop` ile tam durdurulunca boş RAM ~2 GB'tan ~7.9 GB'a çıktı; 4 GB daha güvenli bir pay.
MIN_BOS_RAM_GB = 4.0
LLM = "qwen2.5-7b-instruct-cuda-gpu:4"
HATA_ON = "HATA"


def komut(args, **kw):
    return subprocess.run(args, cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", **kw).stdout.strip()


def komut_sessiz(args, **kw):
    """Pipe YOK. `foundry service stop/start` arka planda kalan bir ajana stdout/stderr
    tutamacını miras bırakıyor gibi görünüyor (ölçüldü: capture_output=True ile
    subprocess.run'ın KENDİ timeout parametresi bile çalışmıyor, communicate() süresiz
    bloke oluyor — klasik Windows "grandchild pipe handle" kilitlenmesi). DEVNULL
    pipe'ı tamamen ortadan kaldırır; wait(timeout) güvenilir çalışır."""
    return subprocess.run(args, cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **kw)


def nobet(env):
    return komut([sys.executable, "-c", NOBET], env=env, timeout=300).split("\n")[-1]


def uc_nokta():
    """Servis durmuşsa başlatır (main() her set öncesi `service stop` çağırıyor)."""
    m = re.search(r"http://127\.0\.0\.1:\d+", komut(["foundry", "service", "status"], timeout=120))
    if not m:
        komut_sessiz(["foundry", "service", "start"], timeout=90)
        m = re.search(r"http://127\.0\.0\.1:\d+", komut(["foundry", "service", "status"], timeout=120))
    sys.exit("Foundry servisi başlatılamadı") if not m else None
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


OLLAMA_APP = r"C:\Users\merve\AppData\Local\Programs\Ollama\ollama app.exe"


def ollama_saglikli(zaman_asimi=10):
    """curl (alt süreç) ile; urllib + Windows soket birleşiminde timeout parametresine
    uymayan bir tam hang görüldü (kosu.py 7+ dk alt süreçsiz donuk kaldı) — curl -m
    kesin sonlanıyor ve subprocess.run'ın kendi timeout'u ikinci bir güvenlik ağı."""
    try:
        kod = komut(["curl", "-s", "-o", os.devnull, "-w", "%{http_code}",
                     "-m", str(zaman_asimi), "-X", "POST", "http://127.0.0.1:11434/api/embed",
                     "-H", "Content-Type: application/json",
                     "-d", json.dumps({"model": "bge-m3", "input": "saglik kontrolu"})],
                    timeout=zaman_asimi + 5)
        return kod == "200"
    except subprocess.TimeoutExpired:
        return False


def ollama_yeniden_baslat():
    """Ollama embed isteklerine hiç yanıt vermeden asılı kalabiliyor (CPU'ya düşmekten
    FARKLI — tam hang, iki kez görüldü). `ollama serve &` ile elle başlatmak kendi
    log dosyasına (server.log) yazmıyor (stdout/stderr ayrı); tray app ikisini de
    doğru yapıyor."""
    komut(["powershell", "-NoProfile", "-Command",
           "Get-Process ollama* -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue"],
          timeout=30)
    time.sleep(2)
    subprocess.Popen(["powershell", "-NoProfile", "-Command", f"Start-Process '{OLLAMA_APP}'"])
    time.sleep(5)


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
    ap = argparse.ArgumentParser()
    ap.add_argument("set")
    ap.add_argument("--klasor", help="pilot: sonuçlar bu klasöre (gerçek koşuya karışmaz)")
    ap.add_argument("--min-ram", type=float, default=MIN_BOS_RAM_GB, help="pilot: eşiği değiştir")
    args = ap.parse_args()
    set_ = args.set
    csv.field_size_limit(10**9)
    # "foundry model unload" servisin kendi taban belleğini (~4.9 GB) BIRAKMIYOR;
    # yalnız "foundry service stop" boşaltıyor (ölçüldü: unload sonrası boş RAM ~2 GB,
    # stop sonrası ~7.9 GB). Ollama'nın bu baskı altında yanıtsız kalıp hiç
    # dönmediği (CPU'ya düşmek değil, tam hang) iki kez görüldü; eşik ölçümünden
    # önce servisi tam yeniden başlat.
    komut_sessiz(["foundry", "service", "stop"], timeout=60)
    time.sleep(3)
    ram = bos_ram_gb()
    if ram < args.min_ram:
        sys.exit(f"Boş RAM {ram:.1f} GB < {args.min_ram} GB; Ollama embedding modelini "
                 "yükleyemeyebilir (gerçek yükleme hatası riski). Koşu başlatılmadı.")
    kirli = komut(["git", "status", "--porcelain", "--", "src", "evaluation", "ingest.py"])
    if kirli:
        sys.exit(f"Commit'lenmemiş kod değişikliği var:\n{kirli}")
    db = hashlib.sha256((ROOT / "rag.db").read_bytes()).hexdigest()[:12]
    if db != DB_OZET:
        sys.exit(f"rag.db özeti {db}, beklenen {DB_OZET}")

    if not ollama_saglikli():
        ollama_yeniden_baslat()
        if not ollama_saglikli():
            sys.exit("Ollama embed isteğine yanıt vermiyor (yeniden başlatma denendi).")

    env = {**os.environ, **ORTAM, "FOUNDRY_LOCAL_ENDPOINT": uc_nokta()}
    out = HERE / (args.klasor or set_)
    out.mkdir(exist_ok=True)
    kaynak = ROOT / "evaluation/datasets" / f"{set_}.csv"
    n = len(satirlar(kaynak))
    sonuc, log = out / "sonuclari.csv", out / "log.txt"
    bilgi = {"set": set_, "commit": komut(["git", "rev-parse", "--short", "HEAD"]), "rag_db": db,
             "bos_ram_gb_basta": round(ram, 2), "ortam": ORTAM, "endpoint": env["FOUNDRY_LOCAL_ENDPOINT"], "nobet_once": nobet(env)}

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
