import csv,glob,sys
csv.field_size_limit(10**9)
R=r"c:\Users\merve\Desktop\rag_project"; C=sys.argv[1]
rd=lambda p:list(csv.DictReader(open(p,encoding="utf-8-sig")))
want={7,21,43,54,59,67,115,215}
S=["test_1","test_2","test_3","test_4","test_5","test_negative"]
for s in S:
    old={int(r["id"]):r for r in rd(R+rf"\experiments\madde39_tam_kosu\head_{s}\birlesik.csv")}
    new={int(r["id"]):r for r in rd(rf"{C}\run1\{s}.csv")}
    for i in sorted(want&set(new)):
        print(f"--- #{i} ({s}) soru:",new[i].get("soru",new[i].get("question",""))[:200].replace("\n"," "))
        print("  ESKI:",old[i]["cevap"][:300].replace("\n"," "))
        print("  YENI:",new[i]["cevap"][:300].replace("\n"," "))
