"""
router.py — 3 Kademeli Akıllı Soru Yönlendirme (Query Routing) Modülü

Sorguları 3 katmanda sınıflandırır:
1. "rule_engine"      : Basit, sabit regex/kural motoru ile anında çözülebilen tekil sorular.
2. "code_interpreter" : Çoklu koşul, gruplama, matematik, yüzde, oran, istatistik gerektiren dinamik analitik sorular (Pandas Sandbox).
3. "semantic_rag"     : Kavramsal açıklamalar, şema anlamları, PDF/Word/TXT genel doküman aramaları (Vektör + BM25 + Reranker).
"""

import re
from enum import Enum
from typing import Dict, Any, Optional, List


class RouteTarget(str, Enum):
    RULE_ENGINE = "rule_engine"            # 1. Aşama: Hızlı kural/regex motoru
    CODE_INTERPRETER = "code_interpreter"  # 2. Aşama: Dinamik LLM Pandas Sandbox
    SEMANTIC_RAG = "semantic_rag"          # 3. Aşama: Semantik doküman / şema RAG


# Geriye dönük uyumluluk
class QueryIntent(str, Enum):
    AGGREGATION = "rule_engine"
    SCHEMA = "semantic_rag"
    SEMANTIC = "semantic_rag"



# ─── 1. Şema ve Doküman Tanım Kalıpları (Kavramsal Soru İşaretleri) ───
SCHEMA_DEFINITION_PATTERNS = [
    r"ne i[sş]e yarar",
    r"ne i[cç]in kullan[ıi]l[ıi]r",
    r"neden g[oö]r[uü]n[uü]r de[gğ]ildir",
    r"neden .* de[gğ]ildir",
    r"b[oö]l[uü]m[uü]ne g[oö]re .* iddia",
    r"do[gğ]rulamas[ıi] iddia",
    r"hangi .* (alabilir|belirtir|tanımlar|açıklar)",
    r"hangi alanlarla a[cç][ıi]k[cç]a",
    r"sentetik.*oldu[gğ]u",
    r"synthetic",
    r"fieldguide",
    r"safetyanddataquality",
]

# ─── 2. Basit Kural Motoru Kalıpları (Hızlı Regex ile Çözülenler) ───
SIMPLE_RULE_PATTERNS = [
    r"^veri setindeki toplam profil say[ıi]s[ıi] ka[cç]t[ıi]r\??$",
    r"^veri setinde ka[cç] farkl[ıi] sekt[oö]r bulunmaktad[ıi]r\??$",
    r"^veri setinde ka[cç] farkl[ıi] meslek.*bulunmaktad[ıi]r\??$",
]

# ─── 3. Karmaşıklık / Analitik Hesaplama Sinyalleri (Code Interpreter) ───
COMPLEXITY_SIGNALS = [
    "ve",
    "göre dağılım",
    "göre dagilim",
    "dağılım",
    "dagilim",
    "%",
    "yüzde",
    "yuzde",
    "ortalama",
    "oran",
    "oranı",
    "toplam",
    "büyük",
    "buyuk",
    "küçük",
    "kucuk",
    "arasında",
    "arasinda",
    "karşılaştır",
    "karsilastir",
    "en sık",
    "en sik",
    "en çok",
    "en cok",
    "en az",
    "en yüksek",
    "en yuksek",
    "en düşük",
    "en dusuk",
    "sıralama",
    "siralama",
    "üzerinde",
    "uzerinde",
    "altında",
    "altinda",
    "fark",
    "farkı",
    "kaç profil",
    "kac profil",
    "kaç farklı",
    "kac farkli",
    "sayısı kaçtır",
    "sayisi kactir",
    "değerleri nedir",
    "degerleri nedir",
    "min",
    "max",
    "minimum",
    "maksimum",
    "filtre",
    "koşul",
    "olanlar",
    "bulunanlar",
    "içeren",
    "iceren",
]

# ─── 4. Veri Seti / Tablo Alan Göstergeleri ───
DATASET_INDICATORS = [
    r"veri seti",
    r"tablo",
    r"profil",
    r"sekt[oö]r",
    r"meslek",
    r"occupation",
    r"[sş]ehir",
    r"city",
    r"country",
    r"[uü]lke",
    r"havaalan[ıi]",
    r"airport",
    r"deneyim",
    r"experience",
    r"dil\b",
    r"language",
    r"profiletype",
    r"servicemodes?",
    r"autoapprove",
    r"duration",
    r"s[uü]re",
    r"dakika",
    r"saat",
    r"enlem",
    r"boylam",
    r"lat",
    r"lon",
]


def matches_simple_pattern(question: str) -> bool:
    """Sorunun basit kural motoruyla (regex/önbellek) çözülüp çözülemeyeceğini kontrol eder."""
    q = question.strip().lower()
    for pat in SIMPLE_RULE_PATTERNS:
        if re.search(pat, q, re.IGNORECASE):
            return True
    return False


def is_schema_or_doc_conceptual(question: str) -> bool:
    """Sorunun şema tanımı (fieldGuide vb.) veya genel metin sorusu olup olmadığını denetler."""
    q = question.strip().lower()
    for pat in SCHEMA_DEFINITION_PATTERNS:
        if re.search(pat, q, re.IGNORECASE):
            return True
    return False


def route_query(question: str, df_schema: Optional[dict] = None) -> str:
    """
    Kullanıcı sorusunu 3'lü mimariye göre yönlendirir.

    1. Önce basit regex / kural motoru dener -> 'rule_engine'
    2. Kavramsal/şema/metin sorusu ise -> 'semantic_rag'
    3. Karmaşıklık sinyalleri veya veri alanı içeriyorsa -> 'code_interpreter'
    4. Hiçbiri değilse genel doküman -> 'semantic_rag'

    Returns:
        "rule_engine" | "code_interpreter" | "semantic_rag"
    """
    q_lower = question.strip().lower()

    # 1. Kural Motoru (En Hızlı Öncelik)
    if matches_simple_pattern(q_lower):
        return RouteTarget.RULE_ENGINE.value

    # 2. Şema ve Kavramsal Doküman Kontrolü (fieldGuide, anlam nedir vb.)
    if is_schema_or_doc_conceptual(q_lower):
        return RouteTarget.SEMANTIC_RAG.value

    # 3. Karmaşıklık Sinyalleri & Veri Seti Hesaplama (Code Interpreter)
    has_complexity = any(sig in q_lower for sig in COMPLEXITY_SIGNALS)
    has_dataset_signal = any(re.search(ind, q_lower, re.IGNORECASE) for ind in DATASET_INDICATORS)
    
    # Eğer özel df_schema verilmişse sütun adlarını da kontrol et
    if df_schema:
        cols = list(df_schema.keys()) if isinstance(df_schema, dict) else []
        if any(c.lower() in q_lower for c in cols):
            has_dataset_signal = True

    if has_complexity and has_dataset_signal:
        return RouteTarget.CODE_INTERPRETER.value

    if has_dataset_signal and any(word in q_lower for word in ["kaç", "kac", "hangisi", "oran", "yüzde", "en"]):
        return RouteTarget.CODE_INTERPRETER.value

    # 4. Hiçbiri değilse kavramsal/genel soru -> Semantik RAG
    return RouteTarget.SEMANTIC_RAG.value


# Geriye dönük uyumluluk ve detaylı bilgi için
def classify_query(query: str, df_schema: Optional[dict] = None) -> Dict[str, Any]:
    """Detaylı rota bilgisi döner."""
    target = route_query(query, df_schema=df_schema)
    return {
        "target": target,
        "intent": target.upper(),
        "query": query,
    }


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

    test_cases = [
        # Rule Engine
        ("Veri setindeki toplam profil sayısı kaçtır?", "rule_engine"),
        ("Veri setinde kaç farklı sektör bulunmaktadır?", "rule_engine"),

        # Code Interpreter (Karmaşık / Hesaplama)
        ("Tüm profillerin experience.years alanlarına göre ortalama mesleki deneyim yılı kaçtır?", "code_interpreter"),
        ('"appointmentSettings.autoApproveRequests" değeri "true" olan profillerin toplam profil sayısına oranı yaklaşık yüzde kaçtır?', "code_interpreter"),
        ("Veri setindeki profillerde toplam kaç farklı şehir (city) yer almaktadır ve en çok profile sahip ilk 3 şehir hangileridir?", "code_interpreter"),
        ('"serviceModes" alanında "Yerinde hizmet" seçeneğini içeren kaç profil bulunmaktadır?', "code_interpreter"),
        ("Çoklu Filtreleme ve Lokasyon Dağılımı: Sağlık sektörü içerisinde deneyimi 10 yılın üzerinde olan profillerin en yoğun bulunduğu iller hangileridir?", "code_interpreter"),
        ("Hangi ülkede kaç havaalanı bulunmaktadır ve en çok havaalanı olan ülke hangisidir?", "code_interpreter"),
        ("En yüksek enlem değerine sahip ilk 3 havaalanı hangileridir?", "code_interpreter"),

        # Semantic RAG (Kavramsal / Doküman)
        ('"profileCode" alanı ne için kullanılır?', "semantic_rag"),
        ('"publicContact" alanında telefon ve e-posta neden görünür değildir?', "semantic_rag"),
        ('Veri setinin "synthetic" (sentetik) olduğu hangi alanlarla açıkça belirtilmiştir?', "semantic_rag"),
        ("Bağlamdan bağımsız dilbilgisi kaç elemanlı bir yapıdır?", "semantic_rag"),
        ("Fourier dönüşümünün ileri yönü hangi işlemi yapar?", "semantic_rag"),
        ("Summer School programı kaç haftalıktır?", "semantic_rag"),
    ]

    print("=" * 70)
    print("3 KADEMELİ ROUTER DOĞRULAMA TESTİ")
    print("=" * 70)

    passed = 0
    for q, expected in test_cases:
        actual = route_query(q)
        ok = (actual == expected)
        if ok:
            passed += 1
        status = "✅ PASS" if ok else "❌ FAIL"
        print(f"{status} | Beklenen: {expected:<16} | Çıkan: {actual:<16} | Soru: {q[:45]}...")

    print(f"\nSonuç: {passed}/{len(test_cases)} Test Başarılı!")
