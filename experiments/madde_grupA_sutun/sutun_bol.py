"""
A1 (#19/#20) otomatik sutun-farkindalikli metin cikarma DENEMESI. src/ DEGISMEZ.
ingest._order_ocr_lines'in (dikey split ara + sol/sag ayir, tam genislikli kutular bolum ayraci) mantigi, OCR kutulari
yerine metin katmanindaki char bbox'larina uyarlandi. Alt-indis yapistirma (ingest._page_text_with_subscripts) AYNEN
kullanilir: onun yapistirdigi char listesi yakalanip sutunlara bolunur.
Fark: OCR kutusu tek parca oldugu icin "x0<x<x1" kesisimi yetiyordu; metin katmaninda tam genislikli bir satir cok
sayida kucuk char'dir, bu yuzden SATIR (top kumesi) duzeyinde "bu satir kesme noktasindan geciyor mu" bakilir:
satirda her iki tarafta char var VE aradaki bosluk < GAP ise (ya da bir char kesme noktasini kesiyorsa) satir tam
genislikli sayilir.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src")]
from pdfplumber.utils import cluster_objects, extract_text  # noqa: E402
import ingest  # noqa: E402

GAP = 12.0          # pt; iki sutun arasi asgari bosluk
MIN_YAN_SATIR = 3   # her sutunda en az bu kadar satir
MIN_YAN_YANA = 2    # yan yana (ayni top kumesinde iki sutun) en az bu kadar satir


def _yakala(page):
    """ingest'in alt-indis yapistirmasindan sonra pdfplumber'a verdigi char listesini ve orijinal metni dondurur."""
    kayit = {}
    orj = ingest.pdfplumber_extract_text

    def sar(chars, *a, **k):
        kayit["chars"] = chars
        return orj(chars, *a, **k)

    ingest.pdfplumber_extract_text = sar
    try:
        metin = ingest._page_text_with_subscripts(page)
    finally:
        ingest.pdfplumber_extract_text = orj
    return kayit.get("chars"), metin


def _satir_durumu(satir, x):
    """'gecen' | 'sol' | 'sag' | 'yan' (iki sutun yan yana, aralarinda >=GAP bosluk) | 'bos'"""
    harf = [c for c in satir if c["text"].strip()]
    if not harf:
        return "bos"
    sol = [c for c in harf if c["x1"] <= x]
    sag = [c for c in harf if c["x0"] >= x]
    kes = [c for c in harf if c["x0"] < x < c["x1"]]
    if kes:
        return "gecen"
    if sol and sag:
        bosluk = min(c["x0"] for c in sag) - max(c["x1"] for c in sol)
        return "yan" if bosluk >= GAP else "gecen"
    return "sol" if sol else "sag"


def bolme_noktasi(satirlar, width):
    """30-70 yuzdelerinde en az 'gecen' satir birakan x; gecerlilik kosullari yukarida. (x, ozet) ya da None."""
    aday = {}
    for pct in range(30, 71):
        x = width * pct / 100
        d = [_satir_durumu(s, x) for s in satirlar]
        sol, sag, yan, gecen = d.count("sol") + d.count("yan"), d.count("sag") + d.count("yan"), d.count("yan"), d.count("gecen")
        if sol >= MIN_YAN_SATIR and sag >= MIN_YAN_SATIR and yan >= MIN_YAN_YANA:
            aday[pct] = gecen
    if not aday:
        return None
    en_az = min(aday.values())
    pcts = sorted(p for p, v in aday.items() if v == en_az)
    pct = pcts[len(pcts) // 2]
    return width * pct / 100, {"pct": pct, "gecen": en_az, "aralik": (pcts[0], pcts[-1]), "satir": len(satirlar)}


def sutunlu_metin(page, max_gecen_orani=None):
    """(yeni_metin, orijinal_metin, bilgi). Sutun bulunamazsa (ya da kapi reddederse) yeni_metin == orijinal_metin.
    max_gecen_orani: tam genislikli (kesen) satirlarin toplam satira orani bu degerden buyukse bolme YAPILMAZ."""
    chars, orijinal = _yakala(page)
    if not chars:
        return orijinal, orijinal, None
    satirlar = sorted(cluster_objects(chars, lambda c: c["top"], 3), key=lambda s: min(c["top"] for c in s))
    bul = bolme_noktasi(satirlar, page.width)
    if bul is None:
        return orijinal, orijinal, None
    x, bilgi = bul
    if max_gecen_orani is not None and bilgi["gecen"] / bilgi["satir"] > max_gecen_orani:
        bilgi = dict(bilgi, reddedildi=True)
        return orijinal, orijinal, bilgi
    cikti, sol, sag = [], [], []

    def bosalt():
        for grup in (sol, sag):
            if grup:
                cikti.append(extract_text(grup) or "")
        sol.clear(); sag.clear()

    for s in satirlar:
        d = _satir_durumu(s, x)
        if d == "gecen":
            bosalt()
            cikti.append(extract_text(s) or "")
        else:
            for c in s:
                (sol if (c["x0"] + c["x1"]) / 2 < x else sag).append(c)
    bosalt()
    return "\n".join(t for t in cikti if t), orijinal, bilgi


def kapili_metin(page):
    """Son kural: bolme yalniz (1) gecerli sutun bulunur, (2) kesen satir orani <= 0.10, (3) sayfada resim nesnesi yok,
    (4) sayfada PUA (U+F0xx, Symbol-font) karakteri yok ise uygulanir. Aksi halde ingest'in mevcut metni aynen doner."""
    if page.images or any(0xF000 <= ord(c["text"][0]) <= 0xF0FF for c in page.chars if c["text"]):
        return ingest._page_text_with_subscripts(page), None
    yeni, eski, bilgi = sutunlu_metin(page, 0.10)
    return yeni, (None if bilgi is None or bilgi.get("reddedildi") else bilgi)
