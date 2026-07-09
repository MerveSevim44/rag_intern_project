from foundry_local_sdk import Configuration, FoundryLocalManager
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

def load_model(alias="qwen2.5-7b"):
    """
    Modeli başlatır ve LangChain ChatOpenAI nesnesini (llm) döndürür.
    """
    # 1. Yapılandır ve başlat
    config = Configuration(app_name="microsoft_internship_project")
    FoundryLocalManager.initialize(config)
    manager = FoundryLocalManager.instance

    # 2. Modeli al
    model = manager.catalog.get_model(alias)

    # 3. İndirilmemişse indir
    if not model.is_cached:
        print(f"Model ({alias}) indiriliyor...")
        model.download(lambda p: print(f"\rİndiriliyor: {p:.2f}%", end="", flush=True))
        print()

    # 4. Yükle (hata olursa program dursun)
    model.load()
    print(f"Model ({alias}) yüklendi.")

    # 5. Web servisini başlat
    manager.start_web_service()
    print(f"Servis adresi: {manager.urls}")

    # 6. base_url'i belirle
    base_url = manager.urls[0]
    if not base_url.endswith("/v1"):
        base_url = base_url + "/v1"
    print(f"base_url: {base_url}")

    # 7. LangChain LLM oluştur
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
        ("system", "Sadece aşağıdaki bağlamı kullan. Bağlamda yoksa 'bilmiyorum' de."),
        ("user", "Bağlam:\n{context}\n\nSoru: {question}")
    ])
    
    chain = prompt | llm
    response = chain.invoke({"context": context, "question": question})
    return response.content