"""147 soruluk kampanya sürücüsü (qwen3-8b-pilot + Ollama, üretim run_tests.py ile).
Kullanım: python drv.py RUN_ADI [--kritik]   -> camp/RUN_ADI/{set}.csv
Her set ayrı süreç; HATA alan sorular BİR kez tekrarlanır ve birleştirilir (madde 39 kosu.py ile aynı kural)."""
import csv,os,subprocess,sys,time,json,re
from pathlib import Path
ROOT=Path(r"c:\Users\merve\Desktop\rag_project"); CAMP=Path(__file__).parent
run=sys.argv[1]; kritik="--kritik" in sys.argv
OUT=CAMP/run; OUT.mkdir(exist_ok=True)
SETS=["test_1","test_2","test_3","test_4","test_5","test_negative"]
KRIT={62,69,73,83,85,74,71,61,88,76,86,84,43,45,231,28,30,41,47,87}
ENV={**os.environ,"RAG_LLM_RUNTIME":"ollama","RAG_EMBED_NUM_GPU":"99","RAG_DENSE_FORCE_TOP_N":"0","PYTHONIOENCODING":"utf-8"}
csv.field_size_limit(10**9)
OLLAMA_APP=r"C:\Users\merve\AppData\Local\Programs\Ollama\ollama app.exe"
def log(m):
    with open(OUT/"progress.txt","a",encoding="utf-8") as f: f.write(f"{time.strftime('%H:%M:%S')} {m}\n")
def sh(a,t=60):
    return subprocess.run(a,capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=t).stdout.strip()
def saglikli():
    try: return sh(["curl","-s","-o",os.devnull,"-w","%{http_code}","-m","20","-X","POST","http://127.0.0.1:11434/api/embed","-H","Content-Type: application/json","-d",json.dumps({"model":"bge-m3","input":"saglik"})],30)=="200"
    except Exception: return False
def restart():
    sh(["powershell","-NoProfile","-Command","Get-Process ollama* -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue"],30); time.sleep(3)
    subprocess.Popen(["powershell","-NoProfile","-Command",f"Start-Process '{OLLAMA_APP}'"]); time.sleep(8)
def unload():
    for m in ("qwen3-8b-pilot","bge-m3"):
        sh(["curl","-s","http://127.0.0.1:11434/api/generate","-d",json.dumps({"model":m,"keep_alive":0})],30); time.sleep(3)
def rows(p): return list(csv.DictReader(open(p,encoding="utf-8-sig")))
def write(p,fn,rs):
    with open(p,"w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fn); w.writeheader(); w.writerows(rs)
def run_tests(src,dst):
    with open(OUT/"log.txt","a",encoding="utf-8") as f:
        f.write(f"\n=== {src} -> {dst}\n"); f.flush()
        return subprocess.run([sys.executable,"-u","evaluation/run_tests.py",str(src),str(dst)],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,env=ENV).returncode
log(f"basla run={run} kritik={kritik}")
for s in SETS:
    final=OUT/f"{s}.csv"
    if final.exists(): log(f"{s} var, atlandi"); continue
    src=ROOT/"evaluation/datasets"/f"{s}.csv"; allr=rows(src); fn=list(allr[0])
    if kritik:
        allr=[r for r in allr if int(r["id"]) in KRIT]
        if not allr: continue
        src=OUT/f"girdi_{s}.csv"; write(src,fn,allr)
    if not saglikli():
        restart()
        if not saglikli(): log("OLLAMA YANITSIZ - DURDU"); sys.exit(1)
    unload(); t0=time.time(); bas=time.time()
    kod=run_tests(src,OUT/f"ham_{s}.csv")
    got=rows(OUT/f"ham_{s}.csv") if (OUT/f"ham_{s}.csv").exists() else []
    hata=[r["id"] for r in got if r["cevap"].startswith("HATA")]
    log(f"{s}: kod={kod} satir={len(got)}/{len(allr)} hata={hata} sure={round(time.time()-t0)}s")
    if hata or len(got)<len(allr):
        eksik={r["id"] for r in allr}-{r["id"] for r in got}|set(hata)
        alt=OUT/f"hata_{s}_girdi.csv"; write(alt,fn,[r for r in allr if r["id"] in eksik])
        if not saglikli(): restart()
        unload(); run_tests(alt,OUT/f"hata_{s}_tekrar.csv")
        tk={r["id"]:r for r in rows(OUT/f"hata_{s}_tekrar.csv")} if (OUT/f"hata_{s}_tekrar.csv").exists() else {}
        by={r["id"]:r for r in got if not r["cevap"].startswith("HATA")}
        by.update({k:v for k,v in tk.items()})
        got=[by[r["id"]] for r in allr if r["id"] in by]
        log(f"{s}: tekrar sonrasi satir={len(got)}/{len(allr)} kalan_hata={[r['id'] for r in got if r['cevap'].startswith('HATA')]}")
    fns=list(got[0]) if got else fn
    write(final,fns,got)
unload(); log("BITTI")
