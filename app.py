import json
from pathlib import Path

import pandas as pd
import streamlit as st
import yfinance as yf
import plotly.graph_objects as go


# ---------------------------------------------------------
# PAGE CONFIG
# ---------------------------------------------------------

st.set_page_config(
    page_title="Stock EMA Analyzer",
    page_icon="📈",
    layout="wide"
)


# ---------------------------------------------------------
# LOAD WATCHLIST
# ---------------------------------------------------------

WATCHLIST_FILE = Path("watchlist.json")


def load_watchlist():
    if not WATCHLIST_FILE.exists():
        st.error("watchlist.json was not found.")
        st.stop()

    with open(WATCHLIST_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


watchlist = load_watchlist()

stocks = watchlist.get("stocks", [])
settings = watchlist.get("settings", {})

EMA_PERIODS = settings.get("ema_periods", [100, 200])


# ---------------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------------

def calculate_ema(data, period):
    return data["Close"].ewm(
        span=period,
        adjust=False
    ).mean()


@st.cache_data(ttl=300)
def get_stock_data(ticker, period="2y"):
    """
    Download historical stock data from Yahoo Finance.
    Cached for 5 minutes to avoid unnecessary repeated downloads.
    """

    data = yf.download(
        ticker,
        period=period,
        interval="1d",
        auto_adjust=False,
        progress=False
    )

    if data.empty:
        return None

    # yfinance can sometimes return MultiIndex columns
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)

    data = data.dropna(subset=["Close"])

    return data


def get_latest_metrics(ticker):
    """
    Get latest price and EMA values for the comparison table.
    """

    data = get_stock_data(ticker, "2y")

    if data is None or data.empty:
        return None

    latest_price = float(data["Close"].iloc[-1])

    result = {
        "Price": latest_price
    }

    for period in EMA_PERIODS:
        ema = calculate_ema(data, period)
        latest_ema = float(ema.iloc[-1])

        distance = (
            (latest_price - latest_ema)
            / latest_ema
        ) * 100

        result[f"EMA {period}"] = latest_ema
        result[f"Distance from EMA {period}"] = distance

    return result


# ---------------------------------------------------------
# HEADER
# ---------------------------------------------------------

st.title("📈 Stock EMA Analyzer")

st.write(
    "Select one or more stocks to view their current EMA metrics "
    "and historical price charts."
)


# ---------------------------------------------------------
# STOCK SELECTION
# ---------------------------------------------------------

stock_names = [stock["name"] for stock in stocks]

stock_lookup = {
    stock["name"]: stock["ticker"]
    for stock in stocks
}


selected_stocks = st.multiselect(
    "Select stocks",
    options=stock_names,
    default=stock_names[:3],
    help="Select one or more stocks from your watchlist."
)


if not selected_stocks:
    st.info("Select at least one stock to continue.")
    st.stop()


selected_tickers = [
    stock_lookup[name]
    for name in selected_stocks
]


# ---------------------------------------------------------
# REFRESH
# ---------------------------------------------------------

col1, col2 = st.columns([1, 5])

with col1:
    if st.button("🔄 Refresh data"):
        st.cache_data.clear()
        st.rerun()


# ---------------------------------------------------------
# CURRENT STOCK METRICS
# ---------------------------------------------------------

st.subheader("📊 Current Overview")

overview_rows = []

with st.spinner("Fetching stock data..."):

    for stock_name in selected_stocks:

        ticker = stock_lookup[stock_name]

        metrics = get_latest_metrics(ticker)

        if metrics is None:
            st.warning(
                f"Could not retrieve data for {stock_name} ({ticker})."
            )
            continue

        row = {
            "Stock": stock_name,
            "Ticker": ticker,
            "Price": metrics["Price"]
        }

        for period in EMA_PERIODS:
            row[f"EMA {period}"] = metrics[f"EMA {period}"]
            row[f"Distance from EMA {period}"] = (
                metrics[f"Distance from EMA {period}"]
            )

        overview_rows.append(row)


if overview_rows:

    overview_df = pd.DataFrame(overview_rows)

    # Format table values
    display_df = overview_df.copy()

    display_df["Price"] = display_df["Price"].map(
        lambda x: f"₹{x:,.2f}"
    )

    for period in EMA_PERIODS:

        display_df[f"EMA {period}"] = display_df[
            f"EMA {period}"
        ].map(
            lambda x: f"₹{x:,.2f}"
        )

        display_df[
            f"Distance from EMA {period}"
        ] = display_df[
            f"Distance from EMA {period}"
        ].map(
            lambda x: f"{x:+.2f}%"
        )

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True
    )


# ---------------------------------------------------------
# CHART SETTINGS
# ---------------------------------------------------------

st.subheader("📈 Historical Charts")

chart_period = st.selectbox(
    "Chart period",
    options=[
        ("3 months", "3mo"),
        ("6 months", "6mo"),
        ("1 year", "1y"),
        ("2 years", "2y"),
        ("5 years", "5y")
    ],
    format_func=lambda x: x[0],
    index=2
)

period_code = chart_period[1]


# ---------------------------------------------------------
# CHARTS
# ---------------------------------------------------------

for stock_name in selected_stocks:

    ticker = stock_lookup[stock_name]

    with st.spinner(f"Loading {stock_name}..."):

        data = get_stock_data(
            ticker,
            period_code
        )

    if data is None or data.empty:
        st.warning(
            f"No chart data available for {stock_name}."
        )
        continue

    # Calculate EMAs
    for ema_period in EMA_PERIODS:
        data[f"EMA {ema_period}"] = calculate_ema(
            data,
            ema_period
        )

    # -----------------------------------------------------
    # CHART
    # -----------------------------------------------------

    fig = go.Figure()

    # Price
    fig.add_trace(
        go.Scatter(
            x=data.index,
            y=data["Close"],
            mode="lines",
            name="Price"
        )
    )

    # EMA lines
    for ema_period in EMA_PERIODS:

        fig.add_trace(
            go.Scatter(
                x=data.index,
                y=data[f"EMA {ema_period}"],
                mode="lines",
                name=f"EMA {ema_period}"
            )
        )

    fig.update_layout(
        title=f"{stock_name} ({ticker})",
        xaxis_title="Date",
        yaxis_title="Price (₹)",
        hovermode="x unified",
        height=500,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0
        )
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )