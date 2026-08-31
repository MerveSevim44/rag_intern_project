"""
benchmark_eval.py — Otomatik Doğruluk Skorlaması (EM / F1 / ROUGE-L / Semantik) ve Benchmark Raporlama

Bu modül, test_sonuclari.csv dosyalarını otomatik olarak değerlendirir:
1. Türkçe Uyumlu Metin Normalizasyonu
2. Exact Match (EM) Skoru (Sıkı & Yumuşak)
3. Token Seviyesi Precision, Recall ve F1 Skoru (SQuAD standardı)
4. ROUGE-L (LCS tabanlı) — kelime sırasına duyarlı örtüşme
5. Semantik Benzerlik (bge-m3 embedding + kosinüs) — anlamca doğruluk
4. Retrieval (Kaynak Eşleşme) Başarısı
5. Negatif Test & Halüsinasyon Tespiti (TP, TN, FP, FN Sınıflandırması)
6. Yanıt Süresi (Latency) Analizi
7. Yüksek Kaliteli Benchmark Görselleri (PNG) Üretimi
8. CSV & JSON Rapor Dışa Aktarımı
"""

import argparse
import csv
import json
import re
import string
from collections import Counter
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np

# Türkçe karakter dönüşüm haritası
TR_LOWER_MAP = {
    ord("İ"): "i",
    ord("I"): "ı",
    ord("Ö"): "ö",
    ord("Ü"): "ü",
    ord("Ş"): "ş",
    ord("Ç"): "ç",
    ord("Ğ"): "ğ",
}


# F1/EM hesabında silinmemesi gereken anlamlı semboller (tek karakterlik olanlar).
MATH_SYMBOLS = ["∈", "∉", "∩", "∪", "⊆", "⊂", "∅", "Ø", "λ", "→", "=", "+", "-", "*", "/", "{", "}"]


def turkish_lower(text: str) -> str:
    """Türkçe karakterleri güvenli şekilde küçük harfe çevirir."""
    if not text:
        return ""
    return text.translate(TR_LOWER_MAP).lower()


def normalize_text_tr(text: str) -> str:
    """
    Değerlendirme öncesi metni temizler ve standardize eder:
    - Küçük harfe çevirme (Türkçe uyumlu)
    - Kaynak satırlarını ("Kaynak: ...", "(sayfa 2)") ve sistem kalıntılarını ("ÜRETİMİ BİTİR.") temizleme
    - Noktalama işaretlerini boşluğa dönüştürme
    - Fazla boşlukları kaldırma
    """
    if not text:
        return ""

    text = turkish_lower(text)

    # Sistem ve kaynak kalıntılarını temizle
    text = re.sub(r"kaynak\s*:\s*.*", "", text)
    text = re.sub(r"üretimi\s+bitir\.?", "", text)
    text = re.sub(r"bu bilgi dokümanlarda bulunmuştur\.?", "", text)
    text = re.sub(r"adlı kaynaktan alındı\.?", "", text)
    text = re.sub(r"cevap\s*:\s*", "", text)

    # Noktalama işaretlerini kaldır
    # Matematiksel/kümesel semboller ANLAM TAŞIR (VT = {+, -, *, /}, VN ∩ VT = Ø).
    # Bunlar tamamen silinince sembolik cevaplarda ortak token kalmıyor ve F1
    # haksız yere 0 çıkıyordu. Önce ayrı token'a açılır, kalan noktalama silinir.
    for sym in MATH_SYMBOLS:
        text = text.replace(sym, f" {sym} ")

    _drop = "".join(
        c for c in (string.punctuation + "'\"’“”«»–—\n\r\t") if c not in set(MATH_SYMBOLS)
    )
    punct_pattern = re.compile(f"[{re.escape(_drop)}]")
    text = punct_pattern.sub(" ", text)

    # Tekrarlayan boşlukları teke indir
    text = " ".join(text.split())
    return text


def tokenize_tr(text: str) -> list[str]:
    """Normalize edilmiş metni kelime token'larına ayırır."""
    normalized = normalize_text_tr(text)
    return normalized.split()


def compute_exact_match(prediction: str, ground_truths: list[str]) -> float:
    """
    Exact Match (EM) Skoru (0.0 veya 1.0)
    Tahmin ile herhangi bir referans cevabın normalize hali birebir eşleşiyor mu?
    """
    norm_pred = normalize_text_tr(prediction)
    for gt in ground_truths:
        norm_gt = normalize_text_tr(gt)
        if norm_pred == norm_gt:
            return 1.0
        # Kısa yanıtlar için (örn "304", "alis", "korev", "sqlite", "dörtlü")
        if len(norm_gt.split()) <= 3 and norm_gt in norm_pred:
            # Eğer yanıt içinde doğrudan hedef net cevap geçiyorsa tam eşleşme kabul edilir
            return 1.0
    return 0.0


def compute_soft_match(prediction: str, ground_truths: list[str]) -> float:
    """
    Yumuşak Eşleşme (Soft EM / Containment).

    Katı EM, uzun referanslarda pratikte hiç 1.0 vermiyor: model doğru cevabı
    kendi cümlesiyle söylediğinde bile 0 alıyor (Orta/Zor kategorilerinde
    EM'in %0 çıkmasının sebebi budur). Soft EM, referansın kısa çekirdeğinin
    tahminin içinde geçip geçmediğine bakar:
      - normalize referans, tahminin alt dizgisi ise, VEYA
      - kısa (<= 12 token) bir referansın TÜM token'ları tahminde geçiyorsa.
    """
    norm_pred = normalize_text_tr(prediction)
    if not norm_pred:
        return 0.0
    pred_tokens = set(norm_pred.split())

    for gt in ground_truths:
        norm_gt = normalize_text_tr(gt)
        if not norm_gt:
            continue
        if norm_gt == norm_pred or norm_gt in norm_pred:
            return 1.0
        gt_tokens = norm_gt.split()
        if 0 < len(gt_tokens) <= 12 and set(gt_tokens).issubset(pred_tokens):
            return 1.0
    return 0.0


# ─────────────────────────────────────────────────────────────────────────────
# EK METRİKLER — ROUGE-L ve Semantik Benzerlik
#
# Katı EM/F1 korunur (geriye dönük kıyas için), yanına iki metrik eklenir:
#   * ROUGE-L : en uzun ortak alt dizi (LCS) tabanlı F-ölçüsü. Kelime sırasını
#               dikkate alır, birebir eşleşme dayatmaz.
#   * Semantik: cevabın ANLAMCA doğruluğu. Türkçe eklemeli bir dil olduğu için
#               ("kümesinin"/"kümesi"/"küme") token eşleşmesi haksız düşük skor
#               veriyor; embedding karşılaştırması bunu telafi eder.
# ─────────────────────────────────────────────────────────────────────────────

def _lcs_length(a: list, b: list) -> int:
    """İki token dizisi arasındaki en uzun ortak alt dizinin (LCS) uzunluğu."""
    if not a or not b:
        return 0
    prev = [0] * (len(b) + 1)
    for x in a:
        cur = [0]
        for j, y in enumerate(b):
            cur.append(prev[j] + 1 if x == y else max(cur[j], prev[j + 1]))
        prev = cur
    return prev[-1]


def compute_rouge_l(prediction: str, ground_truths: list[str]) -> float:
    """
    ROUGE-L F-ölçüsü (0.0–1.0), referanslar arasından EN İYİsi alınır.

    NOT: `rouge_score` paketi yerine yerel LCS kullanılıyor. Paketin varsayılan
    tokenizer'ı metni `[^a-z0-9]` ile filtreler; bu Türkçe karakterleri (ç, ğ,
    ı, ö, ş, ü) tamamen siler ve "kümesinin" -> "k mesinin" gibi bozulmalar
    üretir. Buradaki sürüm projenin kendi `tokenize_tr` normalizasyonunu
    kullanır, böylece ROUGE-L ile EM/F1 aynı token uzayında karşılaştırılır.
    """
    pred_tokens = tokenize_tr(prediction)
    if not pred_tokens:
        return 0.0

    best = 0.0
    for gt in ground_truths:
        gt_tokens = tokenize_tr(gt)
        if not gt_tokens:
            continue
        lcs = _lcs_length(pred_tokens, gt_tokens)
        if lcs == 0:
            continue
        prec = lcs / len(pred_tokens)
        rec = lcs / len(gt_tokens)
        f = (2 * prec * rec) / (prec + rec)
        best = max(best, f)
    return best


# Embedding tabanlı semantik benzerlik. Projenin retrieval'da kullandığı
# bge-m3 modeli tekrar kullanılır: multilingual olduğu için Türkçe'yi destekler
# ve ölçüm sistemin kendi embedding kalitesiyle tutarlı olur.
# Skorlama sirasinda embedding modelini bellekte tutma suresi.
SEMANTIC_KEEP_ALIVE = "10m"

_SEMANTIC_AVAILABLE = None
_EMBED_CACHE: dict = {}


def _semantic_backend_ready() -> bool:
    """bge-m3 embedding servisi (Ollama) erişilebilir mi? Tek sefer denenir."""
    global _SEMANTIC_AVAILABLE
    if _SEMANTIC_AVAILABLE is not None:
        return _SEMANTIC_AVAILABLE
    try:
        _embed_text("test")
        _SEMANTIC_AVAILABLE = True
    except Exception as e:
        print(f"UYARI: Semantik benzerlik devre disi ({type(e).__name__}: {e}). "
              f"EM/F1/ROUGE-L etkilenmez.")
        _SEMANTIC_AVAILABLE = False
    return _SEMANTIC_AVAILABLE


def _embed_text(text: str):
    """Metni bge-m3 ile vektöre çevirir (aynı metin tekrar gelirse cache'ten)."""
    key = text.strip()
    if key in _EMBED_CACHE:
        return _EMBED_CACHE[key]
    import sys as _sys
    from pathlib import Path as _Path
    # benchmark_eval bagimsiz calistirilabildigi icin src/ sys.path'te olmayabilir.
    _src = str(_Path(__file__).resolve().parent.parent / "src")
    if _src not in _sys.path:
        _sys.path.insert(0, _src)
    import ollama
    try:
        from src.embedder import EMBED_MODEL
    except ImportError:
        from embedder import EMBED_MODEL
    # embedder.OLLAMA_KEEP_ALIVE = "0" (her cagrida unload) sorgu zamani icin
    # bellek tasarrufu saglar, ama skorlamada yuzlerce ardisik cagri var:
    # her seferinde yeniden yukleme benchmark'i dakikalarca uzatiyor.
    # Skorlama LLM sorgusundan BAGIMSIZ bir toplu is oldugu icin burada
    # modeli sicak tutuyoruz; bge-m3 ~1.2GB, LLM ile cakismasi beklenmiyor.
    resp = ollama.embeddings(model=EMBED_MODEL, prompt=key,
                             keep_alive=SEMANTIC_KEEP_ALIVE)
    vec = resp["embedding"]
    _EMBED_CACHE[key] = vec
    return vec


def compute_semantic_similarity(prediction: str, ground_truths: list[str]) -> float:
    """
    Cevap ile referanslar arasındaki en yüksek kosinüs benzerliği (0.0–1.0).

    Embedding servisi yoksa 0.0 döner ve metrik rapordan düşülür — bu durumda
    EM/F1/ROUGE-L etkilenmez.
    """
    if not prediction or not prediction.strip() or not ground_truths:
        return 0.0
    if not _semantic_backend_ready():
        return 0.0
    try:
        import numpy as _np
        pv = _np.array(_embed_text(prediction), dtype=_np.float32)
        pn = _np.linalg.norm(pv)
        if pn == 0:
            return 0.0
        best = 0.0
        for gt in ground_truths:
            if not gt or not gt.strip():
                continue
            gv = _np.array(_embed_text(gt), dtype=_np.float32)
            gn = _np.linalg.norm(gv)
            if gn == 0:
                continue
            best = max(best, float(_np.dot(pv, gv) / (pn * gn)))
        # Kosinüs [-1,1] aralığında; negatif benzerlik "alakasız" demektir.
        return max(0.0, min(1.0, best))
    except Exception as e:
        print(f"UYARI: Semantik benzerlik hesaplanamadi: {e}")
        return 0.0


def parse_sources(found_src: str) -> list[str]:
    """'a.pdf (sayfa 3); b.json ($.x)' -> ['a.pdf', 'b.json'] (sıra korunur)."""
    out = []
    for part in (found_src or "").split(";"):
        name = re.sub(r"\s*\(.*?\)\s*$", "", part.strip()).strip()
        if name and name not in out:
            out.append(name)
    return out


def compute_retrieval_rank(expected_src: str, found_src: str) -> int:
    """Beklenen kaynağın getirilen listedeki 1-tabanlı sırası; yoksa 0.

    İkili 'var/yok' ölçümü, doğru dokümanı 1. sırada getiren bir sistemle
    5. sırada getireni aynı sayıyor. Sıra bilgisi MRR için gerekli.
    """
    if not expected_src:
        return 0
    for i, name in enumerate(parse_sources(found_src), start=1):
        if expected_src in name or name in expected_src:
            return i
    return 0


def compute_token_f1(prediction: str, ground_truths: list[str]) -> tuple[float, float, float]:
    """
    Token-Level F1 Skoru (Precision, Recall, F1)
    SQuAD / QA değerlendirme standardına uygun şekilde kelime çakışması üzerinden hesaplanır.
    """
    pred_tokens = tokenize_tr(prediction)
    if not pred_tokens:
        return 0.0, 0.0, 0.0

    best_f1 = 0.0
    best_prec = 0.0
    best_rec = 0.0

    for gt in ground_truths:
        gt_tokens = tokenize_tr(gt)
        if not gt_tokens:
            continue

        common = Counter(pred_tokens) & Counter(gt_tokens)
        num_same = sum(common.values())

        if num_same == 0:
            f1, prec, rec = 0.0, 0.0, 0.0
        else:
            prec = num_same / len(pred_tokens)
            rec = num_same / len(gt_tokens)
            f1 = (2 * prec * rec) / (prec + rec)

        if f1 > best_f1:
            best_f1 = f1
            best_prec = prec
            best_rec = rec

    return best_f1, best_prec, best_rec


# Ret beyani kaliplari (substring taramasi — GEVSEK).
_REFUSAL_MARKERS = [
    "dokumanlarda bulunamadi", "bilgi dokumanlarda", "bulunamadi",
    "bulunmamaktadir", "bulunmuyor", "yer almamaktadir", "yer almiyor",
    "gecmemektedir", "belirtilmemistir", "mevcut degildir",
]

# Ret cumlesini KURAN kalip kelimeler. Bunlarin disinda kalan her sozcuk
# "icerik" sayilir. src/llm_client.py icindeki _REFUSAL_FRAME_WORDS ile
# BILINCLI olarak ayni mantiga dayanir: uretim tarafinda "bu bir ret mi"
# sorusuna verilen cevap ile degerlendirme tarafindaki cevap ayrisirsa,
# halusinasyon sayimi sessizce yaniltici olur.
_EVAL_REFUSAL_FRAME_WORDS = {
    "bu", "bir", "bilgi", "bilgiler", "bilgisi", "veri", "veriler", "konu",
    "konuya", "konuda", "konusunda", "dair", "iliskin", "ait", "hakkinda",
    "baglamda", "baglam", "dokuman", "dokumanda", "dokumanlarda", "dokumanlar",
    "belge", "belgede", "metin", "metinde", "herhangi", "soruyla", "soruya",
    "sorunun", "ilgili", "verilen", "mevcut", "net", "dogrudan", "acikca",
    "ve", "ile", "icin", "da", "de", "ise", "olarak", "cevabi", "cevap",
    "yoktur", "yok", "degildir", "ancak", "fakat", "maalesef", "uzgunum",
    "saglanan", "sunulan", "icerisinde", "icinde", "uzerinde", "kaynaklarda",
    "kaynak", "veri", "setinde", "seti", "dosyada", "dosyasinda",
}

# Matematik/sembolik icerik — kelime sayaci bunlari goremez ama bunlar icerik.
_EVAL_MATH_RE = re.compile(r"[∫∞∑∏√±≤≥≠∈∩∪δωπ]|\\int|\\infty|\\omega")


def _fold_tr(text: str) -> str:
    """Turkce aksanlari duzler: 'dokümanlarda' ile 'dokumanlarda' esitlensin.

    normalize_text_tr aksanlari KORUR (EM/F1 icin dogru davranis), bu yuzden
    kalip karsilastirmasi ayrica katlanmis bicim uzerinden yapilir.
    """
    out = (text or "").lower()
    for a, b in (("ı", "i"), ("ü", "u"), ("ö", "o"), ("ş", "s"),
                 ("ğ", "g"), ("ç", "c"), ("â", "a"), ("î", "i"), ("û", "u")):
        out = out.replace(a, b)
    return out


def _refusal_residual_content(text: str) -> str:
    """
    Ret kaliplarini ve kalip kelimeleri dusurdukten sonra GERIYE KALAN icerik.

    Bos donerse cevap salt bir rettir. Doluysa model ret ifadesi kullanmis
    olsa bile fiilen bir seyler iddia etmistir.
    """
    norm = _fold_tr(normalize_text_tr(text or ""))
    for marker in _REFUSAL_MARKERS:
        norm = norm.replace(marker, " ")
    # "bulunamadi" gibi ekli varyantlari da temizle
    norm = re.sub(r"\bbulunama\w*|\bbulunmam\w*|\bbelirtilmem\w*", " ", norm)
    kept = [w for w in norm.split() if w not in _EVAL_REFUSAL_FRAME_WORDS]
    return " ".join(kept).strip()


# Ret cumlesinden SONRA gelen icerigin "aciklama" mi yoksa "yeni iddia" mi
# oldugunu ayirmak icin kullanilir.
#
# Neden gerekli: saf kelime-sayisi esigi, DURUST bir reddi halusinasyon
# sayabiliyordu. Negatif set #231'de model "Bulunamadi. Not: veri setinde
# 2026 guncellemesinde eklenen havaalanlari bulamadim..." dedi — hicbir sey
# uydurmadi, yalnizca reddini gerekcelendirdi — ama artik 8 icerik kelimesi
# kaldigi icin FP sayildi. Oysa asil olcmek istedigimiz sey "model VAR OLMAYAN
# bir sey hakkinda YENI bir iddiada bulundu mu".
#
# Ayrim: sorunun KENDISINDE gecen sayi/varlik tekrar edilirse bu bir iddia
# degil, sorunun yankisidir. Yalnizca soruda GECMEYEN yeni bir sayi, kod ya da
# ozel isim gercek bir iddiadir.

# Cumle basi sayilan konumdan sonra gelen buyuk harfli sozcuk ozel isim
# sayilmaz (Turkce'de cumle basi zaten buyuk harfle baslar).
_SENTENCE_START_RE = re.compile(r"(?:^|[.!?:;]\s*|\n\s*)$")

# Buyuk harfle baslasa bile ozel isim olmayan, sik kullanilan baglayici/
# soylem sozcukleri.
_NOT_PROPER_NOUN = {
    "not", "veri", "bu", "ancak", "fakat", "maalesef", "uzgunum", "dogrudan",
    "acikca", "ilgili", "sorulan", "belirtilen", "yukaridaki", "boyle",
    "dokuman", "dokumanda", "dokumanlarda", "belge", "metin", "kaynak",
    "bilgi", "konu", "evet", "hayir", "ayrica", "ornegin", "yani",
}


def _question_tokens(question: str) -> set:
    """Sorudaki sozcuk ve sayilarin katlanmis (aksansiz) kumesi."""
    q = _fold_tr(normalize_text_tr(question or ""))
    toks = set(q.split())
    # "acc-124" gibi bilesik kodlarin parcalarini da ekle ki cevapta ayrik
    # yazildiginda yankı olarak taninabilsin.
    for t in list(toks):
        for part in re.split(r"[-_/]", t):
            if part:
                toks.add(part)
    return toks


def _new_claims(text: str, question: str) -> list:
    """
    Ret ifadesinden arta kalan icerikte, soruda GECMEYEN yeni iddialar.

    Iddia sayilanlar:
      * yeni sayi (bakiye, tarih, adet...)
      * yeni alfanumerik kod (ACC-124 gibi)
      * yeni ozel isim (Hawaii gibi) — cumle basi olmayan buyuk harfli sozcuk
    """
    residual = _refusal_residual_content(text)
    if not residual:
        return []
    qtokens = _question_tokens(question)

    claims = []
    for tok in residual.split():
        if tok in qtokens:
            continue                      # soruyu tekrarlamak iddia degil
        if any(ch.isdigit() for ch in tok):
            claims.append(tok)            # yeni sayi / kod

    # Ozel isimler icin ORIJINAL buyuk-kucuk harf bilgisi gerekli; residual
    # kucuk harfli oldugu icin ham metin uzerinden ayrica tararız.
    raw = text or ""
    for m in re.finditer(r"[A-ZÇĞİÖŞÜ][\wçğıöşüÇĞİÖŞÜ]+", raw):
        word = m.group(0)
        folded = _fold_tr(word.lower())
        if folded in qtokens or folded in _NOT_PROPER_NOUN:
            continue
        if _SENTENCE_START_RE.search(raw[:m.start()]):
            continue                      # cumle basi -> ozel isim degil
        claims.append(word)
    return claims


def check_is_not_found(text: str, question: str = None) -> bool:
    """
    Cevap GERCEK bir ret beyani mi?

    DIKKAT — bu fonksiyonun eski hali yalnizca "bulunamadi" alt dizgisini
    ariyordu. O tanimla, "Dogrudan bulunamadi, ancak muhtemelen ACC-124
    hesabinin bakiyesi 3.200 USD'dir." gibi bir cevap RET sayilir ve
    halusinasyon (FP) olarak degil dogru negatif (TN) olarak kaydedilirdi —
    yani halusinasyon orani oldugundan DUSUK gorunurdu. Negatif test setinin
    tum amaci tam olarak bunu olcmek oldugu icin tanim siki tutulmustur:
    cevapta ret ifadesi GECMESI yetmez, cevabin ret ifadesinden BASKA bir sey
    iddia etmemesi de gerekir.
    """
    if not text or not text.strip():
        return False
    norm = _fold_tr(normalize_text_tr(text))
    if not any(m in norm for m in _REFUSAL_MARKERS):
        return False
    residual = _refusal_residual_content(text)
    if _EVAL_MATH_RE.search(text):
        return False
    # Soru verildiyse: karar kelime SAYISINA degil, arta kalan icerikte YENI
    # bir iddia (soruda gecmeyen sayi/kod/ozel isim) olup olmadigina bakar.
    # Boylece gerekceli ama durust bir ret (#231) ret sayilir, "bulunamadi
    # ancak muhtemelen 3.200 USD'dir" ise iddia sayilir.
    if question is not None:
        return len(_new_claims(text, question)) == 0

    # Soru verilmediyse eski (yalnizca uzunluga bakan) davranis korunur —
    # boylece bu fonksiyonu soru gecirmeden cagiran yerler etkilenmez.
    return len(residual.split()) < 3


def check_is_not_found_legacy(text: str) -> bool:
    """Eski (gevsek) tanim — yalnizca karsilastirma/regresyon olcumu icin."""
    norm = _fold_tr(normalize_text_tr(text))
    return any(m in norm for m in [
        "dokumanlarda bulunamadi", "dokümanlarda bulunamadı",
        "bilgi dokumanlarda", "bulunamadi", "bulunmamaktadir",
        "bilgi yer almamaktadir", "metinde gecmemektedir",
    ])


def _is_negative_flag(value: str) -> bool:
    """'dokumanda_var_mi' sütununu Türkçe karakter farklarına dayanıklı okur.

    CSV'lerde bu alan 'Hayır', 'Hayir', 'hayır', 'no' gibi farklı biçimlerde
    yazılabiliyor; düz '== "Hayir"' karşılaştırması negatif soruların tamamını
    pozitif sayıp TN/FP matrisini bozuyordu.
    """
    norm = turkish_lower((value or "").strip())
    return norm in {"hayir", "hayır", "hayÄ±r", "no", "yok", "0", "false"}


def _resolve_file(file_path: str) -> Path:
    """Verilen dosya yolunu yerel, datasets ve root dizinlerinde arayarak çözer."""
    p = Path(file_path)
    if p.exists():
        return p
    eval_dir = Path(__file__).resolve().parent
    root_dir = eval_dir.parent
    candidates = [
        eval_dir / file_path,
        root_dir / file_path,
        eval_dir / "datasets" / file_path,
        eval_dir / "datasets" / p.name,
        eval_dir / "ground_truth" / file_path,
        eval_dir / "ground_truth" / p.name,
        eval_dir / p.name,
        root_dir / p.name,
    ]
    for c in candidates:
        if c.exists():
            return c
    return p


# Test setleri ve bunlara ait sonuc/GT dosyalarinin varsayilan adlandirmasi.
TEST_SETS = ["test_1", "test_2", "test_3", "test_4", "test_5"]

# Negatif (kapsam disi) test setleri. TEST_SETS'ten AYRI tutulur cunku bunlar
# EM/F1 gibi metrikleri degil, TN/FP (halusinasyon) matrisini besler.
# Onceden bu setler evaluate_all'a hic girmiyordu; sonucta TN+FP=0 kaliyor ve
# KPI karti "Negatif Test Basarisi %0.0" / "Halusinasyon Orani %0.0" yaziyordu.
# Bu, olculmemis bir metrigi "sifir halusinasyon" gibi okutan yaniltici bir
# gorunumdu - simdi olculmediyse acikca "Olculmedi (n=0)" yaziliyor.
NEGATIVE_SETS = ["test_negative"]


def negative_kpi_values(conf: dict) -> tuple[str, str]:
    """
    Siniflandirma matrisinden negatif-set KPI metinlerini uretir.

    Negatif set skorlanmadiysa (TN+FP == 0) yuzde YAZILMAZ; "Olculmedi (n=0)"
    dondurulur. Halusinasyon orani da negatif soru sayisina bolunur (toplam
    soruya degil) - aksi halde pozitif sorular paydayi sisirip orani oldugundan
    dusuk gosteriyordu.
    """
    tn, fp = conf.get("TN", 0), conf.get("FP", 0)
    n = tn + fp
    if n == 0:
        return "Ölçülmedi (n=0)", "Ölçülmedi (n=0)"
    return (
        f"%{tn / n * 100:.1f} ({tn}/{n})",
        f"%{fp / n * 100:.1f} ({fp}/{n})",
    )


def _set_name_of(path: Path) -> str:
    """'test_2_sonuclari.csv' -> 'test_2'. Taninmayan adlarda stem doner."""
    stem = path.stem
    for suffix in ("_sonuclari", "_results"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
    return stem


def _default_gt_for(csv_file: Path) -> str:
    """Sonuc CSV'sine karsilik gelen test bazli ground truth dosyasini secer."""
    name = _set_name_of(csv_file)
    candidate = Path(__file__).resolve().parent / "ground_truth" / f"{name}.json"
    if candidate.exists():
        return str(candidate)
    # Geriye donuk uyumluluk: test bazli dosya yoksa eski tekil GT'ye dus.
    return "ground_truth.json"


def evaluate_dataset(
    csv_path: str = "test_sonuclari.csv",
    ground_truth_path: str | None = None,
    output_dir: str = "report",
    return_records: bool = False,
):
    """
    Sonuç CSV dosyasını okuyup ground_truth ile eşleştirerek tüm metrikleri hesaplar.
    """
    csv_file = _resolve_file(csv_path)
    if ground_truth_path is None:
        ground_truth_path = _default_gt_for(csv_file)
    gt_file = _resolve_file(ground_truth_path)
    set_name = _set_name_of(csv_file)
    
    out_dir = Path(output_dir)
    if not out_dir.is_absolute():
        root_dir = Path(__file__).resolve().parent.parent
        out_dir = root_dir / output_dir

    out_dir.mkdir(parents=True, exist_ok=True)
    charts_dir = out_dir / "benchmark_charts" / set_name
    charts_dir.mkdir(parents=True, exist_ok=True)

    if not csv_file.exists():
        raise FileNotFoundError(
            f"Sonuç dosyası bulunamadı: '{csv_path}'.\n"
            f"Benchmark skorlamasını yapabilmek için önce test sorularını LLM ile çalıştırıp sonuç dosyasını üretmelisiniz:\n"
            f"  → python run_tests.py evaluation/datasets/test.csv test_sonuclari.csv\n"
            f"Veya hazır bir sonuç CSV dosyanız varsa yolunu parametre olarak verin:\n"
            f"  → python benchmark_eval.py dosya_yolu.csv"
        )
    if not gt_file.exists():
        raise FileNotFoundError(
            f"Ground truth dosyası bulunamadı: '{ground_truth_path}'.\n"
            f"Referans cevapların bulunduğu ground_truth.json dosyasının varlığından emin olun."
        )

    with open(gt_file, "r", encoding="utf-8") as f:
        ground_truths = json.load(f)

    with open(csv_file, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        results = list(reader)

    scored_records = []
    category_stats = {
        "Kolay": {"total": 0, "scored": 0, "em": 0, "em_soft": 0, "f1_sum": 0.0, "p_sum": 0.0, "r_sum": 0.0, "rouge_sum": 0.0, "sem_sum": 0.0, "retrieval_ok": 0, "latencies": []},
        "Orta": {"total": 0, "scored": 0, "em": 0, "em_soft": 0, "f1_sum": 0.0, "p_sum": 0.0, "r_sum": 0.0, "rouge_sum": 0.0, "sem_sum": 0.0, "retrieval_ok": 0, "latencies": []},
        "Zor": {"total": 0, "scored": 0, "em": 0, "em_soft": 0, "f1_sum": 0.0, "p_sum": 0.0, "r_sum": 0.0, "rouge_sum": 0.0, "sem_sum": 0.0, "retrieval_ok": 0, "latencies": []},
        "Negatif": {"total": 0, "scored": 0, "em": 0, "em_soft": 0, "f1_sum": 0.0, "p_sum": 0.0, "r_sum": 0.0, "rouge_sum": 0.0, "sem_sum": 0.0, "retrieval_ok": 0, "latencies": []},
    }

    confusion = {"TP": 0, "TN": 0, "FP": 0, "FN": 0}
    # FN'lerin kırılımı: sorun retrieval'da mı yoksa üretimde mi?
    fn_breakdown = {"retrieval_kacirdi": 0, "dogru_kaynak_ama_cevap_yok": 0}
    conflicts: list[str] = []        # etiketi çelişkili satırlar (bkz. negatiflik kuralı)
    retrieval_ranks: list[int] = []  # pozitif sorularda beklenen kaynağın sırası (0 = yok)

    for row in results:
        q_id = str(row.get("id", "")).strip()
        difficulty = row.get("zorluk", "Orta").capitalize()
        question = row.get("soru", "")
        expected_src = row.get("beklenen_kaynak", "").strip()
        doc_exists = (row.get("dokumanda_var_mi") or "Evet").strip()
        doc_is_negative = _is_negative_flag(doc_exists)
        prediction = row.get("cevap", "")
        found_src = row.get("bulunan_kaynaklar", "")
        try:
            latency = float(row.get("sure_sn", 0.0))
        except (ValueError, TypeError):
            latency = 0.0

        gt_info = ground_truths.get(q_id, {})
        ref_answers = gt_info.get("referans_cevaplar", [])
        # Referans cevabı olmayan sorular EM/F1 ortalamasına KATILMAZ. Eskiden
        # tahminin kendisi referans kabul ediliyordu; bu her soruya EM=1.0
        # vererek skorları yapay olarak şişiriyordu.
        has_reference = bool(ref_answers)

        # NEGATİFLİK KURALI (düzeltildi).
        # Eskiden yalnızca 'dokumanda_var_mi' sütununa bakılıyordu. test_2.csv'de
        # 23 satır 'Hayır' işaretliyken hem 'beklenen_kaynak' dolu hem de
        # ground truth'ta referans cevap vardı; sistem bu soruları doğru
        # yanıtladığı halde 13'ü "halüsinasyon (FP)" sayıldı. Bir soru ancak
        # gerçekten cevapsız olduğunda negatiftir: beklenen kaynak "-" ise,
        # ya da bayrak 'Hayır' VE referans cevap yoksa.
        label_conflict = doc_is_negative and expected_src not in ("", "-") and has_reference
        is_negative = (expected_src == "-") or (doc_is_negative and not has_reference)
        if label_conflict:
            conflicts.append(q_id)
        # Soru da gecirilir: ret sonrasi kalan icerigin "soruyu tekrar" mi
        # yoksa "yeni iddia" mi oldugu ancak soruyla karsilastirilarak
        # ayirt edilebilir (bkz. _new_claims).
        pred_is_not_found = check_is_not_found(prediction, question)

        # Retrieval kontrolü (sıra bilgisiyle -> MRR)
        if is_negative:
            # Negatif sorularda kaynak aranmaz
            retrieval_match = True
            retrieval_rank = 0
        else:
            retrieval_rank = compute_retrieval_rank(expected_src, found_src)
            retrieval_match = retrieval_rank > 0
            retrieval_ranks.append(retrieval_rank)

        # Exact Match & F1
        if not has_reference and not is_negative:
            em_score = soft_em_score = f1_score = prec_score = rec_score = 0.0
            rouge_l_score = semantic_score = 0.0
        elif is_negative:
            # Negatif soruda başarı: modelin bulunamadı demesi
            em_score = 1.0 if pred_is_not_found else 0.0
            soft_em_score = em_score
            f1_score = 1.0 if pred_is_not_found else 0.0
            prec_score = 1.0 if pred_is_not_found else 0.0
            rec_score = 1.0 if pred_is_not_found else 0.0
            # Negatif soruda "dogru cevap" = ret beyani; metin benzerligi anlamsiz
            # oldugu icin EM ile ayni ikili skoru alir.
            rouge_l_score = semantic_score = em_score
        else:
            em_score = compute_exact_match(prediction, ref_answers)
            soft_em_score = max(em_score, compute_soft_match(prediction, ref_answers))
            f1_score, prec_score, rec_score = compute_token_f1(prediction, ref_answers)
            rouge_l_score = compute_rouge_l(prediction, ref_answers)
            semantic_score = compute_semantic_similarity(prediction, ref_answers)

        # Sınıflandırma Mantığı (TP, TN, FP, FN)
        if not is_negative:
            if pred_is_not_found:
                status = "FN"  # Yanlış Negatif (Dokümanda vardı ama bulamadı)
                confusion["FN"] += 1
                # Aksiyon alınabilir kırılım: doğru chunk geldiği halde model
                # "bulunamadı" diyorsa sorun retriever'da değil, üretim/prompt
                # tarafındadır (ör. PDF'ten bozuk çıkan alt-indisli semboller).
                if retrieval_match:
                    fn_breakdown["dogru_kaynak_ama_cevap_yok"] += 1
                else:
                    fn_breakdown["retrieval_kacirdi"] += 1
            else:
                status = "TP"  # Doğru Pozitif (Dokümanda vardı ve yanıt üretti)
                confusion["TP"] += 1
        else:
            if pred_is_not_found:
                status = "TN"  # Doğru Negatif (Dokümanda yoktu ve başarıyla reddetti)
                confusion["TN"] += 1
            else:
                status = "FP"  # Yanlış Pozitif / Halüsinasyon (Dokümanda yoktu ama uydurdu)
                confusion["FP"] += 1

        # Kategori bazlı istatistikleri güncelle
        cat_key = "Negatif" if is_negative else difficulty
        if cat_key not in category_stats:
            cat_key = "Orta"

        scored_for_accuracy = has_reference or is_negative

        stats = category_stats[cat_key]
        stats["total"] += 1
        if scored_for_accuracy:
            stats["scored"] += 1
        stats["em"] += em_score
        stats["em_soft"] += soft_em_score
        stats["f1_sum"] += f1_score
        stats["p_sum"] += prec_score
        stats["r_sum"] += rec_score
        stats["rouge_sum"] += rouge_l_score
        stats["sem_sum"] += semantic_score
        if retrieval_match:
            stats["retrieval_ok"] += 1
        stats["latencies"].append(latency)

        scored_records.append({
            "id": q_id,
            "zorluk": difficulty,
            "kategori": cat_key,
            "soru": question,
            "beklenen_kaynak": expected_src,
            "dokumanda_var_mi": doc_exists,
            "cevap": prediction,
            "referans_cevaplar": " | ".join(ref_answers),
            "em_score": round(em_score * 100, 1),
            "em_soft_score": round(soft_em_score * 100, 1),
            "f1_score": round(f1_score * 100, 1),
            "precision": round(prec_score * 100, 1),
            "recall": round(rec_score * 100, 1),
            "rouge_l": round(rouge_l_score * 100, 1),
            "semantic_sim": round(semantic_score * 100, 1),
            "retrieval_match": "Evet" if retrieval_match else "Hayır",
            "retrieval_sira": retrieval_rank,
            "siniflandirma": status,
            "referans_var_mi": "Evet" if (has_reference or is_negative) else "Hayır",
            "sure_sn": latency,
        })

    # Genel Özet Hesaplama
    total_q = len(results)
    if not scored_records:
        raise ValueError(f"Sonuç dosyası boş veya okunamadı: {csv_file}")

    # EM/F1 yalnızca referans cevabı olan (veya negatif) sorular üzerinden
    # ortalanır; referanssız sorular paydaya girerse skor yapay olarak düşer.
    accuracy_pool = [r for r in scored_records if r["referans_var_mi"] == "Evet"]
    n_acc = len(accuracy_pool)
    overall_em = sum(r["em_score"] for r in accuracy_pool) / n_acc if n_acc else 0.0
    overall_em_soft = sum(r["em_soft_score"] for r in accuracy_pool) / n_acc if n_acc else 0.0
    overall_f1 = sum(r["f1_score"] for r in accuracy_pool) / n_acc if n_acc else 0.0
    overall_prec = sum(r["precision"] for r in accuracy_pool) / n_acc if n_acc else 0.0
    overall_rec = sum(r["recall"] for r in accuracy_pool) / n_acc if n_acc else 0.0
    overall_rouge = sum(r["rouge_l"] for r in accuracy_pool) / n_acc if n_acc else 0.0
    overall_semantic = sum(r["semantic_sim"] for r in accuracy_pool) / n_acc if n_acc else 0.0
    overall_retrieval = sum(1 for r in scored_records if r["retrieval_match"] == "Evet") / total_q * 100 if total_q else 0.0
    # Sıralama duyarlı retrieval metrikleri (yalnız pozitif sorular üzerinden).
    mrr = (sum(1.0 / r for r in retrieval_ranks if r > 0) / len(retrieval_ranks) * 100) if retrieval_ranks else 0.0
    recall_at_1 = (sum(1 for r in retrieval_ranks if r == 1) / len(retrieval_ranks) * 100) if retrieval_ranks else 0.0
    all_latencies = [r["sure_sn"] for r in scored_records]

    category_summary = {}
    for cat, data in category_stats.items():
        cnt = data["total"]
        acc_cnt = data["scored"] or cnt
        if cnt > 0:
            category_summary[cat] = {
                "toplam_soru": cnt,
                "referansli_soru": data["scored"],
                "exact_match_yuzde": round((data["em"] / acc_cnt) * 100, 2),
                "soft_match_yuzde": round((data["em_soft"] / acc_cnt) * 100, 2),
                "f1_skor_yuzde": round((data["f1_sum"] / acc_cnt) * 100, 2),
                "rouge_l_yuzde": round((data["rouge_sum"] / acc_cnt) * 100, 2),
                "semantik_benzerlik_yuzde": round((data["sem_sum"] / acc_cnt) * 100, 2),
                "precision_yuzde": round((data["p_sum"] / acc_cnt) * 100, 2),
                "recall_yuzde": round((data["r_sum"] / acc_cnt) * 100, 2),
                "retrieval_dogruluk_yuzde": round((data["retrieval_ok"] / cnt) * 100, 2),
                "ortalama_sure_sn": round(np.mean(data["latencies"]), 2) if data["latencies"] else 0.0,
                "medyan_sure_sn": round(float(np.median(data["latencies"])), 2) if data["latencies"] else 0.0,
                "min_sure_sn": round(min(data["latencies"]), 2) if data["latencies"] else 0.0,
                "max_sure_sn": round(max(data["latencies"]), 2) if data["latencies"] else 0.0,
            }

    summary = {
        "test_seti": set_name,
        "sonuc_dosyasi": str(csv_file),
        "ground_truth_dosyasi": str(gt_file),
        "toplam_soru": total_q,
        "referansli_soru": n_acc,
        "referanssiz_soru": total_q - n_acc,
        "genel_metrikler": {
            "exact_match_yuzde": round(overall_em, 2),
            "soft_match_yuzde": round(overall_em_soft, 2),
            "f1_skor_yuzde": round(overall_f1, 2),
            "rouge_l_yuzde": round(overall_rouge, 2),
            "semantik_benzerlik_yuzde": round(overall_semantic, 2),
            "precision_yuzde": round(overall_prec, 2),
            "recall_yuzde": round(overall_rec, 2),
            "retrieval_dogruluk_yuzde": round(overall_retrieval, 2),
            "retrieval_mrr_yuzde": round(mrr, 2),
            "retrieval_recall_at_1_yuzde": round(recall_at_1, 2),
            "ortalama_sure_sn": round(float(np.mean(all_latencies)), 2) if all_latencies else 0.0,
            "medyan_sure_sn": round(float(np.median(all_latencies)), 2) if all_latencies else 0.0,
            "min_sure_sn": round(min(all_latencies), 2) if all_latencies else 0.0,
            "max_sure_sn": round(max(all_latencies), 2) if all_latencies else 0.0,
        },
        "siniflandirma_matrisi": confusion,
        "fn_kirilimi": fn_breakdown,
        "etiket_celiskisi_olan_sorular": conflicts,
        "kategori_bazli": category_summary,
    }

    # CSV Dışa Aktarım
    scored_csv_path = out_dir / f"{set_name}_scored.csv"
    fieldnames = list(scored_records[0].keys())
    with open(scored_csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(scored_records)

    # JSON Dışa Aktarım
    summary_json_path = out_dir / f"{set_name}_summary.json"
    with open(summary_json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    # Grafikleri Üret
    generate_benchmark_charts(summary, scored_records, charts_dir)

    print("\n" + "=" * 80)
    print(f"🎯 OTOMATİK SKORLAMA & BENCHMARK SONUÇLARI — {set_name}")
    print("=" * 80)
    print(f"Toplam Değerlendirilen Soru : {total_q}")
    print(f"Genel Exact Match (EM)      : %{summary['genel_metrikler']['exact_match_yuzde']:.1f}")
    print(f"Genel Token F1 Skoru        : %{summary['genel_metrikler']['f1_skor_yuzde']:.1f}")
    print(f"Genel ROUGE-L Skoru         : %{summary['genel_metrikler']['rouge_l_yuzde']:.1f}")
    print(f"Genel Semantik Benzerlik    : %{summary['genel_metrikler']['semantik_benzerlik_yuzde']:.1f}")
    print(f"Genel Soft Match (Soft EM)  : %{summary['genel_metrikler']['soft_match_yuzde']:.1f}")
    # MRR/Recall@1 yalnızca pozitif sorularda tanımlıdır. Sadece negatif soru
    # içeren bir sette (test_5) bunları basmak "Kaynak %100 ama MRR %0" gibi
    # yanıltıcı bir satır üretiyordu.
    if retrieval_ranks:
        print(f"Retrieval Kaynak Doğruluğu  : %{summary['genel_metrikler']['retrieval_dogruluk_yuzde']:.1f}"
              f"  (MRR %{summary['genel_metrikler']['retrieval_mrr_yuzde']:.1f} | "
              f"Recall@1 %{summary['genel_metrikler']['retrieval_recall_at_1_yuzde']:.1f})")
    else:
        print("Retrieval Kaynak Doğruluğu  : — (set yalnızca negatif soru içeriyor)")
    print(f"Ortalama Yanıt Süresi       : {summary['genel_metrikler']['ortalama_sure_sn']:.2f} sn")
    print(f"Halüsinasyon (FP) Oranı     : {confusion['FP']} / {total_q} (%{(confusion['FP'] / total_q) * 100 if total_q else 0.0:.1f})")
    if confusion["FN"]:
        print(f"Cevapsız (FN) kırılımı      : retrieval kaçırdı {fn_breakdown['retrieval_kacirdi']} | "
              f"doğru kaynak geldi ama cevap yok {fn_breakdown['dogru_kaynak_ama_cevap_yok']}")
    if conflicts:
        print(f"⚠️  ETİKET ÇELİŞKİSİ: {len(conflicts)} soruda 'dokumanda_var_mi=Hayır' olduğu halde "
              f"beklenen_kaynak dolu ve referans cevap var. Bunlar POZİTİF sayıldı "
              f"(id: {', '.join(conflicts[:10])}{'...' if len(conflicts) > 10 else ''}). "
              f"Gerçek negatif soruda 'beklenen_kaynak' sütunu '-' olmalıdır.")
    if total_q - n_acc:
        print(f"⚠️  Referans cevabı olmayan {total_q - n_acc} soru EM/F1 ortalamasına dahil edilmedi "
              f"(doldurmak icin: python evaluation/make_ground_truth.py --status).")
    print("-" * 80)
    print("📊 Kategori Bazlı Dağılım:")
    for cat, m in category_summary.items():
        print(f"  [{cat:8s}] EM: %{m['exact_match_yuzde']:5.1f} | Soft: %{m['soft_match_yuzde']:5.1f} | F1: %{m['f1_skor_yuzde']:5.1f}"
              f" | ROUGE-L: %{m.get('rouge_l_yuzde', 0.0):5.1f} | Semantik: %{m.get('semantik_benzerlik_yuzde', 0.0):5.1f}"
              f" | Kaynak: %{m['retrieval_dogruluk_yuzde']:5.1f} | Süre: {m['ortalama_sure_sn']:4.1f}s")
    print("=" * 80)
    print(f"📁 Kaydedilen Dosyalar:")
    print(f"  - Scored CSV   : {scored_csv_path}")
    print(f"  - Summary JSON : {summary_json_path}")
    print(f"  - Grafikler    : {charts_dir}")

    if return_records:
        return summary, scored_records
    return summary


def generate_benchmark_charts(summary: dict, scored_records: list[dict], output_dir: Path):
    """
    Modern, profesyonel kalitede 3 adet benchmark grafiği üretir ve kaydeder.
    """
    # Genel stil yapılandırması
    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.sans-serif"] = ["Segoe UI", "DejaVu Sans", "Arial", "Helvetica"]
    plt.rcParams["axes.edgecolor"] = "#CBD5E1"
    plt.rcParams["axes.linewidth"] = 0.8

    categories = ["Kolay", "Orta", "Zor", "Negatif"]
    cat_summary = summary["kategori_bazli"]

    # -------------------------------------------------------------
    # Grafik 1: Doğruluk & F1 Skoru (Kategori & Genel Karşılaştırma)
    # -------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(10, 5.5), dpi=300)
    fig.patch.set_facecolor("#FFFFFF")
    ax.set_facecolor("#F8FAFC")

    x_labels = [f"{c}\n(n={cat_summary.get(c, {}).get('toplam_soru', 0)})" for c in categories] + [
        f"GENEL\n(n={summary['toplam_soru']})"
    ]
    x = np.arange(len(x_labels))
    width = 0.26

    em_values = [cat_summary.get(c, {}).get("exact_match_yuzde", 0.0) for c in categories] + [
        summary["genel_metrikler"]["exact_match_yuzde"]
    ]
    f1_values = [cat_summary.get(c, {}).get("f1_skor_yuzde", 0.0) for c in categories] + [
        summary["genel_metrikler"]["f1_skor_yuzde"]
    ]
    retrieval_values = [cat_summary.get(c, {}).get("retrieval_dogruluk_yuzde", 0.0) for c in categories] + [
        summary["genel_metrikler"]["retrieval_dogruluk_yuzde"]
    ]

    rects1 = ax.bar(x - width, em_values, width, label="Exact Match (EM %)", color="#3B82F6", edgecolor="#1D4ED8", alpha=0.9, zorder=3)
    rects2 = ax.bar(x, f1_values, width, label="Token F1 Skoru (%)", color="#10B981", edgecolor="#047857", alpha=0.9, zorder=3)
    rects3 = ax.bar(x + width, retrieval_values, width, label="Retrieval Doğruluğu (%)", color="#F59E0B", edgecolor="#B45309", alpha=0.9, zorder=3)

    # Değer etiketleri
    def autolabel(rects):
        for rect in rects:
            height = rect.get_height()
            if height > 0:
                ax.annotate(
                    f"%{height:.1f}",
                    xy=(rect.get_x() + rect.get_width() / 2, height),
                    xytext=(0, 4),
                    textcoords="offset points",
                    ha="center",
                    va="bottom",
                    fontsize=8.5,
                    fontweight="bold",
                    color="#1E293B",
                )

    autolabel(rects1)
    autolabel(rects2)
    autolabel(rects3)

    ax.set_ylabel("Başarı Oranı (%)", fontsize=11, fontweight="bold", color="#1E293B")
    ax.set_title("RAG Sistemi Soru Zorluğuna Göre Doğruluk & F1 Karşılaştırması", fontsize=13, fontweight="bold", pad=15, color="#0F172A")
    ax.set_xticks(x)
    ax.set_xticklabels(x_labels, fontsize=10, fontweight="bold", color="#334155")
    ax.set_ylim(0, 115)
    ax.grid(axis="y", linestyle="--", alpha=0.5, zorder=0, color="#CBD5E1")
    ax.legend(frameon=True, facecolor="#FFFFFF", edgecolor="#E2E8F0", loc="lower right", fontsize=9.5)

    plt.tight_layout()
    chart1_path = output_dir / "benchmark_accuracy_f1.png"
    plt.savefig(chart1_path, dpi=300)
    plt.close()

    # -------------------------------------------------------------
    # Grafik 2: Yanıt Süresi (Latency) Dağılımı ve Ortalamaları
    # -------------------------------------------------------------
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5), dpi=300, gridspec_kw={"width_ratios": [1.4, 1]})
    fig.patch.set_facecolor("#FFFFFF")
    ax1.set_facecolor("#F8FAFC")
    ax2.set_facecolor("#F8FAFC")

    # Kategori bazlı süre bar grafiği
    cat_names = categories + ["Genel"]
    avg_times = [cat_summary.get(c, {}).get("ortalama_sure_sn", 0.0) for c in categories] + [summary["genel_metrikler"]["ortalama_sure_sn"]]
    med_times = [cat_summary.get(c, {}).get("medyan_sure_sn", 0.0) for c in categories] + [summary["genel_metrikler"]["medyan_sure_sn"]]

    x_idx = np.arange(len(cat_names))
    b_width = 0.35

    ax1.bar(x_idx - b_width/2, avg_times, b_width, label="Ortalama Süre (sn)", color="#6366F1", edgecolor="#4338CA", alpha=0.9, zorder=3)
    ax1.bar(x_idx + b_width/2, med_times, b_width, label="Medyan Süre (sn)", color="#EC4899", edgecolor="#BE185D", alpha=0.9, zorder=3)

    for i, (avg_v, med_v) in enumerate(zip(avg_times, med_times)):
        ax1.text(i - b_width/2, avg_v + 0.6, f"{avg_v:.1f}s", ha="center", va="bottom", fontsize=8.5, fontweight="bold", color="#1E293B")
        ax1.text(i + b_width/2, med_v + 0.6, f"{med_v:.1f}s", ha="center", va="bottom", fontsize=8.5, fontweight="bold", color="#1E293B")

    ax1.set_title("Kategori Bazında Yanıt Süreleri (Latency)", fontsize=11.5, fontweight="bold", pad=12, color="#0F172A")
    ax1.set_ylabel("Süre (Saniye)", fontsize=10, fontweight="bold", color="#1E293B")
    ax1.set_xticks(x_idx)
    ax1.set_xticklabels(cat_names, fontsize=9.5, fontweight="bold", color="#334155")
    ax1.set_ylim(0, (max(avg_times + med_times) or 1.0) * 1.25)
    ax1.grid(axis="y", linestyle="--", alpha=0.5, zorder=0, color="#CBD5E1")
    ax1.legend(frameon=True, facecolor="#FFFFFF", edgecolor="#E2E8F0", loc="upper left", fontsize=8.5)

    # Süre dağılımı (Histogram / Boxplot)
    all_lat = [r["sure_sn"] for r in scored_records] or [0.0]
    ax2.hist(all_lat, bins=8, color="#0EA5E9", edgecolor="#0284C7", alpha=0.85, zorder=3)
    ax2.axvline(np.mean(all_lat), color="#DC2626", linestyle="--", linewidth=1.5, label=f"Ortalama: {np.mean(all_lat):.1f}s", zorder=4)
    ax2.axvline(float(np.median(all_lat)), color="#16A34A", linestyle=":", linewidth=2, label=f"Medyan: {np.median(all_lat):.1f}s", zorder=4)

    ax2.set_title("Tüm Test Sorularının Süre Dağılımı", fontsize=11.5, fontweight="bold", pad=12, color="#0F172A")
    ax2.set_xlabel("Yanıt Süresi (Saniye)", fontsize=10, fontweight="bold", color="#1E293B")
    ax2.set_ylabel("Soru Frekansı", fontsize=10, fontweight="bold", color="#1E293B")
    ax2.grid(axis="y", linestyle="--", alpha=0.5, zorder=0, color="#CBD5E1")
    ax2.legend(frameon=True, facecolor="#FFFFFF", edgecolor="#E2E8F0", loc="upper right", fontsize=8.5)

    plt.tight_layout()
    chart2_path = output_dir / "benchmark_latency.png"
    plt.savefig(chart2_path, dpi=300)
    plt.close()

    # -------------------------------------------------------------
    # Grafik 3: Genel Sistem Başarı Karnesi & Sınıflandırma Matrisi
    # -------------------------------------------------------------
    fig, (ax_donut, ax_card) = plt.subplots(1, 2, figsize=(11, 5), dpi=300, gridspec_kw={"width_ratios": [1, 1.2]})
    fig.patch.set_facecolor("#FFFFFF")
    ax_donut.set_facecolor("#FFFFFF")
    ax_card.set_facecolor("#F8FAFC")

    # Donut Chart - Sınıflandırma
    conf = summary["siniflandirma_matrisi"]
    labels = ["Doğru Pozitif (TP)", "Doğru Negatif (TN)", "Yanlış Negatif (FN)", "Halüsinasyon (FP)"]
    sizes = [conf["TP"], conf["TN"], conf["FN"], conf["FP"]]
    colors = ["#10B981", "#3B82F6", "#F59E0B", "#EF4444"]
    explode = (0.03, 0.03, 0.05, 0.08)

    if sum(sizes) == 0:
        sizes = [1, 0, 0, 0]

    wedges, texts, autotexts = ax_donut.pie(
        sizes,
        explode=explode,
        labels=None,
        colors=colors,
        autopct=lambda p: f"{p:.1f}%\n({int(round(p * sum(sizes) / 100))})" if p > 0 else "",
        startangle=140,
        pctdistance=0.75,
        wedgeprops=dict(width=0.45, edgecolor="#FFFFFF", linewidth=2),
    )
    for at in autotexts:
        at.set_color("#0F172A")
        at.set_fontsize(8.5)
        at.set_fontweight("bold")

    ax_donut.set_title(f"Test Sınıflandırma Dağılımı\n(Toplam {summary['toplam_soru']} Soru)", fontsize=11.5, fontweight="bold", pad=10, color="#0F172A")
    ax_donut.legend(wedges, labels, loc="lower center", bbox_to_anchor=(0.5, -0.15), ncol=2, fontsize=8, frameon=False)

    # KPI Kartları
    ax_card.axis("off")
    _neg_success, _halu_rate = negative_kpi_values(conf)
    kpis = [
        ("Exact Match (EM)", f"%{summary['genel_metrikler']['exact_match_yuzde']:.1f}", "#3B82F6"),
        ("Token F1 Skoru", f"%{summary['genel_metrikler']['f1_skor_yuzde']:.1f}", "#10B981"),
        ("Retrieval Başarısı", f"%{summary['genel_metrikler']['retrieval_dogruluk_yuzde']:.1f}", "#F59E0B"),
        ("Negatif Test Başarısı", _neg_success, "#8B5CF6"),
        ("Halüsinasyon Oranı", _halu_rate, "#EF4444"),
        ("Ortalama Yanıt Süresi", f"{summary['genel_metrikler']['ortalama_sure_sn']:.2f} sn", "#6366F1"),
    ]

    ax_card.text(0.5, 0.98, "Sistem Başarı Karnesi (KPI Özeti)", ha="center", va="top", fontsize=12, fontweight="bold", color="#0F172A")

    for i, (title, val, col) in enumerate(kpis):
        y_pos = 0.82 - (i * 0.14)
        # Kutu arka planı
        rect = plt.Rectangle((0.05, y_pos - 0.04), 0.9, 0.11, facecolor="#FFFFFF", edgecolor=col, linewidth=1.5, transform=ax_card.transAxes, zorder=2, clip_on=False)
        ax_card.add_patch(rect)
        ax_card.text(0.1, y_pos + 0.015, title, fontsize=9.5, fontweight="bold", color="#334155", transform=ax_card.transAxes, zorder=3)
        # "Olculmedi (n=0)" / "%21.9 (7/32)" gibi uzun degerler 11 punto ile
        # baslik metnine binebiliyor; uzunluga gore kuculterek tasmayi onluyoruz.
        val_size = 11 if len(val) <= 10 else (9.5 if len(val) <= 15 else 8.5)
        ax_card.text(0.88, y_pos + 0.015, val, fontsize=val_size, fontweight="bold", color=col, ha="right", transform=ax_card.transAxes, zorder=3)

    plt.tight_layout()
    chart3_path = output_dir / "benchmark_overall_summary.png"
    plt.savefig(chart3_path, dpi=300)
    plt.close()



def _summary_from_records(records: list[dict], label: str) -> dict:
    """
    scored_records listesinden (tek set ya da birden fazla setin birleşimi)
    özet metrikleri hesaplar. evaluate_dataset ile aynı tanımları kullanır:
    EM/F1 yalnızca referansı olan (veya negatif) sorular üzerinden ortalanır.
    """
    total_q = len(records)
    confusion = {"TP": 0, "TN": 0, "FP": 0, "FN": 0}
    for r in records:
        confusion[r["siniflandirma"]] = confusion.get(r["siniflandirma"], 0) + 1

    acc_pool = [r for r in records if r["referans_var_mi"] == "Evet"]
    n_acc = len(acc_pool)

    def mean(key, pool):
        return (sum(x[key] for x in pool) / len(pool)) if pool else 0.0

    lats = [r["sure_sn"] for r in records]
    ranks = [r["retrieval_sira"] for r in records if r["kategori"] != "Negatif"]
    mrr = (sum(1.0 / x for x in ranks if x > 0) / len(ranks) * 100) if ranks else 0.0
    r_at_1 = (sum(1 for x in ranks if x == 1) / len(ranks) * 100) if ranks else 0.0

    cats = {}
    for r in records:
        cats.setdefault(r["kategori"], []).append(r)

    kategori_bazli = {}
    for cat, rows in cats.items():
        pool = [x for x in rows if x["referans_var_mi"] == "Evet"]
        cl = [x["sure_sn"] for x in rows]
        kategori_bazli[cat] = {
            "toplam_soru": len(rows),
            "referansli_soru": len(pool),
            "exact_match_yuzde": round(mean("em_score", pool), 2),
            "soft_match_yuzde": round(mean("em_soft_score", pool), 2),
            "f1_skor_yuzde": round(mean("f1_score", pool), 2),
            "rouge_l_yuzde": round(mean("rouge_l", pool), 2),
            "semantik_benzerlik_yuzde": round(mean("semantic_sim", pool), 2),
            "precision_yuzde": round(mean("precision", pool), 2),
            "recall_yuzde": round(mean("recall", pool), 2),
            "retrieval_dogruluk_yuzde": round(
                sum(1 for x in rows if x["retrieval_match"] == "Evet") / len(rows) * 100, 2),
            "ortalama_sure_sn": round(float(np.mean(cl)), 2) if cl else 0.0,
            "medyan_sure_sn": round(float(np.median(cl)), 2) if cl else 0.0,
            "min_sure_sn": round(min(cl), 2) if cl else 0.0,
            "max_sure_sn": round(max(cl), 2) if cl else 0.0,
        }

    return {
        "test_seti": label,
        "toplam_soru": total_q,
        "referansli_soru": n_acc,
        "referanssiz_soru": total_q - n_acc,
        "genel_metrikler": {
            "exact_match_yuzde": round(mean("em_score", acc_pool), 2),
            "soft_match_yuzde": round(mean("em_soft_score", acc_pool), 2),
            "f1_skor_yuzde": round(mean("f1_score", acc_pool), 2),
            "rouge_l_yuzde": round(mean("rouge_l", acc_pool), 2),
            "semantik_benzerlik_yuzde": round(mean("semantic_sim", acc_pool), 2),
            "precision_yuzde": round(mean("precision", acc_pool), 2),
            "recall_yuzde": round(mean("recall", acc_pool), 2),
            "retrieval_dogruluk_yuzde": round(
                sum(1 for r in records if r["retrieval_match"] == "Evet") / total_q * 100, 2) if total_q else 0.0,
            "retrieval_mrr_yuzde": round(mrr, 2),
            "retrieval_recall_at_1_yuzde": round(r_at_1, 2),
            "ortalama_sure_sn": round(float(np.mean(lats)), 2) if lats else 0.0,
            "medyan_sure_sn": round(float(np.median(lats)), 2) if lats else 0.0,
            "min_sure_sn": round(min(lats), 2) if lats else 0.0,
            "max_sure_sn": round(max(lats), 2) if lats else 0.0,
        },
        "siniflandirma_matrisi": confusion,
        "kategori_bazli": kategori_bazli,
    }


def evaluate_all(sets=None, output_dir: str = "report", results_dir: str = ".") -> dict:
    """
    test_1..test_4 sonuçlarını tek tek skorlar, ardından HEPSİNİN BİRLEŞİMİ
    üzerinden genel bir değerlendirme üretir.

    Beklenen sonuç dosyaları: <set>_sonuclari.csv (run_tests.py bunu üretir).
    """
    # Negatif set varsayilan olarak dahil edilir. Kullanici --sets ile acikca
    # bir liste verdiyse ona dokunulmaz.
    sets = list(sets) if sets else TEST_SETS + NEGATIVE_SETS
    out_dir = Path(output_dir)
    if not out_dir.is_absolute():
        out_dir = Path(__file__).resolve().parent.parent / output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    per_set, all_records, missing = {}, [], []
    for name in sets:
        # ONCELIK results_dir'dedir. Ters sirada arandiginda (once cipla dosya
        # adi, sonra results_dir) kokte ayni isimli ESKI bir sonuc dosyasi varsa
        # --results-dir sessizce yok sayiliyor ve baseline yeniden skorlanip
        # "yeni sonuc" diye raporlaniyordu. Bu, karsilastirmayi fark edilmeden
        # gecersiz kilan bir hataydi.
        csv_candidate = _resolve_file(str(Path(results_dir) / f"{name}_sonuclari.csv"))
        if not csv_candidate.exists():
            csv_candidate = _resolve_file(f"{name}_sonuclari.csv")
        if not csv_candidate.exists():
            missing.append(name)
            continue
        summary, records = evaluate_dataset(str(csv_candidate), None, output_dir, return_records=True)
        per_set[name] = summary
        for r in records:
            row = dict(r)
            row["test_seti"] = name
            all_records.append(row)

    if not all_records:
        raise FileNotFoundError(
            "Hicbir sonuc dosyasi bulunamadi. Once testleri calistirin:\n"
            "  -> python evaluation/run_all.py            (4 seti sirayla calistirir)\n"
            "veya tek tek:\n"
            "  -> python run_tests.py evaluation/datasets/test_1.csv test_1_sonuclari.csv"
        )

    overall = _summary_from_records(all_records, "GENEL (tum setler)")
    overall["dahil_edilen_setler"] = list(per_set.keys())
    _nc = overall["siniflandirma_matrisi"]
    overall["negatif_set_olculdu"] = (_nc["TN"] + _nc["FP"]) > 0
    overall["negatif_soru_sayisi"] = _nc["TN"] + _nc["FP"]
    overall["eksik_setler"] = missing
    overall["set_bazli"] = {
        name: {
            "toplam_soru": sm["toplam_soru"],
            "referansli_soru": sm["referansli_soru"],
            **sm["genel_metrikler"],
            "siniflandirma_matrisi": sm["siniflandirma_matrisi"],
        }
        for name, sm in per_set.items()
    }

    scored_path = out_dir / "genel_scored.csv"
    fieldnames = ["test_seti"] + [k for k in all_records[0].keys() if k != "test_seti"]
    with open(scored_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(all_records)

    summary_path = out_dir / "genel_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(overall, f, ensure_ascii=False, indent=2)

    charts_dir = out_dir / "benchmark_charts" / "genel"
    charts_dir.mkdir(parents=True, exist_ok=True)
    generate_benchmark_charts(overall, all_records, charts_dir)

    g = overall["genel_metrikler"]
    conf = overall["siniflandirma_matrisi"]
    print("\n" + "=" * 96)
    print("GENEL DEĞERLENDİRME — TÜM TEST SETLERİNİN TOPLAMI")
    print("=" * 112)
    print(f"{'Set':<10}{'Soru':>6}{'Ref':>6}{'EM%':>8}{'Soft%':>8}{'F1%':>8}{'RgL%':>8}{'Sem%':>8}{'Retr%':>8}{'MRR%':>8}"
          f"{'TP':>5}{'TN':>5}{'FP':>5}{'FN':>5}{'Sure(s)':>10}")
    print("-" * 112)
    for name, m in overall["set_bazli"].items():
        c = m["siniflandirma_matrisi"]
        print(f"{name:<10}{m['toplam_soru']:>6}{m['referansli_soru']:>6}"
              f"{m['exact_match_yuzde']:>8.1f}{m.get('soft_match_yuzde', 0.0):>8.1f}{m['f1_skor_yuzde']:>8.1f}"
              f"{m.get('rouge_l_yuzde', 0.0):>8.1f}{m.get('semantik_benzerlik_yuzde', 0.0):>8.1f}"
              f"{m['retrieval_dogruluk_yuzde']:>8.1f}{m.get('retrieval_mrr_yuzde', 0.0):>8.1f}"
              f"{c['TP']:>5}{c['TN']:>5}{c['FP']:>5}{c['FN']:>5}{m['ortalama_sure_sn']:>10.2f}")
    print("-" * 112)
    print(f"{'GENEL':<10}{overall['toplam_soru']:>6}{overall['referansli_soru']:>6}"
          f"{g['exact_match_yuzde']:>8.1f}{g['soft_match_yuzde']:>8.1f}{g['f1_skor_yuzde']:>8.1f}"
          f"{g.get('rouge_l_yuzde', 0.0):>8.1f}{g.get('semantik_benzerlik_yuzde', 0.0):>8.1f}"
          f"{g['retrieval_dogruluk_yuzde']:>8.1f}{g['retrieval_mrr_yuzde']:>8.1f}"
          f"{conf['TP']:>5}{conf['TN']:>5}{conf['FP']:>5}{conf['FN']:>5}{g['ortalama_sure_sn']:>10.2f}")
    print("=" * 112)
    tq = overall["toplam_soru"]
    neg_total = conf["TN"] + conf["FP"]
    if neg_total:
        print(f"Halusinasyon (FP) orani     : {conf['FP']}/{neg_total} (%{conf['FP'] / neg_total * 100:.1f}) [negatif set uzerinden]")
        print(f"Negatif test basarisi (TN)  : {conf['TN']}/{neg_total} (%{conf['TN'] / neg_total * 100:.1f})")
    else:
        print("Halusinasyon (FP) orani     : Olculmedi (n=0) - negatif set sonucu yok")
        print("Negatif test basarisi (TN)  : Olculmedi (n=0) - once negatif seti calistirin:")
        print("  -> python run_tests.py evaluation/datasets/test_negative.csv test_negative_sonuclari.csv")
    print(f"Cevapsiz kalma (FN) orani   : {conf['FN']}/{tq} (%{conf['FN'] / tq * 100:.1f})")
    if overall["referanssiz_soru"]:
        print(f"UYARI: {overall['referanssiz_soru']} soruda referans cevap yok - EM/F1 ortalamasina girmedi. "
              f"Durum icin: python evaluation/make_ground_truth.py --status")
    if missing:
        print(f"UYARI: Sonuc dosyasi bulunamayan setler: {', '.join(missing)}")
    print(f"Birlesik CSV  : {scored_path}")
    print(f"Genel ozet    : {summary_path}")
    print(f"Genel grafik  : {charts_dir}")
    return overall


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

    parser = argparse.ArgumentParser(description="RAG test sonuçlarını otomatik skorlar ve benchmark grafikleri üretir.")
    parser.add_argument("sonuclar_csv", nargs="?", default=None,
                        help="Skorlanacak sonuç CSV dosyası (örn: test_2_sonuclari.csv)")
    parser.add_argument("ground_truth", nargs="?", default=None,
                        help="Ground Truth JSON (verilmezse evaluation/ground_truth/<set>.json seçilir)")
    parser.add_argument("--output-dir", default="report", help="Rapor ve grafiklerin kaydedileceği dizin")
    parser.add_argument("--all", action="store_true",
                        help="test_1..test_4 sonuçlarını tek tek skorlar ve GENEL değerlendirme üretir")
    parser.add_argument("--sets", nargs="+", default=None,
                        help="--all ile: değerlendirilecek setler (varsayılan: test_1 test_2 test_3 test_4)")

    args = parser.parse_args()
    try:
        if args.all or args.sonuclar_csv is None:
            evaluate_all(args.sets, args.output_dir)
        else:
            evaluate_dataset(args.sonuclar_csv, args.ground_truth, args.output_dir)
    except FileNotFoundError as e:
        sys.exit(f"\n[HATA] {e}\n")
    except Exception as e:
        sys.exit(f"\n[HATA] Değerlendirme sırasında bir hata oluştu: {e}\n")
