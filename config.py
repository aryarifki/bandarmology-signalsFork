"""
BandarAI — Config v2
Perubahan: WATCHLIST_CORE (15 saham proven), PROVEN_TICKERS, post-open settings
"""
import os

# ─── TELEGRAM ──────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "ISI_TOKEN_BOT_KAMU")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID",   "ISI_CHAT_ID_CHANNEL")
STOCKBIT_TOKEN     = os.environ.get("STOCKBIT_TOKEN", "")

# ─── PATHS ─────────────────────────────────────────────────────────────
SIGNALS_CSV = "data/signals.csv"

# ─── WATCHLIST CORE (15 saham) ─────────────────────────────────────────
# Diprioritaskan di semua sesi. POST_OPEN hanya scan saham ini.
# Dipilih berdasarkan: backtest WR, likuiditas, kesesuaian Wyckoff CMF.
WATCHLIST_CORE = [
    # Proven dari backtest (WR >40%)
    "MDKA", "ADRO", "PTBA", "ULTJ",
    # Banking liquid (dengan v3 gates, Phase B lebih terfilter)
    "BBCA", "BBRI", "BMRI", "BBNI",
    # Mining/energi momentum
    "AMMN", "BYAN", "NCKL", "MBAP",
    # Growth/infrastruktur
    "DCII", "TOWR",
    # Consumer solid
    "INDF",
]

# Saham yang sudah terbukti bagus dari backtest — threshold lebih rendah
PROVEN_TICKERS = {"MDKA", "ADRO", "PTBA", "ULTJ"}

# ─── WATCHLIST EXTENDED (scan setelah CORE jika belum dapat 3 sinyal) ──
WATCHLIST_EXTENDED = [
    # Tambang mid-cap
    "HRUM", "ITMG", "ANTM", "TINS", "DOID", "ESSA", "MBSS",
    # Healthcare
    "HEAL",
    # Consumer mid
    "MYOR", "SIDO",
    # Properti
    "BSDE", "CTRA", "PWON",
    # Lain-lain liquid
    "AKRA", "SMGR", "INTP", "JSMR",
    # Small-mid
    "WTON", "AALI", "DSNG",
]

# Gabungan semua (CORE dulu, baru EXTENDED)
WATCHLIST = list(dict.fromkeys(WATCHLIST_CORE + WATCHLIST_EXTENDED))

# Tier mapping untuk volume filter
TICKER_TIER = {}
for t in WATCHLIST_CORE:     TICKER_TIER[t] = 1
for t in WATCHLIST_EXTENDED: TICKER_TIER[t] = 2

# ─── SIGNAL THRESHOLDS ─────────────────────────────────────────────────
MIN_SCORE_TO_SIGNAL  = 65
MIN_SCORE_STRONG_BUY = 78
MAX_SIGNALS_PER_SESI = 3     # Kualitas > kuantitas
MIN_PRICE_IDR        = 50
MIN_VOLUME_LOT       = 100_000

# Threshold lebih rendah untuk proven tickers
MIN_SCORE_PROVEN     = 62

# ─── TP/SL ─────────────────────────────────────────────────────────────
TP_MIN_PCT    = 5.0    # minimum 5% untuk worthwhile
SL_MAX_PCT    = 7.0    # maximum 7% stop loss
HOLD_MAX_DAYS = 20

# ─── POST-OPEN SCAN SETTINGS ───────────────────────────────────────────
# Scan ke-4 per hari di jam 10:00 WIB setelah konfirmasi intraday
POST_OPEN_CORE_ONLY    = True   # POST_OPEN hanya scan WATCHLIST_CORE
POST_OPEN_MIN_VOL_PACE = 0.60   # Volume harus minimal 60% dari ekspektasi
POST_OPEN_MAX_GAP_UP   = 5.0    # Gap up > 5% = exhaustion risk, skip
POST_OPEN_MAX_GAP_DOWN = 3.0    # Gap down > 3% = breakdown, skip
