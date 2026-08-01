"""
run_tests.py — 30 soruluk test setini otomatik çalıştırır.

Her soru için:
  1. retrieval.py ile ilgili chunk'ları bulur
  2. Context oluşturur
  3. LLM'den cevap alır
  4. Sonucu (soru, cevap, kaynaklar, süre) kaydeder

Kullanım:
  python run_tests.py
"""
import csv
import time
from retrieval import get_top_chunks
from llm_client import load_model, ask
from pathlib import Path


def build_context(chunks):
    """app.py'daki build_context ile aynı mantık — LLM'e giden bağlamı oluşturur."""
    parts = []
    for i, chunk in enumerate(chunks, 1):
        source = Path(chunk["source"]).name
        page_info = chunk.get("page_info", "")
        parts.append(f"[{i}] Kaynak: {source}, {page_info}\n{chunk['content']}")
    return "\n\n".join(parts)


def run_single_test(llm, question, top_k=5, use_reranker=True):
    """Tek bir soruyu çalıştırır, sonucu dict olarak döner."""
    t0 = time.perf_counter()

    chunks = get_top_chunks(question, top_k=top_k, use_reranker=use_reranker)
    context = build_context(chunks)
    answer = ask(llm, context, question)

    elapsed = time.perf_counter() - t0

    kaynaklar = "; ".join(
        f"{Path(c['source']).name} ({c.get('page_info', '')})" for c in chunks
    )

    return {
        "cevap": answer,
        "bulunan_kaynaklar": kaynaklar,
        "sure_sn": round(elapsed, 2),
    }


def main():
    print("Model yükleniyor...")
    llm = load_model("qwen2.5-7b")  # daha hızlı/tutarlı sonuç için büyük modeli kullan
    print("Model hazır.\n")

    # Soruları CSV'den oku
    with open("test_sorulari.csv", "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        sorular = list(reader)

    sonuclar = []
    for soru_row in sorular:
        print(f"[{soru_row['id']}] Soruluyor: {soru_row['soru']}")
        try:
            sonuc = run_single_test(llm, soru_row["soru"])
        except Exception as e:
            sonuc = {"cevap": f"HATA: {e}", "bulunan_kaynaklar": "", "sure_sn": 0}

        sonuclar.append({**soru_row, **sonuc})
        print(f"    → {sonuc['sure_sn']} sn\n")

    # Sonuçları CSV'ye yaz
    fieldnames = list(sorular[0].keys()) + ["cevap", "bulunan_kaynaklar", "sure_sn"]
    with open("test_sonuclari.csv", "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(sonuclar)

    print(f"\nTamamlandı. {len(sonuclar)} soru test edildi.")
    print("Sonuçlar: test_sonuclari.csv")


if __name__ == "__main__":
    main()