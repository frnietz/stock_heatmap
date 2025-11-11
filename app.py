# bist30_heatmap_app.py

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import yfinance as yf
from datetime import timedelta

st.set_page_config(page_title="BIST-30 Heatmap", layout="wide")

st.title("🇹🇷 BIST-30 Heatmap of Returns (Size = Market Cap)")
st.caption("Data source: Yahoo Finance via yfinance. Market caps and prices are fetched live. If a ticker has missing data, it will be skipped.")

# --- BIST-30 tickers (editable) ---
TICKERS = {
    "AKBNK.IS": "Akbank",
    "ARCLK.IS": "Arçelik",
    "ASELS.IS": "Aselsan",
    "BIMAS.IS": "BİM",
    "EKGYO.IS": "Emlak Konut",
    "EREGL.IS": "Ereğli Demir Çelik",
    "FROTO.IS": "Ford Otosan",
    "GARAN.IS": "Garanti BBVA",
    "HEKTS.IS": "Hektaş",
    "ISCTR.IS": "İş Bankası (C)",
    "KCHOL.IS": "Koç Holding",
    "KRDMD.IS": "Kardemir (D)",
    "KOZAL.IS": "Koza Altın",
    "PETKM.IS": "Petkim",
    "PGSUS.IS": "Pegasus",
    "SAHOL.IS": "Sabancı Holding",
    "SASA.IS": "SASA Polyester",
    "SISE.IS": "Şişecam",
    "TAVHL.IS": "TAV Havalimanları",
    "TCELL.IS": "Turkcell",
    "THYAO.IS": "Türk Hava Yolları",
    "TOASO.IS": "Tofaş",
    "TTKOM.IS": "Türk Telekom",
    "TTRAK.IS": "Türk Traktör",
    "TUPRS.IS": "Tüpraş",
    "VESTL.IS": "Vestel",
    "YKBNK.IS": "Yapı Kredi",
    "ALARK.IS": "Alarko Holding",
    "AGHOL.IS": "AG Anadolu Grubu",
    "KONTR.IS": "Kontrolmatik"
}

# You can customize the default selection
DEFAULT_SELECTION = list(TICKERS.keys())

# --- Sidebar controls ---
with st.sidebar:
    st.header("Controls")
    interval_label = st.selectbox(
        "Return Interval",
        ["1 Day", "5 Day", "1 Month", "3 Months", "6 Months", "1 Year"],
        index=2,
    )
    tickers_selected = st.multiselect(
        "Tickers",
        options=list(TICKERS.keys()),
        default=DEFAULT_SELECTION,
        help="Edit the BIST-30 list above in the source if needed.",
    )
    st.markdown("---")
    st.caption("Tip: If some market caps are missing, the app will try to approximate using price × shares outstanding when available.")

# Map interval to calendar-day lookback
LOOKBACK_DAYS = {
    "1 Day": 1,
    "5 Day": 5,
    "1 Month": 30,
    "3 Months": 90,
    "6 Months": 180,
    "1 Year": 365,
}

lookback_days = LOOKBACK_DAYS[interval_label]

@st.cache_data(show_spinner=False)
def fetch_history(symbols: list[str], max_days: int = 400) -> pd.DataFrame:
    """Download daily Adjusted Close for all symbols for ~max_days calendar days."""
    # We use a long-enough period to cover the 1Y lookback + holidays
    data = yf.download(
        symbols,
        period=f"{max_days}d",
        interval="1d",
        auto_adjust=True,
        progress=False,
        group_by="ticker",
        threads=True,
    )
    return data

@st.cache_data(show_spinner=False)
def fetch_fast_info(symbol: str) -> dict:
    t = yf.Ticker(symbol)
    # Prefer fast_info for speed & reliability
    fi = {}
    try:
        fi = dict(t.fast_info)
    except Exception:
        pass
    # Fallbacks from .info if needed
    if not fi.get("market_cap"):
        try:
            info = t.info
            fi["market_cap"] = info.get("marketCap")
            if not fi.get("shares_outstanding"):
                fi["shares_outstanding"] = info.get("sharesOutstanding")
            if not fi.get("last_price"):
                fi["last_price"] = info.get("regularMarketPrice")
        except Exception:
            pass
    return fi


def compute_return(series: pd.Series, days_back: int) -> float | None:
    """Compute % return from the last available close back to the close on or before last_date - days_back.
    Returns a float (e.g., 0.05 for +5%) or None if not computable.
    """
    if series is None or series.dropna().empty:
        return None
    series = series.dropna()
    last_date = series.index.max()
    target_date = last_date - timedelta(days=days_back)
    # Find the last available price on or before target_date
    try:
        past_price = series.loc[:target_date].tail(1)
        if past_price.empty:
            return None
        past_price = float(past_price.values[0])
        last_price = float(series.loc[last_date])
        if past_price == 0:
            return None
        return (last_price / past_price) - 1.0
    except Exception:
        return None


# --- Fetch data ---
symbols = tickers_selected
raw = fetch_history(symbols, max_days=430)

rows = []
for sym in symbols:
    # Pull the Adjusted Close for this symbol
    try:
        if len(symbols) == 1:
            # yfinance returns a simple DF when a single symbol is used
            close_s = raw["Close"]
        else:
            close_s = raw[(sym, "Close")]
    except Exception:
        close_s = pd.Series(dtype=float)

    # Compute return
    ret = compute_return(close_s, lookback_days)

    # Get market cap (prefer fast_info)
    fi = fetch_fast_info(sym)
    mcap = fi.get("market_cap")

    # If market cap missing, approximate from shares × last price
    if not mcap:
        shares = fi.get("shares_outstanding")
        last_price = fi.get("last_price")
        if shares and last_price:
            mcap = float(shares) * float(last_price)

    rows.append({
        "Ticker": sym,
        "Name": TICKERS.get(sym, sym.replace(".IS", "")),
        "Return": ret,
        "MarketCap": mcap if mcap and mcap > 0 else np.nan,
    })


df = pd.DataFrame(rows)

# Drop rows with missing return or mcap
valid = df.dropna(subset=["Return", "MarketCap"]).copy()

if valid.empty:
    st.warning("No valid data to display. Try a different interval or check your internet connection.")
    st.stop()

# Compute color range symmetric around 0 for visual balance
max_abs = float(np.nanmax(np.abs(valid["Return"].values)))
# Avoid zero range
if max_abs == 0:
    max_abs = 0.01

# Format helper columns for hover
valid["ReturnPct"] = (valid["Return"] * 100).round(2)
valid["MarketCapBn"] = (valid["MarketCap"] / 1e9).round(2)

# Plot treemap (size = MarketCap, color = Return)
fig = px.treemap(
    valid,
    path=[px.Constant("BIST-30"), "Name", "Ticker"],
    values="MarketCap",
    color="Return",
    color_continuous_scale="RdYlGn",
    range_color=[-max_abs, max_abs],
)
fig.update_traces(
    hovertemplate=(
        "<b>%{label}</b> (%{customdata[0]})<br>"
        + f"Interval: {interval_label}<br>"
        + "Return: %{customdata[1]}%<br>"
        + "Mkt Cap: %{customdata[2]}B TRY (approx)<br>"
        + "<extra></extra>"
    ),
    customdata=np.stack([valid["Ticker"], valid["ReturnPct"], valid["MarketCapBn"]], axis=-1),
)
fig.update_layout(margin=dict(t=30, l=0, r=0, b=0))

st.plotly_chart(fig, use_container_width=True)

# Display data table below
with st.expander("Show underlying data"):
    show_cols = ["Ticker", "Name", "ReturnPct", "MarketCapBn"]
    st.dataframe(
        valid[show_cols]
        .rename(columns={"ReturnPct": f"Return % ({interval_label})", "MarketCapBn": "Market Cap (B)"})
        .sort_values("MarketCapBn", ascending=False),
        use_container_width=True,
    )

st.caption("Note: Returns are computed using calendar-day lookbacks (e.g., ~30, 90, 180, 365 days) to the most recent available close before that date. This may differ slightly from exact trading-day counts.")
