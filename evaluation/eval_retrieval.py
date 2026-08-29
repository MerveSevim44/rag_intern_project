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


TEST_SETS = ["test_1", "test_2", "test_3", "test_4", "test_5"]


def evaluate_questions(csv_path: str = "test_1.csv", output_csv: str | None = None,
                       quiet: bool = False):
    """
    Tek bir test setini değerlendirir ve özet sözlüğü döner.
    `quiet=True` ise soru bazlı satırlar basılmaz (toplu çalıştırmada gürültüyü azaltır).
    """
    path = _resolve_file(csv_path)
    if not path.exists():
        print(f"Hata: {csv_path} bulunamadı.")
        return None

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
        return None

    passed_retrieval = 0
    scorable = 0
    intent_counts = {}
    latencies = []
    # Zorluk bazlı kırılım: genel değerlendirmede "hangi zorlukta düşüyoruz"
    # sorusunu cevaplamak için tutulur.
    by_difficulty = {}

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
        latencies.append(elapsed_ms)
        d_stats = by_difficulty.setdefault(difficulty, {"total": 0, "scorable": 0, "passed": 0})
        d_stats["total"] += 1

        # Doğruluk kontrolü. expected_src boşsa ("" in x == True) her soru
        # doğru sayılıyordu; artık beklenen kaynağı olmayan sorular skora
        # hiç girmiyor ("-" ile işaretli negatif sorular dahil).
        if expected_src and expected_src != "-":
            scorable += 1
            d_stats["scorable"] += 1
            src_match = (expected_src == top_source) or (expected_src in top_source)
            if src_match:
                passed_retrieval += 1
                d_stats["passed"] += 1
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

        if not quiet:
            print(f"\n[Soru {q_id}] ({difficulty}) {question}")
            print(f"  Rota      : [{intent}] | Süre: {elapsed_ms:.1f} ms")
            print(f"  Top-1     : {top_source} ({top_page}) | Skor: {top_score:.4f}")
            print(f"  İçerik    : {top_content}...")

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
    if latencies:
        print(f"Ortalama Retrieval Süresi : {sum(latencies) / len(latencies):.1f} ms "
              f"(min {min(latencies):.1f} / max {max(latencies):.1f})")
    print("-" * 85)
    print("Zorluk Bazlı Kaynak Doğruluğu:")
    for diff_name, d in sorted(by_difficulty.items()):
        if d["scorable"]:
            print(f"  {diff_name:<10s}: {d['passed']:3d} / {d['scorable']:3d} "
                  f"(%{d['passed'] / d['scorable'] * 100:.1f})")
        else:
            print(f"  {diff_name:<10s}: {d['total']:3d} soru (skorlanabilir yok)")
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
    print(f"Detaylı sonuçlar: {out_path}")

    return {
        "set": path.stem,
        "toplam": total,
        "skorlanabilir": scorable,
        "dogru_kaynak": passed_retrieval,
        "rota_dagilimi": intent_counts,
        "zorluk_bazli": by_difficulty,
        "sureler_ms": latencies,
        "cikti_dosyasi": str(out_path),
    }



def evaluate_all(sets=None, quiet: bool = True) -> dict:
    """
    test_1..test_4 setlerinin hepsini sırayla değerlendirir ve set bazlı +
    GENEL (hepsinin toplamı) retrieval/routing raporu üretir.
    """
    sets = list(sets or TEST_SETS)
    per_set = []
    for name in sets:
        csv_name = name if name.endswith(".csv") else f"{name}.csv"
        print("\n" + "#" * 85)
        print(f"# TEST SETİ: {csv_name}")
        print("#" * 85)
        stats = evaluate_questions(csv_name, quiet=quiet)
        if stats:
            per_set.append(stats)

    if not per_set:
        print("Hiçbir test seti değerlendirilemedi.")
        return {}

    total = sum(s["toplam"] for s in per_set)
    scorable = sum(s["skorlanabilir"] for s in per_set)
    passed = sum(s["dogru_kaynak"] for s in per_set)
    all_lat = [x for s in per_set for x in s["sureler_ms"]]

    intents = {}
    for s in per_set:
        for k, v in s["rota_dagilimi"].items():
            intents[k] = intents.get(k, 0) + v

    diffs = {}
    for s in per_set:
        for k, v in s["zorluk_bazli"].items():
            d = diffs.setdefault(k, {"total": 0, "scorable": 0, "passed": 0})
            for key in d:
                d[key] += v[key]

    print("\n" + "=" * 85)
    print("GENEL RETRIEVAL DEĞERLENDİRMESİ — TÜM SETLERİN TOPLAMI")
    print("=" * 85)
    print(f"{'Set':<12}{'Soru':>6}{'Skorlanabilir':>15}{'Dogru':>8}{'Basari%':>10}{'Ort.ms':>10}")
    print("-" * 85)
    for s in per_set:
        acc = (s["dogru_kaynak"] / s["skorlanabilir"] * 100) if s["skorlanabilir"] else 0.0
        avg = sum(s["sureler_ms"]) / len(s["sureler_ms"]) if s["sureler_ms"] else 0.0
        print(f"{s['set']:<12}{s['toplam']:>6}{s['skorlanabilir']:>15}"
              f"{s['dogru_kaynak']:>8}{acc:>10.1f}{avg:>10.1f}")
    print("-" * 85)
    acc = (passed / scorable * 100) if scorable else 0.0
    avg = sum(all_lat) / len(all_lat) if all_lat else 0.0
    print(f"{'GENEL':<12}{total:>6}{scorable:>15}{passed:>8}{acc:>10.1f}{avg:>10.1f}")
    print("=" * 85)
    print("Zorluk Bazlı (genel):")
    for k, d in sorted(diffs.items()):
        if d["scorable"]:
            print(f"  {k:<10s}: {d['passed']:3d} / {d['scorable']:3d} (%{d['passed'] / d['scorable'] * 100:.1f})")
        else:
            print(f"  {k:<10s}: {d['total']:3d} soru (skorlanabilir yok)")
    print("-" * 85)
    print("Rota Dağılımı (genel):")
    for name, cnt in sorted(intents.items(), key=lambda kv: -kv[1]):
        print(f"  {name:<18s}: {cnt:3d} (%{cnt / total * 100:.1f})")
    print("=" * 85)

    return {
        "set_bazli": per_set,
        "genel": {
            "toplam": total,
            "skorlanabilir": scorable,
            "dogru_kaynak": passed,
            "basari_yuzde": round(acc, 2),
            "ortalama_ms": round(avg, 1),
            "rota_dagilimi": intents,
            "zorluk_bazli": diffs,
        },
    }


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

    import argparse

    parser = argparse.ArgumentParser(
        description="Retrieval & yönlendirme değerlendirmesi (test_1..test_4)."
    )
    parser.add_argument("sorular_csv", nargs="?", default=None,
                        help="Değerlendirilecek soru CSV'si (örn: test_3.csv). "
                             "Verilmezse tüm setler çalıştırılır.")
    parser.add_argument("cikti_csv", nargs="?", default=None,
                        help="Detay çıktı CSV yolu (varsayılan: report/retrieval_eval_<set>.csv)")
    parser.add_argument("--all", action="store_true",
                        help="test_1..test_4 setlerinin tümünü çalıştırıp genel rapor üretir")
    parser.add_argument("--sets", nargs="+", default=None,
                        help="--all ile: çalıştırılacak setler (varsayılan: test_1 test_2 test_3 test_4)")
    parser.add_argument("--verbose", action="store_true",
                        help="--all modunda soru bazlı satırları da yazdırır")

    args = parser.parse_args()
    if args.all or args.sorular_csv is None:
        evaluate_all(args.sets, quiet=not args.verbose)
    else:
        evaluate_questions(args.sorular_csv, args.cikti_csv)
