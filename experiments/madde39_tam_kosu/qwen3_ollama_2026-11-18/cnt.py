import csv,sys,re
csv.field_size_limit(10**9)
R=r"c:\Users\merve\Desktop\rag_project"; C=sys.argv[1]
rd=lambda p:list(csv.DictReader(open(p,encoding="utf-8-sig")))
S=["test_1","test_2","test_3","test_4","test_5","test_negative"]
pat={"HERHANGI bilgi yoktur":r"HERHANGİ bir bilgi","prompt sizintisi (a) VARSA":r"\(a\) VARSA|Bağlamda soruyla ilgili bilgi var mı","'bulunamadi' ret":r"dokümanlarda bulunamadı"}
for tag,base in (("ESKI",lambda s:R+rf"\experiments\madde39_tam_kosu\head_{s}\birlesik.csv"),("YENI run1",lambda s:rf"{C}\run1\{s}.csv"),("YENI run2(20)",lambda s:rf"{C}\run2\{s}.csv")):
    cnt={k:[] for k in pat}; n=0
    for s in S:
        try: rows=rd(base(s))
        except Exception: continue
        for r in rows:
            n+=1
            for k,p in pat.items():
                if re.search(p,r["cevap"]): cnt[k].append(int(r["id"]))
    print(tag,n,{k:(len(v),sorted(v)[:25]) for k,v in cnt.items()})
