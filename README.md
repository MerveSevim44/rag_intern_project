# 🧠 Local RAG AI Assistant with Microsoft Foundry Local

Bu proje, **Microsoft Foundry Local** SDK'sını ve yerel yapay zeka modellerini kullanarak, tamamen çevrimdışı (internet bağlantısı gerektirmeyen) çalışan bir **RAG (Retrieval-Augmented Generation / Arama Destekli Üretim)** soru-cevap uygulamasıdır. 

Uygulama; kullanıcıların yüklediği PDF, DOCX ve TXT formatındaki belgeleri yerel olarak indeksler, SQLite üzerinde saklar ve kullanıcının sorduğu sorulara en alakalı bağlamı (context) bularak yerel dil modelleri (LLM) aracılığıyla anlamlı cevaplar üretir.

---

## 🚀 Öne Çıkan Özellikler

*   **%100 Çevrimdışı (Offline):** Verileriniz ve sorgularınız internete veya bulut servislerine gönderilmez. Tamamen yerel cihazınızda çalışır.
*   **Microsoft Foundry Local Entegrasyonu:** CPU/GPU/NPU donanım ivmelendirmelerinden otomatik faydalanarak yerel LLM'leri (Qwen, Phi-3, Llama vb.) kolayca yükler ve yönetir.
*   **Gelişmiş Arama (Hybrid Retrieval):**
    *   **Vektör Benzerliği (Cosine Similarity):** Ollama üzerindeki `bge-m3` modeli ile semantik arama yapılır.
    *   **Reranker (Yeniden Sıralama):** `sentence-transformers` kütüphanesinden `BAAI/bge-reranker-v2-m3` Cross-Encoder modeli kullanılarak en alakalı sonuçlar tekrar sıralanır.
*   **Zengin Doküman Desteği:** `.pdf`, `.docx` ve `.txt` dosyalarını otomatik olarak paragraflara bölerek indeksler.
*   **Kullanıcı Dostu Streamlit Arayüzü:** Doküman yükleme/silme, model seçme, arama parametrelerini değiştirme ve geçmişi dışa aktarma gibi işlevleri barındıran modern bir web arayüzü sunar.

---

## 🛠️ Mimari ve Dosya Yapısı

Proje, katmanlı ve modüler bir mimariye sahiptir:

```text
├── app.py              # Uygulamanın Streamlit web arayüzü ve akış yönetimi
├── embedder.py         # Embedding (Vektör) üretimi ve Cosine Similarity/Rerank işlevleri
├── llm_client.py       # Foundry Local SDK ile model indirme, yükleme ve LangChain bağlantısı
├── ingest.py           # Belge okuma, parçalama (chunking), embed etme ve SQLite veritabanına kaydetme
├── retrieval.py        # SQLite'tan vektör benzerliğine göre en yakın doküman parçalarını bulma
├── rag.db              # Doküman chunk'larını ve vektörlerini saklayan SQLite veritabanı (otomatik oluşur)
├── data/               # İndekslenecek ham belgelerin yüklendiği klasör
└── readme_not.md       # Geliştirme sürecinde edinilen tecrübeler ve teknik notlar
```

---

## 📦 Kurulum ve Hazırlık

### 1. Gereksinimler

Projenin yerel olarak çalışabilmesi için cihazınızda aşağıdaki araçların kurulu olması gerekmektedir:
1.  **Python 3.10 veya üzeri**
2.  **Ollama** (Yerel embedding işlemleri için `bge-m3` modeli yüklü olmalıdır):
    ```bash
    ollama pull bge-m3
    ```
3.  **Microsoft Foundry Local** runtime ortamı.

### 2. Kütüphanelerin Kurulumu

Gerekli tüm bağımlılıkları yüklemek için terminalde aşağıdaki komutu çalıştırın:

```bash
pip install streamlit foundry-local-sdk langchain-openai langchain-core sentence-transformers numpy ollama pypdf python-docx
```

---

## ⚡ Çalıştırma ve Kullanım

### 1. Uygulamayı Başlatma

Arayüzü başlatmak için terminalden proje klasöründeyken şu komutu verin:

```bash
streamlit run app.py
```

### 2. Adım Adım Kullanım

1.  **Model Yükleme:** Sol panelde bulunan **Model** listesinden bir yerel model seçin (örn. `qwen3-0.6b`, `phi-3-mini`, `llama3.2-3b`) ve **Modeli Yükle / Değiştir** butonuna tıklayın. Model yerel önbellekte yoksa otomatik indirilecek ve ardından RAM/VRAM üzerine yüklenecektir.
2.  **Doküman Yükleme:** Sol paneldeki **Doküman Yükle** alanına sürükleyip bırakarak veya dosya seçerek belgenizi yükleyin ve **Yükle ve İndeksle** butonuna basın. Belgeniz otomatik olarak parçalara bölünecek, `bge-m3` ile vektörleştirilecek ve `rag.db` veritabanına eklenecektir.
3.  **Soru-Cevap:** Ana sayfada yer alan sohbet kutusuna dokümanlarınızla ilgili sorular sorun. Sistem en alakalı doküman parçalarını bularak ekranın altında kaynak olarak gösterecek ve yerel LLM üzerinden cevap üretecektir.

---

## 📝 Teknik Detaylar ve Geliştirici Notları

Projenin geliştirilmesi aşamasında elde edilen önemli bulgular ve tecrübeler [readme_not.md](file:///c:/Users/merve/Desktop/microsoft_intership_project/readme_not.md) dosyasında özetlenmiştir. Bazı önemli notlar:

*   **Foundry Local Başlatma:** SDK'nın güncel sürümlerinde doğrudan `FoundryLocalManager(alias)` şeklinde model adı verilmesi desteklenmemektedir. Bunun yerine önce bir `Configuration` nesnesi tanımlanmalı, `FoundryLocalManager.initialize(config)` ile singleton başlatılmalı ve `FoundryLocalManager.instance` üzerinden erişim sağlanmalıdır.
*   **Vektör Depolama:** Küçük/orta ölçekli doküman setlerinde SQLite kullanımı oldukça pratik ve hızlıdır. Vektörler veritabanında JSON string (vektör listesi) olarak saklanır ve arama esnasında cosine similarity hesabı Python katmanında hızlıca gerçekleştirilir.
*   **Reranker Katkısı:** Cosine similarity hızlı bir ilk eleme yaparken, Cross-Encoder reranker (`BAAI/bge-reranker-v2-m3`) soru ve doküman çiftlerini daha hassas değerlendirerek en doğru bilgilerin üst sıralara çıkmasını sağlar.

---

## 📄 Lisans

Bu proje [MIT Lisansı](file:///c:/Users/merve/Desktop/microsoft_intership_project/license) altında lisanslanmıştır. Detaylar için lisans dosyasına göz atabilirsiniz.

