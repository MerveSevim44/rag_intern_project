"""
Madde 34 Adım 2a — genelleme taraması (LLM yok): "yanıltıcı anahtar kelime
eşleşmesi" deseni #82 dışındaki FN'lerde de var mı?

Her pozitif soru (115) için bugünkü nihai bağlam canlı kurulur (retrieve; N=0
varsayılan ve N=1 dense slotu). Bağlamdaki her chunk için:
  farkli   kaynağı beklenen_kaynak'tan farklı mı
  ortak    soru ile chunk'ın ortak stem'li terimleri (retrieval._tokenize)
  bm25     BM25 ham skoru, rerank skoru, bağlam sırası
Aday (#82'deki 4333 profili): farkli + ortak >= 1 + bm25 > 0.
Aynı kaynak içindeki konu farkı (ör. tek JSON) bu ölçütle görünmez; #56 ayrıca
döküm olarak basılır.

FN evreni (bugünkü sistemle tam pozitif koşu yok): v8 tam koşu ∪ madde 32 n0 ∪
madde 33 prod duman (yalnız pozitifler) = aşağıdaki FN_ADAY. Taban oranı için
aynı ölçüt diğer pozitiflerde (v8'de TP) de sayılır.

Kullanım (kökten): python experiments/madde34_ingilizce_ret/genelleme.py
Çıktı: genelleme.jsonl, sonuc_genelleme.txt
"""
import csv
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(HERE), str(ROOT / "evaluation"), str(ROOT / "src"), str(ROOT)]

FN_ADAY = {("test_2", "50"), ("test_2", "56"), ("test_3", "79"), ("test_3", "82"),
           ("test_4", "91"), ("test_4", "100")}
DOKUM = {("test_2", "56"), ("test_3", "82")}


def main():
    import retrieval as R

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    csv.field_size_limit(10**9)
    v8 = {}
    with open(ROOT / "experiments/madde27_nan_embedding/yeniden_skor_v8/genel_scored.csv", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            v8[(r["test_seti"], r["id"])] = r["siniflandirma"]

    sorular = []
    for s in range(1, 5):
        with open(ROOT / "evaluation/datasets" / f"test_{s}.csv", encoding="utf-8-sig") as f:
            sorular += [{**r, "set": f"test_{s}"} for r in csv.DictReader(f) if r["dokumanda_var_mi"] == "Evet"]

    kayitlar, dokum = [], []
    for row in sorular:
        key = (row["set"], row["id"])
        q_tok = set(R._tokenize(row["soru"]))
        k = {"set": row["set"], "id": row["id"], "soru": row["soru"], "beklenen": row["beklenen_kaynak"],
             "v8": v8.get(key, "?"), "fn_aday": key in FN_ADAY}
        for n in (0, 1):
            chunks = R.retrieve(row["soru"], dense_force_n=n)
            satirlar = []
            for i, c in enumerate(chunks, 1):
                ortak = sorted(q_tok & set(R._tokenize(c["content"])))
                bm25 = (c.get("score_debug") or {}).get("bm25_raw", 0.0)
                farkli = Path(c["source"]).name != row["beklenen_kaynak"]
                satirlar.append({"sira": i, "id": c["id"], "kaynak": Path(c["source"]).name,
                                 "sayfa": c.get("page_info"), "farkli": farkli, "ortak": ortak,
                                 "bm25": round(float(bm25), 3),
                                 "rerank": round(c["rerank_score"], 5) if "rerank_score" in c else None,
                                 "aday": farkli and bool(ortak) and bm25 > 0})
                if key in DOKUM:
                    dokum.append(f"   N={n} [{i}] {c['id']} {Path(c['source']).name} {c.get('page_info')} "
                                 f"rerank={satirlar[-1]['rerank']} bm25={satirlar[-1]['bm25']} ortak={ortak}\n"
                                 + "\n".join("        | " + l for l in c["content"][:400].split("\n")))
            k[f"n{n}"] = satirlar
            k[f"n{n}_aday"] = [s["id"] for s in satirlar if s["aday"]]
            k[f"n{n}_farkli"] = sum(s["farkli"] for s in satirlar)
        kayitlar.append(k)
        print(f"{row['set']}#{row['id']} v8={k['v8']} aday n0={k['n0_aday']} n1={k['n1_aday']}", flush=True)

    lines = ["== FN adayları (v8 ∪ madde 32 n0 ∪ madde 33 prod), bugünkü bağlam", ""]
    for k in kayitlar:
        if not k["fn_aday"]:
            continue
        lines.append(f"{k['set']}#{k['id']} v8={k['v8']}  {k['soru']}")
        for n in (0, 1):
            lines.append(f"  N={n}: aday={k[f'n{n}_aday']}")
            for s in k[f"n{n}"]:
                isaret = "  <-- ADAY" if s["aday"] else ""
                lines.append(f"     [{s['sira']}] {s['id']} {s['kaynak']} {s['sayfa']} farkli={s['farkli']} "
                             f"bm25={s['bm25']} rerank={s['rerank']} ortak={s['ortak']}{isaret}")
        lines.append("")

    lines.append("== Taban oranı: desen (aday chunk bağlamda) pozitiflerde ne kadar yaygın?")
    for n in (0, 1):
        for grup, ks in (("FN adayı", [k for k in kayitlar if k["fn_aday"]]),
                         ("diğer (v8 TP)", [k for k in kayitlar if not k["fn_aday"] and k["v8"] == "TP"])):
            var = [k for k in ks if k[f"n{n}_aday"]]
            lines.append(f"  N={n} {grup:14s}: {len(var)}/{len(ks)} soruda aday chunk var  "
                         f"(set: {dict(Counter(k['set'] for k in var))})")
    lines.append("")
    lines.append("-- v8 TP olup N=0 bağlamında aday chunk taşıyan sorular")
    for k in kayitlar:
        if not k["fn_aday"] and k["v8"] == "TP" and k["n0_aday"]:
            a = [s for s in k["n0"] if s["aday"]]
            lines.append(f"   {k['set']}#{k['id']}: " + "; ".join(
                f"[{s['sira']}] {s['id']} {s['kaynak']} {s['sayfa']} rerank={s['rerank']} ortak={s['ortak']}" for s in a))
    lines.append("")
    lines.append("== Döküm: #56 ve #82 bağlamı (ilk 400 karakter)")
    lines += dokum

    with open(HERE / "genelleme.jsonl", "w", encoding="utf-8") as f:
        for k in kayitlar:
            f.write(json.dumps(k, ensure_ascii=False) + "\n")
    (HERE / "sonuc_genelleme.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
