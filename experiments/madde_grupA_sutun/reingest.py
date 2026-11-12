"""
A1: GERCEK rag.db'de yalniz CFG PDF'inin yedekli yerinde yeniden ingest'i (backlog A1 entegrasyon notu).
Adimlar: (b) rag.db.bak_a1_<tarih> yedegi (ozet kontrollu), (c) ingest_single_file(CFG), ardindan dogrulama:
CFG disindaki tum satirlar yedekle birebir ayni mi, CFG'de yalniz sayfa 13/20/21 metni mi degisti, yeni DB ozeti.
Kullanim (kokten): python -u experiments/madde_grupA_sutun/reingest.py
Onkosul: rag.db'yi kimse kullanmiyor (Streamlit kapali), Ollama (bge-m3) acik; Foundry servisi bellek icin durdurulur.
"""
import hashlib, importlib.util, json, os, shutil, sqlite3, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CFG = "8-Baglamdan_bagimsiz_dilbilgisi.pdf"
BEKLENEN_ESKI_OZET = "757e97059abb"
YEDEK = ROOT / f"rag.db.bak_a1_{time.strftime('%Y-%m-%d')}"

spec = importlib.util.spec_from_file_location("kosu", ROOT / "experiments/madde39_tam_kosu/kosu.py")
kosu = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kosu)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
os.environ.update(kosu.ORTAM)
sys.path[:0] = [str(ROOT / "src")]


def ozet(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()[:12]


def satirlar(db, where="1=1", args=()):
    con = sqlite3.connect(db)
    try:
        return con.execute(f"SELECT source, content, page_info, embedding FROM chunks WHERE {where} ORDER BY source, id", args).fetchall()
    finally:
        con.close()


assert ozet(ROOT / "rag.db") == BEKLENEN_ESKI_OZET, f"rag.db ozeti beklenenden farkli: {ozet(ROOT / 'rag.db')}"
assert not YEDEK.exists(), f"yedek zaten var: {YEDEK}"

# servisler: Foundry bellek icin dursun, Ollama saglikli olsun
kosu.komut_sessiz(["foundry", "service", "stop"], timeout=60)
time.sleep(3)
ram = kosu.bos_ram_gb()
assert ram >= kosu.MIN_BOS_RAM_GB, f"bos RAM {ram:.1f} GB yetersiz"
if not kosu.ollama_saglikli():
    kosu.ollama_yeniden_baslat()
    assert kosu.ollama_saglikli(), "Ollama embed istegine yanit vermiyor"

# (b) yedek
shutil.copy2(ROOT / "rag.db", YEDEK)
assert ozet(YEDEK) == BEKLENEN_ESKI_OZET
print(f"yedek: {YEDEK.name} ozet={ozet(YEDEK)} bos_ram={ram:.2f} GB", flush=True)

# (c) yalniz CFG yeniden ingest
import ingest
bas = time.time()
n = ingest.ingest_single_file(ROOT / "data" / CFG, db_path=str(ROOT / "rag.db"), num_gpu=99)
print(f"yeniden ingest: {n} chunk, {time.time() - bas:.0f} sn", flush=True)

# dogrulama
cfg_where = ("source = ?", (f"data/{CFG}",))
digerleri = ("source != ?", (f"data/{CFG}",))
eski_cfg, yeni_cfg = satirlar(YEDEK, *cfg_where), satirlar(ROOT / "rag.db", *cfg_where)
degisen = [yeni_cfg[i][2] for i in range(min(len(eski_cfg), len(yeni_cfg))) if eski_cfg[i][:3] != yeni_cfg[i][:3]]
rapor = {
    "yedek": YEDEK.name, "eski_ozet": BEKLENEN_ESKI_OZET, "yeni_ozet": ozet(ROOT / "rag.db"),
    "cfg_chunk_eski_yeni": [len(eski_cfg), len(yeni_cfg)],
    "cfg_metni_degisen_sayfalar": degisen,
    "cfg_disi_satirlar_yedekle_birebir_ayni": satirlar(YEDEK, *digerleri) == satirlar(ROOT / "rag.db", *digerleri),
    "toplam_chunk_yedek_yeni": [len(satirlar(YEDEK)), len(satirlar(ROOT / "rag.db"))],
    "ollama_cpu_yuklemeleri": kosu.ollama_cpu_yuklemeleri(bas),
}
print(json.dumps(rapor, ensure_ascii=False, indent=1))
(ROOT / "experiments/madde_grupA_sutun/entegrasyon/reingest.json").write_text(json.dumps(rapor, ensure_ascii=False, indent=1), encoding="utf-8")
