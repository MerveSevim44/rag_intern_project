# öğrendiklerim ve tecrübe ettiklerim 
- "manager = FoundryLocalManager(alias)"  bunu koda yazdığımda "config.validate()
    ^^^^^^^^^^^^^^^
AttributeError: 'str' object has no attribute 'validate' bu şekilde bir hata aldım hatanın nedeni :

model sürümünde API nin değişmiş 
olması yüklü sürümüm artık bir "Configuration" nesnesi bekliyor. Microsoft'un güncel dokümantasyonundaki örnek şu şekilde: Foundry Local SDK'yı başlatmak için Configuration(app_name="foundry_local_samples") oluşturulur, ardından FoundryLocalManager.initialize(config) çağrılır ve manager = "FoundryLocalManager.instance" ile erişilir

FoundryLocalManager("qwen3-0.6b") gibi alias'ı doğrudan constructor'a vermek artık desteklenmiyor

config = Configuration(app_name="microsoft_internship_project")   # 1) Config nesnesi oluştur
FoundryLocalManager.initialize(config)                             # 2) Singleton'ı başlat
manager = FoundryLocalManager.instance 

: önce Configuration → initialize → catalog'dan modeli çek → indir → yükle → chat client al.

embedder.py     → Araç kutusu (kimseyi çağırmaz, herkes onu çağırır)
llm_client.py   → Araç kutusu (kimseyi çağırmaz, herkes onu çağırır)

ingest.py       → embedder.py'yi çağırır (embed etmek için)
                  SQLite'a yazar
                  SADECE BİR KEZ çalışır

retrieval.py    → embedder.py'yi çağırır (soruyu embed etmek için)
                  SQLite'tan okur
                  Her soru geldiğinde çalışır

app.py          → HEPSİNİ birleştirir
                  retrieval.py'yi çağırır (chunk bul)
                  llm_client.py'yi çağırır (cevap üret)
                  Kullanıcıyla konuşur