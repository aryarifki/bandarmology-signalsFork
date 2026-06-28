"""
BandarAI — Config
Watchlist diperluas ke 80+ saham dalam 3 tier.
Scanner memproses semua tier, difilter oleh volume + goreng filter + score.
"""
import os

# ─── TELEGRAM ─────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "ISI_TOKEN_BOT_KAMU")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID",   "ISI_CHAT_ID_CHANNEL")

# ─── STOCKBIT (opsional) ──────────────────────────────────────────────
STOCKBIT_TOKEN = os.environ.get("STOCKBIT_TOKEN", "")

# ─── PATHS ────────────────────────────────────────────────────────────
SIGNALS_CSV = "data/signals.csv"

# ─── WATCHLIST ────────────────────────────────────────────────────────
# Tier 1: Blue chip & LQ45 core — liquid, data lengkap di Yahoo Finance
WATCHLIST_T1 = [
    # Perbankan
    "BBCA", "BBRI", "BMRI", "BBNI", "BJTM", "BJBR",
    # Energi & tambang besar
    "BREN", "BRPT", "TPIA", "CUAN", "ADRO", "ADMR",
    "MDKA", "BYAN", "PTBA", "AMMN", "MEDC", "PGAS",
    # Consumer & farmasi
    "KLBF", "ICBP", "INDF", "MYOR", "SIDO", "ULTJ",
    # Infrastruktur & manufaktur
    "ASII", "UNTR", "JSMR", "AKRA", "SMGR", "INTP",
    # Telco & tech
    "TLKM", "DCII", "TOWR", "GOTO", "BUKA",
    # Properti & konstruksi
    "SSIA", "CDIA", "PANI", "BSDE", "CTRA", "PWON",
]

# Tier 2: Mid cap — potensi return lebih tinggi, perlu volume filter lebih ketat
WATCHLIST_T2 = [
    # Tambang mid-cap
    "NCKL", "NICL", "MBAP", "HRUM", "ITMG", "ANTM", "TINS",
    "INDY", "DOID", "ABMM", "MBSS", "ESSA",
    # Healthcare
    "MIKA", "HEAL", "KAEF", "PYFA",
    # Consumer & retail
    "MAPA", "ACES", "RALS", "LPPF", "ERAA", "MTDL",
    # Media & telco mid
    "MNCN", "SCMA", "EMTK",
    # Properti mid
    "SMRA", "LPKR", "BEST", "WTON",
    # Agrikultur
    "AALI", "SIMP", "PALM", "DSNG",
    # Lain-lain
    "WSKT", "WIKA", "PTPP",
]

# Tier 3: Small-mid cap dengan return potential tinggi
# Volume filter lebih ketat (MIN_VOLUME_LOT_T3)
WATCHLIST_T3 = [
    # Energi baru & nikel
    "NCKL", "WIFI", "RAJA", "ENRG", "RATU",
    # Tech & digital
    "WIRG", "FILM", "MLPL",
    # Tambang kecil
    "PTRO", "HRTA", "BRMS", "STAA",
    # Consumer small
    "MIDI", "HERO", "MCAS",
    # Properti small
    "TOPS", "BKSL",
    # Manufaktur small
    "SMIL", "VKTR", "IMPC",
]

# Semua tier digabung — scanner proses semuanya
# Volume filter per tier yang menentukan lolos atau tidak
WATCHLIST = list(dict.fromkeys(WATCHLIST_T1 + WATCHLIST_T2 + WATCHLIST_T3))

# Tier mapping untuk volume filter berbeda
TICKER_TIER = {}
for t in WATCHLIST_T1: TICKER_TIER[t] = 1
for t in WATCHLIST_T2: TICKER_TIER[t] = 2
for t in WATCHLIST_T3: TICKER_TIER[t] = 3

# ─── VOLUME THRESHOLD PER TIER ────────────────────────────────────────
# Tier 1: minimal 500k lot/hari (liquid)
# Tier 2: minimal 200k lot/hari
# Tier 3: minimal 100k lot/hari (small cap boleh kurang liquid)
MIN_VOLUME_LOT_BY_TIER = {
    1: 500_000,
    2: 200_000,
    3: 100_000,
}
MIN_VOLUME_LOT = 100_000  # default fallback

# ─── SIGNAL THRESHOLDS ────────────────────────────────────────────────
MIN_SCORE_TO_SIGNAL = 65
MIN_SCORE_STRONG_BUY = 75
MAX_SIGNALS_PER_SESI = 5     # maksimum 5 sinyal per sesi
MIN_PRICE_IDR = 50    # turunkan ke 50 agar small cap bisa masuk

# ─── TARGETS ──────────────────────────────────────────────────────────
TP_MIN_PCT = 5.0    # naikkan ke 5% untuk small cap (return lebih tinggi)
SL_MAX_PCT = 7.0    # naikkan ke 7% untuk small cap (volatilitas lebih tinggi)
HOLD_MAX_DAYS = 20

# ─── GORENG FILTER (lebih ketat untuk small cap) ──────────────────────
# Pump threshold per tier — T3 lebih ketat karena prone goreng
PUMP_PCT_BY_TIER = {
    1: 10.0,   # Blue chip: pump >10% dalam 3 hari = suspicious
    2:  8.0,   # Mid cap: pump >8%
    3:  6.0,   # Small cap: pump >6% = kemungkinan goreng
}
PUMP_VOLUME_MULT = {
    1: 5.0,    # Blue chip: volume >5x = suspicious
    2: 4.0,
    3: 3.0,    # Small cap: volume >3x = hati-hati
}
