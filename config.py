"""
BandarAI — Config v2
"""
import os

# ─── TELEGRAM ──────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "ISI_TOKEN_BOT_KAMU")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID",   "ISI_CHAT_ID_CHANNEL")
STOCKBIT_TOKEN     = os.environ.get("STOCKBIT_TOKEN", "")

# ─── PATHS ─────────────────────────────────────────────────────────────
SIGNALS_CSV = "data/signals.csv"

# ─── WATCHLIST CORE (15 saham) ─────────────────────────────────────────
WATCHLIST_CORE = [
    "MDKA", "ADRO", "PTBA", "ULTJ",
    "BBCA", "BBRI", "BMRI", "BBNI",
    "AMMN", "BYAN", "NCKL", "MBAP",
    "DCII", "TOWR", "INDF",
]

PROVEN_TICKERS = {"MDKA", "ADRO", "PTBA", "ULTJ"}

# ─── WATCHLIST EXTENDED ────────────────────────────────────────────────
WATCHLIST_EXTENDED = [
    "HRUM", "ITMG", "ANTM", "TINS", "DOID", "ESSA", "MBSS",
    "HEAL", "MYOR", "SIDO",
    "BSDE", "CTRA", "PWON",
    "AKRA", "SMGR", "INTP", "JSMR",
    "WTON", "AALI", "DSNG",
]

WATCHLIST = list(dict.fromkeys(WATCHLIST_CORE + WATCHLIST_EXTENDED))

TICKER_TIER = {}
for t in WATCHLIST_CORE:     TICKER_TIER[t] = 1
for t in WATCHLIST_EXTENDED: TICKER_TIER[t] = 2

# ─── SIGNAL THRESHOLDS (dilonggarkan untuk kondisi pasar sekarang) ─────
MIN_SCORE_TO_SIGNAL  = 58    # turun dari 65 → lebih banyak kandidat
MIN_SCORE_STRONG_BUY = 75
MAX_SIGNALS_PER_SESI = 3
MIN_PRICE_IDR        = 50
MIN_VOLUME_LOT       = 100_000

MIN_SCORE_PROVEN     = 55    # turun dari 62 → proven tickers lebih mudah lolos

# ─── TP/SL ─────────────────────────────────────────────────────────────
TP_MIN_PCT    = 4.0    # turun dari 5.0 → lebih realistis
SL_MAX_PCT    = 7.0
HOLD_MAX_DAYS = 20

# ─── POST-OPEN SETTINGS ────────────────────────────────────────────────
POST_OPEN_CORE_ONLY     = True
POST_OPEN_MIN_VOL_PACE  = 0.50   # turun dari 0.60 → lebih fleksibel
POST_OPEN_MAX_GAP_UP    = 5.0
POST_OPEN_MAX_GAP_DOWN  = 3.0
