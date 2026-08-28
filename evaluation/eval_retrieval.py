"""
eval_retrieval.py — Otomatik Retrieval & Yönlendirme Değerlendirme (Eval) Scripti

Tüm test soruları üzerinde retrieval doğruluğunu, yönlendirme başarısını
ve veri motoru hesaplama kesinliğini otomatik olarak test eder ve raporlar.
"""

import csv
import sys
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
    from src.retrieval import retrieve
    from src.router import classify_query
except ImportError:
    from retrieval import retrieve
    from router import classify_query


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


def evaluate_questions(csv_path: str = "test.csv", output_csv: str | None = None):
    path = _resolve_file(csv_path)
    if not path.exists():
        print(f"Hata: {csv_path} bulunamadı.")
        return

    print("=" * 85)
    print(f"OTOMATİK RETRIEVAL & YÖNLENDİRME DEĞERLENDİRMESİ: {path.name}")
    print("=" * 85)

    # utf-8-sig: Excel'den kaydedilen CSV'lerde BOM ilk sütun adını "﻿id"
    # yapıp item.get("id") çağrısını sessizce boş döndürüyordu.
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        questions = list(reader)

    total = len(questions)
    if total == 0:
        print(f"Hata: {path.name} içinde satır yok.")
        return

    passed_retrieval = 0
    scorable = 0
    intent_counts = {}

    results = []

    for item in questions:
        q_id = (item.get("id") or "-").strip()
        difficulty = (item.get("zorluk") or "-").strip()
        question = (item.get("soru") or "").strip()
        expected_src = (item.get("beklenen_kaynak") or "").strip()

        if not question:
            print(f"\n[Soru {q_id}] Atlandı: 'soru' alanı boş (CSV satırı bozuk olabilir).")
            continue

        t0 = time.perf_counter()
        
        # 1. Router tahmini
        route_info = classify_query(question)
        raw_intent = route_info.get("intent", route_info.get("target", "SEMANTIC_RAG"))
        intent = raw_intent.value if hasattr(raw_intent, "value") else str(raw_intent)

        # 2. Retrieval çalıştırma
        retrieved_chunks = retrieve(question, top_k=5, use_reranker=True)
        elapsed_ms = (time.perf_counter() - t0) * 1000

        top_chunk = retrieved_chunks[0] if retrieved_chunks else None
        top_source = Path(top_chunk["source"]).name if top_chunk else "YOK"
        top_page = top_chunk.get("page_info", "") if top_chunk else ""
        top_content = top_chunk["content"].replace("\n", " ")[:90] if top_chunk else ""
        top_score = top_chunk["score"] if top_chunk else 0.0

        intent_counts[intent] = intent_counts.get(intent, 0) + 1

        # Doğruluk kontrolü. expected_src boşsa ("" in x == True) her soru
        # doğru sayılıyordu; artık beklenen kaynağı olmayan sorular skora
        # hiç girmiyor ("-" ile işaretli negatif sorular dahil).
        if expected_src and expected_src != "-":
            scorable += 1
            src_match = (expected_src == top_source) or (expected_src in top_source)
            if src_match:
                passed_retrieval += 1
        else:
            src_match = None

        results.append({
            "id": q_id,
            "zorluk": difficulty,
            "soru": question,
            "intent": intent,
            "top_kaynak": f"{top_source} ({top_page})",
            "skor": f"{top_score:.4f}",
            "sure_ms": f"{elapsed_ms:.1f}",
            "beklenen_kaynak": expected_src,
            "kaynak_eslesti": "-" if src_match is None else ("Evet" if src_match else "Hayır"),
            "icerik_ozet": top_content
        })

        print(f"\n[Soru {q_id}] ({difficulty}) {question}")
        print(f"  👉 Rota      : [{intent}] | Süre: {elapsed_ms:.1f} ms")
        print(f"  📌 Top-1     : {top_source} ({top_page}) | Skor: {top_score:.4f}")
        print(f"  📝 İçerik    : {top_content}...")

    print("\n" + "=" * 85)
    print("DEĞERLENDİRME ÖZET RAPORU")
    print("=" * 85)
    print(f"Toplam Test Sorusu     : {total}")
    print(f"Skorlanabilir Soru     : {scorable} (beklenen_kaynak dolu olanlar)")
    if scorable:
        print(f"Doğru Kaynak Eşleşmesi : {passed_retrieval} / {scorable} "
              f"({(passed_retrieval / scorable) * 100:.1f}%)")
    else:
        print("Doğru Kaynak Eşleşmesi : hesaplanamadı (beklenen_kaynak sütunu boş)")
    print("-" * 85)
    print("Rota Dağılımı:")
    for name, cnt in sorted(intent_counts.items(), key=lambda kv: -kv[1]):
        print(f"  {name:<18s}: {cnt:3d} (%{(cnt / len(results)) * 100:.1f})")
    print("=" * 85)

    # Sonuçları diske yaz — eskiden `results` toplanıp hiç kullanılmıyordu.
    if output_csv is None:
        out_dir = _root_dir / "report"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"retrieval_eval_{path.stem}.csv"
    else:
        out_path = Path(output_csv)
        out_path.parent.mkdir(parents=True, exist_ok=True)

    with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)
    print(f"📁 Detaylı sonuçlar: {out_path}")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

    target_file = sys.argv[1] if len(sys.argv) > 1 else "test.csv"
    out_file = sys.argv[2] if len(sys.argv) > 2 else None
    evaluate_questions(target_file, out_file)
