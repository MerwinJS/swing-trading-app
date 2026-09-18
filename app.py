import json
from pathlib import Path

import pandas as pd
import streamlit as st
import yfinance as yf
import plotly.graph_objects as go


# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="Stock EMA Analyzer",
    page_icon="📈",
    layout="wide"
)


# =========================================================
# LOAD WATCHLIST
# =========================================================

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
ALERT_THRESHOLD_PERCENT = settings.get("alert_threshold_percent", 2.0)


# =========================================================
# CREATE STOCK LOOKUP
# =========================================================

stock_lookup = {
    stock["name"]: stock["ticker"]
    for stock in stocks
}


# =========================================================
# SESSION STATE
# =========================================================

if "manual_stocks" not in st.session_state:
    st.session_state.manual_stocks = {}

if "selected_stocks" not in st.session_state:
    st.session_state.selected_stocks = []


# =========================================================
# HELPER FUNCTIONS
# =========================================================

def calculate_ema(data, period):
    return data["Close"].ewm(
        span=period,
        adjust=False
    ).mean()


@st.cache_data(ttl=300)
def get_stock_data(ticker, period="2y"):

    data = yf.download(
        ticker,
        period=period,
        interval="1d",
        auto_adjust=False,
        progress=False
    )

    if data.empty:
        return None

    # Handle MultiIndex columns returned by some yfinance versions
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)

    if "Close" not in data.columns:
        return None

    data = data.dropna(subset=["Close"])

    return data


def get_latest_metrics(ticker):

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

        result[
            f"Distance from EMA {period}"
        ] = distance

    return result


# =========================================================
# HEADER
# =========================================================

st.title("📈 Stock EMA Analyzer")

st.write(
    "Select stocks from your watchlist or search for a stock manually."
)


# =========================================================
# STOCK SELECTION
# =========================================================

st.subheader("🔎 Select Stocks")


# ---------------------------------------------------------
# Saved watchlist stocks
# ---------------------------------------------------------

watchlist_names = [
    stock["name"]
    for stock in stocks
]


selected_watchlist = st.multiselect(
    "Choose from your watchlist",
    options=watchlist_names,
    default=[
        name for name in st.session_state.selected_stocks
        if name in watchlist_names
    ],
    help="These stocks come from watchlist.json."
)


# ---------------------------------------------------------
# Manual stock search
# ---------------------------------------------------------

st.write("**Or add a stock manually**")

manual_col1, manual_col2 = st.columns([4, 1])

with manual_col1:

    manual_ticker = st.text_input(
        "Yahoo Finance ticker",
        placeholder="Example: BAJFINANCE.NS or RELIANCE.NS",
        label_visibility="collapsed"
    )

with manual_col2:

    add_stock = st.button(
        "➕ Add Stock",
        use_container_width=True
    )


# ---------------------------------------------------------
# Add manually entered stock
# ---------------------------------------------------------

if add_stock:

    ticker = manual_ticker.strip().upper()

    if not ticker:

        st.warning("Please enter a ticker.")

    else:

        with st.spinner(f"Checking {ticker}..."):

            test_data = get_stock_data(
                ticker,
                "5d"
            )

        if test_data is None or test_data.empty:

            st.error(
                f"Could not find data for `{ticker}`. "
                "Check the Yahoo Finance ticker."
            )

        else:

            # Try to create a readable name
            try:
                ticker_info = yf.Ticker(ticker).info

                company_name = ticker_info.get(
                    "shortName"
                ) or ticker

            except Exception:
                company_name = ticker

            st.session_state.manual_stocks[
                company_name
            ] = ticker

            st.success(
                f"Added **{company_name} ({ticker})**"
            )


# =========================================================
# MANUALLY ADDED STOCKS
# =========================================================

if st.session_state.manual_stocks:

    st.write("**Manually added stocks**")

    manual_options = list(
        st.session_state.manual_stocks.keys()
    )

    selected_manual = st.multiselect(
        "Choose manually added stocks",
        options=manual_options,
        default=[
            name for name in st.session_state.selected_stocks
            if name in manual_options
        ]
    )

else:

    selected_manual = []


# =========================================================
# COMBINE SELECTIONS
# =========================================================

all_stock_lookup = {
    **stock_lookup,
    **st.session_state.manual_stocks
}


selected_stocks = (
    selected_watchlist +
    selected_manual
)

# Remove duplicates while maintaining order
selected_stocks = list(
    dict.fromkeys(selected_stocks)
)


st.session_state.selected_stocks = selected_stocks


# =========================================================
# SELECTED STOCK SUMMARY
# =========================================================

if selected_stocks:

    st.write("### Selected stocks")

    selected_display = []

    for name in selected_stocks:

        ticker = all_stock_lookup[name]

        selected_display.append(
            f"**{name}** (`{ticker}`)"
        )

    st.write(
        " • ".join(selected_display)
    )

else:

    st.info(
        "Select stocks from your watchlist or add a stock manually."
    )

    st.stop()


# =========================================================
# REFRESH BUTTON
# =========================================================

if st.button("🔄 Refresh data"):

    st.cache_data.clear()

    st.rerun()


# =========================================================
# CURRENT OVERVIEW
# =========================================================

st.divider()

st.subheader("📊 Current Overview")


overview_rows = []


with st.spinner("Fetching stock data..."):

    for stock_name in selected_stocks:

        ticker = all_stock_lookup[stock_name]

        metrics = get_latest_metrics(ticker)

        if metrics is None:

            st.warning(
                f"Could not retrieve data for "
                f"{stock_name} ({ticker})."
            )

            continue

        row = {
            "Stock": stock_name,
            "Ticker": ticker,
            "Price": metrics["Price"]
        }

        for period in EMA_PERIODS:

            row[f"EMA {period}"] = (
                metrics[f"EMA {period}"]
            )

            row[
                f"Distance from EMA {period}"
            ] = (
                metrics[
                    f"Distance from EMA {period}"
                ]
            )

        overview_rows.append(row)


# =========================================================
# DISPLAY TABLE
# =========================================================

if overview_rows:

    overview_df = pd.DataFrame(
        overview_rows
    )

    distance_columns = [
        f"Distance from EMA {period}"
        for period in EMA_PERIODS
    ]

    def highlight_threshold(value):
        if abs(value) <= ALERT_THRESHOLD_PERCENT:
            return "background-color: #d1fae5; color: #065f46"
        return ""

    formatters = {
        "Price": lambda value: f"₹{value:,.2f}"
    }

    for period in EMA_PERIODS:
        formatters[f"EMA {period}"] = (
            lambda value: f"₹{value:,.2f}"
        )
        formatters[f"Distance from EMA {period}"] = (
            lambda value: f"{value:+.2f}%"
        )

    styled_df = (
        overview_df.style
        .map(highlight_threshold, subset=distance_columns)
        .format(formatters)
    )

    st.dataframe(
        styled_df,
        use_container_width=True,
        hide_index=True
    )


# =========================================================
# CHART SETTINGS
# =========================================================

st.divider()

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


# =========================================================
# CHARTS
# =========================================================

for stock_name in selected_stocks:

    ticker = all_stock_lookup[stock_name]

    with st.spinner(
        f"Loading {stock_name}..."
    ):

        data = get_stock_data(
            ticker,
            period_code
        )

    if data is None or data.empty:

        st.warning(
            f"No chart data available for "
            f"{stock_name}."
        )

        continue


    # -----------------------------------------------------
    # Calculate EMAs
    # -----------------------------------------------------

    for ema_period in EMA_PERIODS:

        data[
            f"EMA {ema_period}"
        ] = calculate_ema(
            data,
            ema_period
        )


    # -----------------------------------------------------
    # Create chart
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
                y=data[
                    f"EMA {ema_period}"
                ],
                mode="lines",
                name=f"EMA {ema_period}"
            )
        )


    # -----------------------------------------------------
    # Chart layout
    # -----------------------------------------------------

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


# =========================================================
# FOOTER
# =========================================================

st.divider()

st.caption(
    "Data provided by Yahoo Finance via yfinance. "
    "Prices may be delayed."
)
