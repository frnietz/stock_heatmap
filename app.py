import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import datetime as dt
from datetime import timedelta
import yfinance as yf

st.set_page_config(page_title="BIST30 Stock Returns Heatmap", layout="wide")
st.title("🇹🇷 BIST30 Stock Returns Heatmap (Size = Market Cap)")

# -------- Intervals (calendar-day lookback) --------
INTERVALS = {
    "1 Day": 1,
    "5 Day": 5,        # replaces 1 Week (7d) per original request
    "1 Month": 30,
    "3 Months": 90,
    "6 Months": 180,
    "1 Year": 365,
}
selected_interval = st.selectbox("Select Time Interval", list(INTERVALS.keys()), index=2)
days = INTERVALS[selected_interval]

# -------- BIST30 tickers (editable) --------
bist30_tickers = [
    "AKBNK.IS", "ARCLK.IS", "ASELS.IS", "BIMAS.IS", "EKGYO.IS",
    "EREGL.IS", "FROTO.IS", "GARAN.IS", "HALKB.IS", "ISCTR.IS",
    "KCHOL.IS", "KOZAA.IS", "KOZAL.IS", "KRDMD.IS", "PETKM.IS",
    "PGSUS.IS", "SAHOL.IS", "SASA.IS", "SISE.IS", "TAVHL.IS",
    "TCELL.IS", "THYAO.IS", "TOASO.IS", "TSKB.IS", "TUPRS.IS",
    "VAKBN.IS", "YKBNK.IS", "VESTL.IS", "AKSEN.IS", "TTKOM.IS"
]

# -------- Caching (Streamlit 1.10+ uses cache_data) --------
if hasattr(st, "cache_data"):
    cache_dec = st.cache_data
else:
    cache_dec = st.cache  # fallback for older Streamlit

@cache_dec(ttl=3600, show_spinner=False)
def fetch_stock_data(tickers: list[str], max_days: int) -> dict:
    """Download daily adjusted close per ticker for (~max_days) days."""
    out = {}
    for t in tickers:
        try:
            # pull enough days to cover lookback plus holidays
            df = yf.download(t, period=f"{max_days}d", interval="1d", auto_adjust=True, progress=False)
            if not df.empty and "Close" in df.columns:
                out[t] = df.copy()
        except Exception as e:
            # keep going even if one ticker fails
            out[t] = pd.DataFrame()
    return out

@cache_dec(ttl=3600, show_spinner=False)
def fetch_market_caps(tickers: list[str]) -> dict:
    """Get market caps via fast_info first; fallback to info / shares*price."""
    mktcaps = {}
    for t in tickers:
        cap = None
        try:
            tk = yf.Ticker(t)
            # fast_info is faster and avoids some .info build-time deps
            try:
                fi = dict(tk.fast_info)
                cap = fi.get("market_cap")
                if not cap:
                    # fallback from .info (slower / sometimes flaky)
                    info = tk.info
                    cap = info.get("marketCap")
                    if not cap:
                        shares = info.get("sharesOutstanding")
                        price = info.get("regularMarketPrice")
                        if shares and price:
                            cap = float(shares) * float(price)
            except Exception:
                # last-resort fallback
                info = tk.info
                cap = info.get("marketCap")
        except Exception:
            pass
        # final guard
        if not cap or (isinstance(cap, (int, float)) and cap <= 0):
            cap = np.nan
        mktcaps[t] = float(cap) if pd.notna(cap) else np.nan
    return mktcaps

def compute_calendar_return(close_series: pd.Series, lookback_days: int) -> float | None:
    """% return from last available close back to the last close on/before (last_date - lookback_days)."""
    if close_series is None or close_series.dropna().empty:
        return None
    s = close_series.dropna()
    last_dt = s.index.max()
    target_dt = last_dt - timedelta(days=lookback_days)
    # pick last available close on/before target date
    past = s.loc[:target_dt].tail(1)
    if past.empty:
        return None
    last_price = float(s.loc[last_dt])
    past_price = float(past.values[-1])
    if past_price == 0:
        return None
    return (last_price / past_price - 1.0) * 100.0

with st.spinner("Fetching data..."):
