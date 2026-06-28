"""
Config — baca dari environment variable (GitHub Actions)
atau dari nilai default (lokal).

Di GitHub Actions, semua nilai rahasia disimpan di Secrets.
Di lokal, isi langsung di bawah.
"""
import os

# ─── TELEGRAM ─────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "ISI_TOKEN_BOT_KAMU")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID",   "ISI_CHAT_ID_CHANNEL")

# ─── STOCKBIT (opsional) ──────────────────────────────────────────────
STOCKBIT_TOKEN = os.environ.get("STOCKBIT_TOKEN", "")

# ─── PATHS ────────────────────────────────────────────────────────────
SIGNALS_CSV = "data/signals.csv"   # File sinyal — disimpan di repo

# ─── WATCHLIST ────────────────────────────────────────────────────────
WATCHLIST = [
    "BBCA", "BBRI", "BMRI", "BBNI",
    "BREN", "BRPT", "TPIA", "CUAN",
    "ADRO", "ADMR", "MDKA", "BYAN", "PTBA",
    "AMMN", "MEDC", "PGAS",
    "KLBF", "ICBP", "ASII", "UNTR",
    "TLKM", "DCII", "TOWR",
    "GOTO", "BUKA",
    "SSIA", "CDIA", "PANI",
]

# ─── SIGNAL THRESHOLDS ────────────────────────────────────────────────
MIN_SCORE_TO_SIGNAL  = 65
MIN_SCORE_STRONG_BUY = 75
MAX_SIGNALS_PER_SESI = 5
MIN_PRICE_IDR        = 100
MIN_VOLUME_LOT       = 500_000

# ─── TARGETS ──────────────────────────────────────────────────────────
TP_MIN_PCT    = 3.0
SL_MAX_PCT    = 5.0
HOLD_MAX_DAYS = 20

# ─── DASHBOARD ────────────────────────────────────────────────────────
DASHBOARD_TITLE    = "Bandarmology PRO — Track Record Publik"
DASHBOARD_SUBTITLE = "Semua sinyal tercatat dengan timestamp. Tidak ada cherry-pick."
