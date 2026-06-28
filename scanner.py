"""
Scanner — Scan watchlist, generate sinyal BUY berkualitas tinggi.
Menggunakan logika yang sama dengan Bandarmology PRO v6.
"""

import numpy as np
import pandas as pd
import yfinance as yf
import requests
import warnings
from datetime import datetime, timedelta
from config import (
    WATCHLIST, STOCKBIT_TOKEN, MIN_SCORE_TO_SIGNAL,
    MAX_SIGNALS_PER_SESI, MIN_PRICE_IDR, MIN_VOLUME_LOT,
    TP_MIN_PCT, SL_MAX_PCT
)

warnings.filterwarnings("ignore")

HDR = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
    "Authorization": f"Bearer {STOCKBIT_TOKEN}" if STOCKBIT_TOKEN else "",
}

# ══════════════════════════════════════════════════════
#  TECHNICAL INDICATORS (standalone, no Streamlit)
# ══════════════════════════════════════════════════════

def load_price(ticker: str, period: str = "6mo") -> pd.DataFrame | None:
    try:
        df = yf.download(ticker + ".JK", period=period, interval="1d",
                         progress=False, auto_adjust=True)
        if df is None or df.empty or len(df) < 20:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.rename(columns={
            "Open":"open","High":"high","Low":"low","Close":"close","Volume":"volume"
        })
        df = df[["open","high","low","close","volume"]].dropna()
        # Normalize volume: if median > 5e8 likely in shares not lots
        if df["volume"].median() > 5e8:
            df["volume"] = df["volume"] / 100
        return df if len(df) >= 20 else None
    except:
        return None


def cmf(df: pd.DataFrame, p: int = 14) -> pd.Series:
    hl  = df["high"] - df["low"]
    clv = ((df["close"] - df["low"]) - (df["high"] - df["close"])) / hl.replace(0, np.nan)
    return (clv * df["volume"]).rolling(p).sum() / df["volume"].rolling(p).sum()


def obv(df: pd.DataFrame) -> pd.Series:
    return (np.sign(df["close"].diff()).fillna(0) * df["volume"]).cumsum()


def mfi(df: pd.DataFrame, p: int = 14) -> pd.Series:
    tp  = (df["high"] + df["low"] + df["close"]) / 3
    mf  = tp * df["volume"]
    pos = mf.where(tp > tp.shift(1), 0).rolling(p).sum()
    neg = mf.where(tp < tp.shift(1), 0).rolling(p).sum()
    return (100 - 100 / (1 + pos / neg.replace(0, np.nan))).fillna(50)


def rsi(s: pd.Series, p: int = 14) -> pd.Series:
    d = s.diff()
    g = d.clip(lower=0).rolling(p).mean()
    l = (-d.clip(upper=0)).rolling(p).mean()
    return (100 - 100 / (1 + g / l.replace(0, np.nan))).fillna(50)


def atr(df: pd.DataFrame, p: int = 14) -> pd.Series:
    hl = df["high"] - df["low"]
    hc = (df["high"] - df["close"].shift()).abs()
    lc = (df["low"]  - df["close"].shift()).abs()
    return pd.concat([hl, hc, lc], axis=1).max(axis=1).rolling(p).mean()


def wyckoff_phase(df: pd.DataFrame, c: pd.Series, o: pd.Series) -> tuple:
    """Returns (phase, name, confidence_0_100)"""
    n   = len(df)
    p   = df["close"]
    vol = df["volume"]
    seg = max(n // 3, 5)
    tr  = (p.iloc[-seg:].mean() - p.iloc[:seg].mean()) / (p.iloc[:seg].mean() + 1e-9)
    r20 = (p.tail(20).max() - p.tail(20).min()) / (p.tail(20).mean() + 1e-9)
    vol_ma20 = vol.rolling(20).mean().iloc[-1]
    vol_ratio = vol.tail(5).max() / (vol_ma20 + 1)
    vol_climax = vol_ratio >= 2.5
    ob_rising = float(o.iloc[-1]) > float(o.iloc[-min(10, n-1)])
    price_pos = (p.iloc[-1] - p.tail(20).min()) / ((p.tail(20).max() - p.tail(20).min()) + 1e-9)

    if tr < -0.06 and vol_climax and price_pos < 0.35:
        return "A", "Selling Climax", min(90, 60 + int(abs(tr)*200))
    if tr > 0.10 and ob_rising and price_pos > 0.75:
        return "E", "Markup", min(88, 55 + int(tr*100))
    if tr > 0.03 and ob_rising and vol_ratio >= 1.5 and price_pos > 0.65:
        return "D", "Sign of Strength", min(85, 50 + int(tr*100))

    # Phase C: Spring check
    p_min20 = p.tail(20).min(); p_min10 = p.tail(10).min()
    broke   = p_min10 <= p_min20 * 1.002
    recov   = float(p.iloc[-1]) > float(p.tail(5).min()) * 1.015
    lookback = min(180, n)
    v_lb = vol.iloc[-lookback:]
    v_ma_lb = v_lb.rolling(20).mean()
    vol_hist_ratio = (v_lb / v_ma_lb.replace(0, np.nan)).fillna(0)
    p_lb = p.iloc[-lookback:]
    had_phase_a = bool((vol_hist_ratio >= 2.5).any() and
                       (p_lb.iloc[0] - p_lb.min()) / (p_lb.iloc[0] + 1) > 0.06)
    if broke and recov and vol_climax and tr < 0.05 and r20 < 0.15 and had_phase_a:
        return "C", "Spring ⭐", min(85, 50 + int(vol_ratio*8))

    if r20 < 0.10 and abs(tr) < 0.05:
        return "B", "Building Cause", min(68, 35 + int((0.10-r20)*200))

    return "B", "Indeterminate", 40


def detect_vcp_grade(df: pd.DataFrame) -> str:
    """Quick VCP grade detection — A/B/C/NONE."""
    if len(df) < 60:
        return "NONE"
    close = df["close"]
    vol   = df["volume"]
    lp    = float(close.iloc[-1])
    ma50  = float(close.rolling(50).mean().iloc[-1]) if len(df) >= 50 else lp
    ma150 = float(close.rolling(150).mean().iloc[-1]) if len(df) >= 150 else lp
    above_ma = lp > ma50 and lp > ma150
    # Simple contraction check: recent 15d range vs prior 30d range
    recent_range = (df["high"].tail(15).max() - df["low"].tail(15).min()) / lp * 100
    prior_range  = (df["high"].iloc[-45:-15].max() - df["low"].iloc[-45:-15].min()) / lp * 100
    vol_dry      = float(vol.tail(10).mean()) < float(vol.tail(30).mean()) * 0.75
    contracting  = recent_range < prior_range * 0.7
    if above_ma and contracting and vol_dry and recent_range < 8:
        return "A"
    elif above_ma and contracting and vol_dry:
        return "B"
    elif above_ma and (contracting or vol_dry):
        return "C"
    return "NONE"


def compute_score(df: pd.DataFrame) -> dict:
    """Compute composite score 0-100. Returns full analysis dict."""
    n = len(df)
    p = min(14, max(7, n // 2))

    c_ = cmf(df, p=p)
    o_ = obv(df)
    m_ = mfi(df, p=p)
    r_ = rsi(df["close"], p=14)
    a_ = atr(df, p=14)
    wp, wn, wconf = wyckoff_phase(df, c_, o_)
    vcp_grade     = detect_vcp_grade(df)

    last = df.iloc[-1]
    prev = df.iloc[-2]
    lp   = float(last["close"])
    chg  = (lp - float(prev["close"])) / float(prev["close"]) * 100
    cmf_v = float(c_.iloc[-1]) if not pd.isna(c_.iloc[-1]) else 0.0
    mfi_v = float(m_.iloc[-1]) if not pd.isna(m_.iloc[-1]) else 50.0
    rsi_v = float(r_.iloc[-1]) if not pd.isna(r_.iloc[-1]) else 50.0
    atr_v = float(a_.iloc[-1]) if not pd.isna(a_.iloc[-1]) else lp * 0.02
    obv_up = float(o_.iloc[-1]) > float(o_.iloc[-min(10, n-1)])

    av = float(df["volume"].tail(20).mean())
    vr = float(last["volume"]) / av if av > 0 else 1.0

    # ── Technical score (0-100)
    ts = 50.0
    ts += float(np.clip(cmf_v * 125, -25, 25))
    obv_chg = float(o_.iloc[-1]) - float(o_.iloc[-min(10, n-1)])
    obv_std = max(float(o_.diff().abs().tail(20).std()), 1.0)
    ts += float(np.clip(obv_chg / (obv_std * 3) * 20, -20, 20))
    cp = (lp - float(last["low"])) / (float(last["high"]) - float(last["low"]) + 1e-9)
    ts += (cp - 0.5) * 30
    if vr > 1.3:
        ts += 15 if cp > 0.5 else -15
    if mfi_v < 25:   ts += 18
    elif mfi_v < 40: ts += 8
    elif mfi_v > 75: ts -= 18
    elif mfi_v > 60: ts -= 8
    ts = int(np.clip(round(ts), 0, 100))

    # ── VCP bonus
    vcp_s = {"A": 90, "B": 70, "C": 45, "NONE": 0}.get(vcp_grade, 0)

    # ── Composite (no broker data in standalone scanner)
    raw = int(np.clip(round(ts * 0.65 + vcp_s * 0.10 + 25), 0, 100))
    # Mandatory gates
    if wp == "E":          raw = min(raw, 80)
    if wp == "A":          raw = min(raw, 72)
    if cmf_v < -0.15:      raw = min(raw, 72)
    if wconf < 50:         raw = min(raw, raw - int((50 - wconf) * 0.3))
    if vcp_grade == "NONE": raw = min(raw, 85)
    final = int(np.clip(raw, 0, 100))

    # ── Entry zone (ATR-based)
    sl  = round(lp - 1.5 * atr_v, 0)
    sup = float(df["low"].tail(10).min())
    sl  = max(sl, round(sup * 0.97, 0))
    sl_pct  = (lp - sl) / lp * 100
    tp_mult = 2.0  # R:R 2:1
    tp  = round(lp + tp_mult * (lp - sl), 0)
    tp_pct  = (tp - lp) / lp * 100

    # OBV direction string
    obv_dir = "Rising ▲" if obv_up else "Falling ▼"

    # RS vs IHSG (quick)
    rs_interp = "—"
    try:
        ihsg = yf.download("^JKSE", period="3mo", interval="1d",
                           progress=False, auto_adjust=True)
        if ihsg is not None and not ihsg.empty:
            if isinstance(ihsg.columns, pd.MultiIndex):
                ihsg.columns = ihsg.columns.get_level_values(0)
            ihsg_r20 = (float(ihsg["Close"].iloc[-1]) - float(ihsg["Close"].iloc[-min(20, len(ihsg)-1)])) / float(ihsg["Close"].iloc[-min(20, len(ihsg)-1)]) * 100
            stock_r20 = (lp - float(df["close"].iloc[-min(20, n-1)])) / float(df["close"].iloc[-min(20, n-1)]) * 100
            rs20 = (1 + stock_r20/100) / (1 + ihsg_r20/100) * 100
            if rs20 > 108: rs_interp = "OUTPERFORM ▲"
            elif rs20 < 93: rs_interp = "UNDERPERFORM ▼"
            else: rs_interp = "IN LINE →"
    except:
        pass

    return {
        "score"          : final,
        "ts"             : ts,
        "vcp_grade"      : vcp_grade,
        "wp"             : wp,
        "wn"             : wn,
        "wconf"          : wconf,
        "cmf_v"          : round(cmf_v, 4),
        "mfi_v"          : round(mfi_v, 1),
        "rsi_v"          : round(rsi_v, 1),
        "obv_dir"        : obv_dir,
        "vr"             : round(vr, 2),
        "chg"            : round(chg, 2),
        "lp"             : lp,
        "atr_v"          : round(atr_v, 0),
        "sl"             : sl,
        "sl_pct"         : round(sl_pct, 1),
        "tp"             : tp,
        "tp_pct"         : round(tp_pct, 1),
        "rs_interp"      : rs_interp,
    }


def build_rationale(r: dict) -> str:
    """Build human-readable rationale string."""
    reasons = []
    if r["cmf_v"] > 0.12:
        reasons.append(f"CMF {r['cmf_v']:+.3f} (strong inflow)")
    elif r["cmf_v"] > 0.05:
        reasons.append(f"CMF {r['cmf_v']:+.3f} (mild inflow)")
    if r["obv_dir"].startswith("Rising"):
        reasons.append("OBV rising (cumulative buying)")
    if r["mfi_v"] < 30:
        reasons.append(f"MFI {r['mfi_v']:.0f} (oversold)")
    if r["wp"] in ("C", "D"):
        reasons.append(f"Wyckoff Phase {r['wp']} — {r['wn']}")
    if r["vcp_grade"] in ("A", "B"):
        reasons.append(f"VCP Grade {r['vcp_grade']}")
    if r["vr"] >= 1.5:
        reasons.append(f"Volume {r['vr']:.1f}x avg")
    if r["rs_interp"].startswith("OUT"):
        reasons.append(f"RS vs IHSG: {r['rs_interp']}")
    return " · ".join(reasons) if reasons else "TA momentum confluence"


def scan_once(session: str) -> list:
    """
    Scan seluruh watchlist dan return list sinyal terbaik.
    session: 'PRE_MARKET' / 'MIDDAY' / 'POST_MARKET'
    """
    print(f"\n🔍 Scanning {len(WATCHLIST)} stocks — {session} — {datetime.now().strftime('%H:%M:%S WIB')}")
    candidates = []

    for i, tk in enumerate(WATCHLIST):
        try:
            df = load_price(tk, "6mo")
            if df is None:
                continue

            lp  = float(df["close"].iloc[-1])
            vol_today = float(df["volume"].iloc[-1])

            # Pre-filters
            if lp < MIN_PRICE_IDR:
                continue
            if vol_today < MIN_VOLUME_LOT:
                continue

            r = compute_score(df)

            # Score threshold
            if r["score"] < MIN_SCORE_TO_SIGNAL:
                continue

            # TP/SL sanity check
            if r["tp_pct"] < TP_MIN_PCT:
                continue
            if r["sl_pct"] > SL_MAX_PCT:
                continue

            # Don't signal Phase E (late distribution) or Phase A (still falling)
            if r["wp"] in ("E",):
                continue

            r["ticker"]  = tk
            r["session"] = session
            r["rationale"] = build_rationale(r)

            signal_type = "STRONG_BUY" if r["score"] >= 75 else "BUY"
            r["signal_type"] = signal_type

            candidates.append(r)
            print(f"  ✅ {tk}: score={r['score']}, {signal_type}, Wyckoff {r['wp']}, VCP {r['vcp_grade']}")

        except Exception as e:
            print(f"  ⚠️  {tk}: {e}")
            continue

    # Sort by score descending, take top N
    candidates.sort(key=lambda x: x["score"], reverse=True)
    selected = candidates[:MAX_SIGNALS_PER_SESI]

    if not selected:
        print("  ℹ️  Tidak ada sinyal yang memenuhi threshold hari ini.")
    else:
        print(f"  📊 {len(selected)} sinyal lolos dari {len(candidates)} kandidat")

    return selected


def make_signal_id(ticker: str, session: str) -> str:
    """Generate unique signal ID: BMP-BBCA-20260602-PRE"""
    date_str = datetime.now().strftime("%Y%m%d")
    sess_abbr = {"PRE_MARKET": "PRE", "MIDDAY": "MID", "POST_MARKET": "POST"}.get(session, session[:3])
    return f"BMP-{ticker}-{date_str}-{sess_abbr}"


def prepare_signal_record(r: dict) -> dict:
    """Siapkan dict untuk disimpan ke database."""
    sig_id = make_signal_id(r["ticker"], r["session"])
    return {
        "id"             : sig_id,
        "ticker"         : r["ticker"],
        "signal_type"    : r["signal_type"],
        "session"        : r["session"],
        "entry_low"      : r["lp"],
        "entry_high"     : round(r["lp"] * 1.01, 0),
        "tp_price"       : r["tp"],
        "sl_price"       : r["sl"],
        "tp_pct"         : r["tp_pct"],
        "sl_pct"         : r["sl_pct"],
        "score"          : r["score"],
        "wyckoff_phase"  : f"{r['wp']} — {r['wn']}",
        "cmf_value"      : r["cmf_v"],
        "obv_direction"  : r["obv_dir"],
        "broker_crossing": r.get("broker_crossing", "—"),
        "vcp_grade"      : r["vcp_grade"],
        "rs_interp"      : r["rs_interp"],
        "rationale"      : r["rationale"],
        "timestamp_wib"  : datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "telegram_msg_id": None,
    }
