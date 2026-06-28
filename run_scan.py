"""
Entry point untuk GitHub Actions — scanner.
Jalankan oleh workflow otomatis 3x sehari.

Lokal pun bisa: python3 run_scan.py PRE_MARKET
"""
import os
import sys

# Session dari argument atau environment
SESSION = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("SESSION", "PRE_MARKET")
print(f"\n{'='*50}")
print(f"BANDARMOLOGY PRO — Signal Scanner")
print(f"Session: {SESSION}")
print(f"{'='*50}")

# Import setelah env sudah siap
from scanner import scan_once, prepare_signal_record
from database import save_signal, get_stats
from telegram_bot import format_signal_message, send_message, send_daily_summary

def main():
    signals = scan_once(SESSION)

    if not signals:
        print("ℹ️  Tidak ada sinyal hari ini.")
        # Tetap kirim notif ke Telegram kalau tidak ada sinyal
        session_labels = {
            "PRE_MARKET" : "☀️ Pre-Market (08:30 WIB)",
            "MIDDAY"     : "🕐 Midday (13:00 WIB)",
            "POST_MARKET": "🌙 Post-Market (16:30 WIB)",
        }
        send_message(
            f"📊 <b>{session_labels.get(SESSION, SESSION)}</b>\n\n"
            f"ℹ️ <i>Tidak ada sinyal yang memenuhi threshold hari ini. "
            f"Score semua saham di bawah 65/100.</i>"
        )
        return

    sent = 0
    for r in signals:
        record = prepare_signal_record(r)
        saved  = save_signal(record)
        if not saved:
            print(f"  ⚠️  Duplicate skip: {record['id']}")
            continue
        # Kirim ke Telegram
        msg = format_signal_message(record)
        send_message(msg)
        sent += 1
        print(f"  ✅ Sent: {record['id']}")

    print(f"\n✅ Done — {sent} sinyal dikirim")

    # Kalau ini sesi post-market, kirim daily summary juga
    if SESSION == "POST_MARKET":
        stats = get_stats()
        if stats["total_closed"] > 0:
            send_daily_summary(stats)

if __name__ == "__main__":
    main()
