"""Madde 25: ret kapısı varyantlarının tüm skorlu koşulardaki sınıf değişimi (yeniden skorlama simülasyonu)."""
import csv, re, sys, glob
from pathlib import Path
ROOT = str(Path(__file__).resolve().parents[2])
sys.path[:0] = [ROOT, str(Path(ROOT) / "evaluation")]
import evaluation.benchmark_eval as B

ORIG_MARKERS = list(B._REFUSAL_MARKERS)
orig_gate = lambda norm: any(m in norm for m in ORIG_MARKERS)

# (a) naif: çekimli biçimleri listeye ekle
NAIVE = ORIG_MARKERS + ["bulunmad", "bulunmam", "bulunmaz", "belirtilmem", "belirtilmed",
                        "yer almad", "yer almaz", "gecmed", "gecmiyor", "yoktur", " yok "]
naive_gate = lambda norm: any(m in norm for m in NAIVE)

# (b) ret çerçevesi: olumsuzluk yüklemi + AYNI cümlede bağlam sözcüğü (llm_client mantığı)
# Olumsuzluk eki ZORUNLU: -ma/-me'den sonra d/m/y/z/s (bulunmaktadır, yer almaktadır
# gibi olumlu "-mak/-mek" biçimleri eşleşmesin).
PRED = re.compile(r"bulun(a)?ma[dmyzs]\w*|bulunamad\w*|bulunmuyor|yer alma[dmyzs]\w*|"
                  r"belirtilme[dmyzs]\w*|gecme[dmyzs]\w*|mevcut degil\w*|\byok(tur)?\b")
CTX = re.compile(r"\bbilgi\w*|dokuman\w*|belge\w*|baglam\w*|metin\w*|kaynak\w*|ders not\w*")
def frame_gate(norm, raw):
    if orig_gate(norm):
        return True
    for sent in re.split(r"(?<=[.!?])\s+|\n+", B._fold_tr(raw)):
        if PRED.search(sent) and CTX.search(sent):
            return True
    return False


def classify(row, gate_fn):
    ans, q = row["cevap"], row["soru"]
    norm = B._fold_tr(B.normalize_text_tr(ans))
    old_gate = B._REFUSAL_MARKERS
    try:
        ok = gate_fn(norm) if gate_fn.__code__.co_argcount == 1 else gate_fn(norm, ans)
        if not ok:
            nf = False
        else:
            # kapı geçildi: mevcut ikinci aşama aynen (residual temizliği eski listeyle)
            nf = (not B._EVAL_MATH_RE.search(ans)) and len(B._new_claims(ans, q)) == 0
    finally:
        B._REFUSAL_MARKERS = old_gate
    neg = row["siniflandirma"] in ("TN", "FP")
    return ("TN" if nf else "FP") if neg else ("FN" if nf else "TP")


for path in sorted(glob.glob(str(Path(ROOT) / "experiments" / "*" / "report*" / "genel_scored.csv"))):
    run = Path(path).parent.parent.name + ("+neg" if "with_negative" in path else "")
    rows = [r for r in csv.DictReader(open(path, encoding="utf-8-sig"))
            if r.get("cevap") and not r["cevap"].startswith("HATA") and r["siniflandirma"] in ("TP", "FP", "TN", "FN")]
    base = {(r["test_seti"], r["id"]): classify(r, lambda n: orig_gate(n)) for r in rows}
    stored = {(r["test_seti"], r["id"]): r["siniflandirma"] for r in rows}
    drift = [k for k in base if base[k] != stored[k]]
    for name, fn in (("naif", lambda n: naive_gate(n)), ("cerceve", frame_gate)):
        ch = [(k, base[k], classify(r, fn)) for r in rows for k in [(r["test_seti"], r["id"])] if classify(r, fn) != base[k]]
        print(f"{run:28} {name:8} degisen={len(ch):2} " + " ".join(f"{s}#{i}:{a}->{b}" for (s, i), a, b in ch))
    if drift:
        print(f"{run:28} (not: kayıtlı sınıftan farklı yeniden skor {len(drift)}: {drift[:6]})")
