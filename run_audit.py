"""
BandarAI — TP/SL Auditor Entry Point (GitHub Actions)
Error alert otomatis ke Telegram kalau audit gagal.
"""
import os
import sys

print(f"\n{'='*55}")
print(f"BandarAI TP/SL Auditor")
print(f"{'='*55}")

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from error_alert import send_error_alert, send_warning
from database import get_open_signals, update_signal_outcome
from telegram_bot import (
    format_win_message, format_loss_message,
    format_expired_message, send_message
)
from config import HOLD_MAX_DAYS


def get_price(ticker: str):
    try:
        df = yf.download(
            ticker + ".JK", period="2d", interval="1d",
            progress=False, auto_adjust=True
        )
        if df is None or df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        col = "Close" if "Close" in df.columns else "close"
        return float(df[col].dropna().iloc[-1])
    except Exception:
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
    except Exception:
        return 0


def main():
    try:
        open_sigs = get_open_signals()
    except Exception as e:
        send_error_alert(e, context="run_audit.py — get_open_signals()")
        raise

    if not open_sigs:
        print("ℹ️  Tidak ada sinyal OPEN.")
        return

    print(f"Auditing {len(open_sigs)} sinyal...\n")
    wins = losses = expired = errors = 0
    price_errors = []

    for sig in open_sigs:
        ticker    = sig.get("ticker", "?")
        sig_id    = sig.get("id", "?")
        days_held = trading_days_since(sig.get("timestamp_wib", ""))

        try:
            tp    = float(sig.get("tp_price", 0))
            sl    = float(sig.get("sl_price", 0))
            entry = float(sig.get("entry_low", 0))
        except (ValueError, TypeError) as e:
            print(f"  ⚠️  {ticker}: data tidak valid — {e}")
            errors += 1
            continue

        price = get_price(ticker)

        if price is None:
            print(f"  ⚠️  {ticker}: harga tidak tersedia")
            price_errors.append(ticker)
            continue

        pnl = (price - entry) / entry * 100 if entry > 0 else 0
        print(f"  {ticker}: Rp{price:,.0f} | P&L {pnl:+.1f}% | {days_held}d")

        try:
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
                update_signal_outcome(
                    sig_id, "EXPIRED", price,
                    round(pnl, 2), days_held,
                    f"Expired {days_held} hari"
                )
                send_message(format_expired_message(sig, price, pnl))
                print(f"    ⏰ EXPIRED {pnl:+.1f}%")
                expired += 1

        except Exception as e:
            print(f"  ❌ {ticker}: update error — {e}")
            errors += 1

    print(f"\n✅ Audit: {wins}W / {losses}L / {expired} expired / {errors} errors")

    # Alert kalau banyak error
    if len(price_errors) >= 5:
        send_warning(
            f"Tidak bisa fetch harga untuk: {', '.join(price_errors[:10])}",
            context="Audit TP/SL — kemungkinan Yahoo Finance down"
        )

    if errors >= 3:
        send_warning(
            f"{errors} error saat audit. Cek log GitHub Actions.",
            context="run_audit.py"
        )


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        send_error_alert(e, context="run_audit.py main()")
        sys.exit(1)
