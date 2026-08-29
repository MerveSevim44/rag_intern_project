"""
router.py — 4 Kademeli Akıllı Soru Yönlendirme (Query Routing) Modülü

Sorguları 4 katmanda sınıflandırır:
1. "rule_engine"      : Basit, sabit regex/kural motoru ile anında çözülebilen tekil sorular.
2. "code_interpreter" : Çoklu koşul, gruplama, matematik, yüzde, oran, istatistik gerektiren dinamik analitik sorular (Pandas Sandbox).
3. "semantic_rag"     : Kavramsal açıklamalar, şema anlamları, PDF/Word/TXT genel doküman aramaları (Vektör + BM25 + Reranker).
4. "meta_query"       : Veri setinin sınırlarını/varlığını sorgulayan çıkarım (meta) soruları.

Tasarım notu — DATASET BAĞIMSIZLIĞI:
    Router artık tek bir dataset'e (profiles) hardcode edilmiş bir kelime listesine bağlı değildir.
    Veri seti sinyali (`has_dataset_signal`), çalışma anında verilen `df_schema` (gerçek kolon adları)
    üzerinden hesaplanır. Kolonlar İngilizce olabileceği için `COLUMN_TR_ALIASES` sözlüğü ile
    Türkçe karşılıkları da denetlenir. Yeni bir dataset eklendiğinde router'da değişiklik gerekmez;
    yalnızca (isteğe bağlı olarak) alias sözlüğü genişletilebilir.
"""

import re
import unicodedata
from enum import Enum
from typing import Dict, Any, Optional, List, Set


class RouteTarget(str, Enum):
    RULE_ENGINE = "rule_engine"            # 1. Aşama: Hızlı kural/regex motoru
    CODE_INTERPRETER = "code_interpreter"  # 2. Aşama: Dinamik LLM Pandas Sandbox
    SEMANTIC_RAG = "semantic_rag"          # 3. Aşama: Semantik doküman / şema RAG
    META_QUERY = "meta_query"              # 4. Aşama: Çıkarım / meta (veri seti sınırı) sorusu


# Geriye dönük uyumluluk
class QueryIntent(str, Enum):
    AGGREGATION = "rule_engine"
    SCHEMA = "semantic_rag"
    SEMANTIC = "semantic_rag"
    META_QUERY = "meta_query"


# Meta sorular için synthesizer'a iletilecek talimat.
META_QUERY_INSTRUCTION = (
    "Bu bir çıkarım/meta sorusu. Cevap verirken dokümanda AÇIKÇA belirtilen bilgi ile "
    "SENİN çıkarımın arasındaki farkı net şekilde ayırt et. Çıkarımsa "
    "'bu bir çıkarımdır, dokümanda doğrudan belirtilmemiştir' ifadesini kullan."
)

# Yukarıdaki talimatın synthesizer'da uygulanabilir hâle gelmesi için eklenen biçim
# iskeleti. META_QUERY_INSTRUCTION sözleşme metni olarak sabit kalsın diye ayrı tutulur.
META_QUERY_SYNTH_SUFFIX = (
    "\n\nCevabını iki bölüm hâlinde ver:\n"
    "1) DOKÜMANDA AÇIKÇA OLAN: bağlamda birebir yazan ilgili alan/değerler.\n"
    "2) ÇIKARIM: bunlardan ne türetilebilir, türetilemiyorsa neden. Çıkarım kısmında "
    "'bu bir çıkarımdır, dokümanda doğrudan belirtilmemiştir' ifadesini aynen kullan.\n"
    "Sorunun cevabı 'hayır/belirlenemez' ise bunu da gerekçesiyle açıkça yaz — "
    "veri setinde o bilgiyi taşıyan bir alanın BULUNMAMASI da geçerli bir cevaptır."
)


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

# ─── 3. Meta / Çıkarım Sorusu Kalıpları ───
# "Bu bilgi veri setinde doğrudan var mı, yoksa çıkarım mı?" tipindeki sorular.
META_QUERY_PATTERNS = [
    r"do[gğ]rudan belirtilmi[sş]\s*(mi|midir)",
    r"a[cç][ıi]k[cç]a belirtilmi[sş]\s*(mi|midir)",
    r"[cç][ıi]kar[ıi]labilir\s*m[ıi]",
    r"[cç][ıi]kar[ıi]m yap[ıi]labilir\s*m[ıi]",
    r"belirlenebilir\s*m[ıi]",
    r"tespit edilebilir\s*m[ıi]",
    r"ili[sş]kilendirilebilir\s*m[ıi]",
    r"anla[sş][ıi]labilir\s*m[ıi]",
    r"t[uü]retilebilir\s*m[ıi]",
    r"elde edilebilir\s*m[ıi]",
]

# ─── 4. Karmaşıklık / Analitik Hesaplama Sinyalleri (Code Interpreter) ───
# DİKKAT: Buraya yalnızca GERÇEKTEN analitik/hesaplamalı sinyaller girer.
# Jenerik Türkçe bağlaç ve edatlar ("ve", "arasında", "koşul", "büyük"...)
# burada listelenince içinde o kelime geçen HER soru pandas sandbox'ına
# yönleniyordu; benchmark'ta 100 sorunun 39'u bu yüzden yanlış rotaya gidip
# alakasız bir JSON dataset'inden cevaplanmıştı (bkz. report/baseline).
COMPLEXITY_SIGNALS = [
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
    "en büyük",
    "en buyuk",
    "en küçük",
    "en kucuk",
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
    "olanlar",
    "bulunanlar",
    "içeren",
    "iceren",
    "bakiye",
    "değişimi",
    "degisimi",
    "maliyet",
    "medyan",
    "std",
    "sapma",
]

# ─── 5. Kolon Adı → Türkçe Karşılıklar ───
# Şema kolonları çoğunlukla İngilizce olur; kullanıcı ise Türkçe sorar.
# Yeni dataset eklendiğinde bu sözlük genişletilebilir (router mantığı değişmez).
COLUMN_TR_ALIASES: Dict[str, List[str]] = {
    "amount": ["tutar", "miktar", "meblağ", "meblag"],
    "balance": ["bakiye"],
    "category": ["kategori", "sınıf", "sinif"],
    "status": ["durum", "statü", "statu"],
    "type": ["tür", "tur", "tip", "çeşit", "cesit"],
    "date": ["tarih", "gün", "gun", "ay", "yıl", "yil"],
    "time": ["saat", "zaman"],
    "description": ["açıklama", "aciklama", "detay"],
    "account_id": ["hesap", "hesap no", "hesap numarası", "hesap numarasi"],
    "account": ["hesap"],
    "customer": ["müşteri", "musteri"],
    "merchant": ["satıcı", "satici", "işyeri", "isyeri"],
    "currency": ["para birimi", "döviz", "doviz"],
    "transaction": ["işlem", "islem", "hareket"],
    "transactions": ["işlem", "islem", "hareket"],
    "price": ["fiyat", "ücret", "ucret"],
    "quantity": ["adet", "miktar"],
    "name": ["ad", "isim"],
    "city": ["şehir", "sehir", "il"],
    "country": ["ülke", "ulke"],
    "occupation": ["meslek"],
    "sector": ["sektör", "sektor"],
    "industry": ["sektör", "sektor", "endüstri", "endustri"],
    "experience": ["deneyim", "tecrübe", "tecrube"],
    "language": ["dil"],
    "duration": ["süre", "sure", "dakika", "saat"],
    "profile": ["profil"],
    "airport": ["havaalanı", "havaalani", "havalimanı", "havalimani"],
    "latitude": ["enlem"],
    "longitude": ["boylam"],
    "lat": ["enlem"],
    "lon": ["boylam"],
    "email": ["e-posta", "eposta", "mail"],
    "phone": ["telefon"],
    "address": ["adres"],
    "score": ["puan", "skor"],
    "rating": ["puan", "değerlendirme", "degerlendirme"],
    "count": ["sayı", "sayi", "adet"],
    "total": ["toplam"],
}

# Şema verilmediğinde ya da şema eşleşmesi olmadığında devreye giren, veri-seti-üstü genel ipuçları.
# Tek başına yönlendirme yapmaz; yalnızca dataset sinyali olarak sayılır.
GENERIC_DATASET_INDICATORS = [
    r"veri seti",
    r"veri kumesi",
    r"tablo",
    r"dataset",
    r"kayit",
    r"satir",
    r"sutun",
    r"kolon",
    r"alani\b",
]

# Kolon adı olarak anlamsız kalan, çok kısa/çok genel token'lar (yanlış eşleşme önleyici).
_STOP_COLUMN_TOKENS = {"id", "no", "at", "on", "in", "is", "of", "to", "by", "ve", "bir", "the"}


def _normalize(text: str) -> str:
    """Küçük harfe indirir ve Türkçe karakter farklılıklarını sadeleştirir (aksan-duyarsız eşleşme)."""
    text = text.replace("I", "ı").replace("İ", "i")
    text = text.lower()
    for src, dst in (("ı", "i"), ("ş", "s"), ("ğ", "g"), ("ç", "c"), ("ö", "o"), ("ü", "u")):
        text = text.replace(src, dst)
    text = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def _contains_token(haystack_norm: str, needle: str) -> bool:
    """Kelime başına saygılı arama — 've' sinyalinin 'veri' içinde eşleşmesi gibi hataları önler."""
    needle_norm = _normalize(needle).strip()
    if not needle_norm:
        return False
    if not re.search(r"\w", needle_norm):          # "%" gibi semboller
        return needle_norm in haystack_norm

    # Baştan tam kelime eşleşmesi iste; sondaki Türkçe ekleri kelime uzunluğuna
    # göre serbest bırak. Kısa alias'lar ("ay", "il") aksi hâlde "aynı", "ilgili"
    # gibi alakasız kelimelerde yanlış pozitif üretir.
    n = len(needle_norm)
    if n <= 2:
        suffix = r""          # yalnızca tam kelime
    elif n <= 4:
        suffix = r"\w{0,3}"   # gün -> günlük, fark -> farkı/farklı
    else:
        suffix = r"\w*"       # tutar -> tutarındaki
    return re.search(r"(?<!\w)" + re.escape(needle_norm) + suffix + r"(?!\w)", haystack_norm) is not None


def _iter_schema_columns(df_schema: Any) -> List[str]:
    """
    Farklı df_schema biçimlerinden kolon adlarını toplar.

    Desteklenen biçimler:
      * {"amount": "float64", "type": "object"}      -> tek dataset
      * {"transactions": {...}, "profiles": {...}}   -> çoklu dataset (kolonlar BİRLEŞTİRİLİR)
      * [{"amount": ...}, {"city": ...}]             -> dataset listesi
      * ["amount", "type"]                           -> düz kolon listesi
    """
    cols: List[str] = []
    if df_schema is None:
        return cols

    if isinstance(df_schema, dict):
        for key, val in df_schema.items():
            if isinstance(val, dict):                                       # dataset_name -> schema
                cols.extend(_iter_schema_columns(val))
            elif isinstance(val, (list, tuple, set)) and not isinstance(val, str):
                cols.extend(_iter_schema_columns(list(val)))
            else:
                cols.append(str(key))
    elif isinstance(df_schema, (list, tuple, set)):
        for item in df_schema:
            if isinstance(item, (dict, list, tuple, set)):
                cols.extend(_iter_schema_columns(item))
            else:
                cols.append(str(item))
    else:
        cols.append(str(df_schema))

    seen: Set[str] = set()
    out: List[str] = []
    for c in cols:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def _column_variants(column: str) -> List[str]:
    """
    Bir kolon adının aranabilir varyantlarını üretir:
    tam ad, alt parçalar (snake_case / camelCase / dotted ayrımı) ve Türkçe alias'lar.
    """
    variants: List[str] = [column]
    parts = [p for p in re.split(r"[^A-Za-z0-9ğüşıöçĞÜŞİÖÇ]+", column) if p]
    expanded: List[str] = []
    for p in parts:
        expanded.extend([s for s in re.split(r"(?<=[a-z0-9])(?=[A-Z])", p) if s])

    for token in set(parts + expanded):
        if len(token) >= 3 and _normalize(token) not in _STOP_COLUMN_TOKENS:
            variants.append(token)

    # Türkçe karşılıklar: hem tam kolon adı hem de parçaları üzerinden aranır.
    lookup_keys = {_normalize(column)} | {_normalize(t) for t in parts + expanded}
    for key, aliases in COLUMN_TR_ALIASES.items():
        if _normalize(key) in lookup_keys:
            variants.extend(aliases)

    seen: Set[str] = set()
    out: List[str] = []
    for v in variants:
        n = _normalize(v)
        if n and n not in seen:
            seen.add(n)
            out.append(v)
    return out


def detect_schema_matches(question: str, df_schema: Any = None) -> List[str]:
    """
    Soru metni ile şema kolonları (ve Türkçe karşılıkları) arasındaki eşleşmeleri döner.
    Dönen öğeler "col" veya "col~alias" biçimindedir (loglamada okunabilir olsun diye).
    """
    q_norm = _normalize(question)
    matches: List[str] = []
    for col in _iter_schema_columns(df_schema):
        for variant in _column_variants(col):
            if _contains_token(q_norm, variant):
                matches.append(col if _normalize(variant) == _normalize(col) else f"{col}~{variant}")
                break
    return matches


def matches_simple_pattern(question: str) -> bool:
    """Sorunun basit kural motoruyla (regex/önbellek) çözülüp çözülemeyeceğini kontrol eder."""
    q = question.strip().lower()
    return any(re.search(pat, q, re.IGNORECASE) for pat in SIMPLE_RULE_PATTERNS)


def is_schema_or_doc_conceptual(question: str) -> bool:
    """Sorunun şema tanımı (fieldGuide vb.) veya genel metin sorusu olup olmadığını denetler."""
    q = question.strip().lower()
    return any(re.search(pat, q, re.IGNORECASE) for pat in SCHEMA_DEFINITION_PATTERNS)


def is_meta_query(question: str) -> bool:
    """Sorunun veri setinin sınırlarını/çıkarılabilirliğini sorgulayan bir meta soru olup olmadığı."""
    q = question.strip().lower()
    return any(re.search(pat, q, re.IGNORECASE) for pat in META_QUERY_PATTERNS)


def _analyze(question: str, df_schema: Any = None) -> Dict[str, Any]:
    """route_query'nin tüm sinyallerini hesaplayan ortak çekirdek (debug çıktısının kaynağı)."""
    q_raw = question.strip()
    q_low = q_raw.lower()
    q_norm = _normalize(q_raw)

    matched_simple = [p for p in SIMPLE_RULE_PATTERNS if re.search(p, q_low, re.IGNORECASE)]
    matched_meta = [p for p in META_QUERY_PATTERNS if re.search(p, q_low, re.IGNORECASE)]
    matched_schema = [p for p in SCHEMA_DEFINITION_PATTERNS if re.search(p, q_low, re.IGNORECASE)]
    matched_complexity = [s for s in COMPLEXITY_SIGNALS if _contains_token(q_norm, s)]

    schema_matches = detect_schema_matches(q_raw, df_schema)
    matched_generic = [p for p in GENERIC_DATASET_INDICATORS if re.search(p, q_norm, re.IGNORECASE)]

    has_complexity = bool(matched_complexity)
    has_dataset_signal = bool(schema_matches) or bool(matched_generic)

    # ── Karar Zinciri ──
    if matched_simple:
        target, reason = RouteTarget.RULE_ENGINE.value, "simple_rule_pattern"
    elif matched_meta:
        # Meta kontrolü complexity/schema'dan ÖNCE gelir: bu sorular veri setinin
        # sınırlarını sorgular, ne hesaplama ne de saf doküman sorusudur.
        target, reason = RouteTarget.META_QUERY.value, "meta_query_pattern"
    elif matched_schema:
        target, reason = RouteTarget.SEMANTIC_RAG.value, "schema_or_doc_conceptual"
    elif has_complexity and has_dataset_signal:
        # Complexity sinyali TEK BAŞINA YETMEZ; yanında bir dataset sinyali de
        # gerekir. Eski varsayım "sandbox en kötü 'veri bulunamadı' der, bu
        # RAG'ın yanlış cevabından iyidir" idi — benchmark bunu çürüttü:
        # dataset belirsiz olduğunda sandbox alakasız bir dosya seçip (Fourier
        # sorusuna 728_profiles.json ile) KENDİNDEN EMİN UYDURMA cevap üretiyor.
        # Dataset sinyali yoksa doğru yer semantik RAG'dir.
        target = RouteTarget.CODE_INTERPRETER.value
        reason = "complexity_signal+dataset_signal"
    elif has_dataset_signal and any(
        _contains_token(q_norm, w) for w in ["kaç", "hangisi", "hangileri", "oran", "yüzde", "en"]
    ):
        target, reason = RouteTarget.CODE_INTERPRETER.value, "dataset_signal+interrogative"
    else:
        target, reason = RouteTarget.SEMANTIC_RAG.value, "fallback_semantic"

    return {
        "target": target,
        "reason": reason,
        "has_complexity": has_complexity,
        "has_dataset_signal": has_dataset_signal,
        "is_meta_query": bool(matched_meta),
        "is_schema_conceptual": bool(matched_schema),
        "is_simple_rule": bool(matched_simple),
        "matched_patterns": {
            "simple_rule": matched_simple,
            "meta_query": matched_meta,
            "schema_definition": matched_schema,
            "complexity": matched_complexity,
            "generic_dataset": matched_generic,
        },
        "matched_schema_columns": schema_matches,
        "schema_columns_seen": _iter_schema_columns(df_schema),
    }


def route_query(question: str, df_schema: Optional[Any] = None, debug: bool = False):
    """
    Kullanıcı sorusunu 4'lü mimariye göre yönlendirir.

    Karar sırası:
      1. Basit regex / kural motoru       -> 'rule_engine'
      2. Meta / çıkarım sorusu            -> 'meta_query'
      3. Kavramsal / şema tanımı sorusu   -> 'semantic_rag'
      4. Karmaşıklık (hesaplama) sinyali  -> 'code_interpreter'  (dataset sinyali ŞART DEĞİL)
      5. Dataset sinyali + soru kalıbı    -> 'code_interpreter'
      6. Hiçbiri                          -> 'semantic_rag'

    Args:
        question:  Kullanıcı sorusu.
        df_schema: Yüklü dataset(ler)in kolon şeması. Tek şema, çoklu şema veya düz
                   kolon listesi kabul eder; çoklu ise tüm kolonlar birleştirilir.
        debug:     True ise str yerine tüm sinyalleri içeren dict döner.

    Returns:
        str ("rule_engine" | "code_interpreter" | "semantic_rag" | "meta_query"),
        debug=True ise Dict[str, Any].
    """
    info = _analyze(question, df_schema)
    return info if debug else info["target"]


def classify_query(query: str, df_schema: Optional[Any] = None, debug: bool = False) -> Dict[str, Any]:
    """
    Detaylı rota bilgisi döner (geriye dönük uyumlu: 'target', 'intent', 'query' korunur).

    Ek olarak hangi sinyallerin tetiklendiği (has_complexity, has_dataset_signal),
    hangi regex kalıplarının eşleştiği (matched_patterns) ve hangi df_schema
    kolonlarının soruda geçtiği (matched_schema_columns) raporlanır —
    "neden bu soru şuraya yönlendirildi" sorusu loglardan cevaplanabilsin diye.
    """
    info = _analyze(query, df_schema)
    target = info["target"]

    result: Dict[str, Any] = {
        "target": target,
        "intent": target.upper(),
        "query": query,
        "reason": info["reason"],
        "has_complexity": info["has_complexity"],
        "has_dataset_signal": info["has_dataset_signal"],
        "matched_patterns": info["matched_patterns"],
        "matched_schema_columns": info["matched_schema_columns"],
    }

    if target == RouteTarget.META_QUERY.value:
        result["synthesizer_instruction"] = META_QUERY_INSTRUCTION

    if debug:
        result["debug"] = info

    return result


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

    TX_SCHEMA = {
        "amount": "float64",
        "type": "object",
        "category": "object",
        "account_id": "object",
        "date": "datetime64[ns]",
        "description": "object",
    }

    # (soru, beklenen_rota, df_schema)
    test_cases = [
        # ── Rule Engine ──
        ("Veri setindeki toplam profil sayısı kaçtır?", "rule_engine", None),
        ("Veri setinde kaç farklı sektör bulunmaktadır?", "rule_engine", None),

        # ── Code Interpreter (Karmaşık / Hesaplama) ──
        ("Tüm profillerin experience.years alanlarına göre ortalama mesleki deneyim yılı kaçtır?", "code_interpreter", None),
        ('"appointmentSettings.autoApproveRequests" değeri "true" olan profillerin toplam profil sayısına oranı yaklaşık yüzde kaçtır?', "code_interpreter", None),
        ("Veri setindeki profillerde toplam kaç farklı şehir (city) yer almaktadır ve en çok profile sahip ilk 3 şehir hangileridir?", "code_interpreter", None),
        ('"serviceModes" alanında "Yerinde hizmet" seçeneğini içeren kaç profil bulunmaktadır?', "code_interpreter", None),
        ("Çoklu Filtreleme ve Lokasyon Dağılımı: Sağlık sektörü içerisinde deneyimi 10 yılın üzerinde olan profillerin en yoğun bulunduğu iller hangileridir?", "code_interpreter", None),
        ("Hangi ülkede kaç havaalanı bulunmaktadır ve en çok havaalanı olan ülke hangisidir?", "code_interpreter", None),
        ("En yüksek enlem değerine sahip ilk 3 havaalanı hangileridir?", "code_interpreter", None),

        # ── Yeni: farklı dataset (transactions) üzerinde ──
        ("ACC-123 hesabının net bakiye değişimi (toplam credit - toplam debit) nedir?", "code_interpreter", TX_SCHEMA),
        ("Entertainment kategorisindeki abonelik toplam maliyeti, food kategorisinin yüzde kaçıdır?", "code_interpreter", TX_SCHEMA),

        # ── Yeni: Meta / çıkarım soruları ──
        ("'refund' kategorisindeki işlem hangi orijinal işlemle ilişkilendirilebilir ve bu ilişki doğrudan belirtilmiş midir?", "meta_query", TX_SCHEMA),
        ("Aynı gün içindeki işlemlerin sıralaması belirlenebilir mi?", "meta_query", TX_SCHEMA),

        # ── Semantic RAG (Kavramsal / Doküman) ──
        ('"profileCode" alanı ne için kullanılır?', "semantic_rag", None),
        ('"publicContact" alanında telefon ve e-posta neden görünür değildir?', "semantic_rag", None),
        ('Veri setinin "synthetic" (sentetik) olduğu hangi alanlarla açıkça belirtilmiştir?', "semantic_rag", None),
        ("Bağlamdan bağımsız dilbilgisi kaç elemanlı bir yapıdır?", "semantic_rag", None),
        ("Fourier dönüşümünün ileri yönü hangi işlemi yapar?", "semantic_rag", None),
        ("Summer School programı kaç haftalıktır?", "semantic_rag", None),
    ]

    print("=" * 78)
    print("4 KADEMELİ ROUTER DOĞRULAMA TESTİ")
    print("=" * 78)

    passed, failures = 0, []
    for q, expected, schema in test_cases:
        actual = route_query(q, df_schema=schema)
        ok = (actual == expected)
        if ok:
            passed += 1
        else:
            failures.append((q, expected, actual, schema))
        status = "PASS" if ok else "FAIL"
        print(f"{status} | Beklenen: {expected:<16} | Cikan: {actual:<16} | Soru: {q[:45]}...")

    if failures:
        print("\n--- HATA DETAYLARI (debug) ---")
        for q, expected, actual, schema in failures:
            print(f"\nSoru: {q}\n  beklenen={expected} cikan={actual}")
            for k, v in route_query(q, df_schema=schema, debug=True).items():
                print(f"  {k}: {v}")

    print(f"\nSonuc: {passed}/{len(test_cases)} Test Basarili!")
