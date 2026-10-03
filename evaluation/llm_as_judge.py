"""
llm_as_judge.py — LLM-as-a-Judge Değerlendirme Modülü

Mevcut benchmark_eval.py'daki rule-based metrikler (EM, F1, ROUGE-L, Semantik)
dışında, bir LLM'i "hakem" olarak kullanarak cevap kalitesini DEĞERLENDİRİR.

Değerlendirilen boyutlar (her biri 1-5):
  1. Faithfulness      — Cevap, verilen bağlama (context) sadık mı? Halüsinasyon var mı?
  2. Answer Relevance  — Cevap, sorulan soruyu doğrudan yanıtlıyor mu?
  3. Task Performance  — Cevap öz ve kullanılabilir mi? Gereksiz bağlam tekrarı /
                         şişirme bu boyutta cezalandırılır.
  4. Alignment         — Cevap sorunun kapsamında mı, gereksiz varsayım/ek var mı?

Kullanım:
  python llm_as_judge.py                                           # varsayılan test_1_sonuclari.csv
  python llm_as_judge.py datasets/test_3_sonuclari.csv             # belirli bir sonuç dosyası
  python llm_as_judge.py datasets/test_1_sonuclari.csv --output judge_rapor.csv

Mimari:
  test_sonuclari.csv  ─┐
  ground_truth/*.json ─┤──▶  Judge LLM  ──▶  Skorlar (CSV + özet)
  (context: CSV'deki  ─┘
   'context' sütunu)

NOT:
  - Judge template (JUDGE_PROMPT_TEMPLATE) 4 boyutlu değerlendirme (1-5) +
    "doğru ret cevapları" kuralını içerir: bağlamda cevap yoksa ve cevap bunu
    uydurmadan belirtiyorsa AR=4, TP=4 verilir (aynı ret cevabı tutarlı puan
    alsın diye). Gerekçe Türkçe, çıktı JSON'dur.
  - Judge, cevapları üreten lokal modelden (qwen2.5-7b) FARKLI bir modeldir:
    Groq API üzerinden GPT-OSS-120B (varsayılan: openai/gpt-oss-120b).
    Böylece model kendi cevabını puanlamaz (self-preference bias).
    API key proje kökündeki .env dosyasından (GROQ_API_KEY) okunur;
    .env .gitignore'dadır, repoya girmez.
  - VERİ AKIŞI: soru, retrieve edilen bağlam (ders PDF'lerinden chunk'lar)
    ve cevap Groq sunucularına gönderilir (referans cevaplar şu an template'te
    kullanılmadığı için gönderilmez). Groq'un ücretsiz katmanında gizlilik
    garantisi (privacy SLA) yoktur.
  - Context: run_tests.py'nin kaydettiği 'context' sütunu (cevabın üretildiği
    context) kullanılır. Bu sütun olmayan eski CSV'lerde context yeniden
    oluşturulur; o zaman lokal model (Foundry) + Ollama retrieval için gerekir.
    Çıktıdaki 'context_kaynagi' sütunu hangisinin kullanıldığını gösterir.
"""

import argparse
import csv
import json
import os
import re
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

# ─── Proje import'ları ───────────────────────────────────────────────────────
_eval_dir = Path(__file__).resolve().parent
_root_dir = _eval_dir.parent
_src_dir = _root_dir / "src"

# GROQ_API_KEY proje kökündeki .env'den okunur (.gitignore'da, repoya girmez).
# Açık yol: script hangi dizinden çalıştırılırsa çalıştırılsın aynı dosya bulunur.
load_dotenv(_root_dir / ".env")

for _p in [str(_src_dir), str(_eval_dir), str(_root_dir)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    from src.llm_client import load_model, truncate_chunk_text, truncate_context
    from src.retrieval import get_top_chunks
except ImportError:
    from llm_client import load_model, truncate_chunk_text, truncate_context
    from retrieval import get_top_chunks

from gt_utils import is_run_error, load_ground_truth, resolve_reference
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from openai import RateLimitError


# ═══════════════════════════════════════════════════════════════════════════════
# JUDGE PROMPT TEMPLATE
#
# İçerik: 4 boyut (faithfulness, answer relevance, task performance — gereksiz
# bağlam tekrarı/şişirme burada cezalandırılır —, alignment), 1-5 ölçeği ve her
# puanın karşılığı, boyutların birbirinden bağımsız puanlanması, "doğru ret
# cevapları" özel kuralı (AR=4, TP=4) ve Türkçe gerekçe talimatı.
#
# Kullanılan değişkenler (süslü parantez ile; JSON örneğindeki parantezler {{ }}):
#   {question}          — Kullanıcının sorduğu soru
#   {context}           — Cevabın üretildiği bağlam (run_tests.py 'context' sütunu)
#   {answer}            — RAG pipeline'ının ürettiği cevap
#   {reference_answer}  — Ground truth referans cevap(lar); judge_single bunu
#                         gönderir ama template şu an kullanmıyor.
#                         NOT: ground_truth/test_5.json'daki 15 sorunun
#                         (101-115, dokumanda_var_mi=Hayır) referansı bilerek
#                         boş bırakıldı; çalıştırınca "Referans yok" uyarısı
#                         verir. Template {reference_answer}'ı kullanmaya
#                         başlamadan önce test_5.json elle gözden geçirilecek.
#
# Judge'dan beklenen çıktı formatı (JSON):
#   {
#     "faithfulness_score": 1-5 arası puan,
#     "answer_relevance_score": 1-5 arası puan,
#     "task_performance_score": 1-5 arası puan,
#     "alignment_score": 1-5 arası puan,
#     "reasoning": "Kısa açıklama"
#   }
#
# ═══════════════════════════════════════════════════════════════════════════════

JUDGE_PROMPT_TEMPLATE = """Sen sıkı ve tarafsız bir RAG (Retrieval-Augmented Generation) sistemi 
değerlendiricisisin. Görevin, aşağıdaki SORU-BAĞLAM-CEVAP üçlüsünü dört ayrı boyutta puanlamak.

Bu tek bir soru-cevap çiftinin izole değerlendirmesidir (single-turn), önceki konuşma 
geçmişi yoktur ve değerlendirmeni etkilememelidir.

SORU:
{question}

BAĞLAM:
{context}

CEVAP:
{answer}

Değerlendirme boyutları (her biri 1-5):

1. FAITHFULNESS (Sadakat): Cevaptaki her iddia BAĞLAM'da doğrudan destekleniyor mu? 
   Bağlamda olmayan bilgi uydurulmuş mu (halüsinasyon)?
   1 = Ciddi halüsinasyon, bağlamla çelişen veya bağlamda olmayan iddialar var
   3 = Çoğunlukla destekleniyor ama en az bir doğrulanamayan iddia var
   5 = Her iddia bağlamda birebir veya mantıksal olarak destekleniyor

2. ANSWER RELEVANCE (Alaka): Cevap, SORU'nun sorduğu şeyi doğrudan yanıtlıyor mu?
   1 = Soruyla alakasız veya soruyu yanıtlamıyor
   3 = Kısmen yanıtlıyor, sorunun bir kısmını atlıyor veya dolaylı yanıtlıyor
   5 = Soruyu tam ve doğrudan yanıtlıyor

3. TASK PERFORMANCE (Görev Performansı): Cevap, kullanıcının pratikte ihtiyacını ne 
   kadar iyi karşılıyor? Eksiksiz mi, kullanılabilir mi, gereksiz yere uzatılmış mı?
   ÖNEMLİ: Cevap bağlamı gereksiz yere birebir veya neredeyse birebir tekrar ediyorsa, 
   ya da soruyla ilgisiz ek bilgiyle şişiriliyorsa, bunu bu boyutta puan kırarak cezalandır. 
   Uzun ve iyi formatlanmış olmak başlı başına yüksek puan gerekçesi DEĞİLDİR.
   1 = Eksik, kullanılamaz veya gereksiz tekrar/şişirme ile dolu
   3 = Temel ihtiyacı karşılıyor ama gereksiz tekrar veya eksiklik var
   5 = Öz, eksiksiz, gereksiz tekrar yok, doğrudan kullanılabilir

4. ALIGNMENT (Uyum): Cevap, sorunun kapsamında mı kalıyor? İstenmeyen varsayımlar, 
   kapsam dışı ekler veya talimat/bağlam dışı davranış var mı?
   1 = Kapsam dışına çıkmış, istenmeyen varsayımlar veya alakasız ekler içeriyor
   3 = Büyük ölçüde kapsamda ama küçük kapsam dışı ekler var
   5 = Tamamen kapsamda, hiçbir gereksiz varsayım veya ekleme yok

Puanlama kuralları:
- Skalanın tamamını kullan. Vasat bir cevaba otomatik olarak 4 veya 5 verme; 
  gerçekten hak ediyorsa düşük puan ver (1-2 dahil).
- Cevabın uzunluğu, akıcılığı veya iyi formatlanmış olması puanı YÜKSELTEN bir 
  gerekçe değildir. Sadece doğruluk, alaka, kullanılabilirlik ve kapsama bak.
- Emin olmadığın bir iddiayı "muhtemelen doğrudur" diye yüksek puanlama; bağlamda 
  açıkça yoksa düşük puanla.



ÖNEMLİ: Bu dört boyut birbirinden bağımsızdır. Bir cevap faithfulness veya 
answer_relevance açısından başarısız olsa bile, kapsam dışına çıkmamışsa 
(yani istenmeyen varsayım/ekleme yapmamışsa) alignment puanı yüksek kalabilir. 
"Bu bilgi dokümanlarda bulunamadı" gibi bir ret cevabı, doğru ya da yanlış 
olsun, tek başına kapsam dışı sayılmaz — alignment'ı sadece cevabın kapsam 
dışına taşıp taşmadığına göre puanla, diğer boyutlardaki başarısızlığı 
buraya yansıtma.

ÖZEL DURUM — Doğru Ret Cevapları: Eğer BAĞLAM'da sorunun cevabı gerçekten
yoksa ve CEVAP bunu doğru şekilde belirtip bilgi uydurmuyorsa (örn.
"Bu bilgi dokümanlarda bulunamadı" gibi), bu DOĞRU bir ret cevabıdır. Böyle
bir durumda:
- ANSWER RELEVANCE: 4 puan ver. Cevap, sorunun bağlamda yanıtlanamayacağını
  doğru tespit ettiği için soruya uygun bir yanıt vermiştir; sorunun içeriğini
  yanıtlamadığı için 5 değil, ama doğru ve beklenen davranış olduğu için
  düşük puan da almamalıdır.
- TASK PERFORMANCE: 4 puan ver. Kullanıcıya yanlış/uydurma bilgi vermek
  yerine dürüstçe bilginin eksikliğini bildirmek, pratikte doğru ve
  güvenilir bir davranıştır.
Bu durumda FAITHFULNESS ve ALIGNMENT puanlaması yukarıdaki genel kurallara
göre devam eder (doğru ret genelde ikisinde de yüksek puan alır).

Gerekçeyi (reasoning alanını) MUTLAKA Türkçe yaz, soru veya bağlam başka 
dilde olsa bile.

Önce kısa bir gerekçe yaz (3-5 cümle, her boyut için neden o puanı verdiğini özetle), 
sonra SADECE aşağıdaki JSON formatında yanıt ver, başka hiçbir metin ekleme:

{{"faithfulness_score": <1-5>, "answer_relevance_score": <1-5>, "task_performance_score": <1-5>, "alignment_score": <1-5>, "reasoning": "<kısa gerekçe>"}}
"""


# ─── Yapılandırma ────────────────────────────────────────────────────────────

# Judge'ın vereceği puanların skalası
SCORE_MIN = 1
SCORE_MAX = 5

# Judge'dan beklenen skor alanları (JSON anahtarı = CSV sütunu)
SCORE_KEYS = [
    "faithfulness_score",
    "answer_relevance_score",
    "task_performance_score",
    "alignment_score",
]

# Judge modeli — Groq'taki tam model adı (console.groq.com/docs/models)
JUDGE_MODEL = "openai/gpt-oss-120b"

# Groq OpenAI-uyumlu endpoint; OpenAI SDK'sı (langchain-openai) aynen kullanılır
GROQ_BASE_URL = "https://api.groq.com/openai/v1"

# Kısa süreli rate limit (429, TPM/RPM) için tekrar deneme sayısı. Günlük
# limitte (TPD/RPD) tekrar denenmez; ikisi de 429 + rate_limit_exceeded döner,
# yalnızca mesajdaki "per day" ifadesiyle ayırt edilir.
RATE_LIMIT_RETRIES = 5
_DAILY_LIMIT_PATTERN = re.compile(r"per day \((?:TPD|RPD)\)")

# Judge değerlendirmesi sırasında context'i yeniden mi oluşturalım?
# True: soruyu tekrar retrieve ederek güncel context ile değerlendirir
# False: sonuç CSV'deki mevcut kaynakları kullanır (context yeniden oluşturulmaz)
REBUILD_CONTEXT = True


# ─── Yardımcı fonksiyonlar ───────────────────────────────────────────────────

def load_judge_model(model=JUDGE_MODEL):
    """
    Judge LLM'ini Groq API üzerinden yükler (OpenAI-uyumlu endpoint).

    GPT-OSS-120B Groq'ta JSON Object Mode'u destekliyor; response_format ile
    çıktının geçerli JSON olması API tarafında zorlanır. Yine de
    parse_judge_response ve judge_single'daki try/except korunur — Groq JSON
    doğrulaması başarısız olursa 400 (json_validate_failed) döner, o satır
    [LLM HATASI] olarak işaretlenir.
    """
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        sys.exit(
            "GROQ_API_KEY bulunamadı.\n"
            f"Proje kökündeki .env dosyasına ekleyin: {_root_dir / '.env'}\n"
            "  GROQ_API_KEY=..."
        )
    llm = ChatOpenAI(
        model=model,
        base_url=GROQ_BASE_URL,
        api_key=api_key,
        temperature=0,
        # SDK'nın kendi retry'ı kapalı: kısa süreli limit (TPM/RPM) ile günlük
        # limiti (TPD/RPD) ayırt edemiyor. Retry judge_single'da yapılır.
        max_retries=0,
    )
    return llm.bind(response_format={"type": "json_object"})


def build_context_for_question(question, llm, top_k=5):
    """
    Soruyu retrieval pipeline'ından geçirerek context oluşturur.
    run_tests.py'daki build_context ile aynı mantık.
    """
    chunks = get_top_chunks(question, top_k=top_k, use_reranker=True, llm=llm)
    parts = []
    for i, chunk in enumerate(chunks, 1):
        source = Path(chunk["source"]).name
        page_info = chunk.get("page_info", "")
        content = truncate_chunk_text(chunk["content"])
        parts.append(f"[{i}] Kaynak: {source}, {page_info}\n{content}")
    return truncate_context("\n\n".join(parts))


def parse_judge_response(response_text):
    """
    Judge LLM'in cevabından JSON skorlarını çıkarır.

    Robust parsing: LLM bazen JSON'u markdown code block içinde veya
    ek açıklama ile birlikte dönebilir. Bu fonksiyon bunları tolere eder.

    Returns:
        dict: Parsed skorlar veya hata durumunda varsayılan skorlar
    """
    # Markdown code block varsa içeriğini al
    code_block = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", response_text, re.DOTALL)
    if code_block:
        response_text = code_block.group(1)

    # İlk { ile son } arasını bul
    start = response_text.find("{")
    end = response_text.rfind("}")
    if start != -1 and end != -1 and end > start:
        json_str = response_text[start:end + 1]
        try:
            result = json.loads(json_str)
            # Skorların geçerli aralıkta olduğunu doğrula
            # Eksik ya da sayı olmayan alan None olur (bool da int sayıldığı için hariç)
            for key in SCORE_KEYS:
                score = result.get(key)
                if isinstance(score, (int, float)) and not isinstance(score, bool):
                    result[key] = max(SCORE_MIN, min(SCORE_MAX, round(score)))
                else:
                    result[key] = None
            return result
        except json.JSONDecodeError:
            pass

    # JSON parse edilemezse varsayılan döndür
    return {
        **{key: None for key in SCORE_KEYS},
        "reasoning": f"[PARSE HATASI] Judge çıktısı JSON olarak ayrıştırılamadı: {response_text[:200]}",
    }


class DailyLimitError(Exception):
    """Groq günlük kotası (TPD/RPD) doldu; `wait_seconds` mesajdaki bekleme süresi."""

    def __init__(self, message, wait_seconds):
        super().__init__(message)
        self.wait_seconds = wait_seconds


def _retry_after_seconds(message):
    """Groq mesajındaki 'Please try again in 5m47.76s' süresini saniyeye çevirir."""
    match = re.search(r"try again in ((?:\d+h)?(?:\d+m)?(?:[\d.]+s)?)", message)
    if not match or not match.group(1):
        return None
    total = 0.0
    for value, unit in re.findall(r"([\d.]+)([hms])", match.group(1)):
        total += float(value) * {"h": 3600, "m": 60, "s": 1}[unit]
    return total


def judge_single(llm, question, answer, context, reference_answer):
    """
    Tek bir soru-cevap çiftini judge LLM ile değerlendirir.

    Args:
        llm: LangChain ChatOpenAI nesnesi (judge olarak kullanılacak)
        question: Değerlendirilecek soru
        answer: RAG pipeline'ının ürettiği cevap
        context: Cevabın üretildiği bağlam (retrieve edilen chunk'lar)
        reference_answer: Ground truth referans cevap(lar)

    Returns:
        dict: Judge skorları (SCORE_KEYS + reasoning)
    """
    if not JUDGE_PROMPT_TEMPLATE.strip() or "TODO" in JUDGE_PROMPT_TEMPLATE:
        raise ValueError(
            "JUDGE_PROMPT_TEMPLATE henüz doldurulmadı!\n"
            "Lütfen llm_as_judge.py dosyasındaki JUDGE_PROMPT_TEMPLATE değişkenini\n"
            "kendi judge prompt'unuz ile doldurun."
        )

    # Referans cevapları tek string'e dönüştür
    if isinstance(reference_answer, list):
        ref_text = " | ".join(reference_answer) or "Referans cevap yok"
    else:
        ref_text = str(reference_answer) if reference_answer else "Referans cevap yok"

    # Judge prompt'unu oluştur
    prompt = ChatPromptTemplate.from_messages([
        ("system", "Sen bir RAG değerlendirme hakemisin. Verilen bilgileri analiz ederek puanlama yap."),
        ("user", JUDGE_PROMPT_TEMPLATE),
    ])

    chain = prompt | llm
    inputs = {
        "question": question,
        "context": context,
        "answer": answer,
        "reference_answer": ref_text,
    }
    for attempt in range(RATE_LIMIT_RETRIES + 1):
        try:
            response = chain.invoke(inputs)
            return parse_judge_response(response.content)
        except RateLimitError as e:
            message = str(e)
            wait = _retry_after_seconds(message)
            # Günlük limit: kota dolmuş, tekrar denemek boşuna — çalışmayı durdur.
            if _DAILY_LIMIT_PATTERN.search(message):
                raise DailyLimitError(message, wait) from e
            if attempt == RATE_LIMIT_RETRIES:
                error = e
                break
            wait = wait if wait is not None else 2 ** attempt
            print(f"  ! Kısa süreli rate limit — {wait:.1f} sn bekleniyor "
                  f"({attempt + 1}/{RATE_LIMIT_RETRIES})…")
            time.sleep(wait + 0.5)
        except Exception as e:
            error = e
            break
    return {
        **{key: None for key in SCORE_KEYS},
        "reasoning": f"[LLM HATASI] {error}",
    }


# ─── Ana değerlendirme akışı ─────────────────────────────────────────────────

def resolve_file(file_path):
    """Dosya yolunu çeşitli dizinlerde arayarak çözer."""
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


OUTPUT_FIELDNAMES = ["id", "soru", "cevap", "judge_model", "context_kaynagi",
                     *SCORE_KEYS, "reasoning"]


def load_existing_results(output_csv):
    """
    Önceki judge çıktısını {id: satır} olarak yükler (dosya yoksa boş dict).
    Skorlar CSV'de string olduğu için int/None'a çevrilir.
    """
    path = Path(output_csv)
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        for key in SCORE_KEYS:
            value = (row.get(key) or "").strip()
            row[key] = int(value) if value.isdigit() else None
    return {row["id"]: row for row in rows}


def is_complete(existing, answer, judge_model):
    """
    Önceki judge satırı geçerli mi? Dört skor da dolu olmalı, ve satır aynı
    cevap + aynı judge modeliyle üretilmiş olmalı (sonuç CSV'si yeniden
    üretildiyse ya da judge değiştiyse eski skor bu cevaba ait değildir).
    """
    if existing is None:
        return False
    # run_tests HATA satırı zaten atlanmış olarak yazıldıysa tamamdır; cevap
    # değişirse (run_tests yeniden çalıştı) aşağıdaki kontrol onu yeniden açar.
    if is_run_error(answer) and existing.get("cevap", "") == answer:
        return True
    if existing.get("cevap", "") != answer or existing.get("judge_model") != judge_model:
        return False
    return all(existing.get(key) is not None for key in SCORE_KEYS)


def write_results(output_csv, results):
    with open(output_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDNAMES)
        writer.writeheader()
        writer.writerows(results)


def run_judge_evaluation(sonuc_csv, output_csv=None, ground_truth_path=None,
                         judge_model=JUDGE_MODEL, only_ids=None):
    """
    Sonuç CSV dosyasını LLM-as-a-Judge ile değerlendirir.

    Eksik/hatalı olanları tamamlar: çıktı CSV'si zaten varsa geçerli skorlu
    satırlar korunur, yalnızca skoru boş ya da hatalı (429, parse hatası vb.)
    olan satırlar judge'a gönderilir. `only_ids` verilirse yalnızca o id'ler
    (skorları dolu olsa bile) yeniden değerlendirilir. Baştan çalıştırmak
    için çıktı dosyasını silin.

    Args:
        sonuc_csv: test_X_sonuclari.csv dosya yolu
        output_csv: Çıktı CSV dosya yolu (varsayılan: sonuc_judge.csv)
        ground_truth_path: Ground truth JSON yolu (varsayılan: evaluation/ground_truth/
            altındaki tüm dosyalar, id ile eşleşir; bulunamazsa CSV'deki referans_cevap)
        judge_model: Groq'taki judge model adı (varsayılan: JUDGE_MODEL)
        only_ids: Yalnızca değerlendirilecek soru id'leri (None: eksik/hatalı olanlar)

    Returns:
        list[dict]: Her soru için judge skorları
    """
    # Dosyaları çöz
    sonuc_path = resolve_file(sonuc_csv)
    if not sonuc_path.exists():
        sys.exit(f"Sonuç dosyası bulunamadı: {sonuc_csv}")

    if output_csv is None:
        output_csv = sonuc_path.stem + "_judge.csv"

    # Ground truth yükle
    try:
        gt = load_ground_truth(ground_truth_path)
    except FileNotFoundError as e:
        print(f"[UYARI] {e}")
        gt = {}

    # Sonuç CSV'yi oku
    print(f"Sonuç dosyası: {sonuc_path}")
    with open(sonuc_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        sys.exit("Sonuç dosyası boş!")

    # Hangi satırlar judge'a gidecek?
    for i, row in enumerate(rows, 1):
        row.setdefault("id", str(i))
    existing = load_existing_results(output_csv)
    if only_ids:
        unknown = set(only_ids) - {row["id"] for row in rows}
        if unknown:
            sys.exit(f"Sonuç dosyasında olmayan id(ler): {', '.join(sorted(unknown))}")
        todo = set(only_ids)
    else:
        todo = {row["id"] for row in rows
                if not is_complete(existing.get(row["id"]), row.get("cevap", ""), judge_model)}

    if existing:
        print(f"Önceki çıktı: {output_csv} ({len(existing)} satır) — "
              f"{len(rows) - len(todo)} satır korunuyor, {len(todo)} satır değerlendirilecek.")
    if not todo:
        print("Değerlendirilecek eksik/hatalı satır yok.")
        results = [existing[row["id"]] for row in rows]
        print_summary(results)
        return results

    # Judge modeli (Groq) — cevapları üreten lokal modelden ayrı
    print(f"Judge model: {judge_model} (Groq)")
    judge_llm = load_judge_model(judge_model)

    # run_tests.py LLM'e giden context'i "context" sütununa kaydediyor. Varsa
    # judge cevabı o context'e göre değerlendirir; yeniden retrieve edilen
    # context farklı olabilir (aynı ret cevabı bir context'te 5, ötekinde 1 alır).
    has_saved_context = "context" in rows[0]
    if has_saved_context:
        print("Context: sonuç CSV'sinde kayıtlı (cevabın üretildiği context).")
    else:
        print("[UYARI] Sonuç CSV'sinde 'context' sütunu yok (eski run_tests çıktısı).\n"
              "        Context yeniden oluşturulacak; cevabın üretildiği context'ten "
              "farklı olabilir.")

    # Lokal model yalnızca retrieval (context yeniden oluşturma) için gerekli
    local_llm = None
    if REBUILD_CONTEXT and not has_saved_context:
        print("Retrieval için lokal model yükleniyor...")
        local_llm = load_model()
    print("Hazır.\n")

    # Her satır için judge değerlendirmesi. Korunan satırlar olduğu gibi kalır;
    # çıktı her değerlendirmeden sonra yazılır, böylece süreç yarıda kesilse
    # (Ctrl+C, günlük kota) bile o ana kadarki skorlar kaybolmaz.
    results_by_id = {row["id"]: existing[row["id"]] for row in rows
                     if row["id"] not in todo and row["id"] in existing}
    toplam = len(todo)
    sira = 0
    missing_references = []
    skipped_errors = []
    skipped_context = []

    for row in rows:
        soru_id = row["id"]
        if soru_id not in todo:
            continue
        sira += 1
        question = row.get("soru", "")
        answer = row.get("cevap", "")

        print(f"[{sira}/{toplam}] Soru #{soru_id}: {question[:60]}...")

        # run_tests.py'nin "HATA: ..." yazdığı satır bir cevap değil: judge'a
        # gönderilmez (token harcanmaz), skorsuz ve [ATLANDI] olarak yazılır.
        if is_run_error(answer):
            skipped_errors.append(soru_id)
            results_by_id[soru_id] = {
                "id": soru_id,
                "soru": question,
                "cevap": answer,
                "judge_model": judge_model,
                "context_kaynagi": "",
                **{key: None for key in SCORE_KEYS},
                "reasoning": f"[ATLANDI] run_tests hatası: {answer[:150]}",
            }
            write_results(output_csv, [results_by_id[r["id"]] for r in rows
                                       if r["id"] in results_by_id])
            print("  → [ATLANDI] run_tests hatası, judge'a gönderilmedi")
            continue

        # Ground truth'tan referans cevap
        reference_answer = resolve_reference(row, gt)
        if not reference_answer:
            missing_references.append(soru_id)

        # Context: önce run_tests.py'nin kaydettiği, cevabın gerçekten üretildiği
        # context. Yalnızca o sütun olmayan eski CSV'lerde yeniden oluşturulur.
        if has_saved_context:
            context = row.get("context") or "(Context yok)"
            context_kaynagi = "kayitli"
        elif REBUILD_CONTEXT and question:
            context_kaynagi = "yeniden_olusturuldu"
            try:
                context = build_context_for_question(question, local_llm)
                if not context.strip():
                    raise RuntimeError("Retrieval boş döndü")
            except Exception as e:
                # Context yoksa judge anlamsız skor üretir (Ollama kapalıyken 30
                # soru "(Context oluşturulamadı)" bağlamıyla puanlanmıştı). Satır
                # skorsuz yazılır; skor boş olduğu için resume'da yeniden denenir.
                skipped_context.append(soru_id)
                results_by_id[soru_id] = {
                    "id": soru_id,
                    "soru": question,
                    "cevap": answer,
                    "judge_model": judge_model,
                    "context_kaynagi": context_kaynagi,
                    **{key: None for key in SCORE_KEYS},
                    "reasoning": f"[ATLANDI] context oluşturulamadı: {str(e)[:150]}",
                }
                write_results(output_csv, [results_by_id[r["id"]] for r in rows
                                           if r["id"] in results_by_id])
                print(f"  → [ATLANDI] context oluşturulamadı ({e}), judge'a gönderilmedi")
                continue
        else:
            context = row.get("bulunan_kaynaklar", "(Context bilgisi yok)")
            context_kaynagi = "sadece_kaynak_adlari"

        # Judge'a gönder
        try:
            scores = judge_single(judge_llm, question, answer, context, reference_answer)
        except DailyLimitError as e:
            # Önceki satırlar zaten yazıldı; aynı komut tekrar çalıştırılınca
            # kalan satırlar (resume) tamamlanır.
            wait = (f"{e.wait_seconds / 60:.1f} dk sonra" if e.wait_seconds is not None
                    else "kota sıfırlanınca")
            print(f"\n[DURDU] Groq günlük limiti doldu — {wait} tekrar deneyin.\n"
                  f"        {sira - 1}/{toplam} soru değerlendirildi; aynı komut kalanları tamamlar.\n"
                  f"        Mesaj: {e}")
            break

        result_row = {
            "id": soru_id,
            "soru": question,
            "cevap": answer,
            "judge_model": judge_model,
            "context_kaynagi": context_kaynagi,
            **{key: scores.get(key) for key in SCORE_KEYS},
            "reasoning": scores.get("reasoning", ""),
        }
        results_by_id[soru_id] = result_row
        write_results(output_csv, [results_by_id[r["id"]] for r in rows
                                   if r["id"] in results_by_id])

        # İlerleme bilgisi
        if any(scores.get(key) is not None for key in SCORE_KEYS):
            print(f"  → F: {scores.get('faithfulness_score')} | "
                  f"AR: {scores.get('answer_relevance_score')} | "
                  f"TP: {scores.get('task_performance_score')} | "
                  f"AL: {scores.get('alignment_score')}")
        else:
            print(f"  → [SKOR ALINAMADI] {scores.get('reasoning', '')[:80]}")

        # Sorular arası bekleme (model nefes alsın)
        time.sleep(1)

    results = [results_by_id[r["id"]] for r in rows if r["id"] in results_by_id]

    print(f"\n{'='*60}")
    print(f"Judge değerlendirmesi tamamlandı: {toplam} soru değerlendirildi, "
          f"çıktıda {len(results)} soru")
    print(f"Sonuçlar: {output_csv}")
    if skipped_errors:
        print(f"[UYARI] run_tests HATA'sı olan {len(skipped_errors)} soru judge'a gönderilmedi "
              f"(skorsuz): {', '.join(skipped_errors)}. Bu soruları run_tests ile yeniden çalıştırın.")
    if skipped_context:
        print(f"[UYARI] Context oluşturulamayan {len(skipped_context)} soru judge'a gönderilmedi "
              f"(skorsuz): {', '.join(skipped_context)}. Ollama/Foundry çalışırken aynı komut "
              f"bunları tamamlar.")
    if missing_references:
        print(f"[UYARI] Referans yok ({len(missing_references)} soru — ne ground truth "
              f"dosyalarında ne CSV'nin referans_cevap sütununda): "
              f"{', '.join(missing_references)}")

    # ─── Özet istatistikler ───────────────────────────────────────────────
    print_summary(results)

    return results


def print_summary(results):
    """Judge sonuçlarının özet istatistiklerini yazdırır."""
    metrics = SCORE_KEYS
    print(f"\n{'─'*60}")
    print("LLM-as-a-Judge Özet Rapor")
    print(f"{'─'*60}")
    print(f"{'Metrik':<24} {'Ort':>6} {'Min':>6} {'Max':>6} {'Geçerli':>8}")
    print(f"{'─'*60}")

    for metric in metrics:
        values = [r[metric] for r in results if r[metric] is not None]
        if values:
            avg = sum(values) / len(values)
            print(f"{metric:<24} {avg:>6.2f} {min(values):>6} {max(values):>6} {len(values):>5}/{len(results)}")
        else:
            print(f"{metric:<24} {'N/A':>6} {'N/A':>6} {'N/A':>6} {'0':>5}/{len(results)}")

    print(f"{'─'*60}")

    # Puan dağılımı (her metrik için 1..5 kaç kez verildi)
    scale = range(SCORE_MIN, SCORE_MAX + 1)
    print("\nPuan Dağılımı:")
    print(f"{'Metrik':<24} " + " ".join(f"{s:>4}" for s in scale))
    for metric in metrics:
        values = [r[metric] for r in results if r[metric] is not None]
        print(f"{metric:<24} " + " ".join(f"{values.count(s):>4}" for s in scale))
    print()


# ─── CLI ──────────────────────────────────────────────────────────────────────

def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="LLM-as-a-Judge ile RAG cevap kalitesi değerlendirmesi"
    )
    parser.add_argument(
        "sonuclar",
        nargs="?",
        default="datasets/test_1_sonuclari.csv",
        help="Değerlendirilecek sonuç CSV dosyası (varsayılan: datasets/test_1_sonuclari.csv)",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Çıktı CSV dosyası (varsayılan: <girdi>_judge.csv)",
    )
    parser.add_argument(
        "--ground-truth", "-gt",
        default=None,
        help="Yalnızca bu ground truth JSON dosyasını kullan (varsayılan: "
             "evaluation/ground_truth/*.json birleştirilir, id ile eşleşir)",
    )
    parser.add_argument(
        "--judge-model",
        default=JUDGE_MODEL,
        help=f"Groq'taki judge model adı (varsayılan: {JUDGE_MODEL})",
    )
    parser.add_argument(
        "--only-ids",
        default=None,
        help="Yalnızca bu soru id'lerini (yeniden) değerlendir, virgülle ayrılmış "
             "(örn: 25,26,29). Verilmezse çıktı CSV'sinde skoru boş/hatalı olanlar "
             "tamamlanır; çıktı yoksa tüm sorular değerlendirilir.",
    )
    parser.add_argument(
        "--no-rebuild-context",
        action="store_true",
        help="Context'i yeniden oluşturma, CSV'deki mevcut kaynak bilgisini kullan",
    )
    return parser.parse_args(argv)


def main(argv=None):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

    args = parse_args(argv)

    if args.no_rebuild_context:
        global REBUILD_CONTEXT
        REBUILD_CONTEXT = False

    run_judge_evaluation(
        sonuc_csv=args.sonuclar,
        output_csv=args.output,
        ground_truth_path=args.ground_truth,
        judge_model=args.judge_model,
        only_ids=[i.strip() for i in args.only_ids.split(",") if i.strip()]
                 if args.only_ids else None,
    )


if __name__ == "__main__":
    main()
