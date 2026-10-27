"""
Madde 20 / 2b doğrulaması — "Deneyim yılları histogramı" ve benzerleri bugün
hangi rotaya gidiyor? Yalnız router (classify_query); LLM çağrısı yok.

İki durum: arayüzde dataset SEÇİLİ DEĞİL (varsayılan, source_filter=None) ve
728_profiles.json seçili (retrieval.py selected_dataset'i router'a geçirir).

Kullanım (kökten): python experiments/madde20_router_2b/probe_2b.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]

from router import classify_query  # noqa: E402
from data_engine import get_data_engine  # noqa: E402

QS = [
    "Deneyim yılları histogramı",  # backlog madde 20'deki orijinal örnek
    "deneyim yılı dağılımı",
    "Deneyim yıllarının ortalaması nedir?",
    "Deneyim yılı 10'dan fazla olan kaç kişi var?",
    "En fazla deneyim yılına sahip kişi kim?",
    "Deneyim yıllarını görselleştir",
    "Deneyim yılı histogramı çiz",
    "Ortalama deneyim süresi kaç yıl?",
    "Profillerde deneyim yılları histogramı",  # kontrol: "profil" bağlam kelimesi var
]

if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    S = get_data_engine().get_schemas()
    print(f"{'soru':46} | {'seçimsiz':16} | {'728 seçili':16} | seçimsiz: neden / güçlü kolon")
    for q in QS:
        a = classify_query(q, df_schema=S, debug=True)
        b = classify_query(q, df_schema=S, selected_dataset="728_profiles.json")
        print(f"{q:46} | {a['target']:16} | {b['target']:16} | "
              f"{a.get('reason')} / {a.get('strong_schema_columns', [])[:2]}")
