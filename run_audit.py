"""
Entry point untuk GitHub Actions — auditor TP/SL.
Jalankan setiap 30 menit saat jam bursa.

Lokal: python3 run_audit.py
"""
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from database import get_open_signals, update_signal_outcome
from telegram_bot import (
    format_win_message, format_loss_message,
    format_expired_message, send_message
)
from config import HOLD_MAX_DAYS


def get_price(ticker: str) -> float | None:
    try:
        df = yf.download(ticker + ".JK", period="2d", interval="1d",
                         progress=False, auto_adjust=True)
        if df is None or df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        col = "Close" if "Close" in df.columns else "close"
        return float(df[col].dropna().iloc[-1])
    except:
        return None


def trading_days_since(ts: str) -> int:
    try:
        from_date = datetime.strptime(ts[:10], "%Y-%m-%d").date()
        today     = datetime.now().date()
        days = 0
        d = from_date
        while d < today:
            if d.weekday() < 5:
                days += 1
            d += timedelta(days=1)
        return days
    except:
        return 0


def main():
    print(f"\n{'='*50}")
    print(f"BANDARMOLOGY PRO — TP/SL Auditor")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*50}")

    open_sigs = get_open_signals()
    if not open_sigs:
        print("ℹ️  Tidak ada sinyal OPEN.")
        return

    print(f"Auditing {len(open_sigs)} open signal(s)...\n")
    wins = losses = expired = 0

    for sig in open_sigs:
        ticker    = sig["ticker"]
        tp        = float(sig["tp_price"])
        sl        = float(sig["sl_price"])
        entry     = float(sig["entry_low"])
        sig_id    = sig["id"]
        days_held = trading_days_since(sig["timestamp_wib"])

        price = get_price(ticker)
        if price is None:
            print(f"  ⚠️  {ticker}: harga tidak tersedia")
            continue

        pnl = (price - entry) / entry * 100
        print(f"  {ticker}: Rp{price:,.0f} | P&L {pnl:+.1f}% | {days_held}d")

        if price >= tp:
            pnl_win = round((tp - entry) / entry * 100, 2)
            update_signal_outcome(sig_id, "WIN", tp, pnl_win, days_held, "TP hit")
            send_message(format_win_message(sig, tp, pnl_win, days_held))
            print(f"    ✅ WIN +{pnl_win:.1f}%")
            wins += 1

        elif price <= sl:
            pnl_loss = round((sl - entry) / entry * 100, 2)
            update_signal_outcome(sig_id, "LOSS", sl, pnl_loss, days_held, "SL hit")
            send_message(format_loss_message(sig, sl, pnl_loss, days_held))
            print(f"    ❌ LOSS {pnl_loss:.1f}%")
            losses += 1

        elif days_held >= HOLD_MAX_DAYS:
            update_signal_outcome(sig_id, "EXPIRED", price,
                                  round(pnl, 2), days_held,
                                  f"Expired {days_held} hari")
            send_message(format_expired_message(sig, price, pnl))
            print(f"    ⏰ EXPIRED {pnl:+.1f}%")
            expired += 1

    print(f"\n✅ Audit selesai: {wins}W / {losses}L / {expired} expired")


if __name__ == "__main__":
    main()
