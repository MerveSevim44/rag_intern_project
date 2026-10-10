"""
make_stopword_gt.py — test_stopword setini ve ground truth'unu 728_profiles.json'dan üretir.

Backlog madde 19: Snowball stemmer bazı içerik kelimelerini stopword stem'ine
indiriyor ("deneyim" -> "de", "ön" -> "on", "Damla" -> "da") ve BM25 bunları
siliyor. Mevcut 115 soruluk set alan adlarıyla yazıldığı için bu hatayı
neredeyse hiç sınamıyor. Bu set alan adı İÇERMEYEN doğal sorulardan oluşur;
her soruda ayırt edici terim, düşen kelimenin kendisidir.

Ground truth elle YAZILMAZ: her soru bir filtre ile tanımlanır, cevap ve
hedef profiller veriden hesaplanır. Böylece veri değişirse set yeniden
üretilebilir ve cevabın nereden geldiği izlenebilir ("turetme" alanı).

Çıktılar:
    evaluation/datasets/test_stopword.csv
    evaluation/ground_truth/test_stopword.json

Ek ground truth alanları (benchmark_eval bunları yok sayar):
    dusen_kelimeler        : soruda BM25'ten düşen içerik kelimeleri
    turetme                : cevabın üretildiği filtre (okunabilir)
    hedef_profiller        : filtreyle eşleşen profillerin chunk yolu ($.profiles[i])
    karistirici_profiller  : aynı soyadını taşıyan BAŞKA kişiler (yalnız isim
                             sorularında) — "yanlış kişi karışıyor mu" ölçümü için

Kullanım:
    python evaluation/make_stopword_gt.py
"""

import csv
import json
import sys
from pathlib import Path

_eval_dir = Path(__file__).resolve().parent
_root_dir = _eval_dir.parent
DATA_FILE = _root_dir / "data" / "728_profiles.json"
CSV_OUT = _eval_dir / "datasets" / "test_stopword.csv"
GT_OUT = _eval_dir / "ground_truth" / "test_stopword.json"
SOURCE = "728_profiles.json"
FIRST_ID = 301  # ground_truth/ altında id'ler benzersiz olmalı (1-115, 201-232 dolu)


def services(p):
    return [s["name"] for s in p.get("services", [])]


def by_name(name):
    return lambda p: p["displayName"] == name


def has_service(name):
    return lambda p: name in services(p)


# Her kayıt: soru, zorluk, düşen kelimeler, filtre, filtre açıklaması,
# cevap çıkarıcı (eşleşen profiller -> cevap öğeleri), isim sorusu mu.
QUESTIONS = [
    ("Damla Akın hangi şehirde hizmet veriyor?", "Kolay", ["damla"],
     by_name("Damla Akın"), 'displayName == "Damla Akın" -> location.city',
     lambda ps: sorted({p["location"]["city"] for p in ps}), True),
    ("Deniz Akın'ın mesleği nedir?", "Kolay", ["deniz"],
     by_name("Deniz Akın"), 'displayName == "Deniz Akın" -> occupation',
     lambda ps: sorted({p["occupation"] for p in ps}), True),
    ("Deniz Çelik hangi hizmetleri sunuyor?", "Kolay", ["deniz"],
     by_name("Deniz Çelik"), 'displayName == "Deniz Çelik" -> services[].name',
     lambda ps: sorted({s for p in ps for s in services(p)}), True),
    ("Ön değerlendirme hizmeti hangi meslekteki uzmanlar tarafından veriliyor?", "Orta", ["ön"],
     has_service("Ön değerlendirme"), '"Ön değerlendirme" in services[].name -> occupation',
     lambda ps: sorted({p["occupation"] for p in ps}), False),
    ("Çekim ön görüşmesi yapan uzmanlar hangi meslekten?", "Orta", ["ön"],
     has_service("Çekim ön görüşmesi"), '"Çekim ön görüşmesi" in services[].name -> occupation',
     lambda ps: sorted({p["occupation"] for p in ps}), False),
    ("İş modeli görüşmesi sunan danışmanların mesleği nedir?", "Kolay", ["iş"],
     has_service("İş modeli görüşmesi"), '"İş modeli görüşmesi" in services[].name -> occupation',
     lambda ps: sorted({p["occupation"] for p in ps}), False),
    ("İç mimarlar hangi hizmetleri sunuyor?", "Orta", ["iç", "ön"],
     lambda p: p["occupation"] == "İç Mimar", 'occupation == "İç Mimar" -> services[].name',
     lambda ps: sorted({s for p in ps for s in services(p)}), False),
    ("Aracın iç detay temizliğini hangi uzman yapıyor?", "Kolay", ["iç"],
     has_service("İç detay temizlik"), '"İç detay temizlik" in services[].name -> occupation',
     lambda ps: sorted({p["occupation"] for p in ps}), False),
    ("Çevrim içi Türkçe dersi veren eğitmenlerin mesleği nedir?", "Kolay", ["içi"],
     lambda p: "çevrim içi" in p.get("headline", ""), '"çevrim içi" in headline -> occupation',
     lambda ps: sorted({p["occupation"] for p in ps}), False),
    ("Vatandaş danışma birimi hangi hizmetleri veriyor?", "Orta", ["birimi", "ön"],
     lambda p: p["occupation"] == "Vatandaş Danışma Birimi",
     'occupation == "Vatandaş Danışma Birimi" -> services[].name',
     lambda ps: sorted({s for p in ps for s in services(p)}), False),
    ("Öğrenci işleri görüşmesi hangi danışma biriminde sunuluyor?", "Kolay", ["işleri"],
     has_service("Öğrenci işleri görüşmesi"), '"Öğrenci işleri görüşmesi" in services[].name -> occupation',
     lambda ps: sorted({p["occupation"] for p in ps}), False),
    ("Girişimcilik ve iş geliştirme deneyimi olan uzmanlar hangi meslekte?", "Orta", ["iş", "deneyim"],
     lambda p: "Girişimcilik ve iş geliştirme" in p["experience"].get("credentialSummary", ""),
     '"Girişimcilik ve iş geliştirme" in experience.credentialSummary -> occupation',
     lambda ps: sorted({p["occupation"] for p in ps}), False),
]


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    profiles = json.loads(DATA_FILE.read_text(encoding="utf-8"))["profiles"]

    gt, csv_rows = {}, []
    for offset, (soru, zorluk, dusen, filt, turetme, extract, is_name) in enumerate(QUESTIONS):
        qid = str(FIRST_ID + offset)
        matched = [(i, p) for i, p in enumerate(profiles) if filt(p)]
        if not matched:
            sys.exit(f"#{qid} filtresi hiçbir profille eşleşmedi: {turetme}")
        items = extract([p for _, p in matched])

        confusers = []
        if is_name:
            first, surname = soru.split()[0], soru.split()[1].split("'")[0]
            target_name = f"{first} {surname}"
            confusers = [f"$.profiles[{i}]" for i, p in enumerate(profiles)
                         if p["displayName"].split()[-1] == surname and p["displayName"] != target_name]

        gt[qid] = {
            "soru": soru,
            "zorluk": zorluk,
            "beklenen_kaynak": SOURCE,
            "dokumanda_var_mi": "Evet",
            "referans_cevaplar": [", ".join(items)] + (items if len(items) > 1 else []),
            "anahtar_kelimeler": items,
            "dusen_kelimeler": dusen,
            "turetme": turetme,
            "hedef_profiller": [f"$.profiles[{i}]" for i, _ in matched],
            "karistirici_profiller": confusers,
        }
        csv_rows.append([qid, zorluk, soru, SOURCE, "Evet"])
        print(f"#{qid} {len(matched):3} profil -> {items}"
              + (f" | karıştırıcı: {len(confusers)}" if is_name else ""))

    with open(CSV_OUT, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "zorluk", "soru", "beklenen_kaynak", "dokumanda_var_mi"])
        writer.writerows(csv_rows)
    GT_OUT.write_text(json.dumps(gt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\nYazıldı: {CSV_OUT.relative_to(_root_dir)}, {GT_OUT.relative_to(_root_dir)}")


if __name__ == "__main__":
    main()
