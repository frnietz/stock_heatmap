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
    "5 Day": 5,
    "1 Month": 30,
    "3 Months": 90,
    "6 Months": 180,
    "1 Year": 365,
}
selected_interval = st.selectbox("Select Time Interval", list(INTERVALS.keys()), index=2)
days = INTERVALS[selected_interval]

# -------- BIST30 tickers --------
bist30_tickers = [
    "AKBNK.IS", "ARCLK.IS", "ASELS.IS", "BIMAS.IS", "EKGYO.IS",
    "EREGL.IS", "FROTO.IS", "GARAN.IS", "HALKB.IS", "ISCTR.IS",
    "KCHOL.IS", "KOZAA.IS", "KOZAL.IS", "KRDMD.IS", "PETKM.IS",
    "PGSUS.IS", "SAHOL.IS", "SASA.IS", "SISE.IS", "TAVHL.IS",
    "TCELL.IS", "THYAO.IS", "TOASO.IS", "TSKB.IS", "TUPRS.IS",
    "VAKBN.IS", "YKBNK.IS", "VESTL.IS", "AKSEN.IS", "TTKOM.IS"
]

# -------- Cache selection --------
if hasattr(st, "cache_data"):
    cache_dec = st.cache_data
else:
    cache_dec = st.cache

@cache_dec(ttl=3600, show_spinner=False)
def fetch_stock_data(tickers: list[str], max_days: int) -> dict:
    out = {}
    for t in tickers:
        try:
            df = yf.download(t, period=f"{max_days}d", interval="1d", auto_adjust=True, progress=False)
            if not df.empty:
                out[t] = df.copy()
        except Exception:
            out[t] = pd.DataFrame()
    return out

@cache_dec(ttl=3600, show_spinner=False)
def fetch_market_caps(tickers: list[str]) -> dict:
    caps = {}
    for t in tickers:
        cap = None
        try:
            tk = yf.Ticker(t)
            try:
                fi = dict(tk.fast_info)
                cap = fi.get("market_cap")
                if not cap:
                    info = tk.info
                    cap = info.get("marketCap")
                    if not cap:
                        shares = info.get("sharesOutstanding")
                        price = info.get("regularMarketPrice")
                        if shares and price:
                            cap = float(shares) * float(price)
            except Exception:
                info = tk.info
                cap = info.get("marketCap")
        except Exception:
            pass
        if not cap or (isinstance(cap, (int, float)) and cap <= 0):
            cap = np.nan
        caps[t] = float(cap) if pd.notna(cap) else np.nan
    return caps

def compute_calendar_return(close_series: pd.Series, lookback_days: int) -> float | None:
    if close_series is None or close_series.dropna().empty:
        return None
    s = close_series.dropna()
    last_dt = s.index.max()
    target_dt = last_dt - timedelta(days=lookback_days)
    past = s.loc[:target_dt].tail(1)
    if past.empty:
        return None
    last_price = float(s.loc[last_dt])
    past_price = float(past.values[-1])
    if past_price == 0:
        return None
    return (last_price / past_price - 1.0) * 100.0

# ---------------- Fetching ----------------
with st.spinner("Fetching data..."):
    stock_data = fetch_stock_data(bist30_tickers, max_days=430)
    market_caps = fetch_market_caps(bist30_tickers)

# ---------------- Compute returns ----------------
rows = []
for tkr, df in stock_data.items():
    if df is None or df.empty:
        continue
    ret = compute_calendar_return(df["Close"], days)
    cap = market_caps.get(tkr, np.nan)
    if ret is not None and pd.notna(cap):
        rows.append({
            "Ticker": tkr.replace(".IS", ""),
            "Return (%)": round(ret, 2),
            "Market Cap": float(cap)
        })

if not rows:
    st.error("No sufficient data to compute returns. Try another interval.")
    st.stop()

df = pd.DataFrame(rows)

# ---------------- Plot ----------------
max_abs = float(np.nanmax(np.abs(df["Return (%)"].values))) if not df.empty else 1.0
if max_abs == 0:
    max_abs = 0.01

fig = px.treemap(
    df,
    path=[px.Constant("BIST30"), "Ticker"],
    values="Market Cap",
    color="Return (%)",
    color_continuous_scale="RdYlGn",
    range_color=[-max_abs, max_abs],
    title=f"BIST30 Returns over {selected_interval} (Box Size = Market Cap)"
)
fig.update_traces(
    hovertemplate="<b>%{label}</b><br>Return: %{color:.2f}%<br>Market Cap: %{value:,.0f}<extra></extra>"
)
fig.update_layout(margin=dict(t=30, l=0, r=0, b=0))
st.plotly_chart(fig, use_container_width=True)

# ---------------- Data table ----------------
st.subheader("Underlying Data")
st.dataframe(df.sort_values("Return (%)", ascending=False), use_container_width=True)

st.markdown("---")
st.caption("Returns use calendar-day lookbacks; market caps from Yahoo Finance (fast_info). Approximate values.")
st.caption("Last update: " + dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
