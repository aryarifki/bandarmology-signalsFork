"""
BandarAI Signal Scanner v2
Komponen: TA + VCP + RS vs IHSG + Weekly Confluence + Fundamental Gate + Goreng Filter + Market Regime
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


# ══════════════════════════════════════════════════════
#  PRICE LOADER
# ══════════════════════════════════════════════════════

def load_price(ticker: str, period: str = "6mo", interval: str = "1d"):
    try:
        df = yf.download(ticker + ".JK", period=period, interval=interval,
                         progress=False, auto_adjust=True)
        if df is None or df.empty or len(df) < 15:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.rename(columns={"Open":"open","High":"high","Low":"low",
                                  "Close":"close","Volume":"volume"})
        df = df[["open","high","low","close","volume"]].dropna()
        if df["volume"].median() > 5e8:
            df["volume"] = df["volume"] / 100
        return df if len(df) >= 15 else None
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

def wyckoff_phase(df, c, o):
    n   = len(df)
    p   = df["close"]
    vol = df["volume"]
    seg = max(n // 3, 5)
    tr  = (p.iloc[-seg:].mean() - p.iloc[:seg].mean()) / (p.iloc[:seg].mean() + 1e-9)
    r20 = (p.tail(20).max() - p.tail(20).min()) / (p.tail(20).mean() + 1e-9)
    vol_ma20  = vol.rolling(20).mean().iloc[-1]
    vol_ratio = vol.tail(5).max() / (vol_ma20 + 1)
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
#  MARKET REGIME (dari IHSG, dipakai untuk semua saham)
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

    if dd < -20 or ret60 < -18:
        return {"regime":"CRASH",       "multiplier":0.0, "ok":False,
                "desc":f"IHSG crash ({dd:.1f}%) — sinyal dihentikan sementara"}
    elif (dd < -10 and not above_ma50) or ret60 < -12:
        return {"regime":"RISK_OFF",    "multiplier":0.80,"ok":True,
                "desc":f"IHSG risk-off ({dd:.1f}%) — threshold lebih ketat"}
    elif dd < -5 and above_ma200 and ret60 < -3:
        return {"regime":"CORRECTION",  "multiplier":0.90,"ok":True,
                "desc":f"IHSG koreksi normal ({dd:.1f}%)"}
    elif abs(ret20) < 4 and ret60 > -5 and above_ma200:
        return {"regime":"SIDEWAYS",    "multiplier":1.00,"ok":True,
                "desc":f"IHSG sideways — stock picking optimal"}
    elif above_ma50 and above_ma200 and ma50_up:
        return {"regime":"BULL",        "multiplier":1.10,"ok":True,
                "desc":f"IHSG uptrend — kondisi ideal"}
    else:
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

        score = 50.0
        score += float(np.clip((rs20 - 100) * 1.5, -20, 20))
        # RS trend (5-day slope)
        sr5 = (float(merged["stock"].iloc[-1]) / float(merged["stock"].iloc[-min(5,n-1)]) - 1)
        ir5 = (float(merged["ihsg"].iloc[-1])  / float(merged["ihsg"].iloc[-min(5,n-1)])  - 1)
        rs_trend_up = sr5 > ir5
        score += 5 if rs_trend_up else -5
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
        # CMF weekly (30pts)
        if cmf_v > 0.10:    score += 30
        elif cmf_v > 0.02:  score += 18
        elif cmf_v > -0.05: score += 10
        elif cmf_v > -0.12: score += 4
        # OBV weekly (25pts)
        score += 25 if obv_up else 0
        # MA20 weekly (25pts)
        if above_ma20 and ma20_slope:   score += 25
        elif above_ma20:                 score += 14
        elif ma20_slope:                 score += 6
        # 8-week trend (20pts)
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
        # fast_info lebih cepat dari .info untuk data dasar
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
        return {
            "pass"   : fails <= 1,
            "penalty": penalty,
            "notes"  : " · ".join(notes) if notes else "Fundamental OK",
        }
    except:
        # Kalau gagal fetch, tidak penalti
        return {"pass":True, "penalty":0, "notes":"—"}


# ══════════════════════════════════════════════════════
#  GORENG / PUMP FILTER
# ══════════════════════════════════════════════════════

def is_goreng_pump(df) -> tuple:
    if df is None or len(df) < 5:
        return False, ""
    lp     = float(df["close"].iloc[-1])
    p3ago  = float(df["close"].iloc[-min(4, len(df)-1)])
    ret3   = (lp - p3ago) / p3ago * 100
    vol    = df["volume"]
    vol_ma = float(vol.rolling(20).mean().iloc[-1]) if len(df) >= 20 else float(vol.mean())
    vr     = float(vol.iloc[-1]) / (vol_ma + 1)

    if ret3 > 7 and vr > 2.5:
        return True, f"Pump: +{ret3:.1f}% dalam 3 hari, volume {vr:.1f}x"
    if vr > 5.5:
        return True, f"Volume spike ekstrem {vr:.1f}x — kemungkinan goreng"
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
#  COMPOSITE SCORE v2
# ══════════════════════════════════════════════════════

def compute_score_v2(df, ticker: str, ihsg_df, regime: dict) -> dict:
    n = len(df)
    p = min(14, max(7, n // 2))

    c_ = cmf(df, p=p)
    o_ = obv(df)
    m_ = mfi(df, p=p)
    a_ = atr(df, p=14)
    wp, wn, wconf = wyckoff_phase(df, c_, o_)

    lp    = float(df["close"].iloc[-1])
    prev  = float(df["close"].iloc[-2])
    chg   = (lp - prev) / prev * 100
    cmf_v = float(c_.iloc[-1]) if not pd.isna(c_.iloc[-1]) else 0.0
    mfi_v = float(m_.iloc[-1]) if not pd.isna(m_.iloc[-1]) else 50.0
    atr_v = float(a_.iloc[-1]) if not pd.isna(a_.iloc[-1]) else lp * 0.02
    obv_up = float(o_.iloc[-1]) > float(o_.iloc[-min(10, n-1)])
    av    = float(df["volume"].tail(20).mean())
    vr    = float(df["volume"].iloc[-1]) / av if av > 0 else 1.0

    # ── TA Score (0-100)
    ts = 50.0
    ts += float(np.clip(cmf_v * 125, -25, 25))
    obv_std = max(float(o_.diff().abs().tail(20).std()), 1.0)
    obv_chg = float(o_.iloc[-1]) - float(o_.iloc[-min(10, n-1)])
    ts += float(np.clip(obv_chg / (obv_std * 3) * 20, -20, 20))
    hi, lo = float(df["high"].iloc[-1]), float(df["low"].iloc[-1])
    cp = (lp - lo) / (hi - lo + 1e-9)
    ts += (cp - 0.5) * 30
    if vr > 1.3: ts += 15 if cp > 0.5 else -15
    if mfi_v < 25:   ts += 18
    elif mfi_v < 40: ts += 8
    elif mfi_v > 75: ts -= 18
    elif mfi_v > 60: ts -= 8
    ts = int(np.clip(round(ts), 0, 100))

    vcp_grade = detect_vcp_grade(df)
    vcp_s     = {"A":90, "B":70, "C":40, "NONE":0}[vcp_grade]
    rs        = calc_rs(df, ihsg_df)
    rs_s      = rs["score"]
    weekly_s  = calc_weekly_confluence(ticker)
    fund      = quick_fundamental_check(ticker)

    # ── Weighted composite
    raw = int(np.clip(round(
        ts        * 0.40 +
        vcp_s     * 0.10 +
        rs_s      * 0.20 +
        weekly_s  * 0.20 +
        50        * 0.10
    ), 0, 100))

    # Fundamental penalty
    raw = max(0, raw - fund["penalty"])

    # ── Mandatory gates
    if wp == "E":            raw = min(raw, 78)
    if wp == "A":            raw = min(raw, 70)
    if cmf_v < -0.15:        raw = min(raw, 70)
    if wconf < 50:           raw = min(raw, raw - int((50 - wconf) * 0.3))
    if vcp_grade == "NONE":  raw = min(raw, 85)
    if weekly_s < 40:        raw = min(raw, 72)
    if rs["rs20"] < 90:      raw = min(raw, 78)

    # ── Regime multiplier
    final = int(np.clip(round(raw * regime.get("multiplier", 1.0)), 0, 100))

    # ── Entry zone (ATR-based)
    sl     = round(lp - 1.5 * atr_v, 0)
    sup    = float(df["low"].tail(10).min())
    sl     = max(sl, round(sup * 0.97, 0))
    sl_pct = (lp - sl) / lp * 100
    tp     = round(lp + 2.0 * (lp - sl), 0)
    tp_pct = (tp - lp) / lp * 100

    # ── Rationale
    r = []
    if cmf_v > 0.10:    r.append(f"CMF {cmf_v:+.3f} (inflow kuat)")
    elif cmf_v > 0.05:  r.append(f"CMF {cmf_v:+.3f} (inflow)")
    if obv_up:          r.append("OBV naik ▲")
    if mfi_v < 30:      r.append(f"MFI {mfi_v:.0f} (oversold)")
    if wp in ("C","D"): r.append(f"Wyckoff {wp} — {wn}")
    if vcp_grade in ("A","B"): r.append(f"VCP Grade {vcp_grade}")
    if rs["interp"].startswith("OUT"): r.append(f"RS vs IHSG: {rs['interp']}")
    if weekly_s >= 65:  r.append(f"Weekly {weekly_s}/100")
    if vr >= 1.5:       r.append(f"Volume {vr:.1f}x")

    return {
        "score"         : final,
        "ts"            : ts,
        "vcp_grade"     : vcp_grade,
        "wp"            : wp,
        "wn"            : wn,
        "wconf"         : wconf,
        "cmf_v"         : round(cmf_v, 4),
        "mfi_v"         : round(mfi_v, 1),
        "obv_dir"       : "Rising ▲" if obv_up else "Falling ▼",
        "vr"            : round(vr, 2),
        "chg"           : round(chg, 2),
        "lp"            : lp,
        "atr_v"         : round(atr_v, 0),
        "sl"            : sl,
        "sl_pct"        : round(sl_pct, 1),
        "tp"            : tp,
        "tp_pct"        : round(tp_pct, 1),
        "rs_interp"     : rs["interp"],
        "rs20"          : rs["rs20"],
        "weekly_score"  : weekly_s,
        "fund_ok"       : fund["pass"],
        "rationale"     : " · ".join(r) if r else "TA confluence",
        "signal_type"   : "STRONG_BUY" if final >= 75 else "BUY",
        "session"       : "",
        "ticker"        : ticker,
        "broker_crossing": "—",
    }


# ══════════════════════════════════════════════════════
#  MAIN SCAN
# ══════════════════════════════════════════════════════

def scan_once(session: str) -> list:
    print(f"\n{'='*55}")
    print(f"BandarAI Scanner v2 — {session}")
    print(f"Time: {datetime.now().strftime('%H:%M:%S WIB')}")
    print(f"{'='*55}")

    # Load IHSG sekali, share ke semua saham
    print("📊 Loading IHSG...")
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
        print("⛔ Regime CRASH — tidak ada sinyal hari ini")
        return []

    candidates = []
    threshold = MIN_SCORE_TO_SIGNAL
    if regime["regime"] == "RISK_OFF":
        threshold = min(78, threshold + 10)

    for tk in WATCHLIST:
        try:
            df = load_price(tk, "6mo")
            if df is None:
                continue

            lp = float(df["close"].iloc[-1])
            if lp < MIN_PRICE_IDR:
                continue
            if float(df["volume"].iloc[-1]) < MIN_VOLUME_LOT:
                continue

            # Goreng filter — skip pump & dump
            is_pump, pump_reason = is_goreng_pump(df)
            if is_pump:
                print(f"  ⚠️  {tk}: Skip — {pump_reason}")
                continue

            # Full score
            r = compute_score_v2(df, tk, ihsg_df, regime)
            r["session"] = session

            if r["score"] < threshold:    continue
            if r["tp_pct"] < TP_MIN_PCT:  continue
            if r["sl_pct"] > SL_MAX_PCT:  continue
            if r["wp"] == "E":            continue

            candidates.append(r)
            print(f"  ✅ {tk}: {r['score']}/100 | {r['signal_type']} | "
                  f"Wyckoff {r['wp']} | VCP {r['vcp_grade']} | "
                  f"RS {r['rs20']} | Weekly {r['weekly_score']}")

            time.sleep(0.3)  # rate limit Yahoo Finance

        except Exception as e:
            print(f"  ⚠️  {tk}: {e}")
            continue

    candidates.sort(key=lambda x: x["score"], reverse=True)
    selected = candidates[:MAX_SIGNALS_PER_SESI]

    if not selected:
        print("  ℹ️  Tidak ada sinyal memenuhi semua kriteria hari ini.")
    else:
        print(f"\n  📊 {len(selected)} sinyal terpilih dari {len(candidates)} kandidat")

    return selected


def prepare_signal_record(r: dict) -> dict:
    date_str  = datetime.now().strftime("%Y%m%d")
    sess_abbr = {"PRE_MARKET":"PRE","MIDDAY":"MID","POST_MARKET":"POST"}.get(r["session"],"SIG")
    return {
        "id"            : f"BMP-{r['ticker']}-{date_str}-{sess_abbr}",
        "ticker"        : r["ticker"],
        "signal_type"   : r["signal_type"],
        "session"       : r["session"],
        "entry_low"     : r["lp"],
        "entry_high"    : round(r["lp"] * 1.01, 0),
        "tp_price"      : r["tp"],
        "sl_price"      : r["sl"],
        "tp_pct"        : r["tp_pct"],
        "sl_pct"        : r["sl_pct"],
        "score"         : r["score"],
        "wyckoff_phase" : f"{r['wp']} — {r['wn']}",
        "cmf_value"     : r["cmf_v"],
        "obv_direction" : r["obv_dir"],
        "broker_crossing": r.get("broker_crossing","—"),
        "vcp_grade"     : r["vcp_grade"],
        "rs_interp"     : r["rs_interp"],
        "rationale"     : r["rationale"],
        "timestamp_wib" : datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
