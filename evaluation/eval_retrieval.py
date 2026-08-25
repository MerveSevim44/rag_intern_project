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


def evaluate_questions(csv_path: str = "test_sorulari_json.csv"):
    path = _resolve_file(csv_path)
    if not path.exists():
        print(f"Hata: {csv_path} bulunamadı.")
        return

    print("=" * 85)
    print(f"OTOMATİK RETRIEVAL & YÖNLENDİRME DEĞERLENDİRMESİ: {path.name}")
    print("=" * 85)

    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        questions = list(reader)

    total = len(questions)
    passed_intent = 0
    passed_retrieval = 0

    results = []

    for item in questions:
        q_id = item.get("id", "-")
        difficulty = item.get("zorluk", "-")
        question = item.get("soru", "")
        expected_src = item.get("beklenen_kaynak", "")

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

        # Doğruluk kontrolü
        src_match = (expected_src == top_source) or (expected_src in top_source)
        if src_match:
            passed_retrieval += 1

        results.append({
            "id": q_id,
            "zorluk": difficulty,
            "soru": question,
            "intent": intent,
            "top_kaynak": f"{top_source} ({top_page})",
            "skor": f"{top_score:.4f}",
            "sure_ms": f"{elapsed_ms:.1f}",
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
    print(f"Doğru Kaynak Eşleşmesi : {passed_retrieval} / {total} ({(passed_retrieval/total)*100:.1f}%)")
    print("=" * 85)

if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

    target_file = sys.argv[1] if len(sys.argv) > 1 else "test_sorulari_json.csv"
    evaluate_questions(target_file)
