"""
Madde 29 Adım 1 — rag.db'deki doküman embedding'leri hangi cihaz yerleşimiyle
üretildi? (DB'ye yazmaz; ingest'e dokunmaz.)

Yöntem: her chunk'ın içeriği, ingest'in çağrısı BİREBİR taklit edilerek yeniden
embed edilir ve DB'deki vektörle karşılaştırılır:
- ingest_single_file -> embedder.get_embeddings(texts, batch_size=ingest.BATCH_SIZE)
  -> ollama.embed(input=<64'lük grup>) ; kaynak başına chunk'lar id sırasıyla,
  aynı grup bölünmesiyle (bir kaynak tek ingest çağrısında yazılmışsa id'ler ardışık).
- Üç yerleşim: num_gpu=0 (tam CPU), 24 (kısmi: 24/25 katman GPU'da — Ollama
  loglarında görülüyor), 99 (tam GPU). Her yerleşimden önce model boşaltılır.

Chunk sınıfı: DB vektörüyle BAYT BAYT aynı olan yerleşim(ler); hiçbiri aynı
değilse en yüksek kosinüs. Ayrıca gruplamanın etkisi: tek tek embed (grupsuz)
ile gruplu sonucun farkı bir örneklemde ölçülür.

Kullanım:
    python -u experiments/madde29_embedding_cihaz/cihaz_tespiti.py
Çıktı: cihaz_tespiti.jsonl (chunk başına), sonuc_cihaz_tespiti.txt
"""
import collections
import json
import math
import sqlite3
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]

import ollama  # noqa: E402
from ingest import BATCH_SIZE  # noqa: E402
from embedder import EMBED_MODEL  # noqa: E402

PLACEMENTS = {"cpu": 0, "kismi_24": 24, "gpu": 99}
SAMPLE_SINGLE = 12  # gruplama etkisi için tek tek embed edilecek chunk sayısı (kaynak başına ilkler)


def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


def max_abs(a, b):
    return max(abs(x - y) for x, y in zip(a, b))


def embed_batched(texts, num_gpu):
    out = []
    for i in range(0, len(texts), BATCH_SIZE):
        r = ollama.embed(model=EMBED_MODEL, input=texts[i:i + BATCH_SIZE], keep_alive="5m",
                         options={"num_gpu": num_gpu})
        out.extend(r.embeddings)
    return out


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    con = sqlite3.connect(ROOT / "rag.db")
    rows = con.execute("select id, source, content, embedding from chunks order by id").fetchall()
    by_src = collections.OrderedDict()
    for cid, src, content, emb in rows:
        by_src.setdefault(src, []).append((cid, content, json.loads(emb)))
    gaps = {s: [b[0] - a[0] for a, b in zip(v, v[1:]) if b[0] - a[0] != 1] for s, v in by_src.items()}

    results = {}  # (placement) -> {cid: vec}
    ps = {}
    for name, ng in PLACEMENTS.items():
        ollama.embed(model=EMBED_MODEL, input="x", keep_alive=0)   # boşalt -> yeni num_gpu ile yükle
        vecs = {}
        for src, items in by_src.items():
            embs = embed_batched([c for _, c, _ in items], ng)
            for (cid, _, _), v in zip(items, embs):
                vecs[cid] = v
            if name not in ps:
                ps[name] = subprocess.run(["ollama", "ps"], capture_output=True, text=True).stdout.strip()
            print(f"[{name}] {Path(src).name}: {len(items)} chunk", flush=True)
        results[name] = vecs

    # Gruplama etkisi: CPU'da tek tek embed vs gruplu
    ollama.embed(model=EMBED_MODEL, input="x", keep_alive=0)
    single_diff = []
    for src, items in by_src.items():
        for cid, content, _ in items[:SAMPLE_SINGLE]:
            v = ollama.embed(model=EMBED_MODEL, input=content, keep_alive="5m", options={"num_gpu": 0}).embeddings[0]
            single_diff.append((cosine(v, results["cpu"][cid]), v == results["cpu"][cid], Path(src).name))

    lines = [f"chunk: {len(rows)}  BATCH_SIZE={BATCH_SIZE}"]
    lines += [f"ollama ps ({n}):\n{p}" for n, p in ps.items()]
    lines.append("id boşlukları (kaynak tek ingest çağrısında mı yazıldı?): "
                 + ", ".join(f"{Path(s).name}={g}" for s, g in gaps.items() if g) or "yok")
    per_src = collections.defaultdict(collections.Counter)
    with open(HERE / "cihaz_tespiti.jsonl", "w", encoding="utf-8") as f:
        for src, items in by_src.items():
            for cid, _, db_vec in items:
                rec = {"id": cid, "kaynak": Path(src).name}
                exact = []
                for name in PLACEMENTS:
                    v = results[name][cid]
                    rec[f"cos_{name}"] = cosine(v, db_vec)
                    rec[f"maxabs_{name}"] = max_abs(v, db_vec)
                    if v == db_vec:
                        exact.append(name)
                rec["bayt_bayt_ayni"] = exact
                best = max(PLACEMENTS, key=lambda n: rec[f"cos_{n}"])
                rec["sinif"] = "+".join(exact) if exact else f"yok(en_yakin={best})"
                per_src[Path(src).name][rec["sinif"]] += 1
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    lines.append("\nKaynak başına sınıf (DB vektörüyle bayt bayt aynı olan yerleşim):")
    for src, c in per_src.items():
        lines.append(f"   {src:42} {dict(c)}")
    recs = [json.loads(l) for l in (HERE / "cihaz_tespiti.jsonl").read_text(encoding="utf-8").splitlines()]
    for name in PLACEMENTS:
        cs = sorted(r[f"cos_{name}"] for r in recs)
        lines.append(f"cos(DB, {name}): min={cs[0]:.6f} medyan={cs[len(cs) // 2]:.6f} max={cs[-1]:.6f}")
    sd = sorted(single_diff)
    lines.append(f"\nGruplama etkisi (CPU, {len(sd)} chunk, tek tek vs 64'lük grup): "
                 f"bayt bayt ayni {sum(1 for _, e, _ in sd if e)}/{len(sd)}, cos min={sd[0][0]:.6f}")
    text = "\n".join(lines) + "\n"
    (HERE / "sonuc_cihaz_tespiti.txt").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
