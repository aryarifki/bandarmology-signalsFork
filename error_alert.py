"""
BandarAI — Error Alert System
Kirim notifikasi ke Telegram kalau ada error di GitHub Actions.
Kamu tahu sebelum subscriber tahu.
"""
import os
import traceback
import requests
from datetime import datetime
from functools import wraps


def send_error_alert(error: Exception, context: str = "", extra: str = ""):
    """
    Kirim pesan error ke Telegram admin.
    Dipanggil dari try/except di run_scan.py dan run_audit.py.
    """
    token   = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")

    if not token or not chat_id or token in ("dummy", "ISI_TOKEN_BOT_KAMU"):
        print(f"[ERROR ALERT - no token] {context}: {error}")
        return

    # GitHub Actions metadata
    repo   = os.environ.get("GITHUB_REPOSITORY", "")
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    sha    = os.environ.get("GITHUB_SHA", "")[:7]
    ref    = os.environ.get("GITHUB_REF_NAME", "main")

    run_url = (
        f"https://github.com/{repo}/actions/runs/{run_id}"
        if repo and run_id else ""
    )

    # Traceback singkat (5 baris terakhir)
    tb_full  = traceback.format_exc()
    tb_lines = [l for l in tb_full.strip().splitlines() if l.strip()]
    tb_short = "\n".join(tb_lines[-5:]) if tb_lines else str(error)

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    msg = (
        f"🚨 <b>SYSTEM ERROR — BandarAI</b>\n\n"
        f"⏰ <b>Waktu:</b> {ts} WIB\n"
        f"📄 <b>Script:</b> <code>{context}</code>\n"
        f"❌ <b>Error:</b> <code>{str(error)[:300]}</code>\n"
    )

    if extra:
        msg += f"ℹ️ <b>Detail:</b> {extra[:200]}\n"

    msg += f"\n<pre>{tb_short[:800]}</pre>"

    if run_url:
        msg += f'\n\n🔗 <a href="{run_url}">Lihat log GitHub Actions</a>'
    if sha:
        msg += f"\n📌 Commit: <code>{sha}</code> ({ref})"

    msg += "\n\n⚠️ <i>Sinyal hari ini mungkin tidak terkirim. Cek segera.</i>"

    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id"                : chat_id,
                "text"                   : msg,
                "parse_mode"             : "HTML",
                "disable_web_page_preview": True,
            },
            timeout=15,
        )
        if resp.status_code == 200:
            print(f"✅ Error alert terkirim ke Telegram")
        else:
            print(f"⚠️  Error alert gagal: {resp.status_code} {resp.text[:200]}")
    except Exception as tg_err:
        print(f"⚠️  Tidak bisa kirim error alert: {tg_err}")


def send_warning(message: str, context: str = ""):
    """Kirim warning (bukan error) — misalnya saham tidak bisa di-load."""
    token   = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id or token in ("dummy", "ISI_TOKEN_BOT_KAMU"):
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id"   : chat_id,
                "text"      : f"⚠️ <b>WARNING — BandarAI</b>\n{context}\n{message[:400]}",
                "parse_mode": "HTML",
            },
            timeout=10,
        )
    except Exception:
        pass


def alert_on_error(context: str):
    """
    Decorator — wrap fungsi apapun dengan error alert otomatis.

    Contoh:
        @alert_on_error("run_scan.py PRE_MARKET")
        def main():
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                send_error_alert(e, context=context)
                raise
        return wrapper
    return decorator
