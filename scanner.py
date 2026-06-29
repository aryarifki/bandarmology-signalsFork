"""
BandarAI Signal Scanner v3 — Redesigned berdasarkan backtest findings
======================================================================
Perubahan utama dari v2:
- HARD GATES: Phase A/E blocked, Phase B strict (CMF/MFI/MA/RSI)
- MA50 TREND FILTER: only buy in uptrend
- RSI GATE: block overbought (>65) dan extreme oversold (<25)
- TICKER BLACKLIST: TLKM/BREN/ICBP (structurally tidak cocok Wyckoff)
- PHASE BONUS: Phase C +25pts, Phase D +15pts di scoring
- TP LEBIH JAUH: 2.5x ATR (vs 2.0x) → R:R 2.5:1, break-even 29%
- TICKER COOLDOWN: 1 ticker max 1x per 5 hari
- MAX 3 sinyal/sesi (down dari 5) — kualitas > kuantitas
"""

import numpy as np
import pandas as pd
import yfinance as yf
import warnings
import time
from datetime import datetime, timedelta
from config import (
    WATCHLIST, MIN_SCORE_TO_SIGNAL, MAX_SIGNALS_PER_SESI,
    MIN_PRICE_IDR, MIN_VOLUME_LOT, TP_MIN_PCT, SL_MAX_PCT
)

warnings.filterwarnings("ignore")

# ── TICKER BLACKLIST (structurally tidak cocok Wyckoff CMF scanner) ──
# Data backtest: TLKM 0%/21sig, BREN 0%/12sig, ICBP 0%/16sig
TICKER_BLACKLIST = {
    "TLKM",   # Low-vol defensive, Wyckoff pattern tidak reliable
    "ICBP",   # Consumer staples, low beta, sama seperti TLKM
    "BREN",   # High-vol momentum trap, ATR terlalu besar
    "MIKA",   # Healthcare defensif, volume sering thin
    "KLBF",   # Pharma defensif, pattern Wyckoff tidak terbentuk
}

# ── TICKER REPUTATION (dari backtest, per update berkala) ─────────────
# Saham dengan historical WR buruk kena penalty score
TICKER_PENALTY = {
    "BSDE":  -8,
    "CTRA":  -8,
    "ASII":  -6,
    "SMRA":  -8,
    "AKRA":  -8,
    "MYOR":  -8,
}

# ── SAHAM YANG TERBUKTI WORK (bonus kecil) ────────────────────────────
TICKER_BONUS = {
    "MDKA": +8,
    "ADRO": +5,
    "PTBA": +3,
    "ULTJ": +3,
}


# ══════════════════════════════════════════════════════
#  PRICE LOADER
# ══════════════════════════════════════════════════════

def load_price(ticker: str, period: str = "6mo", interval: str = "1d"):
    try:
        df = yf.download(ticker + ".JK", period=period, interval=interval,
                         progress=False, auto_adjust=True)
        if df is None or df.empty or len(df) < 20:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.rename(columns={"Open":"open","High":"high","Low":"low",
                                  "Close":"close","Volume":"volume"})
        df = df[["open","high","low","close","volume"]].dropna()
        if df["volume"].median() > 5e8:
            df["volume"] = df["volume"] / 100
        return df if len(df) >= 20 else None
    except:
        return None


# ══════════════════════════════════════════════════════
#  TECHNICAL INDICATORS
# ══════════════════════════════════════════════════════

def cmf(df, p=14):
    hl  = df["high"] - df["low"]
    clv = ((df["close"] - df["low"]) - (df["high"] - df["close"])) / hl.replace(0, np.nan)
    return (clv * df["volume"]).rolling(p).sum() / df["volume"].rolling(p).sum()

def obv(df):
    return (np.sign(df["close"].diff()).fillna(0) * df["volume"]).cumsum()

def mfi(df, p=14):
    tp  = (df["high"] + df["low"] + df["close"]) / 3
    mf  = tp * df["volume"]
    pos = mf.where(tp > tp.shift(1), 0).rolling(p).sum()
    neg = mf.where(tp < tp.shift(1), 0).rolling(p).sum()
    return (100 - 100 / (1 + pos / neg.replace(0, np.nan))).fillna(50)

def atr(df, p=14):
    hl = df["high"] - df["low"]
    hc = (df["high"] - df["close"].shift()).abs()
    lc = (df["low"]  - df["close"].shift()).abs()
    return pd.concat([hl, hc, lc], axis=1).max(axis=1).rolling(p).mean()

def rsi(s, p=14):
    d = s.diff()
    g = d.clip(lower=0).rolling(p).mean()
    l = (-d.clip(upper=0)).rolling(p).mean()
    return (100 - 100 / (1 + g / l.replace(0, np.nan))).fillna(50)

def wyckoff_phase(df, c, o):
    n   = len(df)
    p   = df["close"]
    vol = df["volume"]
    seg = max(n // 3, 5)
    tr  = (p.iloc[-seg:].mean() - p.iloc[:seg].mean()) / (p.iloc[:seg].mean() + 1e-9)
    r20 = (p.tail(20).max() - p.tail(20).min()) / (p.tail(20).mean() + 1e-9)
    vol_ma20   = vol.rolling(20).mean().iloc[-1]
    vol_ratio  = vol.tail(5).max() / (vol_ma20 + 1)
    vol_climax = vol_ratio >= 2.5
    ob_rising  = float(o.iloc[-1]) > float(o.iloc[-min(10, n-1)])
    price_pos  = (p.iloc[-1] - p.tail(20).min()) / ((p.tail(20).max() - p.tail(20).min()) + 1e-9)

    if tr < -0.06 and vol_climax and price_pos < 0.35:
        return "A", "Selling Climax", min(90, 60 + int(abs(tr)*200))
    if tr > 0.10 and ob_rising and price_pos > 0.75:
        return "E", "Markup", min(88, 55 + int(tr*100))
    if tr > 0.03 and ob_rising and vol_ratio >= 1.5 and price_pos > 0.65:
        return "D", "Sign of Strength", min(85, 50 + int(tr*100))

    p_min20 = p.tail(20).min()
    p_min10 = p.tail(10).min()
    broke   = p_min10 <= p_min20 * 1.002
    recov   = float(p.iloc[-1]) > float(p.tail(5).min()) * 1.015
    lookback = min(180, n)
    v_lb    = vol.iloc[-lookback:]
    v_ma_lb = v_lb.rolling(20).mean()
    vol_hist = (v_lb / v_ma_lb.replace(0, np.nan)).fillna(0)
    p_lb    = p.iloc[-lookback:]
    had_a   = bool((vol_hist >= 2.5).any() and
                   (p_lb.iloc[0] - p_lb.min()) / (p_lb.iloc[0] + 1) > 0.06)
    if broke and recov and vol_climax and tr < 0.05 and r20 < 0.15 and had_a:
        return "C", "Spring ⭐", min(85, 50 + int(vol_ratio*8))
    if r20 < 0.10 and abs(tr) < 0.05:
        return "B", "Building Cause", min(68, 35 + int((0.10-r20)*200))
    return "B", "Indeterminate", 40


# ══════════════════════════════════════════════════════
#  HARD GATES — BLOKIR SEBELUM SCORING
#  Ini penyebab utama perbaikan dari backtest 21% WR
# ══════════════════════════════════════════════════════

def check_hard_gates(df, wp: str, cmf_v: float, mfi_v: float,
                     obv_s: pd.Series, vr: float) -> tuple:
    """
    Return (passes: bool, reason: str)
    Semua gates harus lolos sebelum masuk ke scoring.
    """
    n = len(df)
    p = df["close"]

    # ── Gate 1: Phase A/E → BLOCK (structurally bad entry)
    if wp == "A":
        return False, "Phase A (Selling Climax) — bukan area entry"
    if wp == "E":
        return False, "Phase E (Markup lanjut) — terlambat masuk, risiko distribusi"

    # ── Gate 2: MA50 trend filter — HANYA beli di uptrend
    if len(p) >= 50:
        ma50 = float(p.rolling(50).mean().iloc[-1])
        lp   = float(p.iloc[-1])
        if wp == "B":
            # Phase B: harus di atas MA50 (trend sudah terbentuk)
            if lp < ma50 * 0.98:
                return False, f"Phase B di bawah MA50 — downtrend, jangan lawan trend"
        if wp in ("C",):
            # Phase C (Spring): boleh sedikit di bawah MA50
            # karena Spring adalah shakeout di bawah support
            ma20 = float(p.rolling(20).mean().iloc[-1]) if len(p) >= 20 else lp
            if lp < ma20 * 0.92:
                return False, f"Phase C terlalu jauh di bawah MA20 — bukan Spring, bisa downtrend lanjut"

    # ── Gate 3: Phase B gates — strict!
    if wp == "B":
        if cmf_v < 0.08:
            return False, f"Phase B + CMF {cmf_v:+.3f} < 0.08 (inflow lemah)"
        if mfi_v > 58:
            return False, f"Phase B + MFI {mfi_v:.0f} > 52 (belum oversold)"
        obv_up_10 = float(obv_s.iloc[-1]) > float(obv_s.iloc[-min(10, n-1)])
        if not obv_up_10:
            return False, "Phase B + OBV tidak rising 10 hari — distribusi"
        if vr < 1.0:
            return False, f"Phase B + volume {vr:.1f}x (perlu volume konfirmasi >= 1.0x)"

    # ── Gate 4: RSI gate — per phase
    # Phase C (Spring) EXEMPT dari RSI overbought check.
    # Spring recovery secara natural push RSI naik dari extreme oversold.
    # RSI tinggi pada Phase C = konfirmasi kekuatan recovery, bukan bahaya.
    rsi_v = float(rsi(p).iloc[-1])
    if wp == "B" and rsi_v > 70:
        return False, f"Phase B + RSI {rsi_v:.0f} > 65 (overbought saat konsolidasi)"
    if wp == "D" and rsi_v > 72:
        return False, f"Phase D + RSI {rsi_v:.0f} > 72 (terlalu extend)"
    if wp not in ("C",) and rsi_v < 20:
        return False, f"RSI {rsi_v:.0f} < 20 (extreme panic)"

    # ── Gate 5: Minimum volume untuk konviksi
    if vr < 0.70 and wp != "C":
        return False, f"Volume {vr:.1f}x terlalu lemah (perlu >= 0.70x)"

    return True, ""


# ══════════════════════════════════════════════════════
#  MARKET REGIME (dari IHSG)
# ══════════════════════════════════════════════════════

def get_market_regime(ihsg_df) -> dict:
    if ihsg_df is None or len(ihsg_df) < 50:
        return {"regime":"UNKNOWN","multiplier":1.0,"ok":True,"desc":"IHSG unavailable"}
    p      = ihsg_df["close"]
    n      = len(p)
    ma50   = p.rolling(50).mean()
    ma200  = p.rolling(min(200,n)).mean()
    lp     = float(p.iloc[-1])
    ma50v  = float(ma50.iloc[-1])
    ma200v = float(ma200.iloc[-1])
    ret20  = (lp / float(p.iloc[-min(20,n-1)]) - 1) * 100
    ret60  = (lp / float(p.iloc[-min(60,n-1)]) - 1) * 100
    peak   = float(p.tail(252).max()) if n >= 252 else float(p.max())
    dd     = (lp - peak) / peak * 100
    above_ma50  = lp > ma50v
    above_ma200 = lp > ma200v
    ma50_up     = float(ma50.iloc[-1]) > float(ma50.iloc[-min(20,n-1)])

    if dd < -40 or ret60 < -28:
        return {"regime":"CRASH",       "multiplier":0.65, "ok":True,
                "desc":f"IHSG crash ({dd:.1f}%) — SEMUA sinyal dihentikan"}
    elif dd < -20 or ret60 < -15:
        return {"regime":"BEAR", "multiplier":0.72, "ok":True,
                "desc":f"IHSG bear market ({dd:.1f}%) — hanya Phase C/D"}
    elif (dd < -10 and not above_ma50) or ret60 < -12:
        return {"regime":"RISK_OFF",    "multiplier":0.75,"ok":True,
                "desc":f"IHSG risk-off ({dd:.1f}%) — threshold dinaikkan, hanya Phase C/D"}
    elif dd < -5 and above_ma200 and ret60 < -3:
        return {"regime":"CORRECTION",  "multiplier":0.90,"ok":True,
                "desc":f"IHSG koreksi ({dd:.1f}%) — selektif"}
    elif abs(ret20) < 4 and ret60 > -5 and above_ma200:
        return {"regime":"SIDEWAYS",    "multiplier":1.00,"ok":True,
                "desc":f"IHSG sideways — stock picking optimal"}
    elif above_ma50 and above_ma200 and ma50_up:
        return {"regime":"BULL",        "multiplier":1.05,"ok":True,
                "desc":f"IHSG uptrend — kondisi ideal"}
    return {"regime":"MIXED",       "multiplier":0.90,"ok":True,
            "desc":f"IHSG mixed — selektif"}


# ══════════════════════════════════════════════════════
#  RS vs IHSG
# ══════════════════════════════════════════════════════

def calc_rs(df, ihsg_df) -> dict:
    if ihsg_df is None or df is None:
        return {"score":50,"interp":"—","rs20":100}
    try:
        merged = df[["close"]].rename(columns={"close":"stock"}).join(
            ihsg_df[["close"]].rename(columns={"close":"ihsg"}), how="inner")
        if len(merged) < 25:
            return {"score":50,"interp":"—","rs20":100}
        n = len(merged)
        sr = (float(merged["stock"].iloc[-1]) / float(merged["stock"].iloc[-min(20,n-1)]) - 1) * 100
        ir = (float(merged["ihsg"].iloc[-1])  / float(merged["ihsg"].iloc[-min(20,n-1)])  - 1) * 100
        rs20 = (1 + sr/100) / (1 + ir/100) * 100
        score = 50.0 + float(np.clip((rs20 - 100) * 1.5, -20, 20))
        sr5 = (float(merged["stock"].iloc[-1]) / float(merged["stock"].iloc[-min(5,n-1)]) - 1)
        ir5 = (float(merged["ihsg"].iloc[-1])  / float(merged["ihsg"].iloc[-min(5,n-1)])  - 1)
        score += 5 if sr5 > ir5 else -5
        score = int(np.clip(round(score), 0, 100))
        if rs20 > 108:   interp = "OUTPERFORM ▲"
        elif rs20 < 93:  interp = "UNDERPERFORM ▼"
        else:            interp = "IN LINE →"
        return {"score":score, "interp":interp, "rs20":round(rs20,1)}
    except:
        return {"score":50,"interp":"—","rs20":100}


# ══════════════════════════════════════════════════════
#  WEEKLY CONFLUENCE
# ══════════════════════════════════════════════════════

def calc_weekly_confluence(ticker: str) -> int:
    try:
        df_w = yf.download(ticker + ".JK", period="2y", interval="1wk",
                           progress=False, auto_adjust=True)
        if df_w is None or df_w.empty or len(df_w) < 20:
            return 50
        if isinstance(df_w.columns, pd.MultiIndex):
            df_w.columns = df_w.columns.get_level_values(0)
        df_w = df_w.rename(columns={"Open":"open","High":"high","Low":"low",
                                     "Close":"close","Volume":"volume"})
        df_w = df_w[["open","high","low","close","volume"]].dropna()
        n = len(df_w)
        cmf_w  = cmf(df_w, p=min(10, n//2))
        obv_w  = obv(df_w)
        ma20_w = df_w["close"].rolling(20).mean()
        cmf_v      = float(cmf_w.iloc[-1]) if not pd.isna(cmf_w.iloc[-1]) else 0.0
        obv_up     = float(obv_w.iloc[-1]) > float(obv_w.iloc[-min(4,n-1)])
        ma20_v     = float(ma20_w.iloc[-1]) if not pd.isna(ma20_w.iloc[-1]) else float(df_w["close"].iloc[-1])
        above_ma20 = float(df_w["close"].iloc[-1]) > ma20_v
        ma20_slope = ma20_v > float(ma20_w.iloc[-min(4,n-1)]) if not pd.isna(ma20_w.iloc[-min(4,n-1)]) else True
        w8_ret     = (float(df_w["close"].iloc[-1]) / float(df_w["close"].iloc[-min(8,n-1)]) - 1) * 100
        score = 0.0
        if cmf_v > 0.10:    score += 30
        elif cmf_v > 0.02:  score += 18
        elif cmf_v > -0.05: score += 10
        elif cmf_v > -0.12: score += 4
        score += 25 if obv_up else 0
        if above_ma20 and ma20_slope:  score += 25
        elif above_ma20:                score += 14
        elif ma20_slope:                score += 6
        if w8_ret >= 8:    score += 20
        elif w8_ret >= 3:  score += 14
        elif w8_ret >= -3: score += 10
        elif w8_ret >= -10: score += 4
        return int(np.clip(round(score), 0, 100))
    except:
        return 50


# ══════════════════════════════════════════════════════
#  FUNDAMENTAL GATE
# ══════════════════════════════════════════════════════

def quick_fundamental_check(ticker: str) -> dict:
    try:
        info  = yf.Ticker(ticker + ".JK").fast_info
        pe    = getattr(info, "pe_ratio", None)
        fails = 0
        notes = []
        if pe and pe > 60:
            fails += 1
            notes.append(f"PE tinggi ({pe:.0f}x)")
        if pe and pe < 0:
            fails += 2
            notes.append("Rugi (PE negatif)")
        penalty = min(15, fails * 7)
        return {"pass":fails<=1, "penalty":penalty,
                "notes":" · ".join(notes) if notes else "OK"}
    except:
        return {"pass":True, "penalty":0, "notes":"—"}


# ══════════════════════════════════════════════════════
#  GORENG / PUMP FILTER
# ══════════════════════════════════════════════════════

def is_goreng_pump(df, ticker_tier: int = 2) -> tuple:
    if df is None or len(df) < 5:
        return False, ""
    lp     = float(df["close"].iloc[-1])
    p3ago  = float(df["close"].iloc[-min(4, len(df)-1)])
    ret3   = (lp - p3ago) / p3ago * 100
    vol    = df["volume"]
    vol_ma = float(vol.rolling(20).mean().iloc[-1]) if len(df) >= 20 else float(vol.mean())
    vr     = float(vol.iloc[-1]) / (vol_ma + 1)
    # Threshold lebih ketat untuk small cap
    pump_thresh = {1: 10.0, 2: 7.0, 3: 5.0}.get(ticker_tier, 7.0)
    vol_thresh  = {1: 5.0, 2: 4.0, 3: 3.0}.get(ticker_tier, 4.0)
    if ret3 > pump_thresh and vr > 2.5:
        return True, f"Pump: +{ret3:.1f}% dalam 3 hari, volume {vr:.1f}x"
    if vr > vol_thresh:
        return True, f"Volume spike ekstrem {vr:.1f}x"
    return False, ""


# ══════════════════════════════════════════════════════
#  VCP GRADE
# ══════════════════════════════════════════════════════

def detect_vcp_grade(df) -> str:
    if len(df) < 60:
        return "NONE"
    close  = df["close"]
    vol    = df["volume"]
    lp     = float(close.iloc[-1])
    ma50   = float(close.rolling(50).mean().iloc[-1]) if len(df) >= 50 else lp
    ma150  = float(close.rolling(150).mean().iloc[-1]) if len(df) >= 150 else lp
    ma200  = float(close.rolling(200).mean().iloc[-1]) if len(df) >= 200 else lp
    above  = lp > ma50 and lp > ma150
    tscore = sum([lp > ma50, lp > ma150, lp > ma200])
    r15 = (df["high"].tail(15).max() - df["low"].tail(15).min()) / lp * 100
    r30 = (df["high"].iloc[-45:-15].max() - df["low"].iloc[-45:-15].min()) / lp * 100 if len(df)>=45 else r15*2
    r60 = (df["high"].iloc[-90:-45].max() - df["low"].iloc[-90:-45].min()) / lp * 100 if len(df)>=90 else r30*1.5
    contracting = r15 < r30 * 0.7 and r30 < r60 * 0.85
    vol_dry     = float(vol.tail(10).mean()) < float(vol.tail(30).mean()) * 0.75
    tight       = r15 < 8
    if above and contracting and vol_dry and tight and tscore >= 2:
        return "A"
    elif above and contracting and vol_dry and tscore >= 2:
        return "B"
    elif above and (contracting or vol_dry) and tscore >= 1:
        return "C"
    return "NONE"


# ══════════════════════════════════════════════════════
#  COMPOSITE SCORE v3
#  Key change: Phase bonus, ticker adj, TP lebih jauh
# ══════════════════════════════════════════════════════

def compute_score_v3(df, ticker: str, ihsg_df, regime: dict) -> dict:
    n = len(df)
    p = min(14, max(7, n // 2))

    c_ = cmf(df, p=p)
    o_ = obv(df)
    m_ = mfi(df, p=p)
    a_ = atr(df, p=14)
    r_ = rsi(df["close"], p=14)
    wp, wn, wconf = wyckoff_phase(df, c_, o_)

    lp    = float(df["close"].iloc[-1])
    cmf_v = float(c_.iloc[-1]) if not pd.isna(c_.iloc[-1]) else 0.0
    mfi_v = float(m_.iloc[-1]) if not pd.isna(m_.iloc[-1]) else 50.0
    rsi_v = float(r_.iloc[-1]) if not pd.isna(r_.iloc[-1]) else 50.0
    atr_v = float(a_.iloc[-1]) if not pd.isna(a_.iloc[-1]) else lp * 0.02
    obv_up = float(o_.iloc[-1]) > float(o_.iloc[-min(10, n-1)])
    av    = float(df["volume"].tail(20).mean())
    vr    = float(df["volume"].iloc[-1]) / av if av > 0 else 1.0

    if atr_v == 0:
        return None

    # ── HARD GATES ────────────────────────────────────────
    passes, gate_reason = check_hard_gates(df, wp, cmf_v, mfi_v, o_, vr)
    if not passes:
        return {"blocked": True, "reason": gate_reason,
                "wp": wp, "ticker": ticker}

    # ── TA BASE SCORE ──────────────────────────────────────
    ts = 50.0
    ts += float(np.clip(cmf_v * 120, -24, 24))
    obv_std = max(float(o_.diff().abs().tail(20).std()), 1.0)
    obv_chg = float(o_.iloc[-1]) - float(o_.iloc[-min(10, n-1)])
    ts += float(np.clip(obv_chg / (obv_std * 3) * 20, -20, 20))
    hi, lo = float(df["high"].iloc[-1]), float(df["low"].iloc[-1])
    cp = (lp - lo) / (hi - lo + 1e-9)
    ts += (cp - 0.5) * 25
    if vr > 1.3: ts += 12 if cp > 0.5 else -12
    if mfi_v < 30:   ts += 15
    elif mfi_v < 45: ts += 7
    elif mfi_v > 70: ts -= 15
    elif mfi_v > 60: ts -= 7
    # RSI kontribusi kecil
    if rsi_v < 35:   ts += 8
    elif rsi_v > 55: ts -= 5
    ts = int(np.clip(round(ts), 0, 100))

    # ── PHASE BONUS (perubahan utama v3) ──────────────────
    phase_bonus = {"C": 25, "D": 15, "B": 0, "A": -30, "E": -30}.get(wp, 0)

    # ── VCP GRADE ─────────────────────────────────────────
    vcp_grade = detect_vcp_grade(df)
    vcp_s     = {"A":90, "B":70, "C":40, "NONE":0}[vcp_grade]

    # ── RS vs IHSG ────────────────────────────────────────
    rs    = calc_rs(df, ihsg_df)
    rs_s  = rs["score"]

    # ── WEEKLY CONFLUENCE ─────────────────────────────────
    weekly_s = calc_weekly_confluence(ticker)

    # ── FUNDAMENTAL ───────────────────────────────────────
    fund = quick_fundamental_check(ticker)

    # ── TICKER ADJUSTMENT ─────────────────────────────────
    ticker_adj = TICKER_PENALTY.get(ticker, 0) + TICKER_BONUS.get(ticker, 0)

    # ── WEIGHTED COMPOSITE ────────────────────────────────
    raw = int(np.clip(round(
        ts         * 0.38 +
        vcp_s      * 0.10 +
        rs_s       * 0.20 +
        weekly_s   * 0.22 +
        50         * 0.10
    ), 0, 100))

    # Apply bonuses / penalties
    raw = raw + phase_bonus + ticker_adj - fund["penalty"]
    raw = int(np.clip(raw, 0, 100))

    # ── REGIME MULTIPLIER ─────────────────────────────────
    # CRASH/BEAR/RISK_OFF: hanya Phase C/D diizinkan
    crash_bear = regime.get("regime") in ("CRASH","BEAR","RISK_OFF")
    if crash_bear and wp not in ("C","D"):
        # Phase B dengan CMF kuat boleh jalan di bear market
        if not (wp == "B" and cmf_v >= 0.15):
            return {"blocked": True,
                    "reason": f"{regime.get('regime')} — hanya Phase C/D (atau B+CMF>=0.15)",
                    "wp": wp, "ticker": ticker}

    final = int(np.clip(round(raw * regime.get("multiplier", 1.0)), 0, 100))

    # ── ENTRY ZONE (TP lebih jauh: 2.5x vs 2.0x sebelumnya) ─
    sl     = max(round(lp - 1.5 * atr_v, 0),
                 round(float(df["low"].tail(10).min()) * 0.97, 0))
    tp     = round(lp + 2.5 * (lp - sl), 0)   # 2.5x → R:R 2.5:1
    sl_pct = (lp - sl) / lp * 100
    tp_pct = (tp  - lp) / lp * 100

    # ── RATIONALE ─────────────────────────────────────────
    r = []
    if cmf_v > 0.15:    r.append(f"CMF {cmf_v:+.3f} (inflow kuat)")
    elif cmf_v > 0.08:  r.append(f"CMF {cmf_v:+.3f} (inflow)")
    if obv_up:          r.append("OBV naik ▲")
    if mfi_v < 35:      r.append(f"MFI {mfi_v:.0f} (oversold)")
    if rsi_v < 40:      r.append(f"RSI {rsi_v:.0f} (oversold)")
    if wp in ("C","D"): r.append(f"Wyckoff {wp} — {wn}")
    if vcp_grade in ("A","B"): r.append(f"VCP Grade {vcp_grade}")
    if rs["interp"].startswith("OUT"): r.append(f"RS OUTPERFORM ▲")
    if weekly_s >= 65:  r.append(f"Weekly {weekly_s}/100")
    if vr >= 1.5:       r.append(f"Vol {vr:.1f}x")

    return {
        "blocked"    : False,
        "score"      : final,
        "ts"         : ts,
        "vcp_grade"  : vcp_grade,
        "wp"         : wp,
        "wn"         : wn,
        "wconf"      : wconf,
        "cmf_v"      : round(cmf_v, 4),
        "mfi_v"      : round(mfi_v, 1),
        "rsi_v"      : round(rsi_v, 1),
        "obv_dir"    : "Rising ▲" if obv_up else "Falling ▼",
        "vr"         : round(vr, 2),
        "lp"         : lp,
        "atr_v"      : round(atr_v, 0),
        "sl"         : sl,
        "sl_pct"     : round(sl_pct, 1),
        "tp"         : tp,
        "tp_pct"     : round(tp_pct, 1),
        "rs_interp"  : rs["interp"],
        "rs20"       : rs["rs20"],
        "weekly_score": weekly_s,
        "fund_ok"    : fund["pass"],
        "rationale"  : " · ".join(r) if r else "TA confluence",
        "signal_type": "STRONG_BUY" if final >= 78 else "BUY",
        "session"    : "",
        "ticker"     : ticker,
        "broker_crossing": "—",
    }


# ══════════════════════════════════════════════════════
#  TICKER COOLDOWN — 1 ticker max 1x per 5 hari
# ══════════════════════════════════════════════════════

def get_recent_signal_tickers(days: int = 5) -> set:
    """Ambil ticker yang sudah sinyal dalam N hari terakhir."""
    try:
        from database import get_all_signals_df
        df = get_all_signals_df()
        if df.empty:
            return set()
        cutoff = pd.Timestamp.now() - pd.Timedelta(days=days)
        df["ts"] = pd.to_datetime(df["timestamp_wib"], errors="coerce")
        recent = df[df["ts"] >= cutoff]
        return set(recent["ticker"].unique())
    except Exception:
        return set()


# ══════════════════════════════════════════════════════
#  MAIN SCAN
# ══════════════════════════════════════════════════════

def _scan_tickers(tickers: list, session: str, ihsg_df,
                   regime: dict, threshold: int,
                   cooldown_tickers: set,
                   post_open_mode: bool) -> tuple:
    """Scan list ticker dan return (candidates, blocked_log)."""
    try:
        from config import PROVEN_TICKERS, MIN_SCORE_PROVEN
    except ImportError:
        PROVEN_TICKERS  = set()
        MIN_SCORE_PROVEN = threshold

    candidates  = []
    blocked_log = []

    for tk in tickers:
        if tk in TICKER_BLACKLIST:
            continue
        if tk in cooldown_tickers:
            continue

        try:
            df = load_price(tk, "1y")
            if df is None:
                continue

            lp = float(df["close"].iloc[-1])
            if lp < MIN_PRICE_IDR:
                continue
            if float(df["volume"].iloc[-1]) < MIN_VOLUME_LOT:
                continue

            is_pump, pump_reason = is_goreng_pump(df)
            if is_pump:
                print(f"  ⚠️  {tk}: Goreng — {pump_reason}")
                continue

            r = compute_score_v3(df, tk, ihsg_df, regime)
            if r is None:
                continue
            if r.get("blocked"):
                blocked_log.append(f"  ⛔ {tk}: {r['reason']}")
                continue

            r["session"] = session

            # Proven tickers get lower threshold
            eff_threshold = MIN_SCORE_PROVEN if tk in PROVEN_TICKERS else threshold

            if r["score"] < eff_threshold:
                continue
            if r["tp_pct"] < TP_MIN_PCT:
                continue
            if r["sl_pct"] > SL_MAX_PCT:
                continue

            # ── POST_OPEN: tambahan intraday confirmation ──────────────
            if post_open_mode:
                intra = calc_intraday_confirmation(tk, df)
                r["intraday"] = intra
                if not intra["confirmed"]:
                    blocked_log.append(
                        f"  📉 {tk}: Intraday reject — {intra['reason']}"
                    )
                    continue
                # Gunakan harga intraday sebagai entry yang lebih akurat
                if intra["intraday_price"] and intra["intraday_price"] > 0:
                    new_entry = intra["intraday_price"]
                    atr_v     = r["atr_v"]
                    sl_new    = max(round(new_entry - 1.5 * atr_v, 0),
                                    round(float(df["low"].tail(10).min()) * 0.97, 0))
                    tp_new    = round(new_entry + 2.5 * (new_entry - sl_new), 0)
                    r["lp"]     = new_entry
                    r["sl"]     = sl_new
                    r["tp"]     = tp_new
                    r["sl_pct"] = round((new_entry - sl_new) / new_entry * 100, 1)
                    r["tp_pct"] = round((tp_new - new_entry) / new_entry * 100, 1)
                    r["rationale"] += f" · Intraday {intra['intraday_price']:,.0f}"
                print(f"  ✅ {tk}: {r['score']}/100 | VWAP Rp{intra['vwap']:,.0f}"
                      f" | Vol {intra['vol_pace']:.1f}x | Gap {intra['gap_pct']:+.1f}%")
            else:
                print(f"  ✅ {tk}: {r['score']}/100 | {r['signal_type']} | "
                      f"Wyckoff {r['wp']} | VCP {r['vcp_grade']} | "
                      f"CMF {r['cmf_v']:+.3f} | Weekly {r['weekly_score']}")

            candidates.append(r)
            time.sleep(0.3)

        except Exception as e:
            print(f"  ⚠️  {tk}: {e}")
            continue

    return candidates, blocked_log


def scan_once(session: str) -> list:
    print(f"\n{'='*58}")
    print(f"BandarAI Scanner v3 — {session}")
    print(f"Time: {datetime.now().strftime('%H:%M:%S WIB')}")
    print(f"{'='*58}")

    # POST_OPEN = jam 10:00 WIB, konfirmasi intraday
    post_open_mode = (session == "POST_OPEN")

    # Load IHSG
    print("📊 Loading IHSG regime...")
    try:
        raw = yf.download("^JKSE", period="1y", interval="1d",
                           progress=False, auto_adjust=True)
        if raw is not None and not raw.empty:
            if isinstance(raw.columns, pd.MultiIndex):
                raw.columns = raw.columns.get_level_values(0)
            ihsg_df = raw.rename(columns={"Close":"close"})[["close"]].dropna()
        else:
            ihsg_df = None
    except:
        ihsg_df = None

    regime = get_market_regime(ihsg_df)
    print(f"🌏 {regime['regime']} — {regime['desc']}")

    if not regime["ok"]:
        print("⛔ CRASH regime — SEMUA sinyal dihentikan")
        return []

    # Cooldown check
    cooldown_tickers = get_recent_signal_tickers(days=5)
    if cooldown_tickers:
        print(f"⏱️  Cooldown: {', '.join(sorted(cooldown_tickers))}")

    # Threshold
    threshold = MIN_SCORE_TO_SIGNAL
    if regime["regime"] == "RISK_OFF":
        threshold = max(threshold, 75)
    elif regime["regime"] == "CORRECTION":
        threshold = max(threshold, 70)

    # Tentukan watchlist yang dipakai
    try:
        from config import WATCHLIST_CORE, POST_OPEN_CORE_ONLY
        core_list     = WATCHLIST_CORE
        extended_list = [t for t in WATCHLIST if t not in WATCHLIST_CORE]
    except ImportError:
        core_list     = WATCHLIST
        extended_list = []
        POST_OPEN_CORE_ONLY = True

    # ── SCAN CORE DULU ──────────────────────────────────────────────────
    print(f"\n▶ Scanning CORE ({len(core_list)} saham)...")
    if post_open_mode:
        print(f"  Mode: POST_OPEN — intraday confirmation aktif")

    candidates, blocked_log = _scan_tickers(
        core_list, session, ihsg_df, regime,
        threshold, cooldown_tickers, post_open_mode
    )

    # ── SCAN EXTENDED jika CORE belum dapat 3 sinyal ────────────────────
    if not post_open_mode and len(candidates) < 3 and extended_list:
        needed = 3 - len(candidates)
        print(f"\n▶ CORE: {len(candidates)} sinyal."
              f" Scanning EXTENDED {needed} lebih ({len(extended_list)} saham)...")
        ext_cands, ext_blocked = _scan_tickers(
            extended_list, session, ihsg_df, regime,
            threshold + 5,   # threshold lebih ketat untuk extended
            cooldown_tickers, False
        )
        candidates.extend(ext_cands)
        blocked_log.extend(ext_blocked)

    # Log blocked
    if blocked_log:
        print(f"\n  Blocked ({len(blocked_log)}):")
        for b in blocked_log[:6]:
            print(b)
        if len(blocked_log) > 6:
            print(f"  ... dan {len(blocked_log)-6} lainnya")

    # Final sort + limit
    candidates.sort(key=lambda x: x["score"], reverse=True)
    selected = candidates[:3]

    if not selected:
        label = "POST_OPEN (intraday)" if post_open_mode else "harian"
        print(f"\n  ℹ️  Tidak ada setup {label} yang memenuhi semua gate.")
    else:
        print(f"\n  📊 {len(selected)} sinyal final"
              f" dari {len(candidates)} kandidat"
              f" ({len(blocked_log)} blocked)")

    return selected


def prepare_signal_record(r: dict) -> dict:
    date_str  = datetime.now().strftime("%Y%m%d")
    sess_abbr = {"PRE_MARKET":"PRE","MIDDAY":"MID","POST_MARKET":"POST"}.get(r["session"],"SIG")
    return {
        "id"             : f"BMP-{r['ticker']}-{date_str}-{sess_abbr}",
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
        "broker_crossing": r.get("broker_crossing","—"),
        "vcp_grade"      : r["vcp_grade"],
        "rs_interp"      : r["rs_interp"],
        "rationale"      : r["rationale"],
        "timestamp_wib"  : datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


# ══════════════════════════════════════════════════════
#  INTRADAY CONFIRMATION (untuk POST_OPEN session)
#  Dijalankan jam 10:00 WIB setelah 1 jam market buka
# ══════════════════════════════════════════════════════

def calc_intraday_confirmation(ticker: str, df_daily) -> dict:
    """
    Ambil data intraday hari ini dan cek 4 hal:
    1. VWAP — harga di atas VWAP = buyers in control
    2. Volume pace — volume sudah sesuai ekspektasi
    3. Gap direction — tidak gap down atau gap up ekstrem
    4. Price vs open — tidak reversal tajam dari open

    Return: {"confirmed": bool, "reason": str,
             "intraday_price": float, "vwap": float, "vol_pace": float}
    """
    DEFAULT_PASS = {
        "confirmed": True, "reason": "No intraday data — skip check",
        "intraday_price": None, "vwap": 0, "vol_pace": 1.0
    }
    try:
        df_i = yf.download(
            ticker + ".JK", period="1d", interval="5m",
            progress=False, auto_adjust=True
        )
        if df_i is None or df_i.empty or len(df_i) < 4:
            return DEFAULT_PASS

        if isinstance(df_i.columns, pd.MultiIndex):
            df_i.columns = df_i.columns.get_level_values(0)
        df_i = df_i.rename(columns={
            "Open":"open", "High":"high", "Low":"low",
            "Close":"close", "Volume":"volume"
        }).dropna()
        if len(df_i) < 4:
            return DEFAULT_PASS

        # Normalize volume kalau dalam satuan shares
        if df_i["volume"].median() > 5e8:
            df_i["volume"] = df_i["volume"] / 100

        # ── VWAP
        tp_i   = (df_i["high"] + df_i["low"] + df_i["close"]) / 3
        vwap   = float((tp_i * df_i["volume"]).sum() / (df_i["volume"].sum() + 1))
        price  = float(df_i["close"].iloc[-1])
        open_p = float(df_i["open"].iloc[0])

        # ── Volume pace
        # Di jam 10:00 WIB (~60 menit setelah buka), harap ~30% daily vol
        avg_daily = float(df_daily["volume"].tail(10).mean()) if df_daily is not None else 0
        intra_vol = float(df_i["volume"].sum())
        vol_pace  = intra_vol / (avg_daily * 0.30 + 1) if avg_daily > 0 else 1.0

        # ── Gap dari close kemarin
        prev_close = float(df_daily["close"].iloc[-1]) if df_daily is not None else price
        gap_pct    = (open_p - prev_close) / prev_close * 100

        # ── Price vs open
        pvo = (price - open_p) / open_p * 100

        # ── Decision
        fails = []
        if price < vwap * 0.998:
            fails.append(f"Di bawah VWAP Rp{vwap:,.0f}")
        if pvo < -2.5:
            fails.append(f"Reversal dari open -{abs(pvo):.1f}%")
        if gap_pct > 5.0:
            fails.append(f"Gap up ekstrem +{gap_pct:.1f}% (exhaustion)")
        if gap_pct < -3.0:
            fails.append(f"Gap down -{abs(gap_pct):.1f}% (breakdown)")
        if vol_pace < 0.55:
            fails.append(f"Volume pace {vol_pace:.1f}x (kurang konviksi)")

        return {
            "confirmed"      : len(fails) == 0,
            "reason"         : " · ".join(fails) if fails else "Intraday ✅",
            "intraday_price" : round(price, 0),
            "vwap"           : round(vwap, 0),
            "vol_pace"       : round(vol_pace, 2),
            "gap_pct"        : round(gap_pct, 2),
            "pvo"            : round(pvo, 2),
        }
    except Exception as e:
        return {**DEFAULT_PASS, "reason": f"Intraday error: {e}"}
