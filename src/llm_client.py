import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

import psutil
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate



# Kullanılacak varsayılan model: qwen2.5-7b'nin CUDA (GPU) varyantı.
# Türkçe kalitesi phi-4-mini'den belirgin daha iyi ve GPU'da çalışıyor.
#
# Kısa alias KULLANILMAZ — katalog kısa alias'ı yanlış varyanta (CPU/NPU)
# çözebiliyor ve GPU hiç devreye girmiyor. Bu yüzden tam model ID'si kullanılır.
DEFAULT_MODEL_ID = "qwen2.5-7b-instruct-cuda-gpu:4"

# Alternatif (indirilmiş ve çalıştığı doğrulanmış) model.
PHI4_MINI_MODEL_ID = "Phi-4-mini-instruct-cuda-gpu:5"

# Cevap uzunluğu üst sınırı. Detaylı cevapların tamamlanmasına yetecek kadar
# yüksek, tekrar döngüsünü sınırlayacak kadar düşük.
MAX_ANSWER_TOKENS = 600

# ─── Bağlam (context) uzunluk sınırları ───────────────────────────────
# Neden: uzun bağlamlarda ONNX Runtime KV-cache için tek parça büyük bir
# tampon ayırmaya çalışıyor ve 8GB VRAM'de patlıyor:
#   "BFCArena::AllocateRawInternal Failed to allocate memory for requested
#    buffer of size ..." (HTTP 500)
# Bellek ihtiyacı prompt uzunluğuyla birlikte büyüdüğü için bağlamı
# kaynağında kırpıyoruz.
#
# Tek bir chunk'ın bağlama girebilecek en fazla karakter sayısı.
MAX_CHUNK_CHARS = 1500

# Tüm chunk'lar birleştirildikten sonraki toplam üst sınır. Chunk sayısı
# artarsa (top_k büyütülürse) tek başına chunk sınırı yetmez; bu ikinci
# sınır prompt'un toplam boyutunu garanti altına alır.
MAX_CONTEXT_CHARS = 6000

# Kırpma yapıldığında metnin sonuna eklenen işaret.
_TRUNCATION_MARKER = " […kısaltıldı]"


def truncate_chunk_text(text, max_chars=MAX_CHUNK_CHARS):
    """
    Tek bir chunk metnini `max_chars` karaktere kırpar.

    Kelime ortasında kesmemek için son boşluktan böler (boşluk yoksa sert
    keser). Kırpıldığı, sona eklenen işaretle belli olur — böylece modelin
    yarım kalmış bir cümleyi tam sanması engellenir.
    """
    if not text or len(text) <= max_chars:
        return text

    cut = text[:max_chars]
    last_space = cut.rfind(" ")
    # Boşluk metnin çok başındaysa kırpmak yerine sert kes.
    if last_space > max_chars * 0.6:
        cut = cut[:last_space]
    return cut.rstrip() + _TRUNCATION_MARKER


def truncate_context(context, max_chars=MAX_CONTEXT_CHARS):
    """Birleştirilmiş bağlam için son güvenlik sınırı (bkz. MAX_CONTEXT_CHARS)."""
    if not context or len(context) <= max_chars:
        return context
    return context[:max_chars].rstrip() + _TRUNCATION_MARKER

# Foundry Local servisinin dinlediği adres. Port her açılışta değişebildiği
# için normalde otomatik bulunur; gerekirse bu ortam değişkeniyle sabitlenir.
ENDPOINT_ENV_VAR = "FOUNDRY_LOCAL_ENDPOINT"

# ─── Foundry Local Model TTL (Idle Timeout) ──────────────────────────────────
# Model yüklendikten sonra bu süre (saniye) boyunca kullanılmazsa otomatik
# olarak bellekten/VRAM'den kaldırılır. 16GB RAM ortamında LLM'in boşta
# VRAM işgal etmesini önler.
# 0 = otomatik unload kapalı (varsayılan Foundry davranışı).
FOUNDRY_MODEL_TTL = 120  # 2 dakika idle timeout

# Servisi barındıran süreçlerin adları (psutil ile port taraması için).
_SERVICE_PROCESS_HINTS = ("inference.service.agent", "foundry")

# Bulunan endpoint süreç ömrü boyunca tekrar taranmasın diye saklanır.
_endpoint_cache = None


def _http_get(url, timeout=15):
    """Foundry servisine GET atar; JSON ise parse eder, değilse düz metin döner."""
    with urllib.request.urlopen(url, timeout=timeout) as response:
        body = response.read().decode("utf-8", errors="replace")
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return body


def _is_foundry_endpoint(base_url):
    """Verilen adres gerçekten bir Foundry Local servisi mi?"""
    try:
        status = _http_get(f"{base_url}/openai/status", timeout=5)
    except (urllib.error.URLError, OSError, TimeoutError):
        return False
    return isinstance(status, dict) and "endpoints" in status


def _discover_endpoint():
    """
    Zaten ÇALIŞAN Foundry Local servisinin adresini bulur.

    Neden SDK kullanılmıyor: FoundryLocalManager.start_web_service() bu makinede
    modelleri göremeyen AYRI ve BOŞ bir servis örneği açıyor (/v1/models -> []),
    çünkü SDK yerel cache'e named pipe üzerinden erişemiyor (UnauthorizedAccess).
    Asıl servis (Inference.Service.Agent) ayrı bir portta çalışıyor ve CUDA
    varyantını o servis barındırıyor. Bu yüzden çalışan servisi kendimiz buluruz.
    """

    #eğer daha önce endpoint bulunduysa onu kullan (cache)
    global _endpoint_cache
    if _endpoint_cache is not None:
        return _endpoint_cache

    # 1. Ortam değişkeni her şeyi ezer.
    override = os.environ.get(ENDPOINT_ENV_VAR)
    if override:
        base = override.rstrip("/")
        if not _is_foundry_endpoint(base):
            raise RuntimeError(
                f"{ENDPOINT_ENV_VAR}={override} adresinde Foundry Local servisi yanıt vermiyor."
            )
        _endpoint_cache = base
        return base

    # 2. Foundry süreçlerinin dinlediği portları tara.
    candidate_ports = set()
    for proc in psutil.process_iter(["name"]):
        name = (proc.info.get("name") or "").lower()
        if not any(hint in name for hint in _SERVICE_PROCESS_HINTS):
            continue
        try:
            connections = proc.net_connections(kind="tcp")
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            continue
        for conn in connections:
            if conn.status == psutil.CONN_LISTEN and conn.laddr:
                candidate_ports.add(conn.laddr.port)

    for port in sorted(candidate_ports):
        base = f"http://127.0.0.1:{port}"
        if _is_foundry_endpoint(base):
            # Servisin kendi bildirdiği adresi tercih et (varsa).
            status = _http_get(f"{base}/openai/status", timeout=5)
            endpoints = status.get("endpoints") or []
            _endpoint_cache = (endpoints[0].rstrip("/") if endpoints else base)
            return _endpoint_cache

    raise RuntimeError(
        "Çalışan bir Foundry Local servisi bulunamadı. Bir terminalde "
        "'foundry service start' ile servisi başlatın, ardından tekrar deneyin. "
        f"Adresi biliyorsanız {ENDPOINT_ENV_VAR} ortam değişkeniyle verebilirsiniz."
    )


def _resolve_model_id(base_url, requested):
    """
    İstenen model adını servisin tanıdığı TAM model ID'sine çevirir.

    - Tam ID verilmişse (ör. "Phi-4-mini-instruct-cuda-gpu:5") doğrudan kullanılır.
    - Kısa alias verilmişse (ör. "phi-4-mini") o alias'ın varyantları arasından
      CUDA/GPU olanı SEÇİLİR; yoksa ilk varyant kullanılır. Kısa alias'ın CPU
      varyantına düşme sorunu böyle engellenir.

    Returns:
        (model_id, runtime_dict) — runtime: {"deviceType", "executionProvider"}
    """
    try:
        catalog = _http_get(f"{base_url}/foundry/list", timeout=30)
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        if ":" in requested or "gpu" in requested.lower():
            return requested, {"deviceType": "GPU", "executionProvider": "CUDAExecutionProvider"}
        raise RuntimeError(f"Foundry model listesi alınamadı: {e}") from e

    if not isinstance(catalog, list):
        if ":" in requested or "gpu" in requested.lower():
            return requested, {"deviceType": "GPU", "executionProvider": "CUDAExecutionProvider"}
        raise RuntimeError("Foundry model listesi beklenmedik biçimde döndü.")

    by_id = {entry.get("name"): entry for entry in catalog}

    # Tam ID eşleşmesi
    if requested in by_id:
        return requested, by_id[requested].get("runtime") or {}

    # Alias eşleşmesi — GPU varyantını tercih et
    variants = [e for e in catalog if e.get("alias") == requested]
    if variants:
        def prefers_gpu(entry):
            runtime = entry.get("runtime") or {}
            device = (runtime.get("deviceType") or "").upper()
            provider = (runtime.get("executionProvider") or "").lower()
            # CUDA en yüksek öncelik, sonra diğer GPU'lar, en son CPU/NPU
            if "cuda" in provider:
                return 0
            if device == "GPU":
                return 1
            return 2

        best = sorted(variants, key=prefers_gpu)[0]
        return best.get("name"), best.get("runtime") or {}

    raise ValueError(
        f"'{requested}' Foundry Local'de bulunamadı. "
        "'foundry cache list' ile indirilmiş modellere bakabilirsiniz."
    )


def load_model(alias=DEFAULT_MODEL_ID, unload_previous=True):
    """
    Modeli çalışan Foundry Local servisinde yükler ve LangChain ChatOpenAI
    nesnesini (llm) döndürür.

    Birden fazla kez çağrılabilir; model zaten yüklüyse servis onu yeniden
    yüklemez. `unload_previous` artık kullanılmıyor (servis bellek yönetimini
    kendisi yapıyor), imza uyumluluğu için korunuyor.
    """
    base_url = _discover_endpoint()

    model_id, runtime = _resolve_model_id(base_url, alias)

    # Modeli belleğe yükle. Zaten yüklüyse bu çağrı hızlıca döner.
    # TTL parametresi ile model belirli bir süre kullanılmazsa otomatik unload olur.
    ttl_param = f"&ttl={FOUNDRY_MODEL_TTL}" if FOUNDRY_MODEL_TTL > 0 else ""
    try:
        _http_get(
            f"{base_url}/openai/load/{urllib.parse.quote(model_id)}?unload=true{ttl_param}",
            timeout=600,
        )
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        raise RuntimeError(f"Model ({model_id}) yüklenemedi: {e}") from e

    # Gerçekten yüklenen modeli servise sor — beklenenden farklıysa görelim.
    try:
        loaded = _http_get(f"{base_url}/openai/loadedmodels", timeout=15)
    except (urllib.error.URLError, OSError, TimeoutError):
        loaded = None

    provider = runtime.get("executionProvider") or "bilinmiyor"
    device = runtime.get("deviceType") or "bilinmiyor"

    # GPU varyantının gerçekten yüklendiğini terminalden doğrulayabilmek için log.
    print(
        f"[Foundry] Model yüklendi: {model_id} | "
        f"execution provider: {provider} | cihaz: {device}"
    )
    print(f"[Foundry] Servis adresi: {base_url}")
    print(f"[Foundry] Serviste yüklü modeller: {loaded}")
    if "cuda" not in provider.lower():
        print(
            "[Foundry] UYARI: CUDA dışı bir varyant yüklendi — GPU kullanılmıyor olabilir."
        )

    llm = ChatOpenAI(
        model=model_id,
        base_url=f"{base_url}/v1",
        api_key="not-needed",
        temperature=0,
        streaming=False,
        # qwen2.5-7b phi-4-mini'den daha uzun/detaylı cevap veriyor; önceki
        # sınırla cevaplar cümle ortasında kesiliyordu. Yine de sınırsız değil:
        # tekrar döngüsüne (repetition loop) girerse üretim burada durur.
        max_tokens=MAX_ANSWER_TOKENS,
        extra_body={"enable_thinking": False}
    )
    return llm


def unload_model(model_id=None, alias=DEFAULT_MODEL_ID):
    """
    Foundry Local'dan modeli bellekten/VRAM'den kaldırır.

    16GB RAM ortamında pipeline'ın belirli aşamalarında (ör. ingest sırasında)
    LLM'e ihtiyaç yoksa bu fonksiyonla VRAM serbest bırakılabilir.

    Args:
        model_id: Tam model ID'si. None ise alias'tan çözülür.
        alias: model_id verilmezse kullanılacak kısa ad.
    """
    try:
        base_url = _discover_endpoint()
    except RuntimeError:
        print("[Foundry] Servis bulunamadı — unload atlanıyor.")
        return

    if model_id is None:
        model_id, _ = _resolve_model_id(base_url, alias)

    try:
        # TTL=1 ile modeli hemen unload etmeye zorla
        _http_get(
            f"{base_url}/openai/load/{urllib.parse.quote(model_id)}?unload=true&ttl=1",
            timeout=30,
        )
        print(f"[Foundry] Model unload istendi: {model_id}")
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        print(f"[Foundry] Unload başarısız: {e}")


# Bağlamda cevap yoksa modelin vermesi gereken TEK cümle.
NOT_FOUND_ANSWER = "Bu bilgi dokümanlarda bulunamadı."

# "Bulunamadı" cevabını tanıyan kalıp: İLK cümlede hem "bulunamadı" hem de
# neyin bulunamadığını söyleyen bir bağlam sözcüğü geçmeli.
_NOT_FOUND_RE = re.compile(r"bulunamad[ıi]", re.IGNORECASE)
_NOT_FOUND_CONTEXT_RE = re.compile(r"doküman|dokuman|belge|bağlam|baglam|metin", re.IGNORECASE)


def _is_not_found_sentence(sentence):
    """Bir cümle 'bağlamda bilgi yok' beyanı mı?"""
    return bool(
        _NOT_FOUND_RE.search(sentence) and _NOT_FOUND_CONTEXT_RE.search(sentence)
    )


def _split_sentences(text):
    """Metni cümle sonu noktalamasını koruyarak cümlelere böler."""
    return [s for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]


def _trim_after_not_found(answer):
    """
    "Bulunamadı" beyanının yol açtığı iki bozulmayı düzeltir:

    1. Cevap "bulunamadı" ile BAŞLIYORSA → gerçekten bilgi yok demektir;
       arkasına eklenmiş her şey (modelin kendi genel bilgisi) atılır ve
       geriye tek cümle kalır.
    2. Normal bir cevabın SONUNA "bulunamadı" iliştirilmişse → model yanlışlıkla
       eklemiştir; sadece o son cümle(ler) silinir, asıl cevap KORUNUR.
    3. Cevap tamamen normalse → dokunulmaz.
    """
    if not isinstance(answer, str):
        return answer

    sentences = _split_sentences(answer.strip())
    if not sentences:
        return answer

    # 1. Baştaki "bulunamadı" → sadece o cümle kalır.
    if _is_not_found_sentence(sentences[0]):
        return NOT_FOUND_ANSWER

    # 2. Sondaki gereksiz "bulunamadı" cümleleri atılır.
    kept = list(sentences)
    while kept and _is_not_found_sentence(kept[-1]):
        kept.pop()

    if not kept:
        return NOT_FOUND_ANSWER
    if len(kept) == len(sentences):
        return answer  # 3. Dokunma — orijinal biçimlendirme korunur.
    return " ".join(kept).strip()


# Modelin uydurmaya en yatkın olduğu para birimi ifadeleri.
_CURRENCY_HALLUCINATIONS = [
    (r"(?<!\w)[Tt][Ll](?=$|[^\wçğıöşü])", "TL"),
    (r"(?<!\w)₺", "₺"),
    (r"(?<!\w)(?:Türk\s+)?[Ll]iras[ıi](?!\w)", "lira"),
    (r"(?<!\w)[Ll]ira(?!\w)", "lira"),
    (r"(?<!\w)[Dd]olar(?!\w)", "dolar"),
    (r"(?<!\d)\s?\$(?!\w)", "$"),
]

# Bağlamda geçebilecek gerçek para birimi kodları
_CURRENCY_CODES = ["USD", "EUR", "GBP", "TRY", "JPY", "CHF", "CAD", "AUD"]


def _fix_currency_hallucination(answer, context):
    """
    Cevapta veri setinde BULUNMAYAN bir para birimi geçiyorsa, bağlamda fiilen
    geçen birim koduyla değiştirir; bağlamda hiç birim yoksa uydurulan birimi siler.

    Prompt kuralı tek başına yetmiyordu: küçük model 'currency': 'USD' sonucunu
    görmesine rağmen cevabı "1 TL" diye yazabiliyor. Bu yüzden deterministik
    bir son kontrol katmanı gerekiyor.
    """
    if not answer:
        return answer

    present = [code for code in _CURRENCY_CODES
               if re.search(rf"(?<!\w){code}(?!\w)", context or "", re.IGNORECASE)]
    # Bağlamda birden fazla birim varsa hangisinin doğru olduğuna karar veremeyiz — dokunma.
    if len(present) > 1:
        return answer
    replacement = present[0] if present else ""

    for pattern, literal in _CURRENCY_HALLUCINATIONS:
        # Bağlamda gerçekten geçen bir ifadeyse hallüsinasyon değildir.
        if re.search(pattern, context or ""):
            continue
        if re.search(pattern, answer):
            answer = re.sub(pattern, (f" {replacement}" if replacement else ""), answer)
            print(f"[llm_client] Para birimi duzeltildi: '{literal}' -> "
                  f"'{replacement or '(kaldirildi)'}'")

    # Birim silindiginde geride kalan artiklari topla: " 'dir." -> "dir.",
    # noktalama oncesi bosluk, cift bosluk.
    answer = re.sub(r"\s+(?='(?:dir|dır|dur|dür|tir|tır|tur|tür)\b)", "", answer)
    answer = re.sub(r"\s+([.,;:!?])", r"\1", answer)
    return re.sub(r"\s{2,}", " ", answer).strip()


def ask(llm, context, question, extra_instruction=None, debug=False):
    """
    Belirli bir bağlam (context) ve soru (question) ile LLM'e soru sorar.
    Sadece verilen bağlama dayanarak yanıt üretir.

    "Sadece sorguda belirtilen dokümana ait bilgiyi kullan.
    Farklı kaynaklardaki bilgileri birbirine karıştırma veya harmanlama."

    Args:
        extra_instruction: Rota-özel ek sistem talimatı. META_QUERY rotasında
            router.META_QUERY_INSTRUCTION buraya geçirilir; base prompt'un
            "bilgi yoksa tek cümle söyle ve sus" kuralının ARDINDAN eklenir ve
            o kuralı bu rota için gevşetir (çıkarım yapılabilir, ama etiketlenir).
        debug: True ise synthesizer'a giden nihai prompt stdout'a basılır.
    """
    base_instruction = (
        "Aşağıdaki bağlamı kullanarak soruyu cevapla. "
        "Kullanıcı hangi dilde sorarsa sorsun, cevabını HER ZAMAN TÜRKÇE ver; "
        "bağlam başka bir dilde olsa bile cevabın Türkçe olmalı. "
        "Bağlamda soruyla ilgili bilgi varsa (kısmen ilgili olsa bile) bu bilgiyi "
        "kullanarak cevap ver ve kaynağını belirt. "
    )

    if extra_instruction:
        # META_QUERY gibi çıkarım rotaları: sert "bilgi yoksa sus" kuralı buraya
        # KONULMAZ. Aksi hâlde model, bağlamda doğrudan cevap bulamadığı için
        # soruyu hiç değerlendirmeden NOT_FOUND_ANSWER'a düşer — oysa bu rotada
        # istenen şey tam olarak "doğrudan yazmıyor, ama şu çıkarım yapılabilir".
        system_parts = [
            base_instruction,
            "\n\n--- BU SORUYA ÖZEL TALİMAT (genel kurallardan ÖNCELİKLİDİR) ---\n",
            # Süslü parantezler ChatPromptTemplate tarafından değişken sanılmasın
            extra_instruction.strip().replace("{", "{{").replace("}", "}}"),
            "\n\nBu soruyu MUTLAKA cevapla; 'bulunamadı' deyip geçme.",
        ]
    else:
        system_parts = [
            base_instruction,
            "Bağlamda soruyla İLGİLİ HİÇBİR bilgi yoksa, cevabın TAMAMI tek bir "
            f"cümleden ibaret olmalı: '{NOT_FOUND_ANSWER}' "
            "Bu cümleyi yazdıktan sonra ÜRETİMİ BİTİR. Tek kelime bile ekleme: "
            "açıklama yapma, konuyu tanıtma, genel/ansiklopedik bilgi verme, "
            "kendi bilginle tamamlama yapma, öneride bulunma, soruyu yorumlama. "
            "Konuyu biliyor olsan bile anlatma — bağlamda yoksa susmalısın. "
            f"O durumda vereceğin çıktı harfi harfine şudur: {NOT_FOUND_ANSWER}",
        ]

    if not question or not question.strip():
        raise ValueError("Soru boş olamaz.")

    # Çağıran taraf kırpmayı atlamış olabilir; burası son savunma hattı.
    context = truncate_context(context)

    system_text = "".join(system_parts)
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_text),
        ("user", "Bağlam:\n{context}\n\nSoru: {question}\n\nCevap:")
    ])

    if debug:
        rendered = prompt.format(context=context, question=question)
        print("=" * 78)
        print("[llm_client] SYNTHESIZER'A GİDEN NİHAİ PROMPT")
        print("=" * 78)
        print(rendered)
        print("=" * 78)

    chain = prompt | llm
    try:
        response = chain.invoke({"context": context, "question": question})
    except Exception as e:
        raise RuntimeError(
            "Model yanıt veremedi. Foundry Local servisi hâlâ çalışıyor mu ve "
            f"model yüklü mü kontrol edin. Ayrıntı: {e}"
        ) from e

    # Model prompt'a tam uymayıp "bulunamadı" dedikten sonra devam ederse
    # o kuyruğu burada keseriz.
    # Çıkarım rotalarında (META_QUERY) cevap bilinçli olarak "doğrudan belirtilmemiştir"
    # gibi ifadeler içerir; NOT_FOUND kırpması bu cevabı ortasından kesebilir.
    if extra_instruction:
        return _fix_currency_hallucination(response.content.strip(), context)
    return _fix_currency_hallucination(_trim_after_not_found(response.content), context)

