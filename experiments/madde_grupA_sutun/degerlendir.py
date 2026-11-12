"""
A1 sutun-bolme denemesinin degerlendirmesi. Kullanim (kokten): python experiments/madde_grupA_sutun/degerlendir.py
 (a) test_1 PDF'i sayfa 16/18-21: eski vs yeni metin, elle temizlenmis referansa token-sirasi benzerligi (#19: s20, #20: s21)
 (b) PDF'in TUM sayfalari: bolme tetiklenen sayfalar, icerik kaybi/cogalmasi (harf coklu-kumesi), sirali fark onizlemesi
 (c) Ek: Fourier/Z-donusumu PDF'leri icin yalniz tetiklenme sayisi (yanlis-pozitif riski icin)
"""
import difflib, re, sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(HERE)]
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import pdfplumber
from sutun_bol import sutunlu_metin

src = (ROOT / "experiments/madde_grupA_duzen/duzen_testi.py").read_text(encoding="utf-8")
ns = {}
exec(src[src.index("TEMIZ_19_S20"):src.index("def bloklar")], ns)
REF = {20: ns["TEMIZ_19_S20"], 21: ns["TEMIZ_20_S21"]}


def tok(t):
    t = re.sub(r"\[\d+\] Kaynak:.*\n", "", t).replace("•", " ").replace("’", "'")
    return t.split()


def oran(a, b):
    return difflib.SequenceMatcher(None, tok(a), tok(b), autojunk=False).ratio()


PDF = ROOT / "data/8-Baglamdan_bagimsiz_dilbilgisi.pdf"
with pdfplumber.open(PDF) as pdf:
    print("=== (a) #19/#20 sayfalari ===")
    for pn in (16, 18, 19, 20, 21):
        yeni, eski, bilgi = sutunlu_metin(pdf.pages[pn - 1])
        satir = f"sayfa {pn}: bolme={bilgi}"
        if pn in REF:
            satir += f" | referansa benzerlik eski={oran(eski, REF[pn]):.3f} yeni={oran(yeni, REF[pn]):.3f}"
        print(satir)
    for pn in (20, 21):
        yeni, eski, bilgi = sutunlu_metin(pdf.pages[pn - 1])
        print(f"\n--- sayfa {pn} YENI metin ---\n{yeni}\n--- referans ---\n{REF[pn].split(chr(10), 1)[1]}")

    print("\n=== (b) PDF'in tum sayfalari ===")
    tetik, degismeyen, kayip = [], 0, []
    for pn, page in enumerate(pdf.pages, start=1):
        yeni, eski, bilgi = sutunlu_metin(page)
        if bilgi is None:
            assert yeni == eski
            degismeyen += 1
            continue
        a = Counter(c for c in eski if not c.isspace())
        b = Counter(c for c in yeni if not c.isspace())
        if a != b:
            kayip.append((pn, dict((a - b)), dict((b - a))))
        tetik.append((pn, bilgi, len(page.images)))
    print(f"sayfa={len(pdf.pages)} | bolme TETIKLENMEYEN (metin birebir ayni)={degismeyen} | TETIKLENEN={len(tetik)}")
    for pn, b, im in tetik:
        print(f"  tetiklendi: sayfa {pn} {b} resim={im}")
    print("icerik kaybi/cogalmasi olan sayfalar:", kayip or "YOK")

for ad in ("lsarSist-H8_FourierTransform.pdf", "lsarSist-H9_ZTransform.pdf"):
    with pdfplumber.open(ROOT / "data" / ad) as pdf:
        t = [pn for pn, p in enumerate(pdf.pages, start=1) if sutunlu_metin(p)[2] is not None]
        print(f"\n=== (c) {ad}: {len(pdf.pages)} sayfadan {len(t)} tetiklendi: {t}")

print("\n=== (d) SON KURAL (kapili_metin: gecerli sutun + kesen oran<=0.10 + resim yok + PUA yok) ===")
from collections import Counter as _C
from sutun_bol import kapili_metin
import ingest
for ad in ("8-Baglamdan_bagimsiz_dilbilgisi.pdf", "lsarSist-H8_FourierTransform.pdf", "lsarSist-H9_ZTransform.pdf"):
    with pdfplumber.open(ROOT / "data" / ad) as pdf:
        degisen, kayip = [], []
        for pn, page in enumerate(pdf.pages, start=1):
            yeni, bilgi = kapili_metin(page)
            eski = ingest._page_text_with_subscripts(page)
            if bilgi is None:
                assert yeni == eski
                continue
            if _C(c for c in eski if not c.isspace()) != _C(c for c in yeni if not c.isspace()):
                kayip.append(pn)
            degisen.append(pn)
        print(f"{ad}: {len(pdf.pages)} sayfadan DEGISEN={degisen} | icerik kaybi/cogalmasi={kayip or 'YOK'}")
