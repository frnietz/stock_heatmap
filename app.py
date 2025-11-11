import streamlit as st
import pandas as pd
import plotly.express as px
import datetime as dt
import yfinance as yf  # Assuming you're using yfinance for stock data

# Check if cache_data is available, otherwise use the older cache decorator
if hasattr(st, 'cache_data'):
    # For newer Streamlit versions (1.10.0+)
    @st.cache_data(ttl=3600)  # Cache for 1 hour
    def fetch_stock_data(tickers, days):
        stock_data = {}
        for ticker in tickers:
            try:
                data = yf.download(ticker, period=f"{days+5}d")
                if not data.empty:
                    stock_data[ticker] = data
            except Exception as e:
                st.warning(f"Error fetching data for {ticker}: {e}")
        return stock_data
    
    @st.cache_data(ttl=3600)
    def fetch_market_caps(tickers):
        market_caps = {}
        for ticker in tickers:
            try:
                stock = yf.Ticker(ticker)
                market_cap = stock.info.get('marketCap', 1000000)
                market_caps[ticker] = market_cap
            except:
                market_caps[ticker] = 1000000
        return market_caps
else:
    # For older Streamlit versions
    @st.cache(ttl=3600)  # Cache for 1 hour
    def fetch_stock_data(tickers, days):
        stock_data = {}
        for ticker in tickers:
            try:
                data = yf.download(ticker, period=f"{days+5}d")
                if not data.empty:
                    stock_data[ticker] = data
            except Exception as e:
                st.warning(f"Error fetching data for {ticker}: {e}")
        return stock_data
    
    @st.cache(ttl=3600)
    def fetch_market_caps(tickers):
        market_caps = {}
        for ticker in tickers:
            try:
                stock = yf.Ticker(ticker)
                market_cap = stock.info.get('marketCap', 1000000)
                market_caps[ticker] = market_cap
            except:
                market_caps[ticker] = 1000000
        return market_caps

# App title
st.title("BIST30 Stock Returns Heatmap")

# Time interval selection
interval_options = {
    "1 Day": 1,
    "1 Week": 7,
    "1 Month": 30,
    "3 Months": 90,
    "6 Months": 180,
    "1 Year": 365
}
selected_interval = st.selectbox("Select Time Interval", list(interval_options.keys()))
days = interval_options[selected_interval]

# Define BIST30 tickers
bist30_tickers = [
    "AKBNK.IS", "ARCLK.IS", "ASELS.IS", "BIMAS.IS", "EKGYO.IS",
    "EREGL.IS", "FROTO.IS", "GARAN.IS", "HALKB.IS", "ISCTR.IS",
    "KCHOL.IS", "KOZAA.IS", "KOZAL.IS", "KRDMD.IS", "PETKM.IS",
    "PGSUS.IS", "SAHOL.IS", "SASA.IS", "SISE.IS", "TAVHL.IS",
    "TCELL.IS", "THYAO.IS", "TOASO.IS", "TSKB.IS", "TUPRS.IS",
    "VAKBN.IS", "YKBNK.IS", "VESTL.IS", "AKSEN.IS", "TTKOM.IS"
]

# Fetch data
with st.spinner("Fetching stock data..."):
    stock_data = fetch_stock_data(bist30_tickers, days)
    market_caps = fetch_market_caps(bist30_tickers)

# Calculate returns
returns = {}
for ticker, data in stock_data.items():
    if len(data) >= 2:
        # Calculate return for the selected period
        start_price = data['Close'].iloc[-min(len(data), days+1)]
        end_price = data['Close'].iloc[-1]
        returns[ticker] = ((end_price - start_price) / start_price) * 100

# Prepare data for heatmap
if returns:
    heatmap_data = []
    for ticker, ret in returns.items():
        # Clean ticker name for display
        display_name = ticker.replace('.IS', '')
        
        # Get market cap (use a default if not available)
        market_cap = market_caps.get(ticker, 1000000)
        
        heatmap_data.append({
            'Ticker': display_name,
            'Return (%)': round(ret, 2),
            'Market Cap': market_cap
        })
    
    df = pd.DataFrame(heatmap_data)
    
    # Create heatmap using Plotly
    fig = px.treemap(
        df,
        path=['Ticker'],
        values='Market Cap',
        color='Return (%)',
        color_continuous_scale=['red', 'white', 'green'],
        color_continuous_midpoint=0,
        title=f'BIST30 Returns Over {selected_interval} (Box Size = Market Cap)'
    )
    
    # Update hover information
    fig.update_traces(
        hovertemplate='<b>%{label}</b><br>Return: %{color:.2f}%<br>Market Cap: %{value:,.0f} TL<extra></extra>'
    )
    
    # Display the heatmap
    st.plotly_chart(fig, use_container_width=True)
    
    # Display data table
    st.subheader("BIST30 Returns Data")
    sorted_df = df.sort_values('Return (%)', ascending=False)
    st.dataframe(sorted_df, use_container_width=True)
else:
    st.error("Failed to fetch sufficient data for BIST30 stocks. Please try again later.")

# Add information footer
st.markdown("---")
st.markdown("**Note:** Market cap data and returns are fetched from Yahoo Finance. Some values might be approximate.")
st.markdown("Data is refreshed hourly. Last update: " + dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
