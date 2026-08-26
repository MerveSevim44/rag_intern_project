"""
styles.py — RAG Soru-Cevap Uygulaması Özel CSS Stilleri

app.py'deki ~290 satırlık inline CSS bu modüle taşındı.
inject_custom_css() fonksiyonu ile Streamlit sayfasına enjekte edilir.

Renk notu: metin renkleri koyu gradient zemin (#24243e ~ luminance 0.026)
üzerinde WCAG AA (4.5:1) eşiğini geçecek şekilde seçildi.
"""

import streamlit as st

# ─── CSS Sabitleri ────────────────────────────────────────────────────────────

CUSTOM_CSS = """
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
    border: 1px solid rgba(255,255,255,0.12);
    border-radius: 16px;
    box-shadow: 0 8px 30px rgba(0,0,0,0.28), inset 0 1px 0 rgba(255,255,255,0.05);
    background:
        radial-gradient(circle at 18% 12%, rgba(167,139,250,0.13), transparent 42%),
        radial-gradient(circle at 82% 88%, rgba(96,165,250,0.10), transparent 45%),
        rgba(255,255,255,0.035);
    margin: 1rem 0 1.5rem 0;
}
.empty-icon  { font-size: 1.9rem; line-height: 1; letter-spacing: 0.1rem; }
.empty-title { color: var(--txt-strong); font-weight: 700; font-size: 1.15rem; margin: 0.55rem 0 0.35rem 0; }
.empty-text  { color: var(--txt-soft); font-size: 0.92rem; line-height: 1.6; }

/* "Sormaya hazırsınız" şeridi */
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

/* Doküman rozetleri (chip) */
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
    text-overflow: ellipsis;
}
.chip-count { color: var(--txt-soft); flex: 0 0 auto; }

/* Kaynak filtresi aktifken seçili dokümanın rozeti */
.chip-active {
    background: rgba(167,139,250,0.30);
    border-color: rgba(167,139,250,0.85);
    color: var(--txt-strong);
    box-shadow: 0 0 0 1px rgba(167,139,250,0.30), 0 4px 14px rgba(167,139,250,0.20);
}

/* "🎯 Filtre: dosya.pdf" rozeti — cevabın hemen altında */
.filter-badge-wrap { margin: -0.35rem 0 0.6rem 0.35rem; }
.filter-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    padding: 0.22rem 0.7rem;
    border-radius: 999px;
    font-size: 0.75rem;
    font-weight: 600;
    color: #ddd6fe;
    background: rgba(167,139,250,0.16);
    border: 1px solid rgba(167,139,250,0.45);
    backdrop-filter: blur(6px);
}
.filter-badge-name { color: var(--txt-strong); font-weight: 700; }

/* Doküman seçici (st.pills) — cam tema ile uyumlu hâle getirilir */
div[data-testid="stButtonGroup"] button {
    border-radius: 999px !important;
    border: 1px solid rgba(255,255,255,0.16) !important;
    background: rgba(255,255,255,0.05) !important;
    color: var(--txt-mid) !important;
    font-size: 0.8rem !important;
    font-weight: 600 !important;
}
div[data-testid="stButtonGroup"] button:hover {
    border-color: rgba(167,139,250,0.55) !important;
    color: var(--txt-strong) !important;
}
div[data-testid="stButtonGroup"] button[aria-pressed="true"],
div[data-testid="stButtonGroup"] button[kind="pillsActive"] {
    background: rgba(167,139,250,0.28) !important;
    border-color: rgba(167,139,250,0.85) !important;
    color: #f5f3ff !important;
    box-shadow: 0 4px 14px rgba(167,139,250,0.22) !important;
}

/* "Nasıl çalışır" mini akışı */
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
[data-testid="stMetric"] {
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 10px;
    padding: 0.55rem 0.85rem;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
}
[data-testid="stMetricLabel"] {
    color: var(--txt-soft) !important;
    font-size: 0.8rem !important;
    font-weight: 600 !important;
}
[data-testid="stMetricValue"] {
    color: var(--txt-strong) !important;
    font-size: 1.25rem !important;
    font-weight: 700 !important;
}

/* Sekmeler (Tabs) */
.stTabs [data-baseweb="tab-list"] {
    gap: 0.4rem;
    border-bottom: 1px solid rgba(255, 255, 255, 0.12);
    margin-top: 0.4rem;
}
.stTabs [data-baseweb="tab"] {
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 8px 8px 0 0;
    color: var(--txt-mid);
    padding: 0.35rem 0.75rem;
    font-size: 0.84rem;
}
.stTabs [aria-selected="true"] {
    background: rgba(139, 92, 246, 0.25) !important;
    border-color: rgba(139, 92, 246, 0.5) !important;
    color: #ffffff !important;
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
"""


def inject_custom_css():
    """Streamlit sayfasına özel CSS stillerini enjekte eder."""
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
