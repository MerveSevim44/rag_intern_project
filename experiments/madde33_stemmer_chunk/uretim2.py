"""
Madde 33 Adım 2, Faz B — bağlamı değişen sorularda cevap (sınıf + doğruluk).

Faz A (havuz2.jsonl) hangi sorularda nihai bağlamın değiştiğini verir. Politika
cache'te simüle edildiği için üretim ALT SÜREÇTE değil, aynı süreçte
run_tests.run_single_test ile (get_top_chunks -> build_context -> ask; src.retrieval
modülüne politika.kur uygulanır). temperature=0.
  MIN=0: herhangi bir MIN'de bağlamı değişen tüm sorular (referans)
  MIN=500/800/1200: o MIN'de bağlamı değişen sorular

Madde 36 geçici kuralı: sınıf (classify_answer) TP->TP doğruluk demek değil;
rapor, değişen her sorunun cevaplarını yan yana döker, doğruluk elle
değerlendirilir. Yardımcı sinyal: GT anahtar_kelimeler'in cevapta geçen oranı.

Kullanım (kökten; Foundry + Ollama):
  python -u experiments/madde33_stemmer_chunk/uretim2.py kos
  python experiments/madde33_stemmer_chunk/uretim2.py rapor
"""
import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(HERE), str(ROOT / "evaluation"), str(ROOT / "src"), str(ROOT)]

MINS = [0, 500, 800, 1200]
FIELDS = ["set", "id", "soru", "cevap", "bulunan_kaynaklar", "sure_sn", "context", "dogrulama_durumu"]


def _hedefler():
    k = {}
    with open(HERE / "havuz2.jsonl", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            k[(r["set"], r["id"], r["min"])] = r["imza"]
    keys = sorted({(s, i) for s, i, _ in k}, key=lambda x: (x[0], int(x[1])))
    deg = {m: [q for q in keys if k[(*q, m)] != k[(*q, 0)]] for m in MINS[1:]}
    deg[0] = [q for q in keys if any(q in deg[m] for m in MINS[1:])]
    return deg


def _sorular():
    out = {}
    for s in ["test_1", "test_2", "test_3", "test_4", "test_5", "test_negative"]:
        with open(ROOT / "evaluation/datasets" / f"{s}.csv", encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                out[(s, r["id"])] = {**r, "set": s}
    return out


def _yol(m):
    return HERE / f"uretim2_min{m}.csv"


def _oku(m):
    p = _yol(m)
    if not p.exists():
        return {}
    with open(p, encoding="utf-8-sig") as f:
        return {(r["set"], r["id"]): r for r in csv.DictReader(f)}


def kos():
    import run_tests as T
    from politika import kur

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    R = sys.modules[T.get_top_chunks.__module__]
    hedef, sorular = _hedefler(), _sorular()
    llm = T.load_model()
    for m in MINS:
        yapildi = _oku(m)
        kalan = [q for q in hedef[m] if q not in yapildi]
        print(f"MIN={m}: {len(hedef[m])} soru, kalan {len(kalan)}", flush=True)
        if not kalan:
            continue
        kur(R, m)
        yeni = not _yol(m).exists()
        with open(_yol(m), "a", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
            if yeni:
                w.writeheader()
            for q in kalan:
                row = sorular[q]
                try:
                    res = T.run_single_test(llm, row["soru"])
                except Exception as e:
                    res = {"cevap": f"HATA: {e}", "bulunan_kaynaklar": "", "sure_sn": 0, "context": "",
                           "dogrulama_durumu": ""}
                w.writerow({**row, **res})
                f.flush()
                print(f"  MIN={m} {q[0]}#{q[1]} ({res['sure_sn']} sn): {res['cevap'][:80]!r}", flush=True)
    kur(R, 0)


def rapor():
    from benchmark_eval import classify_answer, question_polarity
    from gt_utils import load_ground_truth

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    gt, sorular, hedef = load_ground_truth(), _sorular(), _hedefler()
    ref = _oku(0)

    def anahtar(q, cevap):
        kw = gt.get(q[1], {}).get("anahtar_kelimeler") or []
        if not kw:
            return "-"
        low = cevap.lower()
        return f"{sum(1 for k in kw if k.lower() in low)}/{len(kw)}"

    L = [f"Referans (MIN=0) koşulan soru: {len(ref)}"]
    for m in MINS[1:]:
        res = _oku(m)
        if not res:
            L.append(f"\nMIN={m}: koşu yok")
            continue
        gec = {}
        satir = []
        for q in hedef[m]:
            a_row, b_row = {**sorular[q], **ref[q]}, {**sorular[q], **res[q]}
            a, b = classify_answer(a_row, gt), classify_answer(b_row, gt)
            gec[f"{a}->{b}"] = gec.get(f"{a}->{b}", 0) + 1
            neg = question_polarity(sorular[q], gt)[0]
            satir += [f"   {q[0]}#{q[1]} {'NEG' if neg else 'POZ'}: {a} -> {b}"
                      f"{'  <-- SINIF DEĞİŞTİ' if a != b else ''}"
                      f"  | anahtar kelime {anahtar(q, ref[q]['cevap'])} -> {anahtar(q, res[q]['cevap'])}",
                      f"      MIN=0  : {ref[q]['cevap'][:260]!r}",
                      f"      MIN={m}: {res[q]['cevap'][:260]!r}"]
        L.append(f"\nMIN={m}: bağlamı değişen {len(hedef[m])} soru | geçişler: "
                 + ", ".join(f"{k}={v}" for k, v in sorted(gec.items())))
        L += satir
    text = "\n".join(L) + "\n"
    (HERE / "sonuc_uretim2.txt").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    kos() if sys.argv[1] == "kos" else rapor()
