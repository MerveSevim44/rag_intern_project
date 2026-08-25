"""
router.py — Soru Yönlendirme (Query Routing) Modülü

Gelen kullanıcı sorusunu analiz ederek 3 temel niyetten (Intent) birine sınıflandırır:
1. AGGREGATION: Veri seti üzerinde hesaplama gerektiren istatistik/sayma soruları (Pandas / SQL Motoru)
2. SCHEMA: Alan tanımları, fieldGuide, metadata veya veri kalitesi soruları (Meta / Schema Arama)
3. SEMANTIC: PDF, DOCX ve metin dokümanları üzerinden açıklama/kavramsal sorular (Vektör + BM25 Arama)
"""

import re #(regex)
from enum import Enum
from typing import Dict, Any, Optional


class QueryIntent(str, Enum):
    AGGREGATION = "AGGREGATION"  # Sayma, min/max, ortalama, kaç farklı, istatistik
    SCHEMA = "SCHEMA"            # fieldGuide, alan ne işe yarar, veri seti şeması/meta
    SEMANTIC = "SEMANTIC"        # Normal metin/doküman RAG araması (PDF, Word, TXT vb.)


# ─── 1. Veri Seti ve Şema Alan Adları (JSON Anahtarları) ───
SCHEMA_FIELD_NAMES = [
    "profilecode",
    "servicemodes",
    "publiccontact",
    "weeklyavailability",
    "appointmentsettings",
    "displayname",
    "professionalname",
    "safetyanddataquality",
    "fieldguide",
    "statistics",
    "sourcereference",
    "autoapproverequests",
    "experience.years",
    "experience",
]

# ─── 2. Profil/JSON Veri Setine Özgü Genel Göstergeler ───
DATASET_INDICATORS = [
    r"veri seti",
    r"profil",
    r"sekt[oö]r",
    r"meslek",
    r"occupation",
    r"[sş]ehir",
    r"deneyim",
    r"dil\b",
    r"language",
    r"profiletype",
    r"servicemodes?",
    r"hizmet mod",
] + SCHEMA_FIELD_NAMES

# ─── 3. Agregasyon / İstatistik İşlem Kalıpları ───
AGGREGATION_EXPLICIT_PATTERNS = [
    r"ka[cç] profil",
    r"profil say[ıi]s[ıi]",
    r"say[ıi]s[ıi] ka[cç]t[ıi]r",
    r"ka[cç] (farkl[ıi]|tane|ki[sş]i|adet)",
    r"toplam.*(say[ıi]|profil|adet|miktar)",
    r"minimum.*maksimum|min.*max|en (az|fazla|ç[oö]k|yüksek|düşük)",
    r"ortalamas?[ıi]?",
    r"da[gğ][ıi]l[ıi]m[ıi]?",
    r"oran[ıi].*y[uü]zde|y[uü]zde.*ka[cç]",
    r"s[ıi]ralama",
    r"kar[sş][ıi]la[sş]t[ıi]r",
    r"\d+\s*profil",                        # "40 profille", "32 profilli"
    r"istatisti[gğk]",                      # "istatistiğine göre"
    r"sectordistribution",
    r"i[cç]eren ka[cç]",                    # "içeren kaç profil"
    r"en s[ıi]k ge[cç]en",                  # "en sık geçen ikinci dil"
]

# ─── 4. Şema ve Meta Tanım Kalıpları ───
SCHEMA_DEFINITION_PATTERNS = [
    r"ne i[sş]e yarar",
    r"ne i[cç]in kullan[ıi]l[ıi]r",
    r"hangi .* (alabilir|belirt|açıkla)",
    r"neden g[oö]r[uü]n[uü]r de[gğ]ildir",
    r"alan[ıi] ne(dir)?",
    r"b[oö]l[uü]m[uü]ne g[oö]re",
    r"fieldguide",
    r"safetyanddataquality",
    r"sentetik",
    r"synthetic",
    r"do[gğ]rulamas[ıi] iddia",
    r"hangi alan",
    r"hangi .* de[gğ]er",
]


def classify_query(query: str) -> Dict[str, Any]:
    """
    Kullanıcı sorusunu analiz edip doğru rotayı (Intent) ve işlem türünü belirler.

    Öncelik Sırası:
    1. Agregasyon/İstatistik: Soruda hesaplama/sayma/istatistik isteniyorsa
    2. Şema/Alan Tanımı: Şema alan adları, veri kalitesi, fieldGuide sorguları
    3. Semantik/Genel Arama: PDF, Word, metin dokümanları
    """
    q_clean = query.strip().lower()
    
    # ── KONTROL 1: Veri Seti Agregasyonu (Hesaplama / İstatistik) ──
    has_dataset_term = any(re.search(p, q_clean, re.IGNORECASE) for p in DATASET_INDICATORS)
    is_agg_operation = any(re.search(p, q_clean, re.IGNORECASE) for p in AGGREGATION_EXPLICIT_PATTERNS)

    if has_dataset_term and is_agg_operation:
        if re.search(r"minimum.*maksimum|min.*max|en (az|düşük).*en (fazla|çok|yüksek)", q_clean):
            op = "min_max"
        elif re.search(r"ka[cç] farkl[ıi]", q_clean):
            op = "nunique"
        elif re.search(r"true|false|sekt[oö]r[uü]nde|alan[ıi]", q_clean) and re.search(r"say[ıi]|ka[cç]", q_clean):
            op = "filtered_count"
        else:
            op = "count"

        return {
            "intent": QueryIntent.AGGREGATION,
            "target": "dataset",
            "operation": op,
            "reason": f"Veri seti üzerinde sayısal hesaplama tespit edildi (işlem: {op})"
        }

    # ── KONTROL 2: Şema / Meta Alan Tanımı (fieldGuide / metadata) ──
    has_schema_field = any(field in q_clean for field in SCHEMA_FIELD_NAMES)
    is_schema_def = any(re.search(p, q_clean, re.IGNORECASE) for p in SCHEMA_DEFINITION_PATTERNS)

    if (has_schema_field or is_schema_def) and has_dataset_term:
        return {
            "intent": QueryIntent.SCHEMA,
            "target": "schema",
            "operation": "field_lookup",
            "reason": "Veri seti şeması / metadata / fieldGuide tanım sorgusu tespit edildi"
        }

    # ── KONTROL 3: Semantik Doküman Arama (PDF / DOCX / TXT) ──
    return {
        "intent": QueryIntent.SEMANTIC,
        "target": "general_docs",
        "operation": "vector_bm25_search",
        "reason": "Genel doküman içeriği ve semantik RAG araması"
    }


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

    test_queries = [
        # JSON Veri Seti - Agregasyon
        ("Veri setindeki toplam profil sayısı kaçtır?", QueryIntent.AGGREGATION),
        ("Veri setinde kaç farklı sektör bulunmaktadır?", QueryIntent.AGGREGATION),
        ("Veri setinde kaç farklı meslek (occupation) bulunmaktadır?", QueryIntent.AGGREGATION),
        ('"Sağlık" sektöründe kaç profil bulunmaktadır?', QueryIntent.AGGREGATION),
        ("appointmentSettings içindeki autoApproveRequests alanı true olan profil sayısı kaçtır?", QueryIntent.AGGREGATION),
        ("Veri setindeki profillerde toplam kaç farklı şehir yer almaktadır?", QueryIntent.AGGREGATION),
        ("Profillerdeki mesleki deneyim (experience.years) alanının minimum ve maksimum değerleri nedir?", QueryIntent.AGGREGATION),
        
        # JSON Veri Seti - Şema / Meta
        ('"profileCode" alanı ne için kullanılır?', QueryIntent.SCHEMA),
        ("Bir profildeki hizmet modları (serviceModes) hangi üç değerden birini alabilir?", QueryIntent.SCHEMA),
        ('"publicContact" alanında telefon ve e-posta neden görünür değildir?', QueryIntent.SCHEMA),
        ("weeklyAvailability yapısında bir günün aktif olup olmadığı hangi alanla belirtilir?", QueryIntent.SCHEMA),
        ('Veri setinin "synthetic" (sentetik) olduğu hangi alanlarla açıkça belirtilmiştir?', QueryIntent.SCHEMA),
        ('"safetyAndDataQuality" bölümüne göre veri setinin gerçek kişi/işletme doğrulaması iddia edilmekte midir?', QueryIntent.SCHEMA),
        
        # Genel Dokümanlar (PDF / DOCX / TXT) - Semantik RAG
        ("Bağlamdan bağımsız dilbilgisi kaç elemanlı bir yapıdır?", QueryIntent.SEMANTIC),
        ("Fourier dönüşümünün ileri yönü hangi işlemi yapar?", QueryIntent.SEMANTIC),
        ("Summer School programı kaç haftalıktır?", QueryIntent.SEMANTIC),
        ("Gümüş Yaprak kütüphanesinde çalışan genç çırağın adı nedir?", QueryIntent.SEMANTIC),
    ]

    all_passed = True
    print("=" * 70)
    print("ROUTER DOĞRULAMA TESTLERİ")
    print("=" * 70)

    for q, expected_intent in test_queries:
        res = classify_query(q)
        is_ok = (res["intent"] == expected_intent)
        if not is_ok:
            all_passed = False
        status = "✅ PASS" if is_ok else "❌ FAIL"
        print(f"{status} | Beklenen: {expected_intent.value:<11} | Çıkan: {res['intent'].value:<11} | Soru: {q[:50]}...")

    print("\nSonuç:", "🎉 TÜM TESTLER BAŞARIYLA GEÇTİ!" if all_passed else "⚠️ BAZI TESTLER BAŞARISIZ OLDU.")
