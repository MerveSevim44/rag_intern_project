"""
Madde 33 Adım 2, Faz A — .txt birleştirme politikası nihai bağlamı kaç soruda değiştiriyor?

madde 32 Adım 2 havuz.py ile aynı disiplin: 147 soru (test_1..5 + test_negative)
× MIN = 0 / 500 / 800 / 1200 (politika.py); her biri için retrieve() nihai
(reranker sonrası) RERANK_TOP_N chunk'ı (kaynak, page_info) imzasıyla
karşılaştırılır. LLM yok. Sağlama: MIN=0 listesi madde 32 Adım 2'nin n0 kaydıyla
(havuz.jsonl) aynı mı?

#91 için ek: nihai bağlamda "Gümüş Yaprak" ile "Alis"i AYNI chunk'ta taşıyan
bir parça var mı (madde 33 Adım 1: belirleyici koşul bu).

Kullanım (kökten): python -u experiments/madde33_stemmer_chunk/havuz2.py
Çıktı: havuz2.jsonl (kaldığı yerden devam eder), sonuc_havuz2.txt
"""
import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(HERE), str(ROOT / "src"), str(ROOT)]

SETS = ["test_1", "test_2", "test_3", "test_4", "test_5", "test_negative"]
MINS = [0, 500, 800, 1200]


def _imza(chunks):
    return [[Path(c["source"]).name, c.get("page_info")] for c in chunks]


def main():
    import retrieval as R
    from politika import kur

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

    m32 = {}
    with open(ROOT / "experiments/madde32_adim2_dense_force_include/havuz.jsonl", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            m32[(r["set"], r["id"])] = [list(x) for x in r["n0"]]

    sorular = []
    for s in SETS:
        with open(ROOT / "evaluation/datasets" / f"{s}.csv", encoding="utf-8-sig") as f:
            sorular += [(s, r["id"], r["soru"]) for r in csv.DictReader(f)]

    jsonl = HERE / "havuz2.jsonl"
    kayit = {}
    if jsonl.exists():
        with open(jsonl, encoding="utf-8") as f:
            for line in f:
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    break
                kayit[(r["set"], r["id"], r["min"])] = r

    # Politika dışta: cache her MIN için bir kez kurulur
    with open(jsonl, "w", encoding="utf-8") as out:
        for r in kayit.values():
            out.write(json.dumps(r, ensure_ascii=False) + "\n")
        for minc in MINS:
            if all((s, i, minc) in kayit for s, i, _ in sorular):
                continue
            kur(R, minc)
            for s, i, soru in sorular:
                if (s, i, minc) in kayit:
                    continue
                res = R.retrieve(soru)
                r = {"set": s, "id": i, "min": minc, "imza": _imza(res), "ids": [c.get("id") for c in res],
                     "rota": (res[0].get("route") if res else "") or "",
                     "alis_ve_ad_ayni_chunkta": any("Gümüş Yaprak" in c["content"] and "Alis" in c["content"]
                                                    for c in res)}
                kayit[(s, i, minc)] = r
                out.write(json.dumps(r, ensure_ascii=False) + "\n")
                out.flush()
                print(f"MIN={minc} {s}#{i}: {r['rota']}")
    kur(R, 0)

    L = [f"Toplam soru: {len(sorular)}"]
    ayni = [k for k in sorular if kayit[(k[0], k[1], 0)]["imza"] == m32.get((k[0], k[1]))]
    L.append(f"MIN=0 == madde 32 Adım 2 n0 kaydı (politika kapalıyken davranış aynı): {len(ayni)}/{len(sorular)}")
    for s, i, _ in sorular:
        if kayit[(s, i, 0)]["imza"] != m32.get((s, i)):
            L.append(f"   MIN0≠m32: {s}#{i}")
    L.append("")
    L.append("test_4#91 'Gümüş Yaprak' + 'Alis' aynı chunk'ta nihai bağlamda: "
             + ", ".join(f"MIN={m}:{'EVET' if kayit[('test_4', '91', m)]['alis_ve_ad_ayni_chunkta'] else 'hayır'}"
                         for m in MINS))
    L.append("")
    for minc in MINS[1:]:
        deg = [(s, i) for s, i, _ in sorular if kayit[(s, i, minc)]["imza"] != kayit[(s, i, 0)]["imza"]]
        neg = [k for k in deg if k[0] == "test_negative"]
        txt = [k for k in deg if any(x[0].endswith(".txt") for x in kayit[(k[0], k[1], minc)]["imza"]
                                     + kayit[(k[0], k[1], 0)]["imza"])]
        L.append(f"MIN={minc}: nihai bağlamı değişen {len(deg)}/{len(sorular)} "
                 f"(pozitif setler {len(deg) - len(neg)}, negatif {len(neg)}; .txt chunk'ı içeren {len(txt)})")
        for s, i in deg:
            a, b = kayit[(s, i, 0)]["imza"], kayit[(s, i, minc)]["imza"]
            L.append(f"   {s}#{i}: -{[x for x in a if x not in b]} +{[x for x in b if x not in a]}")
    text = "\n".join(L) + "\n"
    (HERE / "sonuc_havuz2.txt").write_text(text, encoding="utf-8")
    print("\n" + text)


if __name__ == "__main__":
    main()
