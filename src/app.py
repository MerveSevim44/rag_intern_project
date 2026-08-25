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
import sys
import time
from pathlib import Path

# Ensure src and root directories are in sys.path
_src_dir = Path(__file__).resolve().parent
_root_dir = _src_dir.parent
for _p in [str(_src_dir), str(_root_dir)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

import streamlit as st

try:
    from src.llm_client import load_model, ask, truncate_chunk_text, truncate_context
    from src.retrieval import get_top_chunks, RERANK_TOP_N
    from src.ingest import ingest_single_file, list_ingested_sources, delete_source, DATA_DIR, init_db
    from src.visualizer import extract_chart_data, render_chart_block
    from src.styles import inject_custom_css
    from src.components import (
        is_meaningful_question, render_doc_card,
        render_assistant_message, empty_state, render_ready_state,
    )
except ImportError:
    from llm_client import load_model, ask, truncate_chunk_text, truncate_context
    from retrieval import get_top_chunks, RERANK_TOP_N
    from ingest import ingest_single_file, list_ingested_sources, delete_source, DATA_DIR, init_db
    from visualizer import extract_chart_data, render_chart_block
    from styles import inject_custom_css
    from components import (
        is_meaningful_question, render_doc_card,
        render_assistant_message, empty_state, render_ready_state,
    )

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

# ─── Sayfa Yapılandırması ────────────────────────────────────────────────────
st.set_page_config(
    page_title="RAG Soru-Cevap",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Özel CSS ────────────────────────────────────────────────────────────────
# CSS stilleri artık styles.py modülünde tanımlı — bakım kolaylığı için ayrıldı.
inject_custom_css()


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

# build_context dışındaki yardımcı/UI fonksiyonları components.py modülüne taşındı.

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
        "Dosya seçin (.txt, .pdf, .docx, .json, .jsonl)",
        type=["txt", "pdf", "docx", "json", "jsonl"],
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
        "Başlamak için sol panelden bir doküman yükleyin (.txt, .pdf, .docx, .json). "
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
                llm=st.session_state.llm,
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

        # Görselleştirme verisi (Chart Data) ve Kod Çıkarımı
        chart_data = None
        code = None
        operation = None

        first_chunk = chunks[0] if chunks else {}
        raw_data = first_chunk.get("data_points") if first_chunk.get("data_points") is not None else first_chunk.get("raw_result")
        operation = first_chunk.get("operation", "")
        code = first_chunk.get("code", None)

        if raw_data is not None:
            chart_data = extract_chart_data(
                raw_data,
                query=question,
                summary=first_chunk.get("content", ""),
                operation=operation,
            )

        # Eğer chunk ham verisinden çıkarılamadıysa LLM cevabındaki dağılımı dene
        if not chart_data and answer:
            chart_data = extract_chart_data(
                None,
                query=question,
                summary=answer,
                operation=operation or "",
            )

        assistant_msg = {
            "role": "assistant",
            "content": answer,
            "sources": chunks,
            "elapsed": elapsed,
            "model": st.session_state.model_alias,
            "chart_data": chart_data,
            "code": code,
            "operation": operation,
        }

        # İstatistikleri güncelle
        st.session_state.total_queries += 1
        st.session_state.total_elapsed += elapsed

    # Önce geçmişe ekle, sonra aynı yardımcıyla çiz: böylece bu turdaki kart
    # anahtarları, sonraki rerun'da geçmişten çizilecek anahtarlarla birebir aynı olur.
    st.session_state.messages.append(assistant_msg)
    render_assistant_message(assistant_msg, msg_key=f"m{len(st.session_state.messages) - 1}")
