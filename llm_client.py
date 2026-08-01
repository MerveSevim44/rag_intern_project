from foundry_local_sdk import Configuration, FoundryLocalManager
from foundry_local_sdk.exception import FoundryLocalException
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

APP_NAME = "microsoft_internship_project"

# En son belleğe yüklenen model (IModel). Model değiştirilirken eskisini
# bellekten indirmek için tutuluyor; SDK'nın "yüklü modelleri listele" API'si
# public değil (manager._model_load_manager.list_loaded), o yüzden kendimiz izliyoruz.
_loaded_model = None


def get_manager():
    """
    Foundry Local singleton manager'ını döndürür; yoksa bir kez initialize eder.

    FoundryLocalManager.instance bir SINIF NİTELİĞİ ve başlangıç değeri None
    (bkz. foundry_local_manager.py). Yani manager hazır değilken AttributeError
    değil, doğrudan None gelir — doğru kontrol `is None`.

    initialize() ikinci kez çağrılırsa FoundryLocalException fırlatır
    ("... is a singleton and has already been initialized"). Arayüzden ikinci
    kez "Modeli Yükle" denince yaşanan hata buydu.
    """
    manager = FoundryLocalManager.instance
    if manager is not None:
        return manager

    config = Configuration(app_name=APP_NAME)
    try:
        FoundryLocalManager.initialize(config)
    except FoundryLocalException:
        # Aramızda başka bir yol (ör. başka bir thread) initialize etmiş olabilir;
        # singleton zaten kurulduysa bu hata zararsız, instance'ı kullanmaya devam et.
        if FoundryLocalManager.instance is None:
            raise

    manager = FoundryLocalManager.instance
    if manager is None:
        raise RuntimeError(
            "Foundry Local manager başlatılamadı. Foundry Local kurulu ve çalışır durumda mı?"
        )
    return manager


def load_model(alias="qwen2.5-7b", unload_previous=True):
    """
    Modeli başlatır ve LangChain ChatOpenAI nesnesini (llm) döndürür.

    Birden fazla kez çağrılabilir: manager singleton'ı yeniden initialize
    edilmez, web servisi zaten çalışıyorsa tekrar başlatılmaz. Yeni bir modele
    geçilirken önceki model bellekten indirilir (unload_previous=False ile
    kapatılabilir; iki modeli aynı anda bellekte tutmak isterseniz).
    """
    global _loaded_model

    # 1. Manager'ı al (ilk çağrıda initialize eder, sonrakilerde mevcut singleton)
    manager = get_manager()

    # 2. Modeli al — bilinmeyen alias'ta catalog None döner
    model = manager.catalog.get_model(alias)
    if model is None:
        raise ValueError(
            f"'{alias}' Foundry Local katalogunda bulunamadı. "
            "Alias'ı kontrol edin veya 'foundry model list' ile mevcut modellere bakın."
        )

    # 3. İndirilmemişse indir
    if not model.is_cached:
        print(f"Model ({alias}) indiriliyor...")
        model.download(lambda p: print(f"\rİndiriliyor: {p:.2f}%", end="", flush=True))
        print()

    # 4. Model değişiyorsa öncekini bellekten indir.
    #    Başarısız olursa yeni modeli yüklemeyi engellemesin — sadece uyar.
    if unload_previous and _loaded_model is not None and _loaded_model.id != model.id:
        try:
            _loaded_model.unload()
            print(f"Önceki model ({_loaded_model.id}) bellekten indirildi.")
        except FoundryLocalException as e:
            print(f"Uyarı: önceki model bellekten indirilemedi: {e}")

    # 5. Yükle (hata olursa program dursun)
    model.load()
    _loaded_model = model
    print(f"Model ({alias}) yüklendi.")

    # 6. Web servisini başlat — aynı manager üzerinde zaten çalışıyorsa tekrar
    #    başlatma; urls None değilse servis ayakta demektir.
    if not manager.urls:
        manager.start_web_service()
        print(f"Servis adresi: {manager.urls}")
    else:
        print(f"Servis zaten çalışıyor: {manager.urls}")

    # 7. base_url'i belirle
    base_url = manager.urls[0]
    if not base_url.endswith("/v1"):
        base_url = base_url + "/v1"
    print(f"base_url: {base_url}")

    # 8. LangChain LLM oluştur
    llm = ChatOpenAI(
        model=model.id,
        base_url=base_url,
        api_key="not-needed",
        temperature=0,
        streaming=False,
        extra_body={"enable_thinking": False}
    )
    return llm

def ask(llm, context, question):
    """
    Belirli bir bağlam (context) ve soru (question) ile LLM'e soru sorar.
    Sadece verilen bağlama dayanarak yanıt üretir.
    """
    prompt = ChatPromptTemplate.from_messages([
        ("system",
        "Aşağıdaki bağlamı kullanarak soruyu cevapla. "
        "Bağlamda soruyla ilgili bilgi varsa (kısmen ilgili olsa bile) bu bilgiyi "
        "kullanarak cevap ver. Bağlamda soruyla hiçbir ilgili bilgi yoksa "
        "sadece 'Bu bilgi dokümanlarda bulunamadı.' yaz. "
        "Cevabın sonunda kullandığın kaynağı belirt."),
        ("user", "Bağlam:\n{context}\n\nSoru: {question}\n\nCevap:")
        ])
    
    if not question or not question.strip():
        raise ValueError("Soru boş olamaz.")

    chain = prompt | llm
    try:
        response = chain.invoke({"context": context, "question": question})
    except Exception as e:
        raise RuntimeError(
            "Model yanıt veremedi. Foundry Local servisi hâlâ çalışıyor mu ve "
            f"model yüklü mü kontrol edin. Ayrıntı: {e}"
        ) from e
    return response.content

