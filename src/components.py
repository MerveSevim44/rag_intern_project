"""
components.py — RAG Soru-Cevap Uygulaması UI Bileşenleri

app.py'deki yeniden kullanılabilir UI fonksiyonları bu modüle taşındı.
Sohbet balonları, kaynak kartları, boş durum ekranları ve yardımcı fonksiyonlar burada tanımlıdır.
"""

import html
import re
from pathlib import Path

import streamlit as st

try:
    from src.visualizer import extract_chart_data, render_chart_block
except ImportError:
    from visualizer import extract_chart_data, render_chart_block


PREVIEW_CHARS = 200


# ─── Yardımcı Fonksiyonlar ───────────────────────────────────────────────────

def is_meaningful_question(text: str) -> bool:
    """
    Girdinin LLM'e gönderilmeye değer olup olmadığını söyler.

    Sadece boşluk ("   "), sadece noktalama ("???") veya tek harflik girdiler
    retrieval + LLM turunu boşa harcar; bunları erken eleriz.
    """
    return len(re.sub(r"[^\w]", "", text, flags=re.UNICODE)) >= 2


def file_icon(name: str) -> str:
    """Dosya uzantısına göre ikon döndürür (.pdf → 📕, .docx → 📘, .json → 🗂️)."""
    return {
        ".pdf": "📕",
        ".docx": "📘",
        ".txt": "📄",
        ".json": "🗂️",
        ".jsonl": "🗂️",
    }.get(Path(name).suffix.lower(), "📄")


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


# ─── Doküman Kartı ───────────────────────────────────────────────────────────

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


# ─── Kaynak Kartları ─────────────────────────────────────────────────────────

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


# ─── Mesaj Bileşenleri ───────────────────────────────────────────────────────

def filter_badge_html(source_filter: str) -> str:
    """'🎯 Filtre: dosya.pdf' rozetinin HTML'ini üretir (glass tema ile uyumlu)."""
    name = html.escape(Path(str(source_filter)).name)
    return (
        f'<div class="filter-badge-wrap"><span class="filter-badge">'
        f'🎯 Filtre: <span class="filter-badge-name">{name}</span>'
        f'</span></div>'
    )


def render_assistant_message(msg: dict, msg_key: str):
    """
    Asistan mesajını balon + görsel analiz grafiği (Plotly/Altair) + kod bloğu + model etiketi + kaynaklar + süre olarak çizer.

    Model etiketi mesajın kendi "model" alanından okunur (o an yüklü olandan
    değil): sohbet geçmişi model değişiminde korunduğu için eski cevaplar
    üretildikleri modeli göstermeye devam eder.
    """
    st.markdown(
        f'<div class="chat-bot">🤖 {msg["content"]}</div>',
        unsafe_allow_html=True,
    )

    # Cevap tek bir doküman üzerinden üretildiyse hangi kaynağın filtrelendiğini göster.
    if msg.get("source_filter"):
        st.markdown(filter_badge_html(msg["source_filter"]), unsafe_allow_html=True)
    
    # ── Görsel Analiz & Grafik Kartı (Plotly / Altair / Veri Tablosu) ──
    if msg.get("chart_data"):
        render_chart_block(msg["chart_data"], block_key=f"viz_{msg_key}")

    # ── Çalıştırılan Kod Bloğu (Python / Pandas) ──
    if msg.get("code"):
        with st.expander("💻 Çalıştırılan Analiz Kodu (Python / Pandas)", expanded=False):
            st.code(msg["code"], language="python")

    if msg.get("model"):
        st.markdown(
            f'<div class="msg-model">🧠 {html.escape(str(msg["model"]))} ile yanıtlandı</div>',
            unsafe_allow_html=True,
        )
    if msg.get("sources"):
        render_sources(msg["sources"], msg_key)
    if msg.get("elapsed") is not None:
        st.caption(f"⏱ {msg['elapsed']:.2f} sn")


# ─── Boş Durum Ekranları ─────────────────────────────────────────────────────

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


def doc_topic(source: str) -> str:
    """Dosya adından okunabilir bir konu başlığı çıkarır ("H8_FourierTransform" → "Fourier Transform")."""
    stem = Path(source).stem
    # Baştaki sıra numarası ("8-", "H8_", "04 ") at
    topic = re.sub(r"^[\dIVX]+[\s._-]+", "", stem)
    # Ayraçları boşluğa çevir, camelCase'i ayır, fazla boşlukları sadeleştir
    topic = re.sub(r"[_\-.]+", " ", topic)
    topic = re.sub(r"(?<=[a-zçğıöşü])(?=[A-ZÇĞİÖŞÜ])", " ", topic)
    topic = re.sub(r"\s+", " ", topic).strip()
    if not topic:
        return ""
    return topic[0].upper() + topic[1:]


def suggested_questions(docs: list[dict], limit: int = 4) -> list[str]:
    """
    İndekslenmiş dokümanların DOSYA ADINDAN ve içerik tipinden örnek sorular türetir.
    JSON/tablo veri setleri varsa analitik grafik soruları da ekler.

    Tek bir doküman verildiğinde (kaynak filtresi aktifken) öneriler yalnızca
    o dokümana göre üretilir; liste kısa kalırsa dosya türüne uygun genel
    sorularla tamamlanır.
    """
    questions = []
    has_profiles = any("728_profiles" in str(d.get("source", "")) for d in docs)
    has_airports = any("airports" in str(d.get("source", "")) for d in docs)

    if has_profiles:
        questions.append("📊 Veri setindeki sektör dağılımı nasıldır?")
        questions.append("📍 En çok profile sahip ilk 5 şehir hangileridir?")

    if has_airports:
        questions.append("✈️ Hangi ülkede kaç havaalanı bulunmaktadır?")

    for doc in docs:
        if len(questions) >= limit:
            break
        stem = Path(doc["source"]).stem
        if "728_profiles" in stem or "airports" in stem:
            continue
        topic = doc_topic(doc["source"])
        if not topic:
            continue
        questions.append(f"{topic} nedir, özetler misin?")

    # Tek doküman seçiliyken 1-2 öneri yeterince yol göstermiyor; o dokümana
    # özel birkaç soru daha ekleyip listeyi doldururuz.
    if len(docs) == 1 and len(questions) < limit:
        name = Path(docs[0]["source"]).name
        topic = doc_topic(name) or name
        is_table = Path(name).suffix.lower() in (".json", ".jsonl", ".csv")
        extras = (
            [
                f"📊 {topic} verisindeki kayıt sayısı kaçtır?",
                f"🧭 {topic} veri setinde hangi alanlar (kolonlar) bulunuyor?",
                f"📈 {topic} içindeki en sık görülen değerler nelerdir?",
            ]
            if is_table
            else [
                f"📝 {topic} dokümanının ana başlıkları nelerdir?",
                f"🔑 {topic} içinde geçen temel kavramları açıklar mısın?",
                f"📌 {topic} dokümanındaki en önemli 3 çıkarım nedir?",
            ]
        )
        for q in extras:
            if len(questions) >= limit:
                break
            if q not in questions:
                questions.append(q)

    return questions[:limit]


def queue_question(text: str):
    """
    Örnek soru butonlarının on_click callback'i.

    st.chat_input'un değeri programatik olarak yazılamadığı için soruyu
    session_state'e bırakıyoruz; Streamlit callback'ten sonra betiği yeniden
    çalıştırır ve giriş bloğu bu bekleyen soruyu chat_input'muş gibi işler.
    """
    st.session_state.pending_question = text


def render_ready_state(docs: list[dict], source_filter: str | None = None):
    """
    "Sormaya hazırsınız" boş durumu: kompakt şerit + doküman rozetleri +
    tek tıkla denenebilen örnek sorular + mini "nasıl çalışır" akışı.

    source_filter verildiğinde o dokümanın rozeti vurgulanır ve örnek sorular
    yalnızca seçili dokümandan türetilir.
    """
    chunk_total = sum(d["chunk_count"] for d in docs)
    active_name = Path(source_filter).name.lower() if source_filter else None
    focus_docs = [d for d in docs if Path(d["source"]).name.lower() == active_name] if active_name else docs
    focus_docs = focus_docs or docs

    chips = []
    for d in docs:
        name = Path(d["source"]).name
        safe = html.escape(name)
        cls = "chip chip-active" if active_name and name.lower() == active_name else "chip"
        chips.append(
            f'<span class="{cls}">{file_icon(name)}'
            f'<span class="chip-name" title="{safe}">{safe}</span>'
            f'<span class="chip-count">· {d["chunk_count"]}</span></span>'
        )

    hint_text = (
        f"Arama <b>{html.escape(Path(source_filter).name)}</b> dokümanıyla sınırlı — "
        "aşağıdaki örnek sorulardan birine tıklayın ya da kendi sorunuzu yazın."
        if source_filter else
        "Aşağıdaki örnek sorulardan birine tıklayın ya da kendi sorunuzu yazın."
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
                {hint_text}
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
    examples = suggested_questions(focus_docs)
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
                        key=f"ex_{active_name or 'all'}_{idx}",
                        use_container_width=True,
                        on_click=queue_question,
                        args=(examples[idx],),
                    )
