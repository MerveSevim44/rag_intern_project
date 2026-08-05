"""
app.py — RAG Soru-Cevap Uygulaması (Streamlit Arayüzü)

Akış:
  1. LLM modeli oturum boyunca bir kez yüklenir (st.session_state)
  2. Kullanıcı sorusunu girer → chunk bulunur → bağlam oluşturulur → LLM yanıtlar
  3. Sohbet geçmişi ve kaynaklar yan panel + ana alanda gösterilir

Çalıştırma:
  streamlit run app.py
"""

import html
import re
import time
from pathlib import Path

import streamlit as st

from llm_client import load_model, ask, truncate_chunk_text, truncate_context
from retrieval import get_top_chunks, RERANK_TOP_N
from ingest import ingest_single_file, list_ingested_sources, delete_source, DATA_DIR, init_db

# Kullanıcıya gösterilen ad -> Foundry Local'in tam model ID'si.
# Kısa alias ("phi-4-mini") KULLANILMIYOR: katalog onu CPU varyantına çözüyor
# ve GPU hiç devreye girmiyor. Tam ID ile CUDA varyantı garanti altına alınır.
#
# Listede yalnızca indirilmiş ve çalıştığı doğrulanmış modeller var.
# Varsayılan (ilk sıra): qwen2.5-7b — Türkçe cevap kalitesi daha iyi.
MODEL_OPTIONS = {
    "qwen2.5-7b (GPU)": "qwen2.5-7b-instruct-cuda-gpu:4",
    "phi-4-mini (GPU)": "Phi-4-mini-instruct-cuda-gpu:5",
}
PREVIEW_CHARS = 200

# ─── Sayfa Yapılandırması ────────────────────────────────────────────────────
st.set_page_config(
    page_title="RAG Soru-Cevap",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Özel CSS ────────────────────────────────────────────────────────────────
# Renk notu: metin renkleri koyu gradient zemin (#24243e ≈ luminance 0.026)
# üzerinde WCAG AA (4.5:1) eşiğini geçecek şekilde seçildi. Daha önce
# opacity:0.6/0.7 ile soluklaştırılan metinler artık sabit renk kullanıyor.
st.markdown("""
<style>
:root {
    --txt-strong: #eef0f8;   /* ~15:1  — başlıklar */
    --txt-mid:    #ced1e0;   /* ~10:1  — gövde metni */
    --txt-soft:   #a8acc4;   /* ~6.1:1 — ikincil bilgi */
}

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
    color: var(--txt-soft);
    font-size: 0.9rem;
    margin-bottom: 1.5rem;
}

/* Sohbet balonları */
.chat-user {
    background: linear-gradient(135deg, #6d28d9, #4f46e5);
    color: #ffffff;
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
    border: 1px solid rgba(255,255,255,0.14);
    color: var(--txt-strong);
    padding: 0.9rem 1.2rem;
    border-radius: 18px 18px 18px 4px;
    margin: 0.5rem 0;
    max-width: 80%;
    box-shadow: 0 4px 15px rgba(0,0,0,0.3);
    line-height: 1.6;
}

/* Mesajın hangi modelle üretildiğini söyleyen küçük etiket */
.msg-model {
    color: var(--txt-soft);
    font-size: 0.75rem;
    margin: -0.25rem 0 0.35rem 0.4rem;
}

/* Kaynak kartları */
.source-card {
    background: rgba(99,102,241,0.14);
    border: 1px solid rgba(99,102,241,0.35);
    border-radius: 12px;
    padding: 0.7rem 0.9rem;
    margin: 0.25rem 0 0.1rem 0;
    font-size: 0.82rem;
    color: var(--txt-mid);
}
.source-head { color: var(--txt-strong); font-weight: 700; }
.source-meta { color: var(--txt-soft); font-weight: 500; }
.source-preview { color: var(--txt-mid); line-height: 1.55; display: block; margin-top: 0.45rem; }

/* Skor göstergesi: 0-1 aralığını dolduran bar + renk kodlu değer */
.score-wrap { display: flex; align-items: center; gap: 0.45rem; margin-top: 0.35rem; }
.score-track {
    flex: 0 0 72px;
    height: 6px;
    border-radius: 3px;
    background: rgba(255,255,255,0.16);
    overflow: hidden;
}
.score-fill { height: 100%; border-radius: 3px; }
.score-val { font-weight: 700; font-size: 0.78rem; font-variant-numeric: tabular-nums; }

/* Aktif model rozeti */
.model-badge {
    display: inline-block;
    padding: 0.35rem 0.75rem;
    border-radius: 999px;
    font-size: 0.8rem;
    font-weight: 600;
    border: 1px solid;
}
.badge-on   { background: rgba(52,211,153,0.15); border-color: rgba(52,211,153,0.55); color: #6ee7b7; }
.badge-warn { background: rgba(251,191,36,0.13); border-color: rgba(251,191,36,0.5);  color: #fcd34d; }
.badge-off  { background: rgba(255,255,255,0.06); border-color: rgba(255,255,255,0.2); color: var(--txt-soft); }

/* İndekslenmiş doküman kartı */
.doc-row {
    display: flex;
    align-items: center;
    gap: 0.45rem;
    min-width: 0;              /* flex çocuğun taşmasına izin ver → ellipsis çalışsın */
}
.doc-icon { flex: 0 0 auto; font-size: 0.95rem; }
.doc-name {
    flex: 1 1 auto;
    min-width: 0;              /* bu olmadan flex item küçülmez, ellipsis devreye girmez */
    max-width: 100%;
    white-space: nowrap;       /* uzun dosya adı satırlara bölünmesin */
    overflow: hidden;
    text-overflow: ellipsis;   /* taşan kısım "…" olsun; tam ad title= ile tooltip'te */
    color: var(--txt-strong);
    font-weight: 600;
    font-size: 0.86rem;
}
.doc-count { color: var(--txt-soft); font-size: 0.74rem; margin-top: 0.2rem; }
.doc-track {
    height: 5px;
    border-radius: 3px;
    background: rgba(255,255,255,0.14);
    overflow: hidden;
    margin-top: 0.3rem;
}
.doc-fill {
    height: 100%;
    border-radius: 3px;
    background: linear-gradient(90deg, #a78bfa, #60a5fa);
}

/* Boş durum (empty state) */
.empty-state {
    text-align: center;
    padding: 2.2rem 1.2rem;
    /* dashed yerine ince solid + gölge: düz zemin yerine derinlik */
    border: 1px solid rgba(255,255,255,0.12);
    border-radius: 16px;
    box-shadow: 0 8px 30px rgba(0,0,0,0.28), inset 0 1px 0 rgba(255,255,255,0.05);
    /* Çok düşük yoğunluklu iki radial katman → dikkat dağıtmayan doku */
    background:
        radial-gradient(circle at 18% 12%, rgba(167,139,250,0.13), transparent 42%),
        radial-gradient(circle at 82% 88%, rgba(96,165,250,0.10), transparent 45%),
        rgba(255,255,255,0.035);
    margin: 1rem 0 1.5rem 0;
}
.empty-icon  { font-size: 1.9rem; line-height: 1; letter-spacing: 0.1rem; }
.empty-title { color: var(--txt-strong); font-weight: 700; font-size: 1.15rem; margin: 0.55rem 0 0.35rem 0; }
.empty-text  { color: var(--txt-soft); font-size: 0.92rem; line-height: 1.6; }

/* "Sormaya hazırsınız" şeridi — kompakt, kutunun üst bandı */
.ready-strip {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.6rem;
    flex-wrap: wrap;
    margin-bottom: 0.9rem;
}
.ready-icon  { font-size: 1.6rem; line-height: 1; }
.ready-title { color: var(--txt-strong); font-weight: 700; font-size: 1.1rem; }
.ready-meta  { color: var(--txt-soft); font-size: 0.85rem; }

/* Doküman rozetleri (chip) — yatay wrap eden kompakt etiketler */
.chip-wrap {
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: 0.4rem;
    margin-bottom: 1rem;
}
.chip {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    max-width: 15rem;
    padding: 0.3rem 0.65rem;
    border-radius: 999px;
    background: rgba(99,102,241,0.16);
    border: 1px solid rgba(99,102,241,0.38);
    font-size: 0.78rem;
    color: var(--txt-mid);
}
.chip-name {
    min-width: 0;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;   /* tam ad title= tooltip'inde */
}
.chip-count { color: var(--txt-soft); flex: 0 0 auto; }

/* "Nasıl çalışır" mini akışı — küçük ve soluk ama AA kontrastının üstünde */
.howto {
    display: flex;
    align-items: center;
    justify-content: center;
    flex-wrap: wrap;
    gap: 0.5rem;
    margin-top: 1.1rem;
    padding-top: 0.85rem;
    border-top: 1px solid rgba(255,255,255,0.09);
    color: var(--txt-soft);
    font-size: 0.75rem;
}
.howto-step { display: inline-flex; align-items: center; gap: 0.3rem; }
.howto-num {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 1.05rem;
    height: 1.05rem;
    border-radius: 50%;
    background: rgba(167,139,250,0.22);
    border: 1px solid rgba(167,139,250,0.45);
    color: #c4b5fd;
    font-size: 0.65rem;
    font-weight: 700;
}
.howto-sep { color: rgba(255,255,255,0.22); }

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
    border: 1px solid rgba(255,255,255,0.18) !important;
    color: #ffffff !important;
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
        # [{"role": "user"|"assistant", "content": ..., "sources": [...],
        #   "elapsed": float, "model": str|None}]
        # "model": cevabı üreten alias. Geçmiş model değişiminde silinmediği için
        # her mesaj kendi modelini taşır.
        "messages": [],
        "llm": None,
        "model_loaded": False,
        "model_alias": "",
        "total_queries": 0,
        "total_elapsed": 0.0,
        "pending_delete": None,   # onay bekleyen silme işleminin source değeri
        "open_fulltext": set(),   # tam metni açılmış kaynak kartlarının anahtarları
        "ingest_report": [],      # son yükleme turunun dosya bazlı sonucu
        "pending_question": None, # örnek soru butonundan gelen, işlenmeyi bekleyen soru
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

init_session()


# ─── Yardımcı Fonksiyonlar ───────────────────────────────────────────────────

def is_meaningful_question(text: str) -> bool:
    """
    Girdinin LLM'e gönderilmeye değer olup olmadığını söyler.

    Sadece boşluk ("   "), sadece noktalama ("???") veya tek harflik girdiler
    retrieval + LLM turunu boşa harcar; bunları erken eleriz.
    """
    return len(re.sub(r"[^\w]", "", text, flags=re.UNICODE)) >= 2


def file_icon(name: str) -> str:
    """Dosya uzantısına göre ikon döndürür (.pdf → 📕, .docx → 📘, .txt → 📄)."""
    return {
        ".pdf": "📕",
        ".docx": "📘",
        ".txt": "📄",
    }.get(Path(name).suffix.lower(), "📄")


def render_doc_card(doc: dict, max_chunks: int):
    """
    İndekslenmiş bir dokümanı kart olarak çizer:
    ikon + tek satıra sığdırılmış ad + parça sayısı + orantısal bar.

    Dosya adı Python tarafında KESİLMEZ; kısaltma CSS ellipsis ile yapılır,
    böylece title= attribute'u sayesinde hover'da tam ad görünür.
    """
    name = Path(doc["source"]).name
    safe_name = html.escape(name)
    count = doc["chunk_count"]
    ratio = (count / max_chunks * 100) if max_chunks else 0

    st.markdown(
        f"""<div class="doc-row">
            <span class="doc-icon">{file_icon(name)}</span>
            <span class="doc-name" title="{safe_name}">{safe_name}</span>
        </div>
        <div class="doc-count">{count} parça</div>
        <div class="doc-track"><div class="doc-fill" style="width:{ratio:.1f}%"></div></div>""",
        unsafe_allow_html=True,
    )


def score_visual(score: float) -> tuple[float, str]:
    """
    Skoru 0-1 aralığına kırpar ve ona uygun rengi döndürür.

    Reranker (bge-reranker-v2-m3) skorları sigmoid'den geçtiği için zaten
    0-1 arasındadır; reranker kapalıyken gelen cosine benzerliği ise teorik
    olarak negatif olabilir, bu yüzden kırpma yapıyoruz.
    """
    s = max(0.0, min(1.0, float(score)))
    if s >= 0.66:
        color = "#34d399"   # yüksek alaka — yeşil
    elif s >= 0.33:
        color = "#fbbf24"   # orta alaka — amber
    else:
        color = "#9aa0b4"   # düşük alaka — gri
    return s, color


def build_context(chunks: list[dict]) -> str:
    """Chunk listesinden numaralandırılmış bağlam metni oluşturur."""
    parts = []
    for i, chunk in enumerate(chunks, 1):
        source = Path(chunk["source"]).name
        page_info = chunk.get("page_info", "")
        score = chunk.get("score", 0.0)
        # Uzun chunk'lar prompt'u şişirip GPU belleğini taşırıyor (bkz.
        # llm_client.MAX_CHUNK_CHARS). Kaynak kartlarında tam metin gösterilmeye
        # devam eder; sadece LLM'e giden kopya kırpılır.
        content = truncate_chunk_text(chunk["content"])
        parts.append(f"[{i}] Kaynak: {source}, {page_info} (skor: {score:.3f})\n{content}")
    return truncate_context("\n\n".join(parts))


def render_source_card(chunk: dict, index: int, card_key: str):
    """
    Tek bir kaynak kartını çizer: dosya adı, sayfa/paragraf bilgisi,
    skor barı, kısa önizleme ve tam metni açan buton.

    Chunk içeriği kullanıcı dokümanından geldiği için HTML'e kaçırılmadan
    basılmamalı; aksi halde '<' içeren bir metin kartın düzenini bozar.
    """
    source = html.escape(Path(chunk["source"]).name)
    page_info = html.escape(str(chunk.get("page_info", "") or "—"))
    raw_score = chunk.get("score", 0.0)
    pct, color = score_visual(raw_score)

    content = chunk.get("content", "")
    preview = html.escape(content[:PREVIEW_CHARS].replace("\n", " "))
    truncated = len(content) > PREVIEW_CHARS
    ellipsis = "…" if truncated else ""

    st.markdown(
        f"""<div class="source-card">
            <span class="source-head">[{index}] {source}</span>
            <span class="source-meta">&nbsp;({page_info})</span>
            <div class="score-wrap">
                <div class="score-track">
                    <div class="score-fill" style="width:{pct * 100:.1f}%; background:{color};"></div>
                </div>
                <span class="score-val" style="color:{color};">{raw_score:.4f}</span>
            </div>
            <span class="source-preview">{preview}{ellipsis}</span>
        </div>""",
        unsafe_allow_html=True,
    )

    # st.expander içinde iç içe expander kullanılamadığı için tam metni
    # buton + salt-okunur text_area ile açıyoruz.
    if truncated:
        is_open = card_key in st.session_state.open_fulltext
        label = "🔽 Önizlemeye dön" if is_open else "📄 Tam metni göster"
        if st.button(label, key=f"btn_{card_key}", use_container_width=True):
            if is_open:
                st.session_state.open_fulltext.discard(card_key)
            else:
                st.session_state.open_fulltext.add(card_key)
            st.rerun()

        if is_open:
            st.text_area(
                "Tam metin",
                value=content,
                height=220,
                disabled=True,
                key=f"ta_{card_key}",
                label_visibility="collapsed",
            )


def render_sources(sources: list[dict], msg_key: str):
    """
    Kaynak chunk'larını kart biçiminde gösterir.

    Geniş ekranda 2 sütunlu grid; Streamlit dar viewport'ta sütunları
    otomatik olarak alt alta yığdığı için ayrıca medya sorgusu gerekmiyor.

    msg_key: buton/text_area anahtarlarını mesaj bazında benzersiz yapar.
             Aynı chunk iki farklı yanıtta geçtiğinde anahtar çakışmaz.
    """
    if not sources:
        return
    with st.expander(f"📚 Kaynaklar ({len(sources)} doküman parçası)", expanded=False):
        for row_start in range(0, len(sources), 2):
            cols = st.columns(2)
            for offset, col in enumerate(cols):
                idx = row_start + offset
                if idx >= len(sources):
                    break
                chunk = sources[idx]
                card_key = f"{msg_key}_{chunk.get('id', idx)}_{idx}"
                with col:
                    render_source_card(chunk, idx + 1, card_key)


def render_assistant_message(msg: dict, msg_key: str):
    """
    Asistan mesajını balon + model etiketi + kaynaklar + süre olarak çizer.

    Model etiketi mesajın kendi "model" alanından okunur (o an yüklü olandan
    değil): sohbet geçmişi model değişiminde korunduğu için eski cevaplar
    üretildikleri modeli göstermeye devam eder.
    """
    st.markdown(
        f'<div class="chat-bot">🤖 {msg["content"]}</div>',
        unsafe_allow_html=True,
    )
    if msg.get("model"):
        st.markdown(
            f'<div class="msg-model">🧠 {html.escape(str(msg["model"]))} ile yanıtlandı</div>',
            unsafe_allow_html=True,
        )
    if msg.get("sources"):
        render_sources(msg["sources"], msg_key)
    if msg.get("elapsed") is not None:
        st.caption(f"⏱ {msg['elapsed']:.2f} sn")


def empty_state(icon: str, title: str, text: str):
    """Ortada duran talimat kartı — boş ekran yerine ne yapılacağını söyler."""
    st.markdown(
        f"""<div class="empty-state">
            <div class="empty-icon">{icon}</div>
            <div class="empty-title">{title}</div>
            <div class="empty-text">{text}</div>
        </div>""",
        unsafe_allow_html=True,
    )


def suggested_questions(docs: list[dict], limit: int = 4) -> list[str]:
    """
    İndekslenmiş dokümanların DOSYA ADINDAN örnek sorular türetir.

    İçerik analizi yapmaz (bu ek bir LLM çağrısı gerektirirdi); dosya adını
    okunabilir bir konu başlığına çevirip soru kalıbına oturtur:
        "8-Baglamdan_bagimsiz_dilbilgisi.pdf" → "Bağlamdan bağımsız dilbilgisi nedir?"

    Her dokümandan en fazla bir soru, toplam `limit` taneyle sınırlı.
    """
    questions = []
    for doc in docs[:limit]:
        stem = Path(doc["source"]).stem
        # Baştaki sıra numarası ("8-", "H8_", "04 ") at
        topic = re.sub(r"^[\dIVX]+[\s._-]+", "", stem)
        # Ayraçları boşluğa çevir, camelCase'i ayır, fazla boşlukları sadeleştir
        topic = re.sub(r"[_\-.]+", " ", topic)
        topic = re.sub(r"(?<=[a-zçğıöşü])(?=[A-ZÇĞİÖŞÜ])", " ", topic)
        topic = re.sub(r"\s+", " ", topic).strip()
        if not topic:
            continue
        topic = topic[0].upper() + topic[1:]
        questions.append(f"{topic} nedir, özetler misin?")
    return questions


def queue_question(text: str):
    """
    Örnek soru butonlarının on_click callback'i.

    st.chat_input'un değeri programatik olarak yazılamadığı için soruyu
    session_state'e bırakıyoruz; Streamlit callback'ten sonra betiği yeniden
    çalıştırır ve giriş bloğu bu bekleyen soruyu chat_input'muş gibi işler.
    """
    st.session_state.pending_question = text


def render_ready_state(docs: list[dict]):
    """
    "Sormaya hazırsınız" boş durumu: kompakt şerit + doküman rozetleri +
    tek tıkla denenebilen örnek sorular + mini "nasıl çalışır" akışı.
    """
    chunk_total = sum(d["chunk_count"] for d in docs)

    chips = []
    for d in docs:
        name = Path(d["source"]).name
        safe = html.escape(name)
        chips.append(
            f'<span class="chip">{file_icon(name)}'
            f'<span class="chip-name" title="{safe}">{safe}</span>'
            f'<span class="chip-count">· {d["chunk_count"]}</span></span>'
        )

    st.markdown(
        f"""<div class="empty-state">
            <div class="ready-strip">
                <span class="ready-icon">🔎📚</span>
                <span class="ready-title">Sormaya hazırsınız</span>
                <span class="ready-meta">· {len(docs)} doküman · {chunk_total} parça indeksli</span>
            </div>
            <div class="chip-wrap">{''.join(chips)}</div>
            <div class="empty-text">
                Aşağıdaki örnek sorulardan birine tıklayın ya da kendi sorunuzu yazın.
            </div>
            <div class="howto">
                <span class="howto-step"><span class="howto-num">1</span>Soru sor</span>
                <span class="howto-sep">›</span>
                <span class="howto-step"><span class="howto-num">2</span>İlgili kaynaklar bulunur</span>
                <span class="howto-sep">›</span>
                <span class="howto-step"><span class="howto-num">3</span>Kaynaklı yanıt üretilir</span>
            </div>
        </div>""",
        unsafe_allow_html=True,
    )

    # Örnek soru butonları: on_click ile pending_question'a yazar, Streamlit
    # callback sonrası rerun eder, soru giriş bloğunda işlenir.
    examples = suggested_questions(docs)
    if examples:
        st.caption("💡 Örnek sorular")
        for row_start in range(0, len(examples), 2):
            cols = st.columns(2)
            for offset, col in enumerate(cols):
                idx = row_start + offset
                if idx >= len(examples):
                    break
                with col:
                    st.button(
                        examples[idx],
                        key=f"ex_{idx}",
                        use_container_width=True,
                        on_click=queue_question,
                        args=(examples[idx],),
                    )


def load_llm(alias: str):
    """
    LLM'i yükler ve session_state'e kaydeder.

    load_model() ilerleme bildirimi sunmadığı için çubuk gerçek yüzdeyi değil
    tamamlanan aşamayı gösterir (hazırlık → yükleme → oturum).
    """
    progress = st.progress(0.0, text=f"**{alias}** hazırlanıyor…")
    try:
        progress.progress(0.15, text=f"**{alias}** katalogdan alınıyor…")
        llm = load_model(alias)

        progress.progress(0.85, text="Oturum hazırlanıyor…")
        st.session_state.llm = llm
        st.session_state.model_loaded = True
        st.session_state.model_alias = alias
        # Sohbet geçmişi KORUNUR: model değiştirmek önceki soru/cevapları silmez.
        # Hangi cevabın hangi modelden geldiği mesaj bazlı "model" alanıyla izlenir.

        # Yükleme bitti → çubuk kaldırılır, durum bilgisini tek başına
        # kenar çubuğundaki "🟢 <alias> aktif" rozeti taşır (tekrar olmasın).
        progress.empty()
    except Exception as e:
        progress.empty()
        st.error(f"❌ Model yüklenemedi: {e}")
        st.session_state.model_loaded = False


def ingest_uploaded_files(files) -> list[dict]:
    """
    Yüklenen dosyaları sırayla kaydeder ve indeksler.

    Her dosyanın kendi ilerleme çubuğu vardır (kaydetme → indeksleme → bitti).
    Bir dosya hata verse bile kalanlar işlenmeye devam eder.

    Returns:
        list[dict]: {"name", "ok", "chunks", "secs", "error"} kayıtları.
    """
    data_path = Path(DATA_DIR)
    data_path.mkdir(exist_ok=True)

    report = []
    for uploaded in files:
        st.markdown(f"**{uploaded.name}**")
        bar = st.progress(0.0, text="Kaydediliyor…")
        started = time.perf_counter()
        try:
            save_path = data_path / uploaded.name
            with open(save_path, "wb") as f:
                f.write(uploaded.getbuffer())

            bar.progress(0.35, text="İndeksleniyor (embedding üretiliyor)…")
            chunk_count = ingest_single_file(save_path)

            secs = time.perf_counter() - started
            bar.progress(1.0, text=f"✅ {chunk_count} parça · {secs:.1f} sn")
            report.append({
                "name": uploaded.name, "ok": True,
                "chunks": chunk_count, "secs": secs, "error": "",
            })
        except Exception as e:
            secs = time.perf_counter() - started
            bar.empty()
            st.error(f"❌ {uploaded.name}: {e}")
            report.append({
                "name": uploaded.name, "ok": False,
                "chunks": 0, "secs": secs, "error": str(e),
            })
    return report


# ─── Kenar Çubuğu ────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ Ayarlar")
    st.divider()

    # Model seçimi, yükleme butonu ve durum rozeti tek kart içinde.
    with st.container(border=True):
        # Kullanıcı okunur adı görür; arka planda tam model ID'si kullanılır.
        model_label = st.selectbox(
            "Model",
            list(MODEL_OPTIONS.keys()),
            index=0,
            help="Foundry Local'de indirilmiş, GPU (CUDA) üzerinde çalışan model",
        )
        model_alias = MODEL_OPTIONS[model_label]
        st.caption(f"Model ID: `{model_alias}`")

        if st.button("🚀 Modeli Yükle / Değiştir", use_container_width=True):
            load_llm(model_alias)

        # Aktif model rozeti: seçilen alias ile gerçekten yüklü olanı ayırt eder.
        # Yükleme butonundan SONRA çiziliyor ki aynı çalıştırmada güncel durumu göstersin.
        if st.session_state.model_loaded:
            active = st.session_state.model_alias
            if active == model_alias:
                badge = f'<span class="model-badge badge-on">🟢 {html.escape(active)} aktif</span>'
            else:
                badge = (
                    f'<span class="model-badge badge-warn">🟡 {html.escape(active)} aktif · '
                    f'{html.escape(model_alias)} seçili, henüz yüklenmedi</span>'
                )
        else:
            badge = '<span class="model-badge badge-off">⚪ Model yüklü değil</span>'
        st.markdown(badge, unsafe_allow_html=True)

    st.divider()

    # ── Doküman Yükleme ──────────────────────────────────────────────
    st.markdown("### 📄 Doküman Yükle")
    uploaded_files = st.file_uploader(
        "Dosya seçin (.txt, .pdf, .docx)",
        type=["txt", "pdf", "docx"],
        accept_multiple_files=True,
        help="Birden fazla dosya seçebilirsiniz; hepsi sırayla indekslenir.",
    )

    if uploaded_files:
        count = len(uploaded_files)
        if st.button(f"📥 {count} dosyayı yükle ve indeksle", use_container_width=True):
            st.session_state.ingest_report = ingest_uploaded_files(uploaded_files)
            st.rerun()

    # Yükleme özeti rerun'dan sonra da görünsün diye session_state'te tutulur.
    if st.session_state.ingest_report:
        report = st.session_state.ingest_report
        ok = [r for r in report if r["ok"]]
        failed = [r for r in report if not r["ok"]]
        total_chunks = sum(r["chunks"] for r in ok)
        total_secs = sum(r["secs"] for r in report)

        if failed:
            st.warning(f"{len(ok)} başarılı, {len(failed)} hatalı · {total_secs:.1f} sn")
        else:
            st.success(f"{len(ok)} dosya · {total_chunks} parça · {total_secs:.1f} sn")

        for r in report:
            if r["ok"]:
                st.caption(f"✅ {r['name']} — {r['chunks']} parça, {r['secs']:.1f} sn")
            else:
                st.caption(f"❌ {r['name']} — {r['error']}")

        if st.button("Özeti kapat", use_container_width=True):
            st.session_state.ingest_report = []
            st.rerun()

    st.divider()

    # ── İndekslenmiş Dokümanlar ──────────────────────────────────────
    st.markdown("### 📂 İndekslenmiş Dokümanlar")
    ingested = list_ingested_sources()
    if ingested:
        # Bar genişlikleri en büyük dokümana göre orantılanır.
        max_chunks = max(d["chunk_count"] for d in ingested)

        for doc in ingested:
            doc_name = Path(doc["source"]).name
            awaiting = st.session_state.pending_delete == doc["source"]

            with st.container(border=True):
                if awaiting:
                    # İki adımlı silme: bu kart onay moduna geçti.
                    st.markdown(
                        f'<div class="doc-row">'
                        f'<span class="doc-icon">⚠️</span>'
                        f'<span class="doc-name" title="{html.escape(doc_name)}">'
                        f'{html.escape(doc_name)}</span></div>'
                        f'<div class="doc-count">silinsin mi? ({doc["chunk_count"]} parça)</div>',
                        unsafe_allow_html=True,
                    )
                    col_yes, col_no = st.columns(2)
                    with col_yes:
                        if st.button("✔️ Onayla", key=f"ok_{doc['source']}", use_container_width=True):
                            deleted = delete_source(doc["source"])
                            st.session_state.pending_delete = None
                            st.toast(f"{doc_name} silindi ({deleted} parça).")
                            st.rerun()
                    with col_no:
                        if st.button("✕ Vazgeç", key=f"no_{doc['source']}", use_container_width=True):
                            st.session_state.pending_delete = None
                            st.rerun()
                else:
                    col_name, col_btn = st.columns([4, 1])
                    with col_name:
                        render_doc_card(doc, max_chunks)
                    with col_btn:
                        if st.button("🗑️", key=f"del_{doc['source']}", help=f"{doc_name} dokümanını sil"):
                            # Başka bir dosya onay bekliyorduysa o iptal olur.
                            st.session_state.pending_delete = doc["source"]
                            st.rerun()
    else:
        st.caption("Henüz indekslenmiş doküman yok.")

    st.divider()

    # Retrieval ayarları
    st.markdown("### 🔎 Retrieval")
    top_k = st.slider(
        "Top-K (aday chunk sayısı)",
        min_value=1, max_value=15, value=5, step=1,
        help=(
            "İlk aşamada cosine similarity ile kaç aday doküman parçası çekileceği. "
            "Yüksek değer kapsamı artırır ama yavaşlar ve alakasız parça riskini yükseltir."
        ),
    )
    # Slider değiştikçe güncellenen canlı açıklama
    st.caption(f"ℹ️ İlk aşamada **{top_k}** aday parça seçilecek.")

    use_reranker = st.toggle(
        "Cross-Encoder Reranker",
        value=True,
        help=(
            "Açıkken adaylar bge-reranker-v2-m3 ile soru-parça çifti olarak yeniden "
            "puanlanır; daha isabetli ama daha yavaştır. Kapalıyken sadece cosine "
            "similarity sıralaması kullanılır."
        ),
    )
    if use_reranker:
        st.caption(f"↳ Reranker bu {top_k} aday içinden en iyi **{RERANK_TOP_N}** tanesini seçecek.")
    else:
        st.caption(f"↳ Reranker kapalı — cosine sıralamasındaki ilk **{RERANK_TOP_N}** parça kullanılacak.")

    st.divider()

    # Geçmiş
    st.markdown("### 📋 Sohbet Geçmişi")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🗑️ Temizle", use_container_width=True):
            st.session_state.messages = []
            st.session_state.total_queries = 0
            st.session_state.total_elapsed = 0.0
            st.session_state.open_fulltext = set()
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

# Boş durum 1: model yüklü değil
if not st.session_state.model_loaded:
    empty_state(
        "🧠",
        "Önce bir model yükleyin",
        "Sol panelden bir model seçip <b>🚀 Modeli Yükle</b> butonuna basın. "
        "Model oturum boyunca bellekte kalır.",
    )
    st.stop()

# Boş durum 2: hiç doküman indekslenmemiş
if not ingested:
    empty_state(
        "📂",
        "Henüz doküman yok",
        "Başlamak için sol panelden bir doküman yükleyin (.txt, .pdf, .docx). "
        "Yüklenen dosyalar otomatik olarak parçalanıp indekslenir.",
    )
    st.stop()

# ── Sohbet geçmişini göster ──────────────────────────────────────────────────
for msg_index, msg in enumerate(st.session_state.messages):
    if msg["role"] == "user":
        st.markdown(
            f'<div class="chat-user">👩 {msg["content"]}</div>',
            unsafe_allow_html=True,
        )
    else:
        render_assistant_message(msg, msg_key=f"m{msg_index}")

# Boş durum 3: doküman var, henüz soru sorulmamış.
# Bekleyen bir örnek soru varsa çizme: aksi halde bu turda hem boş durum
# hem de üretilen cevap alt alta görünürdü.
if not st.session_state.messages and not st.session_state.pending_question:
    render_ready_state(ingested)

# ── Kullanıcı girişi ─────────────────────────────────────────────────────────
raw_question = st.chat_input("Sorunuzu yazın…")

# Örnek soru butonundan gelen soruyu al ve kuyruğu boşalt (tekrar işlenmesin).
pending = st.session_state.pending_question
st.session_state.pending_question = None

# Boş ("   ") veya anlamsız ("???") girdiyi retrieval/LLM'e göndermeden ele.
question = ""
if pending:
    # Butondan gelen soru zaten kontrollü üretildiği için doğrulamaya gerek yok.
    question = pending
elif raw_question is not None:
    candidate = raw_question.strip()
    if not is_meaningful_question(candidate):
        st.warning("Lütfen en az birkaç karakterlik geçerli bir soru yazın.")
    else:
        question = candidate

if question:
    # Kullanıcı mesajını geçmişe ekle ve göster
    st.session_state.messages.append({"role": "user", "content": question})
    st.markdown(
        f'<div class="chat-user">👩 {question}</div>',
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
        assistant_msg = {
            "role": "assistant",
            "content": "Veritabanında bu soruyla eşleşen bir içerik bulunamadı.",
            "sources": [],
            "elapsed": None,
            "model": None,   # LLM çağrılmadı → model etiketi gösterilmez
        }
    else:
        context = build_context(chunks)

        # LLM yanıtı
        with st.spinner(f"{len(chunks)} parça bulundu, yanıt oluşturuluyor…"):
            try:
                answer = ask(st.session_state.llm, context, question)
            except Exception as e:
                answer = f"Yanıt üretilemedi: {e}"
            elapsed = time.perf_counter() - t0

        assistant_msg = {
            "role": "assistant",
            "content": answer,
            "sources": chunks,
            "elapsed": elapsed,
            "model": st.session_state.model_alias,
        }

        # İstatistikleri güncelle
        st.session_state.total_queries += 1
        st.session_state.total_elapsed += elapsed

    # Önce geçmişe ekle, sonra aynı yardımcıyla çiz: böylece bu turdaki kart
    # anahtarları, sonraki rerun'da geçmişten çizilecek anahtarlarla birebir aynı olur.
    st.session_state.messages.append(assistant_msg)
    render_assistant_message(assistant_msg, msg_key=f"m{len(st.session_state.messages) - 1}")
