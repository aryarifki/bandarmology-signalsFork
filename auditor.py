"""
Auditor — cek setiap 10 menit apakah TP atau SL sinyal terbuka sudah tercapai.
Juga handle sinyal yang expired setelah 20 hari trading.
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from database import get_open_signals, update_signal_outcome, log_audit
from telegram_bot import (
    format_win_message, format_loss_message,
    format_expired_message, send_message
)
from config import HOLD_MAX_DAYS


def get_current_price(ticker: str) -> float | None:
    """Ambil harga terakhir dari Yahoo Finance."""
    try:
        df = yf.download(ticker + ".JK", period="1d", interval="1m",
                         progress=False, auto_adjust=True)
        if df is None or df.empty:
            # Fallback ke daily
            df = yf.download(ticker + ".JK", period="5d", interval="1d",
                             progress=False, auto_adjust=True)
        if df is None or df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        close_col = "Close" if "Close" in df.columns else "close"
        return float(df[close_col].dropna().iloc[-1])
    except:
        return None


def count_trading_days(from_ts: str) -> int:
    """Hitung jumlah hari trading sejak sinyal dibuat."""
    try:
        from_date = datetime.strptime(from_ts[:10], "%Y-%m-%d").date()
        today     = datetime.now().date()
        trading_days = 0
        current = from_date
        while current < today:
            if current.weekday() < 5:   # Senin–Jumat
                trading_days += 1
            current += timedelta(days=1)
        return trading_days
    except:
        return 0


def is_market_hours() -> bool:
    """True jika sekarang jam bursa IDX (WIB)."""
    now = datetime.utcnow() + timedelta(hours=7)
    if now.weekday() >= 5:
        return False
    t = now.time()
    from datetime import time as T
    return T(9, 0) <= t <= T(11, 35) or T(13, 30) <= t <= T(16, 35)


def audit_all_open_signals() -> dict:
    """
    Audit semua sinyal OPEN.
    Returns summary dict dengan counts.
    """
    if not is_market_hours():
        print(f"  ℹ️  Audit skip — di luar jam bursa ({datetime.now().strftime('%H:%M WIB')})")
        return {"checked": 0, "wins": 0, "losses": 0, "expired": 0}

    open_sigs = get_open_signals()
    if not open_sigs:
        print("  ℹ️  Tidak ada sinyal OPEN untuk diaudit")
        return {"checked": 0, "wins": 0, "losses": 0, "expired": 0}

    print(f"\n🔍 Auditing {len(open_sigs)} open signal(s) — {datetime.now().strftime('%H:%M:%S WIB')}")
    summary = {"checked": 0, "wins": 0, "losses": 0, "expired": 0}

    for sig in open_sigs:
        ticker    = sig["ticker"]
        tp_price  = sig["tp_price"]
        sl_price  = sig["sl_price"]
        entry     = sig["entry_low"]
        sig_id    = sig["id"]
        ts_open   = sig["timestamp_wib"]
        days_held = count_trading_days(ts_open)

        current_price = get_current_price(ticker)
        if current_price is None:
            print(f"  ⚠️  {ticker}: harga tidak tersedia")
            continue

        summary["checked"] += 1
        log_audit(sig_id, current_price, "CHECKED")
        pnl_pct = (current_price - entry) / entry * 100

        print(f"  📊 {ticker}: price={current_price:,.0f} | TP={tp_price:,.0f} | SL={sl_price:,.0f} | P&L={pnl_pct:+.1f}% | {days_held}d")

        # ── WIN: harga menyentuh TP
        if current_price >= tp_price:
            ok = update_signal_outcome(
                sig_id, "WIN", current_price,
                round((tp_price - entry) / entry * 100, 2),
                days_held, notes="TP hit"
            )
            if ok:
                summary["wins"] += 1
                msg = format_win_message(sig, tp_price,
                                          round((tp_price - entry) / entry * 100, 2),
                                          days_held)
                send_message(msg)
                print(f"  ✅ WIN — {ticker} +{(tp_price-entry)/entry*100:.1f}%")

        # ── LOSS: harga menyentuh SL
        elif current_price <= sl_price:
            ok = update_signal_outcome(
                sig_id, "LOSS", current_price,
                round((sl_price - entry) / entry * 100, 2),
                days_held, notes="SL hit"
            )
            if ok:
                summary["losses"] += 1
                msg = format_loss_message(sig, sl_price,
                                           round((sl_price - entry) / entry * 100, 2),
                                           days_held)
                send_message(msg)
                print(f"  ❌ LOSS — {ticker} {(sl_price-entry)/entry*100:.1f}%")

        # ── EXPIRED: lebih dari HOLD_MAX_DAYS tanpa hit TP/SL
        elif days_held >= HOLD_MAX_DAYS:
            ok = update_signal_outcome(
                sig_id, "EXPIRED", current_price,
                round(pnl_pct, 2),
                days_held,
                notes=f"Expired setelah {days_held} hari trading"
            )
            if ok:
                summary["expired"] += 1
                msg = format_expired_message(sig, current_price, pnl_pct)
                send_message(msg)
                print(f"  ⏰ EXPIRED — {ticker} {pnl_pct:+.1f}%")

    total_closed = summary["wins"] + summary["losses"] + summary["expired"]
    if total_closed > 0:
        print(f"  📊 Audit selesai: {summary['wins']}W / {summary['losses']}L / {summary['expired']} expired")

    return summary
