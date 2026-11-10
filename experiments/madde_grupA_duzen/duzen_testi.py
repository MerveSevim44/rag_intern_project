"""
Grup A / A1 (test_1 #19, #20): sayfa düzeni bozukluğunun etkisini ayırma. src/ ve evaluation/ DEĞİŞMEZ.
Aynı model, üretimle aynı ask() çağrısı. İki koşul:
  orijinal : head_test_1/birlesik.csv'deki context BİREBİR (kontrol — hatayı yeniden üretiyor mu)
  temiz    : yalnız cevabı taşıyan chunk(lar) elle temizlenmiş (iki sütun doğru sıraya konmuş,
             içerik/sözcükler değiştirilmemiş); diğer chunk'lar birebir.
Kullanım (kökten): FOUNDRY_LOCAL_ENDPOINT=... timeout 300 python experiments/madde_grupA_duzen/duzen_testi.py KOSUL N CIKTI.jsonl
"""
import csv, json, os, re, sys, time
from pathlib import Path

os.environ.setdefault("RAG_EMBED_NUM_GPU", "99")
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "evaluation"), str(ROOT / "src"), str(ROOT)]
csv.field_size_limit(10**9)
KOSUL, N, OUT = sys.argv[1], int(sys.argv[2]), Path(sys.argv[3])

TEMIZ_19_S20 = """[1] Kaynak: 8-Baglamdan_bagimsiz_dilbilgisi.pdf, sayfa 20
Örnek 4.7
G4.7=<VN, VT, P, S>
VN= { S, A, B, C, D, E, F }
VT={a, b}
P: S=> B | AC | BS
A=> aA | aF
B=>CF | b
C=> cC | D
D=> C | aD | BD
E=> aA | BSA
F=> bB | b
• (G4.7)’ye eşdeğer; yararsız değişken, simge ve kural içermeyen bir dilbilgisi bulmak için önce (G4.7)’deki değişkenlerden hangilerinin uç simge dizgisi türeten değişkenler olduğunu bulmak gerekir. Uç simge dizgisi türeten değişkenler kümesi algoritma 4.5 ile aşağıdaki gibi bulunur:
• TD = { S, A, B, E, F }
• Yukarıdaki kümede yer almayan C ve D değişkenleri yararsız değişkenlerdir.
"""

TEMIZ_20_S21 = """[2] Kaynak: 8-Baglamdan_bagimsiz_dilbilgisi.pdf, sayfa 21
Örnek 4.7
G’4.7=<VN, VT, P, S>
VN= { S, A, B, C, D, E, F }
VT={a, b}
P: S=> B | BS
A=> aA | aF
B=>b
E=> aA | BSA
F=> bB | b
• Şimdi de (G’4.7)’deki değişkenlerden hangilerinin S’den ulaşılabilen değişkenler olduğunu bulmak gerekir. S’den ulaşılabilen değişkenler kümesi algoritma 4.6 kullanılarak aşağıdaki gibi bulunur:
• TU = { S, B }
• Yukarıdaki kümede yer almayan A, E ve F değişkenleri yararsız değişkenlerdir. Dilbilgisinden bu üç değişken ile bu değişkenlerin yer aldığı kurallar çıkarıldığında a simgesinin de yararsız bir simge olduğu görülür. Bu simge de çıkarıldığında (G4.7)’ye eşdeğer; yararsız simge, değişken ve kural içermeyen aşağıdaki dilbilgisi bulunur:
G”4.7=<VN, VT, P, S>
VN = { S, B }
VT={b}
P: S=> B | BS
B=>b
"""


def bloklar(ctx):
    parcalar = re.split(r"\n\n(?=\[\d+\] Kaynak:)", ctx.strip())
    return parcalar


def temizle(id_, ctx):
    b = bloklar(ctx)
    out = []
    for p in b:
        if id_ == "19" and p.startswith("[1]") and "sayfa 20" in p.split("\n")[0]:
            p = TEMIZ_19_S20.strip()
        if id_ == "20" and p.startswith("[2]") and "sayfa 21" in p.split("\n")[0]:
            p = TEMIZ_20_S21.strip()
        out.append(p)
    return "\n\n".join(out)


def main():
    import run_tests as T
    from llm_client import ask
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    rows = {r["id"]: r for r in csv.DictReader(open(ROOT / "experiments/madde39_tam_kosu/head_test_1/birlesik.csv", encoding="utf-8-sig"))}
    llm = T.load_model()
    for id_ in ("19", "20"):
        r = rows[id_]
        ctx = r["context"] if KOSUL == "orijinal" else temizle(id_, r["context"])
        assert KOSUL == "orijinal" or ctx != r["context"], "temizleme uygulanmadı"
        for i in range(N):
            t = time.time()
            y = ask(llm, ctx, r["soru"])
            k = {"kosul": KOSUL, "id": id_, "tekrar": i + 1, "cevap": y, "sure": round(time.time() - t, 1), "ctx_krk": len(ctx)}
            with open(OUT, "a", encoding="utf-8") as f:
                f.write(json.dumps(k, ensure_ascii=False) + "\n")
            print(json.dumps(k, ensure_ascii=False)[:400], flush=True)


main()
