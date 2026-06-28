"""
Database layer — pakai CSV yang disimpan di GitHub repo.
FIX: Tambah fungsi init_db() yang dibutuhkan track_record.py
"""
import os
import pandas as pd
from datetime import datetime

SIGNALS_CSV = "data/signals.csv"

COLUMNS = [
    "id", "ticker", "signal_type", "session",
    "entry_low", "entry_high", "tp_price", "sl_price",
    "tp_pct", "sl_pct", "score",
    "wyckoff_phase", "cmf_value", "obv_direction",
    "broker_crossing", "vcp_grade", "rs_interp",
    "rationale", "timestamp_wib",
    "status", "exit_price", "exit_timestamp",
    "pnl_pct", "days_held", "notes",
]


def init_db():
    """Buat folder data/ dan signals.csv kosong kalau belum ada."""
    os.makedirs("data", exist_ok=True)
    if not os.path.exists(SIGNALS_CSV):
        pd.DataFrame(columns=COLUMNS).to_csv(SIGNALS_CSV, index=False)


def _load() -> pd.DataFrame:
    """Load signals CSV. Buat baru kalau belum ada."""
    init_db()
    try:
        df = pd.read_csv(SIGNALS_CSV, dtype=str)
        for col in COLUMNS:
            if col not in df.columns:
                df[col] = ""
        return df[COLUMNS]
    except Exception:
        return pd.DataFrame(columns=COLUMNS)


def _save(df: pd.DataFrame):
    os.makedirs("data", exist_ok=True)
    df[COLUMNS].to_csv(SIGNALS_CSV, index=False)


def save_signal(signal: dict) -> bool:
    df = _load()
    if not df.empty and signal["id"] in df["id"].values:
        return False
    row = {col: signal.get(col, "") for col in COLUMNS}
    row["status"] = "OPEN"
    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    _save(df)
    return True


def update_signal_outcome(signal_id: str, status: str,
                           exit_price: float, pnl_pct: float,
                           days_held: int, notes: str = "") -> bool:
    df = _load()
    mask = (df["id"] == signal_id) & (df["status"] == "OPEN")
    if not mask.any():
        return False
    df.loc[mask, "status"]         = status
    df.loc[mask, "exit_price"]     = str(exit_price)
    df.loc[mask, "exit_timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    df.loc[mask, "pnl_pct"]        = str(round(pnl_pct, 2))
    df.loc[mask, "days_held"]      = str(days_held)
    df.loc[mask, "notes"]          = notes
    _save(df)
    return True


def get_open_signals() -> list:
    df = _load()
    if df.empty:
        return []
    return df[df["status"] == "OPEN"].to_dict("records")


def get_all_signals_df() -> pd.DataFrame:
    df = _load()
    for col in ["entry_low", "entry_high", "tp_price", "sl_price",
                "tp_pct", "sl_pct", "score", "exit_price", "pnl_pct", "days_held"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.sort_values("timestamp_wib", ascending=False).reset_index(drop=True)


def get_stats() -> dict:
    df = get_all_signals_df()
    if df.empty:
        return {
            "total": 0, "wins": 0, "losses": 0, "expired": 0,
            "open_count": 0, "win_rate": 0, "avg_pnl": 0,
            "avg_win": 0, "avg_loss": 0, "best_trade": 0,
            "worst_trade": 0, "total_closed": 0,
        }
    wins      = int((df["status"] == "WIN").sum())
    losses    = int((df["status"] == "LOSS").sum())
    expired   = int((df["status"] == "EXPIRED").sum())
    open_c    = int((df["status"] == "OPEN").sum())
    closed    = wins + losses
    closed_df = df[df["status"].isin(["WIN", "LOSS"])]
    win_df    = df[df["status"] == "WIN"]
    loss_df   = df[df["status"] == "LOSS"]
    return {
        "total"       : len(df),
        "wins"        : wins,
        "losses"      : losses,
        "expired"     : expired,
        "open_count"  : open_c,
        "total_closed": closed,
        "win_rate"    : round(wins / closed * 100, 1) if closed > 0 else 0,
        "avg_pnl"     : round(float(closed_df["pnl_pct"].mean()), 2) if not closed_df.empty else 0,
        "avg_win"     : round(float(win_df["pnl_pct"].mean()), 2)    if not win_df.empty    else 0,
        "avg_loss"    : round(float(loss_df["pnl_pct"].mean()), 2)   if not loss_df.empty   else 0,
        "best_trade"  : round(float(win_df["pnl_pct"].max()), 2)     if not win_df.empty    else 0,
        "worst_trade" : round(float(loss_df["pnl_pct"].min()), 2)    if not loss_df.empty   else 0,
    }
