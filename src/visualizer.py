"""
visualizer.py — Akıllı Veri Görselleştirme ve Grafik Motoru (Plotly / Altair)

Bu modül:
1. Kural Motoru (rule_engine), Dinamik Pandas Sandbox (code_interpreter) veya Semantik RAG
   tarafından üretilen analitik verileri (dict, Series, DataFrame, list, metin dağılımları) tespit eder.
2. Verileri kategori ve metrik formatına normalize eder.
3. Streamlit arayüzünde modern, koyu tema uyumlu, interaktif Plotly ve Altair grafikleri (Çubuk, Pasta, Halka)
   ile veri tabloları ve KPI özet kartları oluşturur.
"""

import re
from typing import Any, Dict, List, Optional, Tuple, Union
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import altair as alt
import streamlit as st


# ─── Renk Paletleri & Tema Sabitleri ──────────────────────────────────────────
MODERN_PALETTE = [
    "#8b5cf6",  # Mor / Violet
    "#60a5fa",  # Canlı Mavi / Sky Blue
    "#34d399",  # Zümrüt Yeşili / Emerald
    "#fbbf24",  # Amber / Altın
    "#f472b6",  # Pembe / Rose
    "#38bdf8",  # Açık Turkuaz / Cyan
    "#a78bfa",  # Açık Lavanta
    "#fb923c",  # Turuncu / Orange
    "#e879f9",  # Fuşya / Fuchsia
    "#4ade80",  # Açık Yeşil / Lime
]

DARK_LAYOUT_TEMPLATE = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(255,255,255,0.02)",
    font=dict(
        family="Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
        color="#eef0f8",
        size=12,
    ),
    margin=dict(l=40, r=40, t=50, b=40),
    hoverlabel=dict(
        bgcolor="#1e1b4b",
        bordercolor="#8b5cf6",
        font=dict(color="#ffffff", size=13),
    ),
)


# ─── 1. Veri Çıkarımı & Normalizasyon (extract_chart_data) ─────────────────────

def _try_parse_text_distribution(text: str) -> Optional[Dict[str, float]]:
    """
    Metin içindeki 'Kategori: 123' veya 'Kategori (123)' kalıplarını regex ile yakalar.
    """
    if not text:
        return None

    # Örnek: "İstanbul (250), Ankara (120), İzmir (95)" veya "İstanbul: 250 profil; Ankara: 120"
    matches = re.findall(r"([A-Za-zÇĞİÖŞÜçğıöşü\s\-_/]+?)\s*[:(]\s*([\d.,]+)\s*(?:profil|sektör|kayıt|havaalanı|adet|%|\)|;|,|$)", text, flags=re.UNICODE)
    if len(matches) >= 2:
        res = {}
        for cat, val_str in matches:
            cat_clean = cat.strip().strip("-:;, ")
            val_clean = val_str.replace(".", "").replace(",", ".")
            if len(cat_clean) >= 2 and not cat_clean.isdigit():
                try:
                    res[cat_clean] = float(val_clean)
                except ValueError:
                    continue
        if len(res) >= 2:
            return res

    return None


def extract_chart_data(
    data: Any,
    query: str = "",
    summary: str = "",
    operation: str = ""
) -> Optional[Dict[str, Any]]:
    """
    Verilen veri nesnesini (DataFrame, Series, dict, list, scalar) veya metin özetini
    standartlaştırılmış bir grafik veri modeline (`chart_data`) dönüştürür.

    Returns:
        Dict[str, Any] veya None (grafik için uygun veri bulunamazsa):
        {
            "title": str,
            "df": pd.DataFrame (columns: ['category', 'value']),
            "categories": List[str],
            "values": List[float],
            "unit": str,
            "default_chart_type": 'bar' | 'donut' | 'horizontal_bar',
            "kpis": {
                "total": float,
                "count": int,
                "max_category": str,
                "max_value": float,
                "avg": float
            }
        }
    """
    parsed_dict: Optional[Dict[str, float]] = None

    # 1. pd.DataFrame Kontrolü
    if isinstance(data, pd.DataFrame):
        if data.empty or len(data) < 2:
            return None
        # İlk kategorik ve ilk sayısal sütunu bul
        cat_cols = data.select_dtypes(include=["object", "string", "category"]).columns.tolist()
        num_cols = data.select_dtypes(include=[np.number]).columns.tolist()

        if cat_cols and num_cols:
            cat_col = cat_cols[0]
            num_col = num_cols[0]
            parsed_dict = dict(zip(data[cat_col].astype(str), data[num_col].astype(float)))
        elif len(data.columns) >= 2:
            parsed_dict = dict(zip(data.iloc[:, 0].astype(str), pd.to_numeric(data.iloc[:, 1], errors="coerce").fillna(0)))
        elif len(data.columns) == 1 and num_cols:
            parsed_dict = dict(zip(data.index.astype(str), data.iloc[:, 0].astype(float)))

    # 2. pd.Series Kontrolü
    elif isinstance(data, pd.Series):
        if len(data) >= 2:
            try:
                parsed_dict = {str(k): float(v) for k, v in data.items() if pd.notnull(v)}
            except (ValueError, TypeError):
                pass

    # 3. dict Kontrolü
    elif isinstance(data, dict):
        # İç içe dict yapısı kontrolü (örn. {"top_cities": {...}} veya {"matching_sectors": {...}})
        target_dict = data
        for key in ["top_cities", "matching_sectors", "sector_dist", "distribution", "dist", "rates", "sectors"]:
            if key in data and isinstance(data[key], dict) and len(data[key]) >= 2:
                target_dict = data[key]
                break

        # Sözlük elemanlarının sayısal veya alt sözlük olup olmadığını doğrula
        temp_dict = {}
        for k, v in target_dict.items():
            try:
                if isinstance(v, (int, float, np.number)):
                    temp_dict[str(k)] = float(v)
                elif isinstance(v, str) and v.replace(".", "", 1).replace(",", "", 1).isdigit():
                    temp_dict[str(k)] = float(v.replace(",", "."))
                elif isinstance(v, dict):
                    for metric_key in ["pct", "ratio", "rate", "count", "value", "matching", "ge_services", "profile_count", "total"]:
                        if metric_key in v and isinstance(v[metric_key], (int, float, np.number)):
                            temp_dict[str(k)] = float(v[metric_key])
                            break
            except (ValueError, TypeError):
                continue
        if len(temp_dict) >= 2:
            parsed_dict = temp_dict

    # 4. list / tuple Kontrolü (örn: [("İstanbul", 250), ("Ankara", 120)])
    elif isinstance(data, (list, tuple)) and len(data) >= 2:
        if isinstance(data[0], (list, tuple)) and len(data[0]) >= 2:
            temp_dict = {}
            for item in data:
                try:
                    temp_dict[str(item[0])] = float(item[1])
                except (ValueError, TypeError, IndexError):
                    continue
            if len(temp_dict) >= 2:
                parsed_dict = temp_dict
        elif isinstance(data[0], dict):
            try:
                df_temp = pd.DataFrame(data)
                return extract_chart_data(df_temp, query=query, summary=summary, operation=operation)
            except Exception:
                pass

    # 5. Metin Özetinden Regex ile Çıkarım (Fallback)
    if not parsed_dict and summary:
        parsed_dict = _try_parse_text_distribution(summary)

    if not parsed_dict or len(parsed_dict) < 2:
        return None

    # DataFrame Oluştur ve Sırala
    df_chart = pd.DataFrame([
        {"category": str(k), "value": float(v)}
        for k, v in parsed_dict.items()
    ])
    df_chart = df_chart.sort_values(by="value", ascending=False).reset_index(drop=True)

    # Başlık & Birim Çıkarımı
    q_low = (query + " " + summary + " " + operation).lower()
    unit = "Adet"
    if "%" in q_low or "yüzde" in q_low or "oran" in q_low or "pct" in q_low or "ratio" in q_low:
        unit = "%"
    elif "yıl" in q_low or "deneyim" in q_low or "experience" in q_low:
        unit = "Yıl"
    elif "dakika" in q_low or "duration" in q_low:
        unit = "Dk"
    elif "saat" in q_low or "notice" in q_low:
        unit = "Saat"
    elif "sektör" in q_low or "sector" in q_low:
        unit = "Profil"
    elif "şehir" in q_low or "city" in q_low:
        unit = "Profil"

    # Dinamik Başlık
    if "profiletype" in q_low or "profil tipi" in q_low:
        title = "Profil Tipi Dağılımı (Individual vs Business)"
    elif "servicemode" in q_low or "hizmet mod" in q_low:
        title = "Hizmet Modları (Service Modes) Dağılımı"
    elif "sektor" in q_low or "sector" in q_low:
        title = "Sektör Dağılımı ve Karşılaştırması"
    elif "dil" in q_low or "language" in q_low:
        title = "Dillere Göre Profil Dağılımı"
    elif "sehir" in q_low or "city" in q_low or re.search(r"\b(?:il|iller|illeri)\b", q_low):
        title = "Şehir Bazında Dağılım ve Yoğunluklar"
    elif "meslek" in q_low or "occupation" in q_low:
        title = "Meslek Grupları Dağılımı"
    elif "airport" in q_low or "havaalan" in q_low or "havaliman" in q_low:
        title = "Havaalanı Sayıları ve Dağılımı"
    else:
        title = "Analitik Dağılım ve Karşılaştırma Grafiği"

    # Varsayılan Grafik Türü Belirleme
    if len(df_chart) <= 6 and (unit in ["%", "Profil", "Adet"] or "oran" in q_low or "dagilim" in q_low or "pay" in q_low):
        default_chart_type = "donut"
    elif len(df_chart) > 8:
        default_chart_type = "horizontal_bar"
    else:
        default_chart_type = "bar"

    # KPI Hesaplamaları
    total_val = float(df_chart["value"].sum())
    count_val = len(df_chart)
    max_row = df_chart.iloc[0]
    avg_val = float(df_chart["value"].mean())

    kpis = {
        "total": total_val,
        "count": count_val,
        "max_category": str(max_row["category"]),
        "max_value": float(max_row["value"]),
        "avg": avg_val,
    }

    return {
        "title": title,
        "df": df_chart,
        "categories": df_chart["category"].tolist(),
        "values": df_chart["value"].tolist(),
        "unit": unit,
        "default_chart_type": default_chart_type,
        "kpis": kpis,
    }


# ─── 2. Plotly Grafik Üretimi (create_plotly_figure) ──────────────────────────

def create_plotly_figure(
    chart_data: Dict[str, Any],
    chart_type: str = "bar",
    color_palette: Optional[List[str]] = None
) -> go.Figure:
    """
    Streamlit koyu gradient temasına tam uyumlu, zengin Plotly grafiği üretir.
    """
    df = chart_data["df"]
    title = chart_data.get("title", "")
    unit = chart_data.get("unit", "")
    palette = color_palette or MODERN_PALETTE

    fig = go.Figure()

    if chart_type == "bar":
        fig.add_trace(go.Bar(
            x=df["category"],
            y=df["value"],
            text=[f"{v:g} {unit}".strip() for v in df["value"]],
            textposition="outside",
            marker=dict(
                color=df["value"],
                colorscale=[[0.0, "#6366f1"], [0.5, "#8b5cf6"], [1.0, "#34d399"]],
                line=dict(color="rgba(255,255,255,0.25)", width=1.5),
                cornerradius=6,
            ),
            hovertemplate="<b>%{x}</b><br>Değer: %{y:g} " + unit + "<extra></extra>",
        ))
        fig.update_layout(
            xaxis=dict(
                title=None,
                showgrid=False,
                tickfont=dict(color="#ced1e0", size=11),
            ),
            yaxis=dict(
                title=f"Değer ({unit})",
                showgrid=True,
                gridcolor="rgba(255,255,255,0.08)",
                tickfont=dict(color="#a8acc4", size=10),
            ),
        )

    elif chart_type == "horizontal_bar":
        df_rev = df.iloc[::-1]
        fig.add_trace(go.Bar(
            x=df_rev["value"],
            y=df_rev["category"],
            orientation="h",
            text=[f"{v:g} {unit}".strip() for v in df_rev["value"]],
            textposition="outside",
            marker=dict(
                color=df_rev["value"],
                colorscale=[[0.0, "#4f46e5"], [0.5, "#a78bfa"], [1.0, "#38bdf8"]],
                line=dict(color="rgba(255,255,255,0.25)", width=1.5),
                cornerradius=6,
            ),
            hovertemplate="<b>%{y}</b><br>Değer: %{x:g} " + unit + "<extra></extra>",
        ))
        fig.update_layout(
            xaxis=dict(
                title=f"Değer ({unit})",
                showgrid=True,
                gridcolor="rgba(255,255,255,0.08)",
                tickfont=dict(color="#a8acc4", size=10),
            ),
            yaxis=dict(
                title=None,
                showgrid=False,
                tickfont=dict(color="#ced1e0", size=11),
            ),
        )

    elif chart_type in ["pie", "donut"]:
        hole = 0.55 if chart_type == "donut" else 0.0
        fig.add_trace(go.Pie(
            labels=df["category"],
            values=df["value"],
            hole=hole,
            marker=dict(
                colors=palette[:len(df)],
                line=dict(color="#1e1b4b", width=2),
            ),
            textinfo="percent+label" if len(df) <= 5 else "percent",
            hoverinfo="label+value+percent",
            hovertemplate="<b>%{label}</b><br>Değer: %{value:g} " + unit + " (%{percent})<extra></extra>",
        ))
        if chart_type == "donut":
            fig.update_layout(
                annotations=[dict(
                    text=f"<b>Toplam</b><br>{chart_data['kpis']['total']:g}",
                    x=0.5, y=0.5,
                    font_size=13,
                    font_color="#eef0f8",
                    showarrow=False
                )]
            )

    layout_opts = dict(DARK_LAYOUT_TEMPLATE)
    layout_opts["title"] = dict(
        text=f"<b>{title}</b>",
        font=dict(size=14, color="#eef0f8"),
        x=0.02,
        y=0.96
    )
    fig.update_layout(**layout_opts)
    return fig


# ─── 3. Altair Grafik Üretimi (create_altair_chart) ───────────────────────────

def create_altair_chart(
    chart_data: Dict[str, Any],
    chart_type: str = "bar"
) -> alt.Chart:
    """
    Altair ile koyu tema uyumlu alternatif grafik oluşturur.
    """
    df = chart_data["df"]
    unit = chart_data.get("unit", "")
    title = chart_data.get("title", "")

    if chart_type == "horizontal_bar":
        chart = alt.Chart(df).mark_bar(cornerRadius=6, color="#8b5cf6").encode(
            x=alt.X("value:Q", title=f"Değer ({unit})", axis=alt.Axis(gridColor="rgba(255,255,255,0.08)", labelColor="#a8acc4")),
            y=alt.Y("category:N", sort="-x", title=None, axis=alt.Axis(labelColor="#ced1e0")),
            tooltip=[alt.Tooltip("category:N", title="Kategori"), alt.Tooltip("value:Q", title="Değer", format=",.1f")]
        )
    elif chart_type in ["pie", "donut"]:
        chart = alt.Chart(df).mark_arc(innerRadius=50 if chart_type == "donut" else 0).encode(
            theta=alt.Theta("value:Q"),
            color=alt.Color("category:N", scale=alt.Scale(range=MODERN_PALETTE[:len(df)]), legend=alt.Legend(title=None, labelColor="#ced1e0")),
            tooltip=[alt.Tooltip("category:N", title="Kategori"), alt.Tooltip("value:Q", title="Değer")]
        )
    else:
        chart = alt.Chart(df).mark_bar(cornerRadius=6, color="#60a5fa").encode(
            x=alt.X("category:N", sort="-y", title=None, axis=alt.Axis(labelColor="#ced1e0", labelAngle=-25)),
            y=alt.Y("value:Q", title=f"Değer ({unit})", axis=alt.Axis(gridColor="rgba(255,255,255,0.08)", labelColor="#a8acc4")),
            tooltip=[alt.Tooltip("category:N", title="Kategori"), alt.Tooltip("value:Q", title="Değer")]
        )

    return chart.properties(
        title=title,
        width="container",
        height=320,
        background="transparent"
    ).configure_view(
        strokeOpacity=0
    ).configure_title(
        color="#eef0f8",
        fontSize=14,
        anchor="start"
    )


# ─── 4. Streamlit UI Görselleştirme Bileşeni (render_chart_block) ──────────────

def render_chart_block(chart_data: Dict[str, Any], block_key: str = "chart"):
    """
    Streamlit arayüzünde modern bir görselleştirme kartı çizer:
    - 💡 KPI Özet Metrikleri (Toplam, En Yüksek Kategori, Kategori Sayısı)
    - 📊 Çubuk Grafik (Bar), 🍩 Halka / Pasta Grafik (Donut), 📋 Veri Tablosu sekmeleri
    """
    if not chart_data or "df" not in chart_data or chart_data["df"].empty:
        return

    kpis = chart_data.get("kpis", {})
    unit = chart_data.get("unit", "")

    st.markdown(
        f"""<div style="margin-top: 0.8rem; margin-bottom: 0.4rem; padding: 0.6rem 0.9rem;
                    background: rgba(139, 92, 246, 0.08); border-left: 3px solid #8b5cf6;
                    border-radius: 6px; font-size: 0.88rem; color: #ced1e0; font-weight: 600;">
            📊 <b>Görsel Analiz & Dağılım Grafiği</b>: {chart_data.get('title', '')}
        </div>""",
        unsafe_allow_html=True
    )

    # 1. KPI Metrik Göstergeleri
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(
            label="📌 Kategori Sayısı",
            value=f"{kpis.get('count', 0)}"
        )
    with col2:
        max_cat = kpis.get("max_category", "—")
        max_val = kpis.get("max_value", 0)
        short_cat = (max_cat[:16] + "…") if len(max_cat) > 16 else max_cat
        st.metric(
            label="🏆 En Yüksek",
            value=f"{max_val:g} {unit}".strip(),
            delta=short_cat,
            delta_color="normal"
        )
    with col3:
        st.metric(
            label="∑ Toplam Değer",
            value=f"{kpis.get('total', 0):g} {unit}".strip()
        )

    # 2. Grafik Türü Sekmeleri (Tabs)
    tab_bar, tab_donut, tab_table = st.tabs([
        "📊 Çubuk Grafik (Bar)",
        "🍩 Halka / Pasta (Donut)",
        "📋 Veri Tablosu"
    ])

    with tab_bar:
        bar_type = "horizontal_bar" if len(chart_data["df"]) > 7 else "bar"
        fig_bar = create_plotly_figure(chart_data, chart_type=bar_type)
        st.plotly_chart(
            fig_bar,
            use_container_width=True,
            config={"displayModeBar": True, "displaylogo": False, "responsive": True},
            key=f"plotly_bar_{block_key}"
        )

    with tab_donut:
        fig_donut = create_plotly_figure(chart_data, chart_type="donut")
        st.plotly_chart(
            fig_donut,
            use_container_width=True,
            config={"displayModeBar": True, "displaylogo": False, "responsive": True},
            key=f"plotly_donut_{block_key}"
        )

    with tab_table:
        df_display = chart_data["df"].copy()
        df_display.columns = ["Kategori / İsim", f"Değer ({unit})"]
        if unit == "%":
            df_display[f"Değer ({unit})"] = df_display[f"Değer ({unit})"].map(lambda x: f"{x:.2f}%")
        else:
            df_display[f"Değer ({unit})"] = df_display[f"Değer ({unit})"].map(lambda x: f"{x:g}")
        st.dataframe(df_display, use_container_width=True, hide_index=True)
