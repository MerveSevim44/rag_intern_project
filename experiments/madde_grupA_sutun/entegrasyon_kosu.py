"""
A1 entegrasyon dogrulamasi (src/ingest.py'deki GERCEK sutun-bolme kodu). Uretim rag.db'ye DOKUNMAZ.
  hazirla : (1) rag.db'deki uc PDF chunk'lari HEAD ingest'iyle tutarli mi; (2) uc PDF'i GERCEK yeni kodla TEMIZ bir
            gecici DB'ye yeniden ingest et, rag.db satirlariyla karsilastir (kac chunk degisti, hangi sayfa);
            (3) rag.db'nin kopyasinda YALNIZ CFG PDF'ini yeniden ingest et (tedavi agaci; tek degisken)
  kos     : kontrol (uretim rag.db) ve islem (yalniz CFG yeniden ingest) icin test_1'in TUM sorulari, ayni ortam
Kullanim (kokten): python -u experiments/madde_grupA_sutun/entegrasyon_kosu.py hazirla|kos
Ortam, kosu.py ile ayni (madde 39): RAG_EMBED_NUM_GPU=99, RAG_DENSE_FORCE_TOP_N=0; Foundry/Ollama yonetimi kosu.py'den.
"""
import importlib.util, json, os, shutil, sqlite3, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / "entegrasyon"
TREE = Path(os.environ.get("A1_TREE", r"C:\Users\merve\AppData\Local\Temp\a1_tree"))
CFG = "8-Baglamdan_bagimsiz_dilbilgisi.pdf"
PDFS = [CFG, "lsarSist-H8_FourierTransform.pdf", "lsarSist-H9_ZTransform.pdf"]

spec = importlib.util.spec_from_file_location("kosu", ROOT / "experiments/madde39_tam_kosu/kosu.py")
kosu = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kosu)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def servisleri_hazirla(foundry_dursun):
    if foundry_dursun:
        kosu.komut_sessiz(["foundry", "service", "stop"], timeout=60)
        time.sleep(3)
    ram = kosu.bos_ram_gb()
    if ram < kosu.MIN_BOS_RAM_GB:
        sys.exit(f"Bos RAM {ram:.1f} GB < {kosu.MIN_BOS_RAM_GB}; baslatilmadi")
    if not kosu.ollama_saglikli():
        kosu.ollama_yeniden_baslat()
        if not kosu.ollama_saglikli():
            sys.exit("Ollama embed istegine yanit vermiyor")
    return ram


def satirlar_db(db, kaynak):
    con = sqlite3.connect(db)
    try:
        return con.execute("SELECT content, page_info, embedding FROM chunks WHERE source=? ORDER BY id", (f"data/{kaynak}",)).fetchall()
    finally:
        con.close()


def kosinus(a, b):
    import math
    da, db_ = sum(x * x for x in a) ** .5, sum(x * x for x in b) ** .5
    return sum(x * y for x, y in zip(a, b)) / (da * db_)


def hazirla():
    OUT.mkdir(exist_ok=True)
    os.environ.update(kosu.ORTAM)
    ram = servisleri_hazirla(foundry_dursun=True)
    sys.path[:0] = [str(ROOT / "src")]
    import ingest as yeni
    spec2 = importlib.util.spec_from_file_location("ingest_old", HERE / "_ingest_head.py")
    (HERE / "_ingest_head.py").write_text(
        subprocess.check_output(["git", "show", "HEAD:src/ingest.py"], cwd=ROOT).decode("utf-8"), encoding="utf-8")
    eski = importlib.util.module_from_spec(spec2)
    spec2.loader.exec_module(eski)
    rapor = {"rag_db_ozet": kosu.hashlib.sha256((ROOT / "rag.db").read_bytes()).hexdigest()[:12], "bos_ram_gb": round(ram, 2), "pdf": {}}

    scratch = OUT / "_gecici_yeniden_ingest.db"
    scratch.unlink(missing_ok=True)
    for ad in PDFS:
        p = ROOT / "data" / ad
        db_satir = satirlar_db(ROOT / "rag.db", ad)
        c_eski, c_yeni = eski.extract_chunks_from_pdf(p), yeni.extract_chunks_from_pdf(p)
        # (1) uretim DB'si HEAD ingest'iyle tutarli mi?
        db_eski_uyum = [(r[0], r[1]) for r in db_satir] == c_eski
        # (2) gercek yeni kodla temiz DB'ye yeniden ingest
        n = yeni.ingest_single_file(p, db_path=str(scratch), num_gpu=99)
        yeni_satir = satirlar_db(scratch, ad)
        degisen = [i for i, (a, b) in enumerate(zip(db_satir, yeni_satir)) if (a[0], a[1]) != (b[0], b[1])]
        kos_ = [kosinus(json.loads(a[2]), json.loads(b[2])) for a, b in zip(db_satir, yeni_satir)]
        rapor["pdf"][ad] = {
            "rag_db_chunk": len(db_satir), "yeniden_ingest_chunk": n,
            "rag_db_HEAD_ingest_ile_tutarli": db_eski_uyum,
            "metni_degisen_chunk_sayfalari": [yeni_satir[i][1] for i in degisen],
            "metni_ayni_chunklarin_embedding_kosinus_min": round(min((k for i, k in enumerate(kos_) if i not in degisen), default=1.0), 5),
        }
        print(ad, json.dumps(rapor["pdf"][ad], ensure_ascii=False), flush=True)
    scratch.unlink(missing_ok=True)

    # (3) tedavi agaci: yalniz CFG yeniden ingest
    if TREE.exists():
        shutil.rmtree(TREE)
    TREE.mkdir(parents=True)
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc")
    for d in ("src", "evaluation", "data"):
        shutil.copytree(ROOT / d, TREE / d, ignore=ignore)
    for f in ("run_tests.py", "ingest.py", "rag.db"):
        shutil.copy2(ROOT / f, TREE / f)
    kod = ("import sys; sys.path.insert(0,'src'); import ingest; "
           f"print(ingest.ingest_single_file('data/{CFG}', db_path='rag.db', num_gpu=99))")
    cp = subprocess.run([sys.executable, "-c", kod], cwd=TREE, env={**os.environ, **kosu.ORTAM}, capture_output=True, text=True, encoding="utf-8", errors="replace")
    print(cp.stdout[-600:], cp.stderr[-300:])
    rapor["tedavi_db_cfg_chunk"] = len(satirlar_db(TREE / "rag.db", CFG))
    rapor["tedavi_db_ozet"] = kosu.hashlib.sha256((TREE / "rag.db").read_bytes()).hexdigest()[:12]
    a = {(r[0], r[1]) for r in satirlar_db(ROOT / "rag.db", CFG)}
    b = {(r[0], r[1]) for r in satirlar_db(TREE / "rag.db", CFG)}
    rapor["tedavi_vs_uretim_CFG_degisen_sayfalar"] = sorted({x[1] for x in (b - a)})
    # CFG disindaki tum kaynaklar birebir ayni mi?
    con1, con2 = sqlite3.connect(ROOT / "rag.db"), sqlite3.connect(TREE / "rag.db")
    q = f"SELECT source, content, page_info, embedding FROM chunks WHERE source != 'data/{CFG}' ORDER BY source, id"
    rapor["tedavi_CFG_disi_satirlar_birebir_ayni"] = con1.execute(q).fetchall() == con2.execute(q).fetchall()
    (OUT / "hazirlik.json").write_text(json.dumps(rapor, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(rapor, ensure_ascii=False, indent=1))


def kos():
    OUT.mkdir(exist_ok=True)
    servisleri_hazirla(foundry_dursun=True)
    env = {**os.environ, **kosu.ORTAM, "FOUNDRY_LOCAL_ENDPOINT": kosu.uc_nokta()}
    kaynak = ROOT / "evaluation/datasets/test_1.csv"
    for ad, cwd in (("kontrol", ROOT), ("islem", TREE)):
        d = OUT / ad
        d.mkdir(exist_ok=True)
        sonuc, log = d / "sonuclari.csv", d / "log.txt"
        if sonuc.exists():
            continue
        bas = time.time()
        with open(log, "a", encoding="utf-8") as f:
            rc = subprocess.run([sys.executable, "-u", "evaluation/run_tests.py", str(kaynak), str(sonuc)],
                                cwd=cwd, stdout=f, stderr=subprocess.STDOUT, env=env).returncode
        info = {"kosul": ad, "cwd": str(cwd), "cikis": rc, "sure_sn": round(time.time() - bas),
                "nobet": kosu.nobet(env), "ollama_cpu_yukleme": kosu.ollama_cpu_yuklemeleri(bas)}
        (d / "ortam.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
        print(json.dumps(info, ensure_ascii=False), flush=True)


{"hazirla": hazirla, "kos": kos}[sys.argv[1]]()
