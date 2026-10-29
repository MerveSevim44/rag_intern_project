"""
Madde 34 Adım 1a — kapsam: "İngilizce slayt gövdesi + bozuk sembol + Türkçe soru"
deseni #82'ye özel mi? (LLM yok, DB salt okunur)

Chunk düzeyi (rag.db, tüm chunk'lar):
  dil   gövdedeki İngilizce / Türkçe işlev kelimesi sayısı -> EN / TR / karışık
  pua   Symbol fontu Private Use Area karakteri (U+F000–U+F0FF) sayısı;
        PDF metin katmanında δ, ω, ∫, ( ) vb. bu kod noktalarına düşüyor
Soru düzeyi (115 pozitif + negatifler): güncel nihai bağlam
  (madde 32 havuz.jsonl n0_ids = bayrak kapalı, n1_ids = RAG_DENSE_FORCE_TOP_N=1;
  madde 33 yalnız .txt chunk'larını değiştirdi, PDF id'leri aynı) içindeki
  EN / PUA chunk'ları ve en son tam koşunun sınıfı (madde 27 yeniden_skor_v8 —
  ESKİ sistem; bağlamı bugünkünden farklı olabilir, yalnız kaba gösterge).

Kullanım (kökten): python experiments/madde34_ingilizce_ret/kapsam.py
Çıktı: kapsam.jsonl, sonuc_kapsam.txt
"""
import csv
import json
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

EN_SW = set("""the is of and in to a that for with are this by as be on it we an or from
which can so at if then its be has have was were not but also these those
there their when where what how into than any all each such recall note let""".split())
TR_SW = set("""ve bir bu ile için da de olarak olan veya ya ki ne her gibi daha çok en
ise şu o mi mı mu mü değil kadar sonra önce göre ait üzerine olur olduğu""".split())
TR_HARF = set("çğıöşüÇĞİÖŞÜ")
PUA = re.compile("[-]")
KELIME = re.compile(r"[^\W\d_]+", re.UNICODE)


def dil(metin):
    kel = [k.lower() for k in KELIME.findall(metin)]
    en = sum(k in EN_SW for k in kel)
    tr = sum(k in TR_SW or any(h in TR_HARF for h in k) for k in kel)
    if en >= 3 and en >= 2 * tr:
        etiket = "EN"
    elif tr >= 3 and tr >= 2 * en:
        etiket = "TR"
    elif en + tr < 3:
        etiket = "az_metin"
    else:
        etiket = "karisik"
    return etiket, en, tr


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    db = sqlite3.connect(ROOT / "rag.db")
    chunks = {}
    for cid, src, page, metin in db.execute("SELECT id, source, page_info, content FROM chunks"):
        etiket, en, tr = dil(metin)
        chunks[cid] = {"id": cid, "kaynak": Path(src).name, "sayfa": page, "dil": etiket,
                       "en": en, "tr": tr, "pua": len(PUA.findall(metin)), "uzunluk": len(metin)}

    lines = ["== Chunk düzeyi (rag.db, %d chunk)" % len(chunks), ""]
    by_src = defaultdict(list)
    for c in chunks.values():
        by_src[c["kaynak"]].append(c)
    for src, cs in sorted(by_src.items()):
        d = Counter(c["dil"] for c in cs)
        pua = sum(c["pua"] > 0 for c in cs)
        en_pua = sum(c["dil"] == "EN" and c["pua"] > 0 for c in cs)
        lines.append(f"{src:45s} n={len(cs):4d}  dil={dict(d)}  PUA'lı={pua}  EN+PUA={en_pua}")
    lines.append("")

    # Fourier / Z: sayfa sayfa döküm
    for src in ("lsarSist-H8_FourierTransform.pdf", "lsarSist-H9_ZTransform.pdf"):
        lines.append(f"-- {src}")
        for c in sorted(by_src[src], key=lambda c: c["id"]):
            lines.append(f"   {c['id']} {c['sayfa']:10s} dil={c['dil']:8s} en={c['en']:2d} tr={c['tr']:2d} pua={c['pua']:3d}")
        lines.append("")

    # Soru düzeyi
    csv.field_size_limit(10**9)
    v8 = {}
    with open(ROOT / "experiments/madde27_nan_embedding/yeniden_skor_v8/genel_scored.csv", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            v8[(r["test_seti"], r["id"])] = r["siniflandirma"]
    kayitlar = []
    with open(ROOT / "experiments/madde32_adim2_dense_force_include/havuz.jsonl", encoding="utf-8") as f:
        for line in f:
            h = json.loads(line)
            k = {"set": h["set"], "id": h["id"], "soru": h["soru"], "v8": v8.get((h["set"], h["id"]), "?")}
            for n in ("n0", "n1"):
                ids = [i for i in h[f"{n}_ids"] if i in chunks]  # .txt id'leri madde 33'te değişti
                k[n] = [(i, chunks[i]["dil"], chunks[i]["pua"]) for i in ids]
                k[f"{n}_en"] = sum(chunks[i]["dil"] == "EN" for i in ids)
                k[f"{n}_pua"] = sum(chunks[i]["pua"] > 0 for i in ids)
                k[f"{n}_ilk_en"] = bool(ids) and chunks[ids[0]]["dil"] == "EN"
            kayitlar.append(k)

    lines.append("== Soru düzeyi (güncel nihai bağlam; sınıf = v8, eski sistem)")
    for n in ("n0", "n1"):
        lines.append(f"-- {n}")
        for set_ in sorted({k["set"] for k in kayitlar}):
            ks = [k for k in kayitlar if k["set"] == set_]
            en_var = [k for k in ks if k[f"{n}_en"] > 0]
            ilk_en = [k for k in ks if k[f"{n}_ilk_en"]]
            hepsi_en = [k for k in ks if k[n] and k[f"{n}_en"] == len(k[n])]
            lines.append(f"   {set_:14s} soru={len(ks):3d}  bağlamda EN chunk={len(en_var):3d}  "
                         f"1. sıra EN={len(ilk_en):3d}  tümü EN={len(hepsi_en):3d}  "
                         f"1. sıra EN olanların v8 sınıfı={dict(Counter(k['v8'] for k in ilk_en))}")
        lines.append("")

    lines.append("-- 1. sırası EN olan sorular (n1), v8 sınıfı")
    for k in kayitlar:
        if k["n1_ilk_en"]:
            lines.append(f"   {k['set']}#{k['id']:>3s} v8={k['v8']:3s} n1={k['n1']}  {k['soru'][:70]}")

    with open(HERE / "kapsam.jsonl", "w", encoding="utf-8") as f:
        for k in kayitlar:
            f.write(json.dumps(k, ensure_ascii=False) + "\n")
    (HERE / "sonuc_kapsam.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
