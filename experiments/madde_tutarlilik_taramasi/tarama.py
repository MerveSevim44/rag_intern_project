"""
Deterministik tutarlilik/groundedness taramasi — TASARIM + PILOT (henuz 94 soruda calistirilmadi).

Amac: LLM judge kullanmadan, final cevaptaki somut degerlerin (sayi, oran, isim) sentezleyiciye
giden HAM BAGLAMDA gercekten var olup olmadigini ucuza taramak. madde 41/38'deki vakalari (#53,
#82/#83/#85/#89 ailesi) elle bulduğumuz yontemi genellestirir. evaluation/ ve src/ DEGISMEZ;
yalnizca experiments/madde39_tam_kosu/head_<set>/birlesik.csv (veya sonuclari.csv) okunur.

Tasarim notlari (talep edilen 4 nokta):

1. Ham baglam kaynagi: EK INSTRUMENTASYON GEREKMEZ. birlesik.csv'nin "context" sutunu her iki
   yol icin de zaten dolu:
   - semantik RAG: retrieval chunk'larinin ham metni ("[1] Kaynak: ...").
   - code_interpreter: sandbox'in "[KESIN HESAPLAMA SONUCU]" ile baslayan DOGAL DIL ozeti.
   SINIRLAMA: code_interpreter yolunda bu ozet, result_to_natural_language'in CIKTISIDIR —
   sandbox'in ham sozluk/sayisal sonucu degil (madde 41: bu adim zaten "bulaniklastirici").
   Yani bu tarama code_interpreter sorularinda "ask()'in ozeti otesine gecip yeni deger
   uydurdugu mu" sorusunu yanitlar; "ozetin kendisi orijinal hesaptan sapti mi" sorusunu
   YANITLAMAZ (bunun icin sandbox print/log yakalama gerekir — kapsam disi, asagida not).

2. Somut deger cikarimi:
   - SAYI: regex ile tamsayi/ondalik/yuzde ("12", "4.5", "%30", "30%"), kelime sinirinda
     (alfanumerik kod icine gommulu degilse — "DB-ZD5HGKSC" icindeki "5" YAKALANMAZ).
   - OZEL AD: ardisik 2+ Baslik-Harfli kelime (Turkce karakter farkindaligiyla), kucuk bir
     "cumlebasi" engelleme listesiyle (Bu, Su, Ancak, Daha, Sonra, ...).
   - Kategorik alan: v1'de KAPSAM DISI — alan listesi soru setine ozel, genellestirmek ayri
     bir is; not olarak birakildi (asagida "Sinirlar").

3. Eslesme kriteri (sayilar icin):
   - BIREBIR: normalize edilmis sayi (virgul/nokta esitlenir, % ayri) baglam metninde
     birebir geciyor mu.
   - TURETILMIS: birebir yoksa, baglamdaki sayi ciftlerinin toplam/fark/oran/yuzde-fark
     kombinasyonlarindan (tolerans ±0.5 mutlak VEYA ±%1 bagil) uretilebiliyor mu. Bu adim
     YANLIS POZITIFI (hesaplanmis ama dogru degeri "uydurma" sanma) azaltmak icin var.
   - Ikisi de yoksa "supheli". Ayrica 0/1/2/3/100/%100/%0 gibi cok genel sayilar "dusuk_oncelik"
     supheli olarak ayri etiketlenir (bunlar heryerde tesadufen gecebilir, agirlikli sayilmaz).
   - OZEL AD icin yalnizca BIREBIR (case/Turkce-karakter normalize) alt-dize eslesmesi —
     turetme kavrami isim icin yok.
   - Satir duzeyi karar: en az bir YUKSEK-ONCELIK supheli deger varsa satir "SUPHELI";
     yalnizca dusuk_oncelik varsa "ZAYIF_SUPHELI"; hicbiri yoksa "TEMIZ".

4. Pilot: asagida calistirilir (bu dosyanin sonunda), 94 soruya cikmadan once.

Kullanim (kokten): python experiments/madde_tutarlilik_taramasi/tarama.py pilot
"""
import csv
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HEAD = ROOT / "experiments" / "madde39_tam_kosu"
csv.field_size_limit(10**9)

SAYI_RE = re.compile(r"(?<![\w.,])(\d+(?:[.,]\d+)?)\s*(%)?(?!\w)")
AD_RE = re.compile(r"\b([A-ZÇĞİÖŞÜ][a-zçğıöşü]+(?:\s+[A-ZÇĞİÖŞÜ][a-zçğıöşü]+)+)\b")
CUMLEBASI = {"Bu", "Su", "Ancak", "Daha", "Sonra", "Ilk", "İlk", "Her", "Tum", "Tüm", "Eger", "Eğer",
             "Ayrica", "Ayrıca", "Boylece", "Böylece", "Dolayisiyla", "Dolayısıyla", "Ornegin", "Örneğin"}
DUSUK_ONCELIK = {"0", "1", "2", "3", "100"}


def normalize(s):
    s = s.replace(",", ".")
    return unicodedata.normalize("NFKD", s.lower()).encode("ascii", "ignore").decode()


def sayilari_cikar(metin):
    out = []
    for m in SAYI_RE.finditer(metin or ""):
        deger, yuzde = m.group(1), bool(m.group(2))
        out.append((deger.replace(",", "."), yuzde))
    return out


def adlari_cikar(metin):
    out = set()
    for m in AD_RE.finditer(metin or ""):
        ad = m.group(1)
        ilk = ad.split()[0]
        if ilk not in CUMLEBASI:
            out.add(ad)
    return out


def birebir_var_mi(deger, baglam_norm):
    return normalize(deger) in baglam_norm


def turetilmis_mi(deger, baglam_sayilar, tol_abs=0.5, tol_rel=0.01):
    try:
        v = float(deger)
    except ValueError:
        return False
    vals = []
    for d, _ in baglam_sayilar:
        try:
            vals.append(float(d))
        except ValueError:
            pass
    for i, a in enumerate(vals):
        for b in vals[i + 1:]:
            kombinasyonlar = [a + b, abs(a - b), a - b]
            if b:
                kombinasyonlar += [a / b * 100, (a - b) / b * 100]
            for k in kombinasyonlar:
                if abs(k - v) <= max(tol_abs, tol_rel * abs(v)):
                    return True
    return False


def satiri_tara(soru, cevap, baglam):
    baglam_norm = normalize(baglam or "")
    baglam_sayilar = sayilari_cikar(baglam)
    sonuc = {"sayi_supheli_yuksek": [], "sayi_supheli_dusuk": [], "ad_supheli": []}
    for deger, yuzde in sayilari_cikar(cevap):
        if birebir_var_mi(deger, baglam_norm):
            continue
        if turetilmis_mi(deger, baglam_sayilar):
            continue
        hedef = "sayi_supheli_dusuk" if deger in DUSUK_ONCELIK else "sayi_supheli_yuksek"
        sonuc[hedef].append(deger + ("%" if yuzde else ""))
    for ad in adlari_cikar(cevap):
        if normalize(ad) not in baglam_norm:
            sonuc["ad_supheli"].append(ad)
    if sonuc["sayi_supheli_yuksek"] or sonuc["ad_supheli"]:
        karar = "SUPHELI"
    elif sonuc["sayi_supheli_dusuk"]:
        karar = "ZAYIF_SUPHELI"
    else:
        karar = "TEMIZ"
    return karar, sonuc


def satiri_oku(set_adi, id_):
    yol = HEAD / f"head_{set_adi}" / "birlesik.csv"
    if not yol.exists():
        yol = HEAD / f"head_{set_adi}" / "sonuclari.csv"
    with open(yol, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if r["id"] == id_:
                return r
    raise KeyError((set_adi, id_))


# --- PILOT: bilinen 10 soru, beklenen etiketle karsilastirma icin ---
PILOT = [
    ("test_2", "43", "bilinen_dogru"),      # madde11 notu: pandas ile dogrulandi
    ("test_2", "53", "bilinen_yanlis"),     # madde11/41: Sinem iptal 4 / gercek 12 vb.
    ("test_4", "91", "bilinen_dogru"),      # madde33: "Gumus Yaprak", TP
    ("test_3", "82", "bilinen_yanlis"),     # madde38 ornek2: carpim/toplama karistirma
    ("test_3", "83", "bilinen_yanlis"),     # ayni aile: Y=F+F yerine 1/2F+1/2F
    ("test_3", "85", "bilinen_yanlis"),     # 2pi carpani kaybi
    ("test_3", "89", "bilinen_yanlis"),     # ayni modulasyon, katsayi kaybi
    ("test_3", "78", "bilinen_kavramsal"),  # kendi icinde celisen cumle — SAYISAL degil
    ("test_3", "87", "bilinen_kavramsal"),  # tanim hatasi — SAYISAL degil
]


def pilot():
    print(f"{'set':8} {'id':4} {'beklenen':16} {'KARAR':14} detay")
    for s, i, beklenen in PILOT:
        r = satiri_oku(s, i)
        karar, detay = satiri_tara(r["soru"], r["cevap"], r["context"])
        print(f"{s:8} {i:4} {beklenen:16} {karar:14} {detay}")


if __name__ == "__main__":
    mod = sys.argv[1] if len(sys.argv) > 1 else "pilot"
    if mod == "pilot":
        pilot()
