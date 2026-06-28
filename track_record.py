"""
BandarAI — Track Record Dashboard
Tema: Putih + Hijau — clean, profesional
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
from database import init_db, get_all_signals_df, get_stats

st.set_page_config(
    page_title="BandarAI — Track Record",
    page_icon="📊",
    layout="wide",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;600&display=swap');

/* ── GLOBAL RESET ── */
*, *::before, *::after { box-sizing: border-box; }

[data-testid="stAppViewContainer"] {
    background: #f0f4f0 !important;
    font-family: 'Inter', sans-serif;
}
[data-testid="stHeader"] { background: transparent !important; }
[data-testid="stToolbar"] { display: none; }
[data-testid="stDecoration"] { display: none; }
section[data-testid="stSidebar"] { display: none; }
[data-testid="stMainBlockContainer"] {
    padding: 0 2rem 2rem !important;
    max-width: 1280px;
    margin: 0 auto;
}

/* ── HIDE STREAMLIT ELEMENTS ── */
#MainMenu, footer, header { visibility: hidden; }
.stDeployButton { display: none; }

/* ── TYPOGRAPHY ── */
h1, h2, h3 {
    font-family: 'Inter', sans-serif !important;
    color: #1a2e1a !important;
    font-weight: 700 !important;
}

/* ── METRIC CARDS ── */
[data-testid="metric-container"] {
    background: #ffffff !important;
    border: 1px solid #d4e8d4 !important;
    border-radius: 12px !important;
    padding: 16px 20px !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06) !important;
}
[data-testid="stMetricValue"] {
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 1.5rem !important;
    font-weight: 700 !important;
    color: #1a2e1a !important;
}
[data-testid="stMetricLabel"] {
    font-size: 11px !important;
    font-weight: 600 !important;
    letter-spacing: 1.5px !important;
    text-transform: uppercase !important;
    color: #5a7a5a !important;
}

/* ── DATAFRAME ── */
[data-testid="stDataFrame"] {
    border: 1px solid #d4e8d4 !important;
    border-radius: 10px !important;
    overflow: hidden !important;
    background: #ffffff !important;
}

/* ── MULTISELECT & INPUT ── */
[data-testid="stMultiSelect"] [data-baseweb="select"] > div,
[data-testid="stTextInput"] > div > div {
    background: #ffffff !important;
    border: 1px solid #c8e0c8 !important;
    border-radius: 8px !important;
}

/* ── DIVIDER ── */
hr { border-color: #d4e8d4 !important; margin: 1.5rem 0 !important; }

/* ── SCROLLBAR ── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #f0f4f0; }
::-webkit-scrollbar-thumb { background: #a5c8a5; border-radius: 3px; }
</style>
""", unsafe_allow_html=True)

init_db()

# ══════════════════════════════════════════════════════
#  TOPBAR / NAVBAR
# ══════════════════════════════════════════════════════
st.markdown("""
<div style='background:#1a5e20;padding:0;margin:-1rem -2rem 0;
            box-shadow:0 2px 8px rgba(0,0,0,0.15)'>
  <div style='max-width:1280px;margin:0 auto;padding:0 2rem;
              display:flex;justify-content:space-between;align-items:center;height:60px'>
    <div style='display:flex;align-items:center;gap:10px'>
      <div style='width:34px;height:34px;background:#43a047;border-radius:8px;
                  display:flex;align-items:center;justify-content:center;
                  font-size:18px'>📊</div>
      <span style='font-family:Inter,sans-serif;font-size:1.2rem;font-weight:700;
                   color:#ffffff;letter-spacing:1px'>BandarAI</span>
      <span style='font-family:Inter,sans-serif;font-size:11px;color:#a5d6a7;
                   margin-left:4px;letter-spacing:0.5px'>IDX Signal Intelligence</span>
    </div>
    <div style='display:flex;align-items:center;gap:6px'>
      <div style='width:8px;height:8px;background:#69f0ae;border-radius:50%;
                  animation:pulse 1.5s infinite'></div>
      <span style='font-family:Inter,sans-serif;font-size:12px;color:#a5d6a7'>
        Live · Auto-update</span>
    </div>
  </div>
</div>
<style>
@keyframes pulse {0%,100%{opacity:1}50%{opacity:0.4}}
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════
#  HERO SECTION
# ══════════════════════════════════════════════════════
st.markdown("""
<div style='background:linear-gradient(135deg,#1b5e20 0%,#2e7d32 50%,#388e3c 100%);
            margin:-1px -2rem 0;padding:3rem 2rem 2.5rem'>
  <div style='max-width:1280px;margin:0 auto'>
    <div style='font-family:Inter,sans-serif;font-size:2rem;font-weight:700;
                color:#ffffff;margin-bottom:8px'>
      Track Record Publik
    </div>
    <div style='font-size:14px;color:#c8e6c9;line-height:1.7;max-width:600px'>
      Semua sinyal tercatat dengan timestamp yang tidak bisa diubah.
      WIN dan LOSS ditampilkan lengkap — tidak ada cherry-pick.
    </div>
    <div style='display:flex;gap:1.5rem;margin-top:1.5rem;flex-wrap:wrap'>
      <div style='display:flex;align-items:center;gap:6px;font-size:12px;color:#a5d6a7'>
        <span style='font-size:14px'>☀️</span> Pre-Market 08:30 WIB
      </div>
      <div style='display:flex;align-items:center;gap:6px;font-size:12px;color:#a5d6a7'>
        <span style='font-size:14px'>🕐</span> Midday 13:00 WIB
      </div>
      <div style='display:flex;align-items:center;gap:6px;font-size:12px;color:#a5d6a7'>
        <span style='font-size:14px'>🌙</span> Post-Market 16:30 WIB
      </div>
      <div style='display:flex;align-items:center;gap:6px;font-size:12px;color:#a5d6a7'>
        <span style='font-size:14px'>🔍</span> Audit TP/SL setiap 30 menit
      </div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════
#  LOAD DATA
# ══════════════════════════════════════════════════════
df    = get_all_signals_df()
stats = get_stats()
total = stats.get("total", 0)

# ── EMPTY STATE
if df.empty or total == 0:
    st.markdown("""
    <div style='background:#ffffff;border:1px solid #d4e8d4;border-radius:16px;
                text-align:center;padding:5rem 2rem;margin:1rem 0;
                box-shadow:0 2px 8px rgba(0,100,0,0.06)'>
      <div style='font-size:4rem;margin-bottom:1rem'>📡</div>
      <div style='font-family:Inter,sans-serif;font-size:1.25rem;font-weight:700;
                  color:#1a2e1a;margin-bottom:10px'>Membangun track record...</div>
      <div style='font-size:14px;color:#5a7a5a;max-width:420px;
                  margin:0 auto;line-height:1.8'>
        Sinyal pertama akan muncul di sini setiap hari bursa mulai
        <strong style='color:#2e7d32'>08:30 WIB</strong>.<br>
        Semua sinyal — termasuk yang loss — dicatat secara transparan.
      </div>
      <div style='margin-top:2rem;padding:1rem;background:#f1f8e9;
                  border-radius:10px;display:inline-block'>
        <div style='font-size:12px;color:#33691e;font-weight:600'>
          Sistem aktif · Sinyal otomatis dikirim ke Telegram setiap hari bursa
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# ══════════════════════════════════════════════════════
#  KPI CARDS
# ══════════════════════════════════════════════════════
wr      = stats.get("win_rate", 0)
avg_pnl = stats.get("avg_pnl", 0) or 0
wins    = stats.get("wins", 0)
losses  = stats.get("losses", 0)
open_c  = stats.get("open_count", 0)
best    = stats.get("best_trade", 0) or 0
worst   = stats.get("worst_trade", 0) or 0
closed  = stats.get("total_closed", 0)

wr_color  = "#2e7d32" if wr >= 60 else "#e65100" if wr >= 50 else "#c62828"
avg_color = "#2e7d32" if avg_pnl >= 0 else "#c62828"

def kpi_card(label, value, color, bg="#ffffff", sub=""):
    return f"""
    <div style='background:{bg};border:1px solid #d4e8d4;border-radius:12px;
                padding:18px 20px;box-shadow:0 1px 4px rgba(0,0,0,0.05)'>
      <div style='font-family:Inter,sans-serif;font-size:10px;font-weight:600;
                  letter-spacing:1.5px;color:#5a7a5a;text-transform:uppercase;
                  margin-bottom:6px'>{label}</div>
      <div style='font-family:"IBM Plex Mono",monospace;font-size:1.6rem;
                  font-weight:700;color:{color}'>{value}</div>
      {f'<div style="font-size:11px;color:#8a9e8a;margin-top:3px">{sub}</div>' if sub else ''}
    </div>"""

cols = st.columns(7)
kpis = [
    ("Win Rate",    f"{wr:.1f}%",       wr_color,  f"{wins}W / {losses}L"),
    ("Total Sinyal",str(total),          "#1a2e1a", f"{closed} selesai"),
    ("Win",         str(wins),           "#2e7d32", "TP tercapai"),
    ("Loss",        str(losses),         "#c62828", "SL tercapai"),
    ("Avg Return",  f"{avg_pnl:+.2f}%", avg_color, "per sinyal"),
    ("Best Trade",  f"+{best:.1f}%",    "#2e7d32", "tertinggi"),
    ("Open",        str(open_c),         "#e65100", "sedang berjalan"),
]
for col, (label, val, color, sub) in zip(cols, kpis):
    col.markdown(kpi_card(label, val, color, sub=sub), unsafe_allow_html=True)

st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
st.markdown("---")

# ══════════════════════════════════════════════════════
#  CHARTS
# ══════════════════════════════════════════════════════
closed_df = df[df["status"].isin(["WIN","LOSS"])].copy()

if not closed_df.empty:
    closed_df = closed_df.sort_values("timestamp_wib").reset_index(drop=True)
    closed_df["cumulative"] = closed_df["pnl_pct"].cumsum()

    col_eq, col_dist = st.columns([3, 2])

    with col_eq:
        st.markdown("""
        <div style='font-family:Inter,sans-serif;font-size:15px;font-weight:600;
                    color:#1a2e1a;margin-bottom:8px'>Performa Kumulatif</div>
        <div style='font-size:12px;color:#5a7a5a;margin-bottom:12px'>
          P&L per sinyal + kurva kumulatif</div>
        """, unsafe_allow_html=True)

        fig = go.Figure()
        bar_colors = ["#43a047" if v >= 0 else "#e53935" for v in closed_df["pnl_pct"]]
        fig.add_trace(go.Bar(
            x=list(range(1, len(closed_df)+1)),
            y=closed_df["pnl_pct"],
            marker_color=bar_colors, opacity=0.65,
            name="P&L per sinyal",
            hovertemplate="Sinyal #%{x}<br>P&L: %{y:+.2f}%<extra></extra>",
        ))
        fig.add_trace(go.Scatter(
            x=list(range(1, len(closed_df)+1)),
            y=closed_df["cumulative"],
            name="Kumulatif",
            mode="lines",
            line=dict(color="#1b5e20", width=2.5),
            hovertemplate="Kumulatif: %{y:+.2f}%<extra></extra>",
        ))
        fig.add_hline(y=0, line_color="#c8e6c9", line_width=1.5)
        fig.update_layout(
            paper_bgcolor="#ffffff", plot_bgcolor="#fafffe",
            font=dict(color="#3d5a3d", family="Inter", size=11),
            margin=dict(l=0, r=0, t=8, b=0), height=280,
            xaxis=dict(title="Nomor sinyal", gridcolor="#e8f5e9",
                       showline=True, linecolor="#c8e6c9"),
            yaxis=dict(title="P&L (%)", gridcolor="#e8f5e9",
                       showline=True, linecolor="#c8e6c9"),
            legend=dict(bgcolor="#f1f8f1", bordercolor="#c8e6c9",
                        font=dict(size=11), orientation="h", y=1.08),
            hovermode="x unified",
            plot_bgcolor="#fafffe",
        )
        st.plotly_chart(fig, use_container_width=True)

    with col_dist:
        st.markdown("""
        <div style='font-family:Inter,sans-serif;font-size:15px;font-weight:600;
                    color:#1a2e1a;margin-bottom:8px'>Distribusi Return</div>
        <div style='font-size:12px;color:#5a7a5a;margin-bottom:12px'>
          Sebaran P&L semua sinyal</div>
        """, unsafe_allow_html=True)

        avg_v = float(closed_df["pnl_pct"].mean())
        fig2  = go.Figure(go.Histogram(
            x=closed_df["pnl_pct"], nbinsx=20,
            marker_color="#43a047", opacity=0.75,
            hovertemplate="Return: %{x:.1f}%<br>Count: %{y}<extra></extra>",
        ))
        fig2.add_vline(x=0,     line_color="#c8e6c9", line_width=1.5)
        fig2.add_vline(x=avg_v, line_color="#1b5e20",  line_dash="dash",
                       line_width=1.5,
                       annotation_text=f"Avg {avg_v:+.1f}%",
                       annotation_font_color="#1b5e20",
                       annotation_font_size=11)
        fig2.update_layout(
            paper_bgcolor="#ffffff", plot_bgcolor="#fafffe",
            font=dict(color="#3d5a3d", family="Inter", size=11),
            margin=dict(l=0, r=0, t=8, b=0), height=280,
            xaxis=dict(title="Return (%)", gridcolor="#e8f5e9",
                       showline=True, linecolor="#c8e6c9"),
            yaxis=dict(title="Count", gridcolor="#e8f5e9",
                       showline=True, linecolor="#c8e6c9"),
            bargap=0.08,
        )
        st.plotly_chart(fig2, use_container_width=True)

st.markdown("---")

# ══════════════════════════════════════════════════════
#  SIGNAL TABLE
# ══════════════════════════════════════════════════════
st.markdown("""
<div style='font-family:Inter,sans-serif;font-size:15px;font-weight:600;
            color:#1a2e1a;margin-bottom:4px'>Semua Sinyal</div>
<div style='font-size:12px;color:#5a7a5a;margin-bottom:14px'>
  WIN dan LOSS ditampilkan lengkap — tidak ada yang disembunyikan
</div>
""", unsafe_allow_html=True)

col_f1, col_f2, col_f3 = st.columns(3)
with col_f1:
    f_status = st.multiselect("Filter Status",
        ["WIN","LOSS","OPEN","EXPIRED"],
        default=["WIN","LOSS","OPEN","EXPIRED"],
        label_visibility="visible")
with col_f2:
    f_ticker = st.text_input("Filter Ticker", "",
                              placeholder="Contoh: BBCA",
                              label_visibility="visible").upper().strip()
with col_f3:
    f_session = st.multiselect("Filter Sesi",
        ["PRE_MARKET","MIDDAY","POST_MARKET"],
        default=["PRE_MARKET","MIDDAY","POST_MARKET"],
        label_visibility="visible")

df_f = df.copy()
if f_status:  df_f = df_f[df_f["status"].isin(f_status)]
if f_ticker:  df_f = df_f[df_f["ticker"].str.contains(f_ticker, na=False)]
if f_session: df_f = df_f[df_f["session"].isin(f_session)]

disp = [
    "timestamp_wib","ticker","signal_type","session","score",
    "entry_low","tp_price","sl_price","tp_pct","sl_pct",
    "wyckoff_phase","vcp_grade","rs_interp",
    "status","exit_price","pnl_pct","days_held"
]
df_show = df_f[[c for c in disp if c in df_f.columns]]

st.dataframe(
    df_show, hide_index=True, use_container_width=True,
    height=420,
    column_config={
        "timestamp_wib": st.column_config.TextColumn("Waktu"),
        "signal_type"  : st.column_config.TextColumn("Tipe"),
        "score"        : st.column_config.ProgressColumn(
            "Score", min_value=0, max_value=100, format="%d"),
        "pnl_pct"      : st.column_config.NumberColumn("P&L %",  format="%+.2f%%"),
        "tp_pct"       : st.column_config.NumberColumn("TP %",   format="+%.1f%%"),
        "sl_pct"       : st.column_config.NumberColumn("SL %",   format="-%.1f%%"),
        "entry_low"    : st.column_config.NumberColumn("Entry",  format="Rp %.0f"),
        "tp_price"     : st.column_config.NumberColumn("TP",     format="Rp %.0f"),
        "sl_price"     : st.column_config.NumberColumn("SL",     format="Rp %.0f"),
        "exit_price"   : st.column_config.NumberColumn("Exit",   format="Rp %.0f"),
        "wyckoff_phase": st.column_config.TextColumn("Wyckoff"),
        "vcp_grade"    : st.column_config.TextColumn("VCP"),
        "rs_interp"    : st.column_config.TextColumn("RS vs IHSG"),
        "days_held"    : st.column_config.NumberColumn("Hari"),
    }
)

# ══════════════════════════════════════════════════════
#  DISCLAIMER + FOOTER
# ══════════════════════════════════════════════════════
st.markdown("""
<div style='background:#f1f8e9;border:1px solid #c5e1a5;border-radius:10px;
            padding:14px 18px;margin:1.5rem 0 0.5rem;
            font-family:Inter,sans-serif;font-size:12px;color:#33691e;
            line-height:1.7'>
  <strong>⚠️ Disclaimer:</strong>
  BandarAI adalah alat analisis teknikal, bukan nasihat investasi.
  Performa masa lalu tidak menjamin hasil di masa depan.
  Selalu gunakan manajemen risiko dan stop-loss di setiap transaksi.
  Keputusan investasi sepenuhnya menjadi tanggung jawab masing-masing investor.
</div>
""", unsafe_allow_html=True)

st.markdown(f"""
<div style='text-align:center;padding:1.2rem 0;margin-top:0.5rem;
            border-top:1px solid #d4e8d4;
            font-family:Inter,sans-serif;font-size:11px;color:#8a9e8a'>
  BandarAI IDX Signal Intelligence &nbsp;·&nbsp;
  {len(df_show)} dari {total} sinyal ditampilkan &nbsp;·&nbsp;
  Update otomatis &nbsp;·&nbsp;
  {datetime.now().strftime("%d %b %Y, %H:%M WIB")}
</div>
""", unsafe_allow_html=True)
