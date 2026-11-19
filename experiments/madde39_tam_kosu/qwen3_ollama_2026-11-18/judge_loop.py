"""Kota-dayanıklı judge yürütücü: eksik satır kaldıkça judge_w3'ü tekrar çağırır, günlük limitte bekler.
Skorlar her satırda kaydedilir; süreç ölse bile aynı komut kaldığı yerden sürer."""
import csv,subprocess,sys,time,os
CAMP=os.path.dirname(os.path.abspath(__file__))
OLD=r"C:\Users\merve\AppData\Local\Temp\claude\c301482ba979e838\c9686f86-abe4-447c-9c79-f1a2a338c452\scratchpad\judge_w3.py"
JOBS=[("judge1","k1",["test_1","test_2","test_3","test_4","test_5","test_negative"]),("judge2","k2",["test_1","test_2","test_3","test_negative"])]
csv.field_size_limit(10**9)
def eksik():
    t=0
    for d,p,sets in JOBS:
        for s in sets:
            n=len(list(csv.DictReader(open(f"{CAMP}\{d}\sonuc_{p}_{s}.csv",encoding="utf-8-sig"))))
            j=f"{CAMP}\{d}\judge_{p}_{s}.csv"; k=0
            if os.path.exists(j): k=sum(1 for r in csv.DictReader(open(j,encoding="utf-8-sig")) if r["faithfulness_score"].strip())
            t+=n-k
    return t
def log(m): open(CAMP+r"\judge_loop.log","a",encoding="utf-8").write(f"{time.strftime('%d.%m %H:%M:%S')} {m}\n")
while True:
    e=eksik(); log(f"eksik satir: {e}")
    if e==0: log("TAMAM"); break
    for d,p,sets in JOBS:
        names=[f"{p}_{s}" for s in sets]
        subprocess.run([sys.executable,"-u",OLD,f"{CAMP}\{d}"]+names,cwd=r"c:\Users\merve\Desktop\rag_project\evaluation",
                       stdout=open(f"{CAMP}\{d}.loop.log","a",encoding="utf-8"),stderr=subprocess.STDOUT,env={**os.environ,"PYTHONIOENCODING":"utf-8"})
    log(f"tur sonu, eksik: {eksik()}")
    if eksik()==0: continue
    time.sleep(1500)
