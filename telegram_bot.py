"""
Telegram delivery — kirim sinyal dan notifikasi WIN/LOSS ke channel.
Semua pesan menggunakan format yang konsisten dan profesional.
"""

import requests
from datetime import datetime
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID


BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


def send_message(text: str, parse_mode: str = "HTML",
                 disable_web_page_preview: bool = True) -> int | None:
    """
    Kirim pesan ke Telegram channel.
    Returns message_id jika berhasil, None jika gagal.
    """
    url = f"{BASE_URL}/sendMessage"
    payload = {
        "chat_id"                  : TELEGRAM_CHAT_ID,
        "text"                     : text,
        "parse_mode"               : parse_mode,
        "disable_web_page_preview" : disable_web_page_preview,
    }
    try:
        r = requests.post(url, json=payload, timeout=15)
        data = r.json()
        if data.get("ok"):
            msg_id = data["result"]["message_id"]
            print(f"  📤 Telegram sent — msg_id: {msg_id}")
            return msg_id
        else:
            print(f"  ❌ Telegram error: {data.get('description')}")
            return None
    except Exception as e:
        print(f"  ❌ Telegram exception: {e}")
        return None


def format_signal_message(sig: dict) -> str:
    """Format pesan sinyal BUY untuk Telegram."""
    session_labels = {
        "PRE_MARKET" : "☀️ Pre-Market Signal  |  08:30 WIB",
        "MIDDAY"     : "🕐 Midday Signal  |  13:00 WIB",
        "POST_MARKET": "🌙 Post-Market Watchlist  |  16:30 WIB",
    }
    session_label = session_labels.get(sig.get("session", ""), "📊 Signal")

    signal_type = sig.get("signal_type", "BUY")
    emoji = "🔥" if signal_type == "STRONG_BUY" else "🟢"
    label = "STRONG BUY" if signal_type == "STRONG_BUY" else "BUY"

    score      = sig.get("score", 0)
    ticker     = sig.get("ticker", "—")
    entry_low  = sig.get("entry_low", 0)
    entry_high = sig.get("entry_high", 0)
    tp         = sig.get("tp_price", 0)
    sl         = sig.get("sl_price", 0)
    tp_pct     = sig.get("tp_pct", 0)
    sl_pct     = sig.get("sl_pct", 0)
    wp         = sig.get("wyckoff_phase", "—")
    cmf_v      = sig.get("cmf_value", 0)
    obv_d      = sig.get("obv_direction", "—")
    vcp        = sig.get("vcp_grade", "NONE")
    rs         = sig.get("rs_interp", "—")
    cross      = sig.get("broker_crossing", "—")
    rationale  = sig.get("rationale", "—")
    sig_id     = sig.get("id", "—")
    ts         = sig.get("timestamp_wib", datetime.now().strftime("%Y-%m-%d %H:%M"))

    # VCP display
    vcp_line = ""
    if vcp in ("A", "B"):
        vcp_line = f"\n📐 <b>VCP Grade {vcp}</b> {'⭐ PREMIUM SETUP' if vcp == 'A' else ''}"

    # Broker crossing
    cross_line = ""
    if cross and cross not in ("—", "None", None, "NO REAL DATA"):
        cross_icon = "🔥" if "ACC" in str(cross) else "💀"
        cross_line = f"\n{cross_icon} <b>Broker: {cross}</b>"

    # Score grade
    if score >= 80:   grade = "S ⭐"
    elif score >= 65: grade = "A"
    elif score >= 50: grade = "B"
    else:             grade = "C"

    msg = f"""<b>{emoji} {label} — ${ticker}</b>
{session_label}

💰 <b>Entry</b>: Rp {entry_low:,.0f} – {entry_high:,.0f}
🎯 <b>Take Profit</b>: Rp {tp:,.0f}  <code>(+{tp_pct:.1f}%)</code>
🛑 <b>Stop Loss</b>: Rp {sl:,.0f}  <code>(-{sl_pct:.1f}%)</code>

📊 <b>Score</b>: {score}/100  |  Grade {grade}
📈 <b>Wyckoff</b>: {wp}
💧 <b>CMF</b>: {cmf_v:+.4f}
📉 <b>OBV</b>: {obv_d}
🌏 <b>RS vs IHSG</b>: {rs}{vcp_line}{cross_line}

💡 <i>{rationale}</i>

🔖 <code>{sig_id}</code>
🕐 {ts} WIB

⚠️ <i>Bukan nasihat investasi. Selalu gunakan SL.</i>"""

    return msg


def format_win_message(sig: dict, exit_price: float,
                        pnl_pct: float, days_held: int) -> str:
    """Format notifikasi WIN."""
    ticker  = sig.get("ticker", "—")
    sig_id  = sig.get("id", "—")
    tp      = sig.get("tp_price", 0)
    entry   = sig.get("entry_low", 0)

    msg = f"""✅ <b>WIN — {ticker}</b>

Entry: Rp {entry:,.0f}
TP Hit: Rp {exit_price:,.0f}
<b>Profit: <code>+{pnl_pct:.1f}%</code></b>
Durasi: {days_held} hari trading

🔖 <code>{sig_id}</code>

📊 <i>Track record diperbarui otomatis.</i>"""
    return msg


def format_loss_message(sig: dict, exit_price: float,
                         pnl_pct: float, days_held: int) -> str:
    """Format notifikasi LOSS — ditampilkan transparan, tidak disembunyikan."""
    ticker = sig.get("ticker", "—")
    sig_id = sig.get("id", "—")
    sl     = sig.get("sl_price", 0)
    entry  = sig.get("entry_low", 0)

    msg = f"""❌ <b>LOSS — {ticker}</b>

Entry: Rp {entry:,.0f}
SL Hit: Rp {exit_price:,.0f}
<b>Loss: <code>{pnl_pct:.1f}%</code></b>
Durasi: {days_held} hari trading

🔖 <code>{sig_id}</code>

📊 <i>Transparansi penuh — semua hasil dicatat, termasuk loss.</i>"""
    return msg


def format_expired_message(sig: dict, exit_price: float, pnl_pct: float) -> str:
    """Format notifikasi sinyal expired (20 hari tanpa hit TP/SL)."""
    ticker = sig.get("ticker", "—")
    sig_id = sig.get("id", "—")
    entry  = sig.get("entry_low", 0)

    emoji = "📈" if pnl_pct >= 0 else "📉"
    msg = f"""{emoji} <b>EXPIRED — {ticker}</b>

Entry: Rp {entry:,.0f}
Harga saat expired: Rp {exit_price:,.0f}
P&L saat expired: <code>{pnl_pct:+.1f}%</code>
Status: <i>TP/SL tidak tercapai dalam 20 hari</i>

🔖 <code>{sig_id}</code>"""
    return msg


def send_daily_summary(stats: dict) -> None:
    """Kirim ringkasan harian setiap hari setelah market tutup."""
    total   = stats.get("total", 0)
    wins    = stats.get("wins", 0)
    losses  = stats.get("losses", 0)
    wr      = stats.get("win_rate", 0)
    avg_pnl = stats.get("avg_pnl") or 0
    avg_win = stats.get("avg_win") or 0
    avg_loss= stats.get("avg_loss") or 0
    best    = stats.get("best_trade") or 0
    worst   = stats.get("worst_trade") or 0
    open_c  = stats.get("open_count", 0)

    wr_emoji = "🟢" if wr >= 60 else "🟡" if wr >= 50 else "🔴"
    date_str = datetime.now().strftime("%d %b %Y")

    msg = f"""📊 <b>DAILY TRACK RECORD — {date_str}</b>

{wr_emoji} <b>Win Rate: {wr:.1f}%</b>  ({wins}W / {losses}L)
📈 Avg Return: <code>{avg_pnl:+.2f}%</code>
✅ Avg Win: <code>+{avg_win:.1f}%</code>
❌ Avg Loss: <code>{avg_loss:.1f}%</code>
🏆 Best Trade: <code>+{best:.1f}%</code>
💔 Worst Trade: <code>{worst:.1f}%</code>

📋 Total sinyal: {total}  |  Open: {open_c}

<i>Semua hasil tercatat dengan timestamp. Tidak ada cherry-pick.</i>"""

    send_message(msg)


def test_connection() -> bool:
    """Test apakah bot token dan chat ID valid."""
    url = f"{BASE_URL}/getMe"
    try:
        r = requests.get(url, timeout=10)
        data = r.json()
        if data.get("ok"):
            bot_name = data["result"]["username"]
            print(f"✅ Telegram OK — bot: @{bot_name}")
            # Test send
            msg_id = send_message(
                "✅ <b>Bandarmology PRO Signal System</b> — Koneksi berhasil! "
                "Bot siap mengirim sinyal.",
            )
            return msg_id is not None
        else:
            print(f"❌ Token tidak valid: {data.get('description')}")
            return False
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False
