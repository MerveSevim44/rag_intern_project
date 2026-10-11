"""
Kalıp B ölçümü: commit edilmiş skorlayıcı (git REV) ile çalışma ağacındaki
skorlayıcının tüm skorlu koşulardaki sınıf farkı. Deterministik, servis gerektirmez.

Kalıp B: sorudaki tanımlayıcının (G_4.5.1, L_S.4.8.1) cevaptaki yankısı "yeni
iddia" sayılıyor, saf ret TP (gizli FN) oluyordu. Beklenen: v3 #26, #29 TP->FN.
Kritik yön: negatif soruda FP->TN olursa bir halüsinasyon gizlenmiş demektir.

Kullanım:
    python experiments/madde25_ret_tespiti/kalip_b_olcum.py [REV]   (varsayılan f888033)
"""
import csv
import glob
import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "evaluation")]
import evaluation.benchmark_eval as NEW  # noqa: E402

REV = sys.argv[1] if len(sys.argv) > 1 else "f888033"
src = subprocess.run(["git", "show", f"{REV}:evaluation/benchmark_eval.py"], cwd=ROOT,
                     capture_output=True, check=True).stdout
with tempfile.NamedTemporaryFile("wb", suffix="_benchmark_eval_old.py", delete=False) as f:
    f.write(src)
spec = importlib.util.spec_from_file_location("benchmark_eval_old", f.name)
OLD = importlib.util.module_from_spec(spec)
spec.loader.exec_module(OLD)


def cls(mod, row):
    nf = mod.check_is_not_found(row["cevap"], row["soru"])
    neg = row["siniflandirma"] in ("TN", "FP")
    return ("TN" if nf else "FP") if neg else ("FN" if nf else "TP")


total = 0
for path in sorted(glob.glob(str(ROOT / "experiments" / "*" / "report*" / "genel_scored.csv"))):
    run = Path(path).parent.parent.name + ("+neg" if "with_negative" in path else "")
    rows = [r for r in csv.DictReader(open(path, encoding="utf-8-sig"))
            if r.get("cevap") and not r["cevap"].startswith("HATA")
            and r["siniflandirma"] in ("TP", "FP", "TN", "FN")]
    total += len(rows)
    ch = [(r, cls(OLD, r), cls(NEW, r)) for r in rows if cls(OLD, r) != cls(NEW, r)]
    print(f"{run:28} satir={len(rows):3} degisen={len(ch)}")
    for r, a, b in ch:
        flag = "  <-- NEGATIF FP->TN (halusinasyon gizlenmis olabilir)" if (a, b) == ("FP", "TN") else ""
        print(f"    {r['test_seti']}#{r['id']}: {a} -> {b}{flag}")
        print(f"      eski iddia={OLD._new_claims(r['cevap'], r['soru'])} yeni iddia={NEW._new_claims(r['cevap'], r['soru'])}")
        print(f"      {r['cevap'][:180]!r}")
print(f"toplam satir: {total}")
