"""
Madde 30 Adım 2 — #224/#101 X/XR izolasyonu (madde 34 disipliniyle).

Hipotez (Adım 1'den): FP'nin nedeni sayfa 18 chunk'ı (4344, "Yararsız Değişken
ve Kuralların Atılması") — CNF'ye yakın ama CNF'nin kendisi değil, "alakalı ama
yanlış konu". Test:
  V0  bugünkü bağlam (zaten FP, bilinen)
  X   sayfa 18 chunk'ı bağlamdan çıkarılmış
  XR  sayfa 18'in yerine konuyla tamamen ilgisiz bir chunk (Fourier PDF) konmuş
      — etkinin "bağlam kısalığı"ndan değil, o chunk'ın İÇERİĞİNDEN geldiğini
      ayırmak için
Her varyant 2 tekrar (temperature=0, tekrarlanabilirlik sağlaması).

Taban oranı kontrolü: sayfa 18 chunk'ını bağlamında taşıyan TÜM sorular
(madde 39 taban koşusu, 145 soru) ve sınıfları — desen tek başına FP
öngörüyor mu, yoksa yalnız CNF-sorulan sorularda mı sorun çıkıyor?

Kullanım (kökten): python -u experiments/madde30_sikilastirma/adim2_izolasyon.py
Çıktı: adim2_izolasyon.jsonl, sonuc_adim2_izolasyon.txt
"""
import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(HERE), str(ROOT / "evaluation"), str(ROOT / "src"), str(ROOT)]

SORULAR = [("test_negative", "224"), ("test_5", "101")]
SAYFA18 = ("8-Baglamdan_bagimsiz_dilbilgisi.pdf", "sayfa 18")
DISTRAKTOR_SORGU = "Fourier donusumunun temel ozellikleri nelerdir"
TEKRAR = 2
SETS_BASELINE = ["test_1", "test_2", "test_3", "test_4", "test_5", "test_negative"]


def taban_orani(gt, classify_answer):
    """Sayfa 18 chunk'ını bağlamında taşıyan tüm sorular + sınıfları (madde 39 taban)."""
    sonuc = []
    for s in SETS_BASELINE:
        yol = ROOT / "experiments/madde39_tam_kosu" / s / "sonuclari.csv"
        with open(yol, encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        for r in rows:
            ctx = r.get("context", "")
            if "sayfa 18" in ctx and "8-Baglamdan_bagimsiz_dilbilgisi" in ctx:
                sinif = classify_answer({**r, "set": s}, gt)
                sonuc.append((s, r["id"], sinif, r["soru"][:70]))
    return sonuc


def main():
    import run_tests as T
    from benchmark_eval import classify_answer
    from gt_utils import load_ground_truth

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    R = sys.modules[T.get_top_chunks.__module__]
    gt = load_ground_truth()

    satirlar = {}
    for s, i in SORULAR:
        with open(ROOT / "evaluation/datasets" / f"{s}.csv", encoding="utf-8-sig") as f:
            satirlar[(s, i)] = next(r for r in csv.DictReader(f) if r["id"] == i)

    def sayfa18_index(chunks):
        for idx, c in enumerate(chunks):
            if (Path(c["source"]).name, c["page_info"]) == SAYFA18:
                return idx
        return None

    distraktor_chunks = R.retrieve(DISTRAKTOR_SORGU)
    distraktor = dict(distraktor_chunks[0])
    assert Path(distraktor["source"]).name != SAYFA18[0], "distraktör yanlışlıkla aynı belgeden"

    def baglam(qid_key, varyant):
        s, i = qid_key
        chunks = [dict(c) for c in R.retrieve(satirlar[qid_key]["soru"])]
        idx = sayfa18_index(chunks)
        assert idx is not None, f"{s}#{i}: sayfa 18 bağlamda bulunamadı (V0 varsayımı geçersiz)"
        if varyant == "V0":
            return chunks
        if varyant == "X":
            return chunks[:idx] + chunks[idx + 1:]
        if varyant == "XR":
            yeni = chunks[:idx] + chunks[idx + 1:]
            return yeni[:idx] + [distraktor] + yeni[idx:]
        raise ValueError(varyant)

    llm = T.load_model()
    kayitlar, lines = [], []
    lines.append("# Taban oranı kontrolü (madde 39, sayfa 18 chunk'ını taşıyan tüm sorular)")
    for s, i, sinif, soru in taban_orani(gt, classify_answer):
        lines.append(f"  {s}#{i}: {sinif}  {soru}")
    lines.append("")
    print("\n".join(lines), flush=True)

    for qid_key in SORULAR:
        s, i = qid_key
        row = satirlar[qid_key]
        for varyant in ["V0", "X", "XR"]:
            chunks = baglam(qid_key, varyant)
            ctx = T.build_context(chunks, row["soru"])
            cevaplar = [T.ask(llm, ctx, row["soru"]) for _ in range(TEKRAR)]
            siniflar = [classify_answer({**row, "set": s, "cevap": c}, gt) for c in cevaplar]
            k = {"set": s, "id": i, "varyant": varyant,
                 "baglam": [(c["id"], c.get("page_info")) for c in chunks],
                 "cevaplar": cevaplar, "siniflar": siniflar}
            kayitlar.append(k)
            blok = [f"=== {s}#{i} {varyant}  bağlam {k['baglam']}"]
            blok += [f"  [{n + 1}] {sin}: {c[:200]!r}" for n, (sin, c) in enumerate(zip(siniflar, cevaplar))]
            blok.append(f"  tekrarlar aynı: {len(set(cevaplar)) == 1}")
            blok.append("")
            lines += blok
            print("\n".join(blok), flush=True)

    with open(HERE / "adim2_izolasyon.jsonl", "w", encoding="utf-8") as f:
        for k in kayitlar:
            f.write(json.dumps(k, ensure_ascii=False) + "\n")
    (HERE / "sonuc_adim2_izolasyon.txt").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
