"""
Database layer — pakai CSV yang disimpan di GitHub repo.
Kenapa CSV bukan SQLite? Karena GitHub Actions tidak bisa
menyimpan file binary antar-run. CSV bisa di-commit ke repo.
"""
import os
import pandas as pd
from datetime import datetime
from config import SIGNALS_CSV

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


def _load() -> pd.DataFrame:
    """Load signals CSV. Buat baru kalau belum ada."""
    os.makedirs(os.path.dirname(SIGNALS_CSV), exist_ok=True)
    if os.path.exists(SIGNALS_CSV):
        try:
            df = pd.read_csv(SIGNALS_CSV, dtype=str)
            # Ensure all columns exist
            for col in COLUMNS:
                if col not in df.columns:
                    df[col] = ""
            return df[COLUMNS]
        except Exception as e:
            print(f"  ⚠️  CSV load error: {e} — creating fresh")
    return pd.DataFrame(columns=COLUMNS)


def _save(df: pd.DataFrame):
    """Simpan DataFrame ke CSV."""
    os.makedirs(os.path.dirname(SIGNALS_CSV), exist_ok=True)
    df[COLUMNS].to_csv(SIGNALS_CSV, index=False)


def save_signal(signal: dict) -> bool:
    """
    Simpan sinyal baru. Return False jika ID sudah ada (duplicate).
    """
    df = _load()
    if not df.empty and signal["id"] in df["id"].values:
        return False   # duplicate

    row = {col: signal.get(col, "") for col in COLUMNS}
    row["status"] = "OPEN"
    new_row = pd.DataFrame([row])
    df = pd.concat([df, new_row], ignore_index=True)
    _save(df)
    return True


def update_signal_outcome(signal_id: str, status: str,
                           exit_price: float, pnl_pct: float,
                           days_held: int, notes: str = "") -> bool:
    """Update sinyal OPEN → WIN / LOSS / EXPIRED."""
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
    """Return list of dict untuk sinyal OPEN."""
    df = _load()
    if df.empty:
        return []
    open_df = df[df["status"] == "OPEN"]
    return open_df.to_dict("records")


def get_all_signals_df() -> pd.DataFrame:
    """Return semua sinyal sebagai DataFrame untuk dashboard."""
    df = _load()
    # Convert numeric columns
    for col in ["entry_low", "entry_high", "tp_price", "sl_price",
                "tp_pct", "sl_pct", "score", "exit_price", "pnl_pct", "days_held"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.sort_values("timestamp_wib", ascending=False).reset_index(drop=True)


def get_stats() -> dict:
    """Hitung statistik keseluruhan."""
    df = get_all_signals_df()
    if df.empty:
        return {"total": 0, "wins": 0, "losses": 0, "expired": 0,
                "open_count": 0, "win_rate": 0, "avg_pnl": 0,
                "avg_win": 0, "avg_loss": 0, "best_trade": 0, "worst_trade": 0}

    wins     = int((df["status"] == "WIN").sum())
    losses   = int((df["status"] == "LOSS").sum())
    expired  = int((df["status"] == "EXPIRED").sum())
    open_c   = int((df["status"] == "OPEN").sum())
    total    = len(df)
    closed   = wins + losses

    closed_df = df[df["status"].isin(["WIN", "LOSS"])]
    win_df    = df[df["status"] == "WIN"]
    loss_df   = df[df["status"] == "LOSS"]

    return {
        "total"       : total,
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
