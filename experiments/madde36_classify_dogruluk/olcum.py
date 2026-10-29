"""
Madde 36 — classify_answer'ın TP/FN/TN/FP etiketi gerçek doğrulukla ne sıklıkla çelişiyor?

Küme: madde 32 Adım 2 (uretim_n{0,0_tekrar11,1,3,5}) + madde 33 Adım 1 (#91 oracle'ları)
cevapları; tekil (set, id, cevap) çiftleri -> ciftler.json (73 çift, 45 soru).
Sınıf GÜNCEL GT ile (#214 düzeltmesi sonrası) hesaplandı.

Doğruluk etiketi ELLE (2026-10-29, tek değerlendirici: Claude), soru + GT referansıyla:
  D doğru | K kısmen (çekirdek kısmen doğru / eksik / içinde yanlış iddia) | Y yanlış
  R ret (cevap yok) | B bozuk (yarım cümle, iddia yok)
Çelişki tanımı:
  pozitif soru, TP ama Y           -> "TP ama yanlış"   (TP doğruluk değil)
  pozitif soru, FN ama D/K         -> "FN ama cevap var"
  negatif soru, FP ama R/B         -> "FP ama uydurma yok"
  negatif soru, TN ama Y           -> "TN ama uydurma var"

Kullanım (kökten): python experiments/madde36_classify_dogruluk/olcum.py
Çıktı: degerlendirme.json, sonuc_olcum.txt
"""
import json
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent

# ciftler.json indeksine göre elle değerlendirme (gerekçeler README'de)
J = {0: "D", 1: "K", 2: "D", 3: "D", 4: "Y", 5: "K", 6: "Y", 7: "K", 8: "K", 9: "Y", 10: "D", 11: "D",
     12: "D", 13: "K", 14: "K", 15: "K", 16: "Y", 17: "K", 18: "D", 19: "Y", 20: "Y", 21: "K", 22: "K",
     23: "K", 24: "K", 25: "R", 26: "Y", 27: "Y", 28: "D", 29: "K", 30: "D", 31: "R", 32: "D", 33: "D",
     34: "R", 35: "K", 36: "Y", 37: "Y", 38: "Y", 39: "Y", 40: "R", 41: "D", 42: "K", 43: "Y", 44: "D",
     45: "D", 46: "Y", 47: "Y",
     48: "Y", 49: "R", 50: "R", 51: "R", 52: "R", 53: "R", 54: "R", 55: "R",
     56: "R", 57: "D", 58: "D", 59: "K",
     60: "R", 61: "R", 62: "R", 63: "R", 64: "R", 65: "B", 66: "R", 67: "R", 68: "Y", 69: "R", 70: "R",
     71: "R", 72: "Y"}


def main():
    c = json.load(open(HERE / "ciftler.json", encoding="utf-8"))
    assert len(J) == len(c), (len(J), len(c))
    for i, o in enumerate(c):
        o["dogruluk"] = J[i]
    json.dump(c, open(HERE / "degerlendirme.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    pos = [o for o in c if not o["negatif"]]
    neg = [o for o in c if o["negatif"]]
    L = [f"Küme: {len(c)} tekil çift, {len({(o['set'], o['id']) for o in c})} soru "
         f"(pozitif {len(pos)} çift, negatif {len(neg)} çift)", ""]

    def tablo(grup, ad):
        t = defaultdict(Counter)
        for o in grup:
            t[o["sinif"]][o["dogruluk"]] += 1
        L.append(f"{ad}: sınıf -> elle doğruluk")
        for s in sorted(t):
            L.append(f"  {s} ({sum(t[s].values())}): " + ", ".join(f"{k}={v}" for k, v in sorted(t[s].items())))
        return t

    tp = tablo(pos, "Pozitif")
    tn = tablo(neg, "Negatif")
    cel = {
        "TP ama yanlış": [o for o in pos if o["sinif"] == "TP" and o["dogruluk"] == "Y"],
        "FN ama cevap var": [o for o in pos if o["sinif"] == "FN" and o["dogruluk"] in "DK"],
        "FP ama uydurma yok": [o for o in neg if o["sinif"] == "FP" and o["dogruluk"] in "RB"],
        "TN ama uydurma var": [o for o in neg if o["sinif"] == "TN" and o["dogruluk"] == "Y"],
    }
    L += ["", "Çelişkiler:"]
    for k, v in cel.items():
        L.append(f"  {k}: {len(v)}" + (" -> " + ", ".join(f"{o['set']}#{o['id']}({'/'.join(o['kos'])})" for o in v) if v else ""))
    n_tp = sum(tp["TP"].values())
    L.append(f"\nTP içinde: doğru {tp['TP']['D']}/{n_tp}, kısmen {tp['TP']['K']}/{n_tp}, "
             f"yanlış {tp['TP']['Y']}/{n_tp} (%{100 * tp['TP']['Y'] / n_tp:.0f})")

    # Madde 32 Adım 2: "TP->TP, yan etki yok" iddiası doğrulukta da geçerli mi?
    sira = {"Y": 0, "K": 1, "D": 2}
    by_q = defaultdict(dict)
    for o in pos:
        for k in o["kos"]:
            if k.startswith("m32_N") and k != "m32_N0":
                by_q[(o["set"], o["id"])][k[4:]] = o
            if k in ("m32_N0", "m32_N0_tekrar11"):
                if o["cevap"].startswith("HATA"):
                    continue
                by_q[(o["set"], o["id"])].setdefault("N0", o)
                if k == "m32_N0_tekrar11":
                    by_q[(o["set"], o["id"])]["N0"] = o
    L += ["", "Madde 32 Adım 2 — sınıfı TP->TP kalan pozitiflerde doğruluk değişimi (N0'a göre):"]
    for n in ("N1", "N3", "N5"):
        kotu, iyi = [], []
        for q, d in sorted(by_q.items()):
            if n in d and "N0" in d and d["N0"]["sinif"] == "TP" and d[n]["sinif"] == "TP":
                a, b = d["N0"]["dogruluk"], d[n]["dogruluk"]
                if sira[b] < sira[a]:
                    kotu.append(f"{q[0]}#{q[1]} {a}->{b}")
                elif sira[b] > sira[a]:
                    iyi.append(f"{q[0]}#{q[1]} {a}->{b}")
        L.append(f"  {n}: kötüleşen {len(kotu)} {kotu} | iyileşen {len(iyi)} {iyi}")

    text = "\n".join(L) + "\n"
    (HERE / "sonuc_olcum.txt").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
