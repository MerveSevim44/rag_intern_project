"""Madde 25 kapsam taraması: skorlayıcının ret saymadığı ama olumsuzluk kalıbı taşıyan cevaplar."""
import csv, re, sys, glob
from collections import defaultdict
from pathlib import Path
ROOT = str(Path(__file__).resolve().parents[2])
sys.path[:0] = [ROOT, str(Path(ROOT) / "evaluation")]
from evaluation.benchmark_eval import check_is_not_found, _REFUSAL_MARKERS, _fold_tr, normalize_text_tr, _new_claims

# Geniş olumsuzluk kalıbı (fold'lu metin üzerinde). Bilerek GEVŞEK: aday toplar, karar elle.
BROAD = re.compile(
    r"bulunma[dyzm]\w*|bulunam\w*|bulama[dy]\w*|\byok(tur|tu)?\b|yer alma\w*|"
    r"belirtilme\w*|gecme[dmy]\w*|mevcut degil\w*|icerm(e|i)\w*|bahsedilme\w*|"
    r"verilme(di|mi)\w*|tespit edileme\w*|rastlanma\w*|ulasilama\w*|erisileme\w*|"
    r"saglanma(di|mi)\w*|sunulma(di|mi)\w*|\bbilinmiyor|\bbelirsiz")

runs = sorted(glob.glob(str(Path(ROOT) / "experiments" / "*" / "report*" / "genel_scored.csv")))
cands = []           # (run, set, id, cls, gate, answer, question)
gate_ok_claims = []  # kapıdan geçen ama iddia filtresi FP/TP yapan
for path in runs:
    run = Path(path).parent.parent.name + ("+neg" if "with_negative" in path else "")
    for r in csv.DictReader(open(path, encoding="utf-8-sig")):
        ans, q, cls = r.get("cevap", ""), r.get("soru", ""), r.get("siniflandirma", "")
        if not ans or ans.startswith("HATA") or cls not in ("TP", "FP"):
            continue                         # yalnız "ret değil" sayılanlar
        norm = _fold_tr(normalize_text_tr(ans))
        gate = any(m in norm for m in _REFUSAL_MARKERS)
        if gate:
            gate_ok_claims.append((run, r["test_seti"], r["id"], cls, _new_claims(ans, q), ans))
        elif BROAD.search(norm):
            cands.append((run, r["test_seti"], r["id"], cls, BROAD.search(norm).group(0), ans, q))

print(f"tarama: {len(runs)} koşu")
print(f"\n=== A) KAPIDAN GEÇEMEYEN (ret kalıbı yok) ama olumsuzluk taşıyan TP/FP cevaplar: {len(cands)}")
uniq = defaultdict(list)
for c in cands:
    uniq[(c[1], c[2], c[5])].append(c[0])
print(f"   (farklı cevap metni: {len(uniq)})")
for (s, i, ans), rs in sorted(uniq.items(), key=lambda kv: (kv[0][0], int(kv[0][1]))):
    c = next(c for c in cands if (c[1], c[2], c[5]) == (s, i, ans))
    print(f"--- {s}#{i} {c[3]} [{c[4]}] koşular={','.join(rs)}\n    {ans[:260]!r}")

print(f"\n=== B) KAPIDAN GEÇEN ama 'yeni iddia' filtresi ret SAYMAYAN: {len(gate_ok_claims)}")
uq = {}
for run, s, i, cls, claims, ans in gate_ok_claims:
    uq.setdefault((s, i, ans), (cls, claims, []))[2].append(run)
for (s, i, ans), (cls, claims, rs) in sorted(uq.items(), key=lambda kv: (kv[0][0], int(kv[0][1]))):
    print(f"--- {s}#{i} {cls} iddia={claims} koşular={','.join(rs)}\n    {ans[:260]!r}")
