"""
app.py — RAG Soru-Cevap Uygulaması (Streamlit Arayüzü)

Akış:
  1. LLM modeli oturum boyunca bir kez yüklenir (st.session_state)
  2. Kullanıcı sorusunu girer → chunk bulunur → bağlam oluşturulur → LLM yanıtlar
  3. Sohbet geçmişi ve kaynaklar yan panel + ana alanda gösterilir

Çalıştırma:
  streamlit run app.py
"""

import time
from pathlib import Path

import streamlit as st

from llm_client import load_model, ask
from retrieval import get_top_chunks
from ingest import ingest_single_file, list_ingested_sources, delete_source, DATA_DIR, init_db

# ─── Sayfa Yapılandırması ────────────────────────────────────────────────────
st.set_page_config(
    page_title="RAG Soru-Cevap",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Özel CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* Genel arka plan */
[data-testid="stAppViewContainer"] {
    background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
}
[data-testid="stSidebar"] {
    background: rgba(255,255,255,0.05);
    border-right: 1px solid rgba(255,255,255,0.1);
}

/* Başlık */
.rag-title {
    font-family: 'Inter', sans-serif;
    font-size: 2.2rem;
    font-weight: 800;
    background: linear-gradient(90deg, #a78bfa, #60a5fa, #34d399);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 0.2rem;
}
.rag-subtitle {
    color: rgba(255,255,255,0.45);
    font-size: 0.9rem;
    margin-bottom: 1.5rem;
}

/* Sohbet balonları */
.chat-user {
    background: linear-gradient(135deg, #6d28d9, #4f46e5);
    color: white;
    padding: 0.9rem 1.2rem;
    border-radius: 18px 18px 4px 18px;
    margin: 0.5rem 0;
    max-width: 80%;
    margin-left: auto;
    box-shadow: 0 4px 15px rgba(109,40,217,0.4);
    line-height: 1.6;
}
.chat-bot {
    background: rgba(255,255,255,0.07);
    border: 1px solid rgba(255,255,255,0.12);
    color: rgba(255,255,255,0.92);
    padding: 0.9rem 1.2rem;
    border-radius: 18px 18px 18px 4px;
    margin: 0.5rem 0;
    max-width: 80%;
    box-shadow: 0 4px 15px rgba(0,0,0,0.3);
    line-height: 1.6;
}

/* Kaynak kartları */
.source-card {
    background: rgba(99,102,241,0.12);
    border: 1px solid rgba(99,102,241,0.3);
    border-radius: 10px;
    padding: 0.6rem 1rem;
    margin: 0.3rem 0;
    font-size: 0.82rem;
    color: rgba(255,255,255,0.75);
}
.source-score {
    color: #a78bfa;
    font-weight: 700;
}

/* Metrik kutuları */
.metric-box {
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 10px;
    padding: 0.8rem;
    text-align: center;
}

/* Input alanı */
[data-testid="stChatInput"] textarea {
    background: rgba(255,255,255,0.06) !important;
    border: 1px solid rgba(255,255,255,0.15) !important;
    color: white !important;
    border-radius: 12px !important;
}

/* Düğmeler */
.stButton > button {
    background: linear-gradient(135deg, #6d28d9, #4f46e5);
    color: white;
    border: none;
    border-radius: 8px;
    transition: opacity 0.2s;
}
.stButton > button:hover { opacity: 0.85; }
</style>
""", unsafe_allow_html=True)


# ─── Session State Başlatma ───────────────────────────────────────────────────
def init_session():
    """Session state değişkenlerini ilk kez oluşturur."""
    defaults = {
        "messages": [],        # [{"role": "user"|"assistant", "content": ..., "sources": [...], "elapsed": float}]
        "llm": None,
        "model_loaded": False,
        "model_alias": "",
        "total_queries": 0,
        "total_elapsed": 0.0,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

init_session()


# ─── Yardımcı Fonksiyonlar ───────────────────────────────────────────────────

def build_context(chunks: list[dict]) -> str:
    """Chunk listesinden numaralandırılmış bağlam metni oluşturur."""
    parts = []
    for i, chunk in enumerate(chunks, 1):
        source = Path(chunk["source"]).name
        score = chunk.get("score", 0.0)
        parts.append(f"[{i}] Kaynak: {source} (skor: {score:.3f})\n{chunk['content']}")
    return "\n\n".join(parts)


def render_sources(sources: list[dict]):
    """Kaynak chunk'larını kart biçiminde gösterir."""
    if not sources:
        return
    with st.expander(f"📚 Kaynaklar ({len(sources)} doküman parçası)", expanded=False):
        for i, chunk in enumerate(sources, 1):
            source = Path(chunk["source"]).name
            score = chunk.get("score", 0.0)
            preview = chunk["content"][:200].replace("\n", " ")
            st.markdown(
                f"""<div class="source-card">
                    <b>[{i}] {source}</b>
                    &nbsp;&nbsp;<span class="source-score">▲ {score:.4f}</span><br/>
                    <span style="opacity:0.7">{preview}…</span>
                </div>""",
                unsafe_allow_html=True,
            )


def load_llm(alias: str):
    """LLM'i yükler ve session_state'e kaydeder."""
    with st.spinner(f"**{alias}** modeli yükleniyor, lütfen bekleyin…"):
        try:
            llm = load_model(alias)
            st.session_state.llm = llm
            st.session_state.model_loaded = True
            st.session_state.model_alias = alias
            st.session_state.messages = []        # yeni model = temiz sohbet
            st.success(f"✅ **{alias}** hazır!")
        except Exception as e:
            st.error(f"❌ Model yüklenemedi: {e}")
            st.session_state.model_loaded = False


# ─── Kenar Çubuğu ────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ Ayarlar")
    st.divider()

    # Model seçimi
    model_alias = st.selectbox(
        "Model",
        ["qwen3-0.6b", "qwen2.5-7b", "phi-3-mini", "llama3.2-3b"],
        index=0,
        help="Foundry Local katalogundaki model alias'ı",
    )
    if st.button("🚀 Modeli Yükle / Değiştir", use_container_width=True):
        load_llm(model_alias)

    st.divider()

    # ── Doküman Yükleme ──────────────────────────────────────────────
    st.markdown("### 📄 Doküman Yükle")
    uploaded_file = st.file_uploader(
        "Dosya seçin (.txt, .pdf, .docx)",
        type=["txt", "pdf", "docx"],
        help="Yüklemek istediğiniz dokümanı seçin. Otomatik olarak indekslenecektir.",
    )

    if uploaded_file is not None:
        if st.button("📥 Yükle ve İndeksle", use_container_width=True):
            # Ensure data directory exists
            data_path = Path(DATA_DIR)
            data_path.mkdir(exist_ok=True)

            # Save uploaded file to data directory
            save_path = data_path / uploaded_file.name
            with open(save_path, "wb") as f:
                f.write(uploaded_file.getbuffer())

            # Ingest the file
            with st.spinner(f"**{uploaded_file.name}** indeksleniyor…"):
                try:
                    chunk_count = ingest_single_file(save_path)
                    st.success(f"✅ **{uploaded_file.name}** yüklendi! ({chunk_count} parça indekslendi)")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ İndeksleme hatası: {e}")

    st.divider()

    # ── İndekslenmiş Dokümanlar ──────────────────────────────────────
    st.markdown("### 📂 İndekslenmiş Dokümanlar")
    ingested = list_ingested_sources()
    if ingested:
        for doc in ingested:
            doc_name = Path(doc["source"]).name
            col_name, col_btn = st.columns([3, 1])
            with col_name:
                st.markdown(f"📄 **{doc_name}** ({doc['chunk_count']} parça)")
            with col_btn:
                if st.button("🗑️", key=f"del_{doc['source']}", help=f"{doc_name} dokümanını sil"):
                    delete_source(doc["source"])
                    st.success(f"{doc_name} silindi.")
                    st.rerun()
    else:
        st.caption("Henüz indekslenmiş doküman yok.")

    st.divider()

    # Retrieval ayarları
    st.markdown("### 🔎 Retrieval")
    top_k = st.slider(
        "Top-K (aday chunk sayısı)",
        min_value=1, max_value=15, value=5, step=1,
    )
    use_reranker = st.toggle("Cross-Encoder Reranker", value=True)

    st.divider()

    # Geçmiş
    st.markdown("### 📋 Sohbet Geçmişi")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🗑️ Temizle", use_container_width=True):
            st.session_state.messages = []
            st.session_state.total_queries = 0
            st.session_state.total_elapsed = 0.0
            st.rerun()
    with col2:
        if st.session_state.messages:
            lines = []
            for m in st.session_state.messages:
                role = "Kullanici" if m["role"] == "user" else "Asistan"
                lines.append(f"[{role}]\n{m['content']}\n")
            export_text = "\n".join(lines)
            st.download_button(
                "💾 İndir",
                data=export_text.encode("utf-8"),
                file_name="rag_gecmis.txt",
                mime="text/plain",
                use_container_width=True,
            )

    st.divider()

    # İstatistikler
    st.markdown("### 📊 Oturum İstatistikleri")
    q = st.session_state.total_queries
    avg = (st.session_state.total_elapsed / q) if q > 0 else 0.0
    c1, c2 = st.columns(2)
    c1.metric("Toplam Soru", q)
    c2.metric("Ort. Süre", f"{avg:.1f}s")


# ─── Ana Alan ────────────────────────────────────────────────────────────────
st.markdown('<p class="rag-title">🔍 RAG Soru-Cevap</p>', unsafe_allow_html=True)
st.markdown(
    '<p class="rag-subtitle">Dokümanlarınıza dayalı yapay zeka destekli arama</p>',
    unsafe_allow_html=True,
)

# Model yüklü değilse uyarı göster
if not st.session_state.model_loaded:
    st.info("👈 Sol panelden bir model seçip **Modeli Yükle** butonuna basın.")
    st.stop()

# ── Sohbet geçmişini göster ──────────────────────────────────────────────────
for msg in st.session_state.messages:
    if msg["role"] == "user":
        st.markdown(
            f'<div class="chat-user">👩 {msg["content"]}</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div class="chat-bot">🤖 {msg["content"]}</div>',
            unsafe_allow_html=True,
        )
        # Varsa kaynakları ve süreyi göster
        if msg.get("sources"):
            render_sources(msg["sources"])
        if msg.get("elapsed") is not None:
            st.caption(f"⏱ {msg['elapsed']:.2f} sn")

# ── Kullanıcı girişi ─────────────────────────────────────────────────────────
if question := st.chat_input("Sorunuzu yazın…"):

    # Kullanıcı mesajını geçmişe ekle ve göster
    st.session_state.messages.append({"role": "user", "content": question})
    st.markdown(
        f'<div class="chat-user">🧑 {question}</div>',
        unsafe_allow_html=True,
    )

    # Retrieval
    with st.spinner("İlgili dokümanlar aranıyor…"):
        t0 = time.perf_counter()
        try:
            chunks = get_top_chunks(
                question,
                top_k=top_k,
                use_reranker=use_reranker,
            )
        except Exception as e:
            st.error(f"Arama hatası: {e}")
            chunks = []

    if not chunks:
        bot_msg = "Veritabanında bu soruyla eşleşen bir içerik bulunamadı."
        st.markdown(f'<div class="chat-bot">🤖 {bot_msg}</div>', unsafe_allow_html=True)
        st.session_state.messages.append({"role": "assistant", "content": bot_msg, "sources": [], "elapsed": None})
    else:
        context = build_context(chunks)

        # LLM yanıtı
        with st.spinner(f"{len(chunks)} parça bulundu, yanıt oluşturuluyor…"):
            try:
                answer = ask(st.session_state.llm, context, question)
                elapsed = time.perf_counter() - t0
            except Exception as e:
                answer = f"Yanıt üretilemedi: {e}"
                elapsed = time.perf_counter() - t0

        # Yanıtı göster
        st.markdown(
            f'<div class="chat-bot">🤖 {answer}</div>',
            unsafe_allow_html=True,
        )
        render_sources(chunks)
        st.caption(f"⏱ {elapsed:.2f} sn")

        # Geçmişe kaydet
        st.session_state.messages.append({
            "role": "assistant",
            "content": answer,
            "sources": chunks,
            "elapsed": elapsed,
        })

        # İstatistikleri güncelle
        st.session_state.total_queries += 1
        st.session_state.total_elapsed += elapsed
