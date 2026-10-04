"""
run_tests.py — 30 soruluk test setini otomatik çalıştırır.

Her soru için:
  1. retrieval.py ile ilgili chunk'ları bulur
  2. Context oluşturur
  3. LLM'den cevap alır
  4. Sonucu (soru, cevap, kaynaklar, süre, LLM'e giden context, sandbox
     sonucunun semantik doğrulama durumu) kaydeder; run sonunda doğrulama
     durumu özeti basar

Kullanım:
  python run_tests.py                          # test_sorulari.csv
  python run_tests.py test_sorulari_json.csv   # başka bir soru seti
  python run_tests.py test_sorulari_json.csv sonuc.csv
  python run_tests.py test_1.csv --max-consecutive-errors 5   # durma eşiği (vars. 3)

Ardışık N soru HATA ile biterse (altyapı çökmüş: Ollama/Foundry/DB) run durur;
yarım sonuçlar <çıktı>.partial.csv'ye yazılır, asıl çıktı dosyası oluşturulmaz.
"""
import argparse
import csv
import re
import sys
import gc
import time
from pathlib import Path

# Add src and root to sys.path
_eval_dir = Path(__file__).resolve().parent
_root_dir = _eval_dir.parent
_src_dir = _root_dir / "src"

for _p in [str(_src_dir), str(_eval_dir), str(_root_dir)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    from src.retrieval import get_top_chunks
    from src.llm_client import load_model, ask, truncate_chunk_text, truncate_context
except ImportError:
    from retrieval import get_top_chunks
    from llm_client import load_model, ask, truncate_chunk_text, truncate_context


def _resolve_file(file_path: str) -> Path:
    """Verilen dosya yolunu yerel, datasets ve root dizinlerinde arayarak çözer."""
    p = Path(file_path)
    if p.exists():
        return p
    candidates = [
        _eval_dir / file_path,
        _root_dir / file_path,
        _eval_dir / "datasets" / file_path,
        _eval_dir / "datasets" / p.name,
        _eval_dir / p.name,
        _root_dir / p.name,
    ]
    for c in candidates:
        if c.exists():
            return c
    return p

# GPU bellek hatalarını tanıyan işaretler. Foundry/ONNX Runtime bunları
# HTTP 500 gövdesinde döndürüyor:
#   "BFCArena::AllocateRawInternal Failed to allocate memory for requested
#    buffer of size ..."
_MEMORY_ERROR_HINTS = (
    "failed to allocate memory",
    "bfcarena",
    "out of memory",
    "cuda error",
    "error code: 500",
)


def is_memory_error(exc):
    """Hata GPU/bellek kaynaklı mı? (retry öncesi temizlik yapmaya karar vermek için)"""
    return any(hint in str(exc).lower() for hint in _MEMORY_ERROR_HINTS)


def free_gpu_memory():
    """
    Sorular arasında bu sürecin tuttuğu belleği bırakır.

    NOT: VRAM'i asıl dolduran iki bileşen de AYRI süreçlerde çalışıyor —
    LLM (Foundry Local) ve embedding modeli (Ollama/bge-m3). Onların
    belleğine buradan doğrudan müdahale edilemez; asıl çözüm bağlamı
    kısa tutmak (bkz. llm_client.MAX_CHUNK_CHARS).

    Bu süreçte GPU'yu kullanabilecek tek şey reranker (CrossEncoder/torch).
    Mevcut kurulumda torch CPU derlemesi olduğu için aşağıdaki torch bloğu
    devreye girmez; torch'un CUDA derlemesine geçilirse otomatik çalışır.
    """
    gc.collect()
    try:
        import torch
    except ImportError:
        return
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.ipc_collect()


def build_context(chunks):
    """app.py'daki build_context ile aynı mantık — LLM'e giden bağlamı oluşturur."""
    parts = []
    for i, chunk in enumerate(chunks, 1):
        source = Path(chunk["source"]).name
        page_info = chunk.get("page_info", "")
        # Uzun chunk'lar prompt'u şişirip VRAM'i taşırıyor — kırp.
        content = truncate_chunk_text(chunk["content"])
        parts.append(f"[{i}] Kaynak: {source}, {page_info}\n{content}")
    return truncate_context("\n\n".join(parts))


def run_single_test(llm, question, top_k=5, use_reranker=True, retries=1):
    """
    Tek bir soruyu çalıştırır, sonucu dict olarak döner.

    Foundry Local servisi art arda sorgularda ara sıra "Connection error" ya da
    GPU bellek hatası (500 / BFCArena) veriyor. Bu geçici olduğu için sorguyu
    `retries` kez yeniden deneriz; bellek hatasıysa yeniden denemeden önce
    GPU cache'ini de boşaltırız. Kalıcı hatalar yine yukarı fırlar.
    """
    t0 = time.perf_counter()

    chunks = get_top_chunks(question, top_k=top_k, use_reranker=use_reranker, llm=llm)
    # retrieve() veritabanında hiç chunk bulamazsa hata fırlatmadan [] döner.
    # Boş context'le LLM "bulunamadı" der; bu pozitif soruda FN, negatif soruda
    # TN (doğru ret) sayılır ve run sessizce makul görünen sayılar üretir.
    # Hata olarak yukarı fırlatıyoruz: cevap "HATA: ..." olur, skorlanmaz.
    if not chunks:
        raise RuntimeError("Retrieval boş döndü (veritabanında chunk yok ya da DB yolu yanlış?)")
    # Kod üreten LLM servisi yanıt veremediyse retrieval "[İŞLENEMEDİ]" bloğu
    # döner ve synthesizer "bulunamadı; tekrar denenebilir" der (backlog madde
    # 14). Bu kullanıcı için doğru cümle ama eval için cevap değil, altyapı
    # hatası: skorlansaydı test_2 #43/#53 gibi judge'da F=1-2 alıp ortalamayı
    # haksız düşürüyordu. Boş retrieval gibi HATA yoluna çevrilir.
    if any(c.get("operation") == "service_failure" for c in chunks):
        raise RuntimeError("service_failure: code_interpreter LLM servisi yanıt veremedi")
    context = build_context(chunks)

    # app.py ile BİREBİR aynı mantık: META_QUERY rotasında retrieval, chunk'lara
    # "açık bilgi vs. çıkarım" talimatını iliştirir. Bu talimat synthesizer'a
    # geçirilmezse hesaplanmış/sentezlenmiş context blokları için LLM app.py'dan
    # farklı davranır ve benchmark skorları yapay olarak düşer.
    extra_instruction = next(
        (c.get("synthesizer_instruction") for c in chunks
         if c.get("synthesizer_instruction")),
        None,
    )

    for attempt in range(retries + 1):
        try:
            answer = ask(llm, context, question,
                         extra_instruction=extra_instruction)
            break
        except Exception as e:
            if attempt == retries:
                raise
            if is_memory_error(e):
                print(f"    ! GPU bellek hatası — bellek temizlenip tekrar deneniyor…")
                free_gpu_memory()
            else:
                print(f"    ! Hata ({e}) — 3 sn sonra tekrar deneniyor…")
            time.sleep(3)

    elapsed = time.perf_counter() - t0

    kaynaklar = "; ".join(
        f"{Path(c['source']).name} ({c.get('page_info', '')})" for c in chunks
    )

    return {
        "cevap": answer,
        "bulunan_kaynaklar": kaynaklar,
        "sure_sn": round(elapsed, 2),
        # LLM'e giden bağlamın birebir kopyası — llm_as_judge.py cevabı
        # yeniden retrieve edilmiş değil, bu bağlama göre değerlendirir.
        "context": context,
        "dogrulama_durumu": validation_label(chunks),
    }


def validation_label(chunks):
    """
    Sandbox sonucunun semantik doğrulama durumu (validator A ölçümü):
    "ok" / "objection" / "not_run" / "failed (<hata>)". Sandbox chunk'ı yoksa
    (semantik RAG cevabı) boş string. Faithfulness bunu yakalayamadığı için
    ayrı sütunda tutulur (docs/implementation_plan_validator_failure.md).
    """
    chunk = next((c for c in chunks if c.get("validation_status")), None)
    if chunk is None:
        return ""
    status = chunk["validation_status"]
    if status == "failed" and chunk.get("validation_error"):
        return f"failed ({chunk['validation_error']})"
    return status


def validation_summary(sonuclar):
    """Run sonu özeti: sandbox sorularının doğrulama durumu dağılımı."""
    by_status = {}
    for row in sonuclar:
        label = row.get("dogrulama_durumu") or ""
        if label:
            by_status.setdefault(label.split(" ", 1)[0], []).append(row)
    if not by_status:
        return None
    toplam = sum(len(rows) for rows in by_status.values())
    sayim = " ".join(f"{s}={len(by_status.get(s, []))}"
                     for s in ("ok", "objection", "failed", "not_run"))
    lines = [f"Semantik doğrulama ({toplam} sandbox sorusu): {sayim}"]
    for row in by_status.get("failed", []):
        hata = row["dogrulama_durumu"][len("failed ("):].split(":", 1)[0]
        lines.append(f"  failed : #{row.get('id', '?')} ({hata})")
    if by_status.get("not_run"):
        lines.append("  not_run: " + ", ".join(f"#{r.get('id', '?')}" for r in by_status["not_run"]))
    return "\n".join(lines)


# Ardışık bu kadar soru HATA ile biterse altyapı (Ollama, Foundry, DB) çökmüş
# demektir; kalan soruları da HATA ile doldurmak yerine run durdurulur.
DEFAULT_MAX_CONSECUTIVE_ERRORS = 3


def error_kind(message):
    """Hata mesajının kısa tipi: 'Error code: 500', 'Embedding olusturulamadi' gibi."""
    match = re.search(r"Error code: \d+", message)
    if match:
        return match.group(0)
    return re.split(r"[:.(]", message, maxsplit=1)[0].strip()[:40] or "bilinmeyen hata"


def write_results(path, fieldnames, sonuclar):
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(sonuclar)


def default_output_path(input_path):
    """test.csv -> test_sonuclari.csv veya girdi setine göre isim üret."""
    p = Path(input_path)
    name = p.name
    if name.startswith("test_sorulari_json"):
        name = "test_sonuclari_json" + name[len("test_sorulari_json"):]
    elif name == "test.csv":
        name = "test_sonuclari.csv"
    else:
        name = p.stem + "_sonuclari" + p.suffix
    return str(name)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="RAG test setini çalıştırır.")
    parser.add_argument(
        "sorular",
        nargs="?",
        default="test.csv",
        help="Soru CSV dosyası (varsayılan: test.csv)",
    )
    parser.add_argument(
        "cikti",
        nargs="?",
        default=None,
        help="Sonuç CSV dosyası (varsayılan: girdi adından türetilir, örn: test_sonuclari.csv)",
    )
    parser.add_argument(
        "--max-consecutive-errors",
        type=int,
        default=DEFAULT_MAX_CONSECUTIVE_ERRORS,
        help="Ardışık bu kadar soru HATA ile biterse run durdurulur "
             f"(varsayılan: {DEFAULT_MAX_CONSECUTIVE_ERRORS}; 0 = hiç durma)",
    )
    args = parser.parse_args(argv)
    if args.cikti is None:
        args.cikti = default_output_path(args.sorular)
    return args


def main(argv=None):
    import sys as _sys
    try:
        _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

    args = parse_args(argv)
    soru_path = _resolve_file(args.sorular)

    if not soru_path.exists():
        sys.exit(f"Soru dosyası bulunamadı: {args.sorular}")

    print("Model yükleniyor...")
    llm = load_model()  # varsayılan: qwen2.5-7b-instruct-cuda-gpu:4 (GPU/CUDA)
    print("Model hazır.\n")

    # Soruları CSV'den oku
    print(f"Soru seti: {soru_path}")
    with open(soru_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        sorular = list(reader)

    if not sorular:
        sys.exit(f"Soru dosyası boş: {args.sorular}")
    if "soru" not in sorular[0]:
        sys.exit(
            f"'{args.sorular}' içinde 'soru' sütunu yok. "
            f"Bulunan sütunlar: {', '.join(sorular[0].keys())}"
        )

    fieldnames = list(sorular[0].keys()) + ["cevap", "bulunan_kaynaklar", "sure_sn", "context",
                                            "dogrulama_durumu"]
    sonuclar = []
    ardisik_hatalar = []  # [(id, hata tipi)] — başarılı bir soruda sıfırlanır
    for soru_row in sorular:
        print(f"[{soru_row.get('id', '?')}] Soruluyor: {soru_row['soru']}")
        try:
            sonuc = run_single_test(llm, soru_row["soru"])
            ardisik_hatalar = []
        except Exception as e:
            sonuc = {"cevap": f"HATA: {e}", "bulunan_kaynaklar": "", "sure_sn": 0,
                     "context": "", "dogrulama_durumu": ""}
            ardisik_hatalar.append((soru_row.get("id", "?"), error_kind(str(e))))

        sonuclar.append({**soru_row, **sonuc})
        if sonuc["dogrulama_durumu"] not in ("", "ok"):
            # Sandbox chunk'ı build_context'te hep [1]; etiket içeriğin ilk satırı.
            etiket = (sonuc["context"].split("\n", 2) + [""])[1]
            print(f"    ! doğrulama: {sonuc['dogrulama_durumu']} — context [1] {etiket}")
        print(f"    → {sonuc['sure_sn']} sn\n")

        if args.max_consecutive_errors and len(ardisik_hatalar) >= args.max_consecutive_errors:
            # Yarım sonuçlar asıl çıktı yoluna YAZILMAZ: run_all.py var olan
            # çıktıyı "tamamlanmış" sayıp atlıyor, yarım dosya skorlanırdı.
            partial = Path(args.cikti).with_suffix(".partial.csv")
            write_results(partial, fieldnames, sonuclar)
            liste = ", ".join(f"#{i} ({tip})" for i, tip in ardisik_hatalar)
            sys.exit(f"\n{len(ardisik_hatalar)} ardışık hata: {liste} — altyapı kontrolü "
                     f"gerekiyor, run durduruldu.\n"
                     f"{len(sonuclar)}/{len(sorular)} soru işlendi; yarım sonuçlar: {partial}")

        # Her sorudan sonra GPU belleğini bırak — 8GB VRAM'de reranker'ın
        # tuttuğu cache birikince Foundry uzun context'te yer bulamıyor.
        free_gpu_memory()

        # Servise nefes aldır: art arda gelen sorgular bağlantı hatasını tetikliyor.
        time.sleep(1)

    write_results(args.cikti, fieldnames, sonuclar)

    print(f"\nTamamlandı. {len(sonuclar)} soru test edildi.")
    print(f"Sonuçlar: {args.cikti}")
    ozet = validation_summary(sonuclar)
    if ozet:
        print(ozet)


if __name__ == "__main__":
    main()