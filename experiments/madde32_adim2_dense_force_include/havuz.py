"""
Madde 32 Adım 2, Faz A — dense güvenlik slotu nihai bağlamı kaç soruda değiştiriyor?

madde 20 kapsam_topk.py ile aynı disiplin: her soru için retrieve() çağrılır,
nihai (reranker sonrası) RERANK_TOP_N chunk'lık liste karşılaştırılır. Tek
değişken dense_force_n (0 = kapalı, 1, 3, 5); top_k, reranker, rerank_top_n
varsayılan. DB'ye yazmaz, LLM çağrısı yok.

Kapsam: tam benchmark (test_1..test_5, 115) + test_negative (32) = 147.
Ek sağlama: N=0 listesi madde 20'nin top_k=8 kaydıyla (kapsam_topk.jsonl,
değişiklik öncesi kod) karşılaştırılır — bayrak kapalıyken davranış aynı mı?

Kullanım (kökten): python -u experiments/madde32_adim2_dense_force_include/havuz.py
Çıktı: havuz.jsonl (soru başına), sonuc_havuz.txt (özet).
"""
import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]

SETS = ["test_1", "test_2", "test_3", "test_4", "test_5", "test_negative"]
NS = [0, 1, 3, 5]
HEDEF = {("test_3", "79"): 4183, ("test_3", "82"): 4185}  # madde 32 Adım 1


def _imza(chunks):
    return [(Path(c["source"]).name, c.get("page_info")) for c in chunks]


def main():
    from retrieval import retrieve

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

    m20 = {}
    with open(ROOT / "experiments/madde20_topk_benchmark/kapsam_topk.jsonl", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            m20[(r["set"], r["id"])] = [tuple(x) for x in r["top_k8"]]

    # Kesintiden sonra kaldığı yerden devam: tam yazılmış kayıtlar yeniden koşulmaz.
    kayitlar = []
    jsonl = HERE / "havuz.jsonl"
    if jsonl.exists():
        with open(jsonl, encoding="utf-8") as f:
            for line in f:
                try:
                    kayitlar.append(json.loads(line))
                except json.JSONDecodeError:
                    break
    bitmis = {(r["set"], r["id"]) for r in kayitlar}
    with open(jsonl, "w", encoding="utf-8") as out:
        for r in kayitlar:
            out.write(json.dumps(r, ensure_ascii=False) + "\n")
        for set_name in SETS:
            with open(ROOT / "evaluation/datasets" / f"{set_name}.csv", encoding="utf-8-sig") as f:
                rows = list(csv.DictReader(f))
            for row in rows:
                key = (set_name, row["id"])
                if key in bitmis:
                    continue
                rec = {"set": set_name, "id": row["id"], "soru": row["soru"]}
                for n in NS:
                    res = retrieve(row["soru"], dense_force_n=n)
                    rec[f"n{n}"] = _imza(res)
                    rec[f"n{n}_ids"] = [c.get("id") for c in res]
                rec["rota"] = (res[0].get("route") if res else "") or ""
                rec["m20_ayni"] = (key in m20 and [tuple(x) for x in rec["n0"]] == m20[key])
                for n in NS[1:]:
                    rec[f"n{n}_degisti"] = rec[f"n{n}"] != rec["n0"]
                if key in HEDEF:
                    rec["hedef"] = HEDEF[key]
                    for n in NS:
                        rec[f"n{n}_hedef_var"] = HEDEF[key] in rec[f"n{n}_ids"]
                out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                out.flush()
                kayitlar.append(rec)
                deg = " ".join(f"N{n}:{'D' if rec[f'n{n}_degisti'] else '='}" for n in NS[1:])
                print(f"{set_name}#{row['id']}: {rec['rota']:<16} {deg} m20={'=' if rec['m20_ayni'] else 'FARKLI'}")

    lines = [f"Toplam soru: {len(kayitlar)}",
             f"N=0 == madde 20 top_k=8 kaydı (bayrak kapalıyken davranış aynı): "
             f"{sum(r['m20_ayni'] for r in kayitlar)}/{len(kayitlar)}"]
    for k in kayitlar:
        if not k["m20_ayni"]:
            lines.append(f"   N0≠m20: {k['set']}#{k['id']}")
    lines.append("")
    for (s, i), cid in HEDEF.items():
        k = next(r for r in kayitlar if r["set"] == s and r["id"] == i)
        lines.append(f"{s}#{i} cevap chunk'ı {cid} nihai bağlamda: "
                     + ", ".join(f"N={n}:{'EVET' if k[f'n{n}_hedef_var'] else 'hayır'}" for n in NS))
    lines.append("")
    for n in NS[1:]:
        deg = [k for k in kayitlar if k[f"n{n}_degisti"]]
        neg = [k for k in deg if k["set"] == "test_negative"]
        lines.append(f"N={n}: nihai bağlamı değişen {len(deg)}/{len(kayitlar)} "
                     f"(pozitif setler {len(deg) - len(neg)}, negatif {len(neg)})")
        for k in deg:
            yeni = [x for x in k[f"n{n}"] if x not in k["n0"]]
            lines.append(f"   {k['set']}#{k['id']}: +{yeni}")
    text = "\n".join(lines) + "\n"
    (HERE / "sonuc_havuz.txt").write_text(text, encoding="utf-8")
    print("\n" + text)


if __name__ == "__main__":
    main()
