"""
Madde 39 — sorgu embedding'i GPU'da mı CPU'da mı alınırsa nihai bağlam ne kadar değişiyor?
(LLM yok, DB salt okunur.) Benchmark'ta LLM yüklüyken Ollama CPU'ya düşüyor; DB vektörleri GPU'dan.

Her mod ayrı süreç: RAG_EMBED_NUM_GPU=99 (gpu) / 0 (cpu), retrieve() varsayılanları, 147 soru.
Yerleşim sağlaması: sabit metnin embedding özeti mod başında ve sonunda beklenenle karşılaştırılır.
Karşılaştırma: gpu kaydı ayrıca madde 33 prod duman kaydıyla (duman_prod_retrieval.jsonl).

Kullanım (kökten):
  python -u experiments/madde39_tam_kosu/fark.py gpu
  python -u experiments/madde39_tam_kosu/fark.py cpu
  python -u experiments/madde39_tam_kosu/fark.py ozet
Çıktı: fark_gpu.jsonl, fark_cpu.jsonl, sonuc_fark.txt
"""
import csv
import hashlib
import json
import os
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SETS = ["test_1", "test_2", "test_3", "test_4", "test_5", "test_negative"]
NOBET_METIN = "Bağlamdan bağımsız dilbilgisi için türetme ağacı nedir?"
BEKLENEN = {"gpu": "d16e556d14284ac8", "cpu": "5b827b2a0b6f3404"}


def oku(yol):
    with open(yol, encoding="utf-8") as f:
        return {(r["set"], r["id"]): r for r in map(json.loads, f)}


def nobet():
    from embedder import get_embedding
    return hashlib.sha256(json.dumps(get_embedding(NOBET_METIN)).encode()).hexdigest()[:16]


def kos(mod):
    os.environ["RAG_EMBED_NUM_GPU"] = "99" if mod == "gpu" else "0"
    sys.path[:0] = [str(ROOT / "src"), str(ROOT)]
    from retrieval import retrieve

    yol = HERE / f"fark_{mod}.jsonl"
    bitmis = oku(yol) if yol.exists() else {}
    once = nobet()
    print(f"{mod}: nöbet başta {once} (beklenen {BEKLENEN[mod]})", flush=True)
    if once != BEKLENEN[mod]:
        sys.exit("Embedding beklenen cihazda değil; koşu başlatılmadı.")
    with open(yol, "a", encoding="utf-8") as out:
        for set_ in SETS:
            with open(ROOT / "evaluation/datasets" / f"{set_}.csv", encoding="utf-8-sig") as f:
                for row in csv.DictReader(f):
                    if (set_, row["id"]) in bitmis:
                        continue
                    c = retrieve(row["soru"])
                    out.write(json.dumps({"set": set_, "id": row["id"], "soru": row["soru"],
                                          "ids": [x["id"] for x in c],
                                          "imza": [[Path(x["source"]).name, x.get("page_info")] for x in c],
                                          "rerank": [round(x.get("rerank_score", 0), 5) for x in c],
                                          "rota": c[0].get("route") if c else None},
                                         ensure_ascii=False) + "\n")
                    out.flush()
                    print(f"{mod} {set_}#{row['id']}", flush=True)
    sonra = nobet()
    print(f"{mod}: nöbet sonda {sonra}", flush=True)
    if sonra != BEKLENEN[mod]:
        sys.exit("Koşu sırasında embedding cihazı değişti; kayıt güvenilir değil.")


def ozet():
    g, c = oku(HERE / "fark_gpu.jsonl"), oku(HERE / "fark_cpu.jsonl")
    d = oku(ROOT / "experiments/madde33_stemmer_chunk/duman_prod_retrieval.jsonl")
    lines = [f"soru: gpu {len(g)}, cpu {len(c)}",
             f"gpu == madde 33 prod kaydı: {sum(g[k]['imza'] == d[k]['imza'] for k in g)}/{len(g)}", ""]
    tablo = Counter()
    detay = []
    for k in g:
        a, b = g[k], c[k]
        if a["ids"] == b["ids"]:
            t = "aynı"
        elif set(a["ids"]) == set(b["ids"]):
            t = "aynı küme, sıra farklı"
        else:
            t = "küme farklı"
        tablo[(k[0], t)] += 1
        tablo[("GENEL", t)] += 1
        if a["ids"] and b["ids"] and a["ids"][0] != b["ids"][0]:
            tablo[(k[0], "1. chunk farklı")] += 1
            tablo[("GENEL", "1. chunk farklı")] += 1
        if t != "aynı":
            detay.append(f"  {k[0]}#{k[1]} [{t}] rota={a['rota']}\n    gpu {a['ids']} {a['rerank']}\n"
                         f"    cpu {b['ids']} {b['rerank']}\n    {a['soru'][:80]}")
    for s in SETS + ["GENEL"]:
        lines.append(f"{s:14s} aynı={tablo[(s, 'aynı')]:3d}  sıra={tablo[(s, 'aynı küme, sıra farklı')]:3d}  "
                     f"küme={tablo[(s, 'küme farklı')]:3d}  1. chunk={tablo[(s, '1. chunk farklı')]:3d}")
    lines += ["", "== Farklı olanlar"] + detay
    (HERE / "sonuc_fark.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    ozet() if sys.argv[1] == "ozet" else kos(sys.argv[1])
