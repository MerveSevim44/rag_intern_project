"""
Madde 18 Adım 3 — #107 deseninin kapsamı (LLM'SİZ, yalnız log/CSV okur).

Desen: soru bir kavramdan (X) bahsediyor ama doğrulayıcının gördüğü kod+sonuçta X hiç
geçmiyor. Kaynak: madde 30 tam koşusunun log.txt'leri (taze, 6 set) — sandbox'a
(route=code_interpreter) giden her sorunun SON başarılı kodu ve çıktısı.
Soru terimleri (>=5 harf) kod+sonuç metninde 5 harflik ön ekle aranır (ASCII katlama);
145 sorudaki belge sıklığı >=%10 olan terimler genel sayılıp atılır. Çıktı gözle
incelenmek üzere: otomatik hüküm yok.

Kullanım (kökten): python -u experiments/madde18_dogrulayici/adim3_kapsam.py
"""
import csv, re, sys, collections
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT / "evaluation"), str(ROOT)]
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from benchmark_eval import classify_answer
from gt_utils import load_ground_truth

SETS = ["test_1", "test_2", "test_3", "test_4", "test_5", "test_negative"]
KOK = ROOT / "experiments/madde30_sikilastirma"
FOLD = str.maketrans("çğıöşüÇĞİÖŞÜâîû", "cgiosucgiosuaiu")


def katla(s):
    return s.replace("İ", "i").replace("I", "ı").lower().translate(FOLD)


def terimler(s):
    return {w for w in re.findall(r"[a-z]{5,}", katla(s))}


gt = load_ground_truth()
kayit = []
for s in SETS:
    log = (KOK / s / "log.txt").read_text(encoding="utf-8", errors="replace")
    rows = {r["id"]: r for r in csv.DictReader(open(KOK / s / "sonuclari.csv", encoding="utf-8-sig"))}
    tekrar = KOK / s / "hata_tekrar.csv"
    if tekrar.exists():
        rows.update({r["id"]: r for r in csv.DictReader(open(tekrar, encoding="utf-8-sig"))})
    bloklar = {}
    for m in re.finditer(r"\[(\d+)\] Soruluyor: .*?(?=\n\[\d+\] Soruluyor|\nTamamlandı|\Z)", log, re.S):
        bloklar[m.group(1)] = m.group(0)  # sonraki (hata_tekrar) blok öncekini ezer
    for qid, b in bloklar.items():
        if "route=code_interpreter" not in b or "Basarili! Cikti:" not in b:
            continue
        son = b.rfind("Basarili! Cikti:")
        k = b.rfind("[CodeInterpreter] Uretilen Kod:", 0, son)
        kod = b[k:son].split("\n", 1)[1]
        cikti = re.split(r"\n\s+(?:→|\[llm_client\]|!)", b[son:])[0].replace("Basarili! Cikti:", "")
        r = rows.get(qid)
        if not r:
            continue
        sinif = classify_answer({**r, "set": s}, gt)
        kayit.append(dict(set=s, id=qid, soru=r["soru"], kod=kod, cikti=cikti, sinif=sinif,
                          neg=r["dokumanda_var_mi"].strip().lower().startswith("h"),
                          dogrulama=r.get("dogrulama_durumu", "")))

tum = []
for s in SETS:
    tum += [r["soru"] for r in csv.DictReader(open(ROOT / "evaluation/datasets" / f"{s}.csv", encoding="utf-8-sig"))]
df = collections.Counter(w for q in tum for w in terimler(q))
genel = {w for w, c in df.items() if c / len(tum) >= 0.10}

print(f"sandbox'a giden ve başarılı sonuç dönen soru: {len(kayit)} / {len(tum)}")
print("sınıf dağılımı:", dict(collections.Counter(r['sinif'] for r in kayit)))
print("negatif (dokumanda_var_mi=Hayır) olanlar:", [(r['set'], r['id'], r['sinif']) for r in kayit if r['neg']])
print()
print("== Eksik terim taraması (soruda var, kod+sonuçta ön ek yok) ==")
for r in kayit:
    metin = katla(r["kod"] + " " + r["cikti"])
    eksik = sorted(w for w in terimler(r["soru"]) - genel if w[:5] not in metin)
    r["eksik"] = eksik
    if eksik:
        print(f"{r['set']}#{r['id']} [{r['sinif']}{' NEG' if r['neg'] else ''}] eksik={eksik}\n    S: {r['soru'][:130]}")
import json
(HERE / "adim3_kapsam.json").write_text(json.dumps(kayit, ensure_ascii=False, indent=1), encoding="utf-8")
