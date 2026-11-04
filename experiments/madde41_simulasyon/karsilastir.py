"""Madde 41 ön şart ölçümü — D5 davranış değişikliği simülasyonunu iki gerçek tam koşuyla
(madde 39 taban, madde 30 koşusu) soru soru karşılaştırır.
Kullanım (kökten): python -u experiments/madde41_simulasyon/karsilastir.py"""
import csv, json, re, sys, collections
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT / "evaluation"), str(ROOT)]
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from benchmark_eval import classify_answer
from gt_utils import load_ground_truth

gt = load_ground_truth()
KAYNAKLAR = {"taban39": ROOT / "experiments/madde39_tam_kosu", "kosu30": ROOT / "experiments/madde30_sikilastirma", "SIM": HERE}


def oku(klasor, s):
    def d(p):
        with open(p, encoding="utf-8-sig") as f:
            return {r["id"]: r for r in csv.DictReader(f)}
    rows = d(klasor / s / "sonuclari.csv")
    t = klasor / s / "hata_tekrar.csv"
    if t.exists():
        rows.update(d(t))
    return rows


for s in ["test_negative", "test_2"]:
    veri = {k: oku(v, s) for k, v in KAYNAKLAR.items()}
    sinif = {k: {i: classify_answer({**r, "set": s}, gt) for i, r in rows.items()} for k, rows in veri.items()}
    print(f"\n===== {s} =====")
    for k in veri:
        print(f"  {k:8s}", dict(collections.Counter(sinif[k].values())))
    farklar = [(i, sinif["taban39"][i], sinif["kosu30"][i], sinif["SIM"][i]) for i in sinif["SIM"]
               if not (sinif["taban39"][i] == sinif["kosu30"][i] == sinif["SIM"][i])]
    print("  sınıfı değişen sorular (taban39, kosu30, SIM):", farklar or "YOK")
    # D5 olayları
    olaylar = []
    p = HERE / s / "d5_olaylar.jsonl"
    if p.exists():
        olaylar = [json.loads(l) for l in open(p, encoding="utf-8")]
    sorular = {i: r["soru"] for i, r in veri["SIM"].items()}
    ters = {v: k for k, v in sorular.items()}
    print("  D5 olayı (sandbox 3 denemede çözemedi):", len(olaylar), "olay,", len({o['soru'] for o in olaylar}), "soru")
    for q in dict.fromkeys(o["soru"] for o in olaylar):
        i = ters.get(q)
        if i is None:
            print("   ? soru eşleşmedi:", q[:70]); continue
        print(f"   #{i} sınıf taban39={sinif['taban39'][i]} kosu30={sinif['kosu30'][i]} SIM={sinif['SIM'][i]} | {q[:70]}")
        print(f"      taban39 cevap: {veri['taban39'][i]['cevap'][:110]!r}")
        print(f"      SIM     cevap: {veri['SIM'][i]['cevap'][:130]!r}")
    # D5 dışındaki sorularda SIM cevabı = taban cevabı mı (davranış değişikliği yalnız D5'i etkilemeli)
    d5_ids = {ters[o["soru"]] for o in olaylar if o["soru"] in ters}
    ayni = sum(1 for i in sorular if i not in d5_ids and veri["SIM"][i]["cevap"] == veri["kosu30"][i]["cevap"])
    toplam = sum(1 for i in sorular if i not in d5_ids)
    print(f"  D5 dışı {toplam} sorudan SIM cevabı madde 30 koşusuyla birebir aynı: {ayni}")
