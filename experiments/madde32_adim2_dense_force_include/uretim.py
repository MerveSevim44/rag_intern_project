"""
Madde 32 Adım 2, Faz B — bağlamı değişen sorularda cevap sınıfı değişiyor mu?

Faz A (havuz.py -> havuz.jsonl) dense güvenlik slotunun nihai bağlamı hangi
sorularda değiştirdiğini verir. Bağlamı değişmeyen soru LLM'e aynı girdiyi
götürür; üretici temperature=0 ve tekrarlanabilirliği madde 21'de doğrulandı
(2 koşu birebir aynı) — bu yüzden yalnız değişen sorular koşulur.

Her konfigürasyon AYRI süreçte evaluation/run_tests.py ile, RAG_DENSE_FORCE_TOP_N
ortam değişkeniyle:
  N=0 (kapalı, referans): herhangi bir N'de değişen tüm sorular
  N=1/3/5: o N'de bağlamı değişen sorular
Sınıf: benchmark_eval.classify_answer (TP/TN/FP/FN). Judge yok.

Kullanım (kökten; Foundry + Ollama gerekir):
  python experiments/madde32_adim2_dense_force_include/uretim.py kos 0   # sonra 1, 3, 5
  python experiments/madde32_adim2_dense_force_include/uretim.py rapor
"""
import csv
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
NS = [1, 3, 5]
FIELDS = ["id", "zorluk", "soru", "beklenen_kaynak", "dokumanda_var_mi", "referans_cevap", "set"]


def _havuz():
    with open(HERE / "havuz.jsonl", encoding="utf-8") as f:
        return [json.loads(l) for l in f]


def _hedefler(n):
    recs = _havuz()
    if n == 0:
        return {(r["set"], r["id"]) for r in recs if any(r[f"n{m}_degisti"] for m in NS)}
    return {(r["set"], r["id"]) for r in recs if r[f"n{n}_degisti"]}


def kos(n):
    hedef = _hedefler(n)
    out = HERE / f"uretim_n{n}"
    out.mkdir(exist_ok=True)
    rows = []
    for s in sorted({s for s, _ in hedef}):
        with open(ROOT / "evaluation/datasets" / f"{s}.csv", encoding="utf-8-sig") as f:
            rows += [{**r, "set": s} for r in csv.DictReader(f) if (s, r["id"]) in hedef]
    assert len(rows) == len(hedef), (len(rows), len(hedef))
    sorular = out / "sorular.csv"
    with open(sorular, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore", restval="")
        w.writeheader()
        w.writerows(rows)
    print(f"N={n}: {len(rows)} soru")
    with open(out / "log_run_tests.txt", "w", encoding="utf-8") as log:
        rc = subprocess.run([sys.executable, "evaluation/run_tests.py", str(sorular), str(out / "sonuclari.csv")],
                            cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                            env={**os.environ, "PYTHONIOENCODING": "utf-8", "RAG_DENSE_FORCE_TOP_N": str(n)}).returncode
    # run_tests.py tüm soruları yazıp kapanışta 0xC0000005 ile çökebiliyor (N=0 koşusunda
    # görüldü); başarı ölçütü çıkış kodu değil, sonuç dosyasındaki soru sayısı.
    with open(out / "sonuclari.csv", encoding="utf-8-sig") as f:
        yazilan = sum(1 for _ in csv.DictReader(f))
    print(f"N={n}: çıkış kodu {rc}, sonuç {yazilan}/{len(rows)}")
    if yazilan != len(rows):
        sys.exit(1)


def rapor():
    sys.path[:0] = [str(ROOT / "evaluation"), str(ROOT / "src"), str(ROOT)]
    from benchmark_eval import classify_answer
    from gt_utils import load_ground_truth

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    gt = load_ground_truth()

    def oku(n):
        p = HERE / f"uretim_n{n}" / "sonuclari.csv"
        if not p.exists():
            return None
        with open(p, encoding="utf-8-sig") as f:
            return {(r["set"], r["id"]): r for r in csv.DictReader(f)}

    ref = oku(0)
    lines = [f"Referans (N=0) koşulan soru: {len(ref)}"]
    for n in NS:
        res = oku(n)
        if res is None:
            lines.append(f"\nN={n}: koşu yok")
            continue
        degisim = []
        for key, r in sorted(res.items()):
            a, b = classify_answer(ref[key], gt), classify_answer(r, gt)
            degisim.append((key, a, b, ref[key]["cevap"], r["cevap"]))
        gecis = {}
        for _, a, b, *_ in degisim:
            gecis[f"{a}->{b}"] = gecis.get(f"{a}->{b}", 0) + 1
        lines.append(f"\nN={n}: bağlamı değişen {len(degisim)} soru | geçişler: "
                     + ", ".join(f"{k}={v}" for k, v in sorted(gecis.items())))
        for (s, i), a, b, ca, cb in degisim:
            isaret = "" if a == b else "  <-- SINIF DEĞİŞTİ"
            lines.append(f"   {s}#{i}: {a} -> {b}{isaret}")
            if a != b or (s, i) in {("test_3", "79"), ("test_3", "82")}:
                lines.append(f"      N=0: {ca[:150]!r}")
                lines.append(f"      N={n}: {cb[:150]!r}")
    text = "\n".join(lines) + "\n"
    (HERE / "sonuc_uretim.txt").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    if sys.argv[1] == "kos":
        kos(int(sys.argv[2]))
    else:
        rapor()
