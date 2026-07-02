"""
BandarAI — Signal Scanner Entry Point (GitHub Actions)
Error alert otomatis ke Telegram kalau ada yang gagal.
"""
import os
import sys

SESSION = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("SESSION", "PRE_MARKET")

print(f"\n{'='*55}")
print(f"BandarAI Signal Scanner — {SESSION}")
print(f"{'='*55}")

from error_alert import send_error_alert, send_warning
from scanner import scan_once, prepare_signal_record
from database import save_signal, get_stats
from telegram_bot import format_signal_message, send_message, send_daily_summary
import config  # noqa — pastikan config tersedia di semua modul


def main():
    session_labels = {
        "PRE_MARKET" : "☀️ Pre-Market (08:30 WIB)",
        "MIDDAY"     : "🕐 Midday (13:00 WIB)",
        "POST_MARKET": "🌙 Post-Market (16:30 WIB)",
    }

    try:
        signals = scan_once(SESSION)
    except Exception as e:
        send_error_alert(
            e,
            context=f"scan_once() — {SESSION}",
            extra="Scanner gagal total. Tidak ada sinyal yang dikirim hari ini."
        )
        # Kirim notif ke channel bahwa sistem bermasalah
        send_message(
            f"⚠️ <b>Sistem Error — {session_labels.get(SESSION, SESSION)}</b>\n\n"
            f"Scanner mengalami error teknis hari ini. Tim sedang investigasi.\n"
            f"<i>Sinyal akan kembali normal setelah diperbaiki.</i>"
        )
        raise

    if not signals:
        print("ℹ️  Tidak ada sinyal hari ini.")
        # Ambil diagnosa dari scanner agar pesan Telegram informatif
        import scanner as _sc
        diag = getattr(_sc, "LAST_SCAN_DIAG", {}) or {}
        msg = (f"📊 <b>{session_labels.get(SESSION, SESSION)}</b>\n\n"
               f"ℹ️ <i>Tidak ada saham yang lolos semua kriteria.</i>\n")
        if diag.get("regime"):
            msg += f"\n🌏 Regime: <b>{diag['regime']}</b>"
        near = diag.get("near") or []
        if near:
            msg += "\n\n📈 <b>Terdekat dengan threshold:</b>"
            for tk, sc_, th in near:
                msg += f"\n  • {tk}: {sc_}/100 (butuh {th})"
        bt = diag.get("blocked_top") or []
        if bt:
            msg += "\n\n⛔ <b>Contoh yang diblok gate:</b>"
            for b in bt:
                msg += f"\n  • {b[:70]}"
        if diag.get("n_cooldown"):
            msg += f"\n\n⏱️ Cooldown: {diag['n_cooldown']} ticker"
        send_message(msg)
        return

    sent = 0
    errors = []
    for r in signals:
        try:
            record = prepare_signal_record(r)
            saved  = save_signal(record)
            if not saved:
                print(f"  ⚠️  Duplicate: {record['id']}")
                continue
            msg = format_signal_message(record)
            send_message(msg)
            sent += 1
            print(f"  ✅ Sent: {record['id']} score={record['score']}")
        except Exception as e:
            ticker = r.get("ticker", "?")
            errors.append(f"{ticker}: {e}")
            print(f"  ❌ Error sending {ticker}: {e}")

    print(f"\n✅ Done — {sent} sinyal dikirim")

    if errors:
        send_warning(
            "\n".join(errors),
            context=f"Partial error saat kirim sinyal ({SESSION})"
        )

    # Daily summary di sesi terakhir
    if SESSION == "POST_MARKET":
        try:
            stats = get_stats()
            if stats.get("total_closed", 0) > 0:
                send_daily_summary(stats)
        except Exception as e:
            print(f"⚠️  Daily summary error: {e}")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        # Catch-all kalau main() sendiri crash sebelum try/except di dalamnya
        send_error_alert(e, context=f"run_scan.py main() — {SESSION}")
        sys.exit(1)
