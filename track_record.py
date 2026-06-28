"""
Track Record Dashboard — Streamlit app publik.
Ini yang membedakan kita dari Zeta AI: semua sinyal ditampilkan,
termasuk yang loss. Tidak ada cherry-pick.

Jalankan: streamlit run track_record.py
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
from database import init_db, get_all_signals_df, get_stats
from config import DASHBOARD_TITLE, DASHBOARD_SUBTITLE

st.set_page_config(
    page_title=DASHBOARD_TITLE,
    page_icon="📊",
    layout="wide",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600;700&display=swap');
:root {
  --bg:#05080c; --green:#00e676; --red:#ff1744;
  --amber:#ffab00; --blue:#00b0ff; --text:#cdd8e6; --dim:#5a7a9a;
}
[data-testid="stAppViewContainer"] { background:var(--bg); color:var(--text); }
[data-testid="stMetricValue"] {
  font-family:'IBM Plex Mono',monospace!important;
  font-size:1.8rem!important; font-weight:700!important;
}
h1,h2,h3 { font-family:'IBM Plex Mono',monospace!important; color:#eaf0f8!important; }
</style>
""", unsafe_allow_html=True)

init_db()

# ── HEADER
st.markdown(f"""
<div style='padding:14px 0 8px;border-bottom:2px solid #141e2e;margin-bottom:16px'>
  <div style='font-family:"IBM Plex Mono",monospace;font-size:1.6rem;font-weight:700;color:#00e676'>
    📊 {DASHBOARD_TITLE}</div>
  <div style='font-size:12px;color:#5a7a9a;margin-top:4px'>{DASHBOARD_SUBTITLE}</div>
  <div style='font-size:11px;color:#2a3d52;margin-top:2px'>
    Update otomatis · Semua sinyal termasuk loss ditampilkan · Timestamp tidak bisa diubah
  </div>
</div>
""", unsafe_allow_html=True)

# ── LOAD DATA
df = get_all_signals_df()
stats = get_stats()

if df.empty:
    st.info("Belum ada sinyal. Jalankan `python3 scheduler.py` untuk mulai generate sinyal.")
    st.stop()

# ── KPI ROW
c1, c2, c3, c4, c5, c6, c7 = st.columns(7)

wr = stats.get("win_rate", 0)
wr_color = "#00e676" if wr >= 60 else "#ffab00" if wr >= 50 else "#ff1744"

kpis = [
    (c1, "WIN RATE",    f"{wr:.1f}%",              wr_color),
    (c2, "TOTAL SINYAL",f"{stats.get('total',0)}",  "#cdd8e6"),
    (c3, "WIN",         f"{stats.get('wins',0)}",   "#00e676"),
    (c4, "LOSS",        f"{stats.get('losses',0)}", "#ff1744"),
    (c5, "AVG RETURN",  f"{stats.get('avg_pnl') or 0:+.2f}%",
         "#00e676" if (stats.get("avg_pnl") or 0) > 0 else "#ff1744"),
    (c6, "BEST TRADE",  f"+{stats.get('best_trade') or 0:.1f}%", "#00e676"),
    (c7, "OPEN",        f"{stats.get('open_count',0)}", "#ffab00"),
]
for col, label, val, color in kpis:
    col.markdown(f"""
    <div style='background:#0b1018;border:1px solid #141e2e;border-top:2px solid {color};
                padding:12px;border-radius:4px;text-align:center'>
      <div style='font-size:9px;color:#5a7a9a;letter-spacing:1.5px;font-family:"IBM Plex Mono",monospace'>{label}</div>
      <div style='font-size:1.5rem;font-weight:700;color:{color};font-family:"IBM Plex Mono",monospace'>{val}</div>
    </div>""", unsafe_allow_html=True)

st.markdown("---")

# ── EQUITY CURVE (cumulative PnL per sinyal)
closed = df[df["status"].isin(["WIN", "LOSS"])].copy()
if not closed.empty:
    closed = closed.sort_values("timestamp_wib").reset_index(drop=True)
    closed["cumulative_pnl"] = closed["pnl_pct"].cumsum()
    col_eq, col_dist = st.columns([3, 2])

    with col_eq:
        st.markdown("##### Cumulative P&L (per sinyal, %, Rp sama per entry)")
        fig_eq = go.Figure()
        colors_bar = ["#00e676" if v >= 0 else "#ff1744" for v in closed["pnl_pct"]]
        fig_eq.add_trace(go.Bar(
            x=list(range(1, len(closed)+1)),
            y=closed["pnl_pct"],
            name="P&L per sinyal",
            marker_color=colors_bar, opacity=0.6,
        ))
        fig_eq.add_trace(go.Scatter(
            x=list(range(1, len(closed)+1)),
            y=closed["cumulative_pnl"],
            name="Kumulatif",
            line=dict(color="#00e676", width=2.5),
            mode="lines",
        ))
        fig_eq.add_hline(y=0, line_color="#2a3d52", line_width=1)
        fig_eq.update_layout(
            paper_bgcolor="#05080c", plot_bgcolor="#090d12",
            font=dict(color="#cdd8e6", family="IBM Plex Mono", size=11),
            margin=dict(l=0,r=0,t=10,b=0), height=300,
            xaxis=dict(title="Nomor sinyal", gridcolor="#141e2e"),
            yaxis=dict(title="P&L (%)", gridcolor="#141e2e"),
            legend=dict(bgcolor="#0b1018", bordercolor="#141e2e"),
            hovermode="x unified",
        )
        st.plotly_chart(fig_eq, use_container_width=True)

    with col_dist:
        st.markdown("##### Distribusi Return")
        fig_dist = go.Figure(go.Histogram(
            x=closed["pnl_pct"], nbinsx=30,
            marker_color="#00b0ff", opacity=0.75,
        ))
        fig_dist.add_vline(x=0, line_color="#5a7a9a", line_width=1)
        avg_v = closed["pnl_pct"].mean()
        fig_dist.add_vline(x=avg_v, line_color="#ffab00", line_dash="dash",
                            annotation_text=f"Avg {avg_v:+.1f}%",
                            annotation_font_color="#ffab00")
        fig_dist.update_layout(
            paper_bgcolor="#05080c", plot_bgcolor="#090d12",
            font=dict(color="#cdd8e6", family="IBM Plex Mono", size=11),
            margin=dict(l=0,r=0,t=10,b=0), height=300,
            xaxis=dict(title="Return (%)", gridcolor="#141e2e"),
            yaxis=dict(title="Count", gridcolor="#141e2e"),
        )
        st.plotly_chart(fig_dist, use_container_width=True)

st.markdown("---")

# ── SIGNAL TABLE (semua sinyal, termasuk loss)
st.markdown("##### Semua Sinyal — Lengkap dengan Loss (tidak ada cherry-pick)")

# Filter sidebar
col_f1, col_f2, col_f3 = st.columns(3)
with col_f1:
    filter_status = st.multiselect(
        "Status", ["WIN", "LOSS", "OPEN", "EXPIRED"],
        default=["WIN", "LOSS", "OPEN", "EXPIRED"]
    )
with col_f2:
    filter_ticker = st.text_input("Ticker", "").upper().strip()
with col_f3:
    filter_session = st.multiselect(
        "Sesi", ["PRE_MARKET", "MIDDAY", "POST_MARKET"],
        default=["PRE_MARKET", "MIDDAY", "POST_MARKET"]
    )

df_filtered = df.copy()
if filter_status:
    df_filtered = df_filtered[df_filtered["status"].isin(filter_status)]
if filter_ticker:
    df_filtered = df_filtered[df_filtered["ticker"].str.contains(filter_ticker)]
if filter_session:
    df_filtered = df_filtered[df_filtered["session"].isin(filter_session)]

# Display columns
display_cols = [
    "id", "timestamp_wib", "ticker", "signal_type", "session",
    "score", "entry_low", "tp_price", "sl_price", "tp_pct", "sl_pct",
    "wyckoff_phase", "vcp_grade", "status", "exit_price", "pnl_pct", "days_held"
]
df_show = df_filtered[[c for c in display_cols if c in df_filtered.columns]]

# Color-coded status
def style_status(val):
    colors = {"WIN":"color:#00e676;font-weight:bold",
              "LOSS":"color:#ff1744;font-weight:bold",
              "OPEN":"color:#ffab00",
              "EXPIRED":"color:#5a7a9a"}
    return colors.get(val, "")

st.dataframe(
    df_show,
    hide_index=True,
    use_container_width=True,
    column_config={
        "score"   : st.column_config.ProgressColumn("Score", min_value=0, max_value=100, format="%d"),
        "pnl_pct" : st.column_config.NumberColumn("P&L %", format="%+.2f%%"),
        "tp_pct"  : st.column_config.NumberColumn("TP %", format="+%.1f%%"),
        "sl_pct"  : st.column_config.NumberColumn("SL %", format="-%.1f%%"),
        "entry_low": st.column_config.NumberColumn("Entry", format="Rp %.0f"),
        "tp_price" : st.column_config.NumberColumn("TP", format="Rp %.0f"),
        "sl_price" : st.column_config.NumberColumn("SL", format="Rp %.0f"),
    }
)

st.markdown(f"""
<div style='font-size:10px;color:#2a3d52;font-family:"IBM Plex Mono",monospace;padding:8px 0;
            text-align:center'>
  Menampilkan {len(df_show)} dari {len(df)} total sinyal · 
  Database: signals.db · 
  Update: {datetime.now().strftime('%d %b %Y %H:%M WIB')}
</div>
""", unsafe_allow_html=True)

# ── FOOTER
st.markdown("---")
st.markdown("""
<div style='text-align:center;font-family:"IBM Plex Mono",monospace;font-size:10px;color:#2a3d52'>
Bandarmology PRO Signal System · Semua sinyal tercatat dengan timestamp immutable ·
Track record ini dapat diverifikasi siapapun · Tidak ada sinyal yang dihapus atau disembunyikan
</div>
""", unsafe_allow_html=True)
