"""
Madde 22 Adım 2a — yedek kontrolü + gramer PDF'inin yeniden ingest'i + DB doğrulaması.
Plan: docs/implementation_plan_madde22_ornek_cevap.md §3, §5 Adım 2.

1. Ön koşul: rag.db.bak_madde22_2026-10-12 var, 916 chunk, parmak izi f61f7119a6c8.
2. ingest_single_file(gramer PDF'i): eski chunk'ları AYNI transaction'da silip
   yenilerini yazar (planda önce delete_source deniyordu; ayrı silme, ingest
   yarıda kalırsa DB'yi PDF'siz bırakırdı — atomik yol seçildi).
3. Doğrulama (yeni rag.db vs yedek):
   - toplam chunk 911;
   - gramer PDF'i dışındaki 885 chunk: id, içerik, page_info, embedding AYNEN;
   - gramer PDF'inin birleşmeyen 21 sayfası: içerik + page_info aynı (embedding
     yeniden üretildi — sapma ölçülür, madde 29);
   - birleşik 5 chunk: içerik = yedekteki Örnek + "\\n" + Cevap; page_info "sayfa N-M".

Kullanım:
    python -u experiments/madde22_ornek_cevap/adim2_reingest.py
Çıktı: sonuc_adim2_reingest.txt
"""
import hashlib
import json
import math
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]

DB = ROOT / "rag.db"
BACKUP = ROOT / "rag.db.bak_madde22_2026-10-12"
PDF = "data/8-Baglamdan_bagimsiz_dilbilgisi.pdf"
EXPECTED_BACKUP = (916, "f61f7119a6c8")


def fingerprint(path):
    con = sqlite3.connect(path)
    h = hashlib.sha1()
    for row in con.execute("select id, source, content, page_info from chunks order by id"):
        h.update(repr(row).encode())
    n = con.execute("select count(*) from chunks").fetchone()[0]
    con.close()
    return n, h.hexdigest()[:12]


def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    lines = []

    def log(s=""):
        print(s, flush=True)
        lines.append(s)

    fb = fingerprint(BACKUP)
    log(f"Yedek: {BACKUP.name} chunk={fb[0]} parmak_izi={fb[1]}")
    if fb != EXPECTED_BACKUP:
        sys.exit(f"Yedek beklenen durumda degil {fb} != {EXPECTED_BACKUP} — ingest YAPILMADI")
    if fingerprint(DB) != EXPECTED_BACKUP:
        sys.exit("rag.db yedekle ayni degil (zaten degistirilmis?) — ingest YAPILMADI")

    from ingest import ingest_single_file
    n = ingest_single_file(ROOT / PDF, db_path=str(DB))
    log(f"Yeniden ingest: {PDF} -> {n} chunk")

    old = sqlite3.connect(BACKUP)
    new = sqlite3.connect(DB)
    total = new.execute("select count(*) from chunks").fetchone()[0]
    log(f"\nToplam chunk: {total} (beklenen 911) -> {'OK' if total == 911 else 'FARKLI'}")

    q_other = "select id, source, content, page_info, embedding from chunks where source != ? order by id"
    o_rows, n_rows = old.execute(q_other, (PDF,)).fetchall(), new.execute(q_other, (PDF,)).fetchall()
    log(f"Gramer PDF'i disi chunk'lar: {len(n_rows)} — id/icerik/page_info/embedding ayni: {o_rows == n_rows}")

    o_pdf = {p: (t, json.loads(e)) for t, p, e in old.execute(
        "select content, page_info, embedding from chunks where source=? order by id", (PDF,))}
    n_pdf = [(t, p, json.loads(e)) for t, p, e in new.execute(
        "select content, page_info, embedding from chunks where source=? order by id", (PDF,))]
    log(f"\nGramer PDF'i: yedekte {len(o_pdf)}, yeni {len(n_pdf)} chunk")
    cos_plain, diff_plain = [], 0
    for text, page, emb in n_pdf:
        if "-" in page:
            a, b = page.split()[1].split("-")
            exp = f"{o_pdf[f'sayfa {a}'][0]}\n{o_pdf[f'sayfa {b}'][0]}"
            log(f"   {page:12} birlesik  icerik=Ornek+Cevap: {'AYNI' if text == exp else 'FARKLI'}")
        else:
            same = page in o_pdf and o_pdf[page][0] == text
            c = cosine(emb, o_pdf[page][1]) if page in o_pdf else float("nan")
            cos_plain.append(c)
            diff_plain += not same
            if not same or c < 0.99999:
                log(f"   {page:12} icerik={'AYNI' if same else 'FARKLI'} embedding cosine={c:.6f}")
    log(f"   birlesmeyen {len(cos_plain)} sayfa: icerigi farkli {diff_plain}, embedding cosine "
        f"min={min(cos_plain):.6f} max={max(cos_plain):.6f} (yeniden embed edildi)")
    log(f"\nYeni rag.db parmak izi: {fingerprint(DB)}")
    (HERE / "sonuc_adim2_reingest.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
