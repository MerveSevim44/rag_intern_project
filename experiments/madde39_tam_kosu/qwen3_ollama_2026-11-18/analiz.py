import csv,glob,os,sys,statistics as st
from collections import Counter,defaultdict
R=r"c:\Users\merve\Desktop\rag_project"; CAMP=os.path.dirname(os.path.abspath(__file__))
sys.path[:0]=[R+r"\evaluation",R+r"\src",R]; csv.field_size_limit(10**9)
from benchmark_eval import classify_answer
from gt_utils import load_ground_truth
gt=load_ground_truth()
K=["faithfulness_score","answer_relevance_score","task_performance_score","alignment_score"]; KN=["F","AR","TP","AL"]
SETS=["test_1","test_2","test_3","test_4","test_5","test_negative"]
KRIT=[62,69,73,83,85,74,71,61,88,76,86,84,43,45,231,28,30,41,47,87]
rd=lambda p:list(csv.DictReader(open(p,encoding="utf-8-sig")))
def sc(r):
    try: return [float(r[k]) for k in K]
    except: return None
# ESKİ
old_cls={}; old_j={}
for s in SETS:
    d=R+rf"\experiments\madde39_tam_kosu\head_{s}"
    for r in rd(d+r"\birlesik.csv"):
        old_cls[int(r["id"])]="HATA" if r["cevap"].startswith("HATA") else classify_answer({**r,"set":s},gt)
    for f in sorted(glob.glob(d+r"\judge_*.csv"),key=os.path.getmtime):
        for r in rd(f):
            if sc(r): old_j[int(r["id"])]=sc(r)
# YENİ run1
def load_run(run,judgedir,prefix,sets):
    cls={}; jud={}; ans={}
    for s in sets:
        p=os.path.join(CAMP,run,f"{s}.csv")
        if not os.path.exists(p): continue
        for r in rd(p):
            i=int(r["id"]); ans[i]=r["cevap"]
            cls[i]="HATA" if r["cevap"].startswith("HATA") else classify_answer({**r,"set":s},gt)
        jp=os.path.join(CAMP,judgedir,f"judge_{prefix}_{s}.csv")
        if os.path.exists(jp):
            for r in rd(jp):
                if sc(r): jud[int(r["id"])]=sc(r)
    return cls,jud,ans
c1,j1,a1=load_run("run1","judge1","k1",SETS)
c2,j2,a2=load_run("run2","judge2","k2",SETS)
mean=lambda xs:round(st.mean(xs),2)
def table(title,cls,jud):
    print(f"\n### {title}"); print("| Sınıf | n | judge'lı | F | AR | TP | AL |"); print("|---|---|---|---|---|---|---|")
    for c in ["TP","TN","FN","FP","HATA"]:
        ids=[i for i in cls if cls[i]==c]; js=[i for i in ids if i in jud]
        if ids: print(f"| {c} | {len(ids)} | {len(js)} | "+" | ".join(str(mean([jud[i][j] for i in js])) if js else "-" for j in range(4))+" |")
    js=list(jud); print(f"| TÜMÜ | {len(cls)} | {len(js)} | "+" | ".join(str(mean([jud[i][j] for i in js])) for j in range(4))+" |")
print("# ANALİZ"); print("judge1 dolu:",len(j1),"/",len(c1),"| judge2 dolu:",len(j2),"/",len(c2))
table("ESKİ (qwen2.5 Foundry, head_*)",old_cls,old_j)
# yeni birleşik: kritik sorular için run1+run2 ortalaması
j_new={i:(([ (a+b)/2 for a,b in zip(j1[i],j2[i])]) if (i in j2 and i in j1) else j1[i]) for i in j1}
table("YENİ run1 (qwen3 Ollama, tek koşu, 147)",c1,j1)
table("YENİ (kritik 20'de run1+run2 ORTALAMASI, diğerleri run1)",c1,j_new)
# sınıf geçişleri
print("\n### Sınıf geçişi eski→yeni (run1)"); tr=Counter((old_cls[i],c1[i]) for i in c1); print(dict(sorted(tr.items())))
print("sınıf değişen sorular:",{i:(old_cls[i],c1[i]) for i in sorted(c1) if old_cls[i]!=c1[i]})
# soru bazında değişim
def dur(old,new):
    d=st.mean(new)-st.mean(old)
    return "düzeldi" if d>=0.5 else "kötüleşti" if d<=-0.5 else "aynı"
for ad,jn in (("run1 tek koşu",j1),("kritik=ortalama",j_new)):
    ids=[i for i in jn if i in old_j]
    cnt=Counter(dur(old_j[i],jn[i]) for i in ids)
    tpc=Counter("düzeldi" if jn[i][2]>old_j[i][2] else "kötüleşti" if jn[i][2]<old_j[i][2] else "aynı" for i in ids)
    fc=Counter("düzeldi" if jn[i][0]>old_j[i][0] else "kötüleşti" if jn[i][0]<old_j[i][0] else "aynı" for i in ids)
    print(f"\n### TOPLAM değişim ({ad}, n={len(ids)})\n- bileşik (4 skorun ort., eşik ±0,5): {dict(cnt)}\n- yalnız TP skoru (herhangi fark): {dict(tpc)}\n- yalnız F skoru (herhangi fark): {dict(fc)}")
    if ad=="run1 tek koşu":
        print("  kötüleşenler:",[(i,old_cls[i]+'→'+c1[i],[round(x,1) for x in old_j[i]],jn[i]) for i in ids if dur(old_j[i],jn[i])=="kötüleşti"])
        print("  düzelenler:",[i for i in ids if dur(old_j[i],jn[i])=="düzeldi"])
# kritik alt küme: run1 vs run2
print("\n### Kritik 20: run1 vs run2 (judge)")
ks=[i for i in KRIT if i in j1 and i in j2]; print("judge'lı çift:",len(ks))
print("| # | sınıf eski | run1 sınıf | run2 sınıf | eski F/AR/TP/AL | run1 | run2 | cevap aynı |"); print("|---|---|---|---|---|---|---|---|")
n=lambda s:" ".join(s.split())
for i in KRIT:
    if i in j1 and i in j2: print(f"| {i} | {old_cls[i]} | {c1[i]} | {c2[i]} | {[int(x) for x in old_j[i]]} | {[int(x) for x in j1[i]]} | {[int(x) for x in j2[i]]} | {n(a1[i])==n(a2[i])} |")
if ks:
    print("\nkritik 20 ortalama (F/AR/TP/AL): eski",[mean([old_j[i][j] for i in ks]) for j in range(4)],"run1",[mean([j1[i][j] for i in ks]) for j in range(4)],"run2",[mean([j2[i][j] for i in ks]) for j in range(4)])
    mavg=[mean([(j1[i][j]+j2[i][j])/2 for i in ks]) for j in range(4)]; print("run1+run2 ort:",mavg)
    ad=[mean([abs(j1[i][j]-j2[i][j]) for i in ks]) for j in range(4)]; print("run1-run2 mutlak fark ort. (soru başına):",ad)
    d12=[mean([j2[i][j]-j1[i][j] for i in ks]) for j in range(4)]; print("run2−run1 ortalama fark (işaretli):",d12)
    sh=[mean([(j1[i][j]+j2[i][j])/2-old_j[i][j] for i in ks]) for j in range(4)]; print("yeni(ort)−eski ortalama kayma:",sh)
    print("birebir aynı cevap:",sum(n(a1[i])==n(a2[i]) for i in ks),"/",len(ks))
    print("her iki koşuda da eskiden iyi/aynı yönde: kayma/gürültü oranı:",[round(abs(sh[j])/ad[j],2) if ad[j] else None for j in range(4)])
