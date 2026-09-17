import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(
    page_title="Stock EMA Analyzer",
    page_icon="📈",
    layout="wide"
)

st.title("📈 Stock EMA Analyzer")
st.caption("Yahoo Finance data via yfinance | For informational use only")

# -------------------------
# Sidebar
# -------------------------

st.sidebar.header("Stock Settings")

ticker = st.sidebar.text_input(
    "Stock ticker",
    value="RELIANCE.NS"
).strip().upper()

period = st.sidebar.selectbox(
    "Period",
    ["1 Month", "3 Months", "6 Months", "1 Year", "2 Years", "5 Years"],
    index=3
)

period_map = {
    "1 Month": "1mo",
    "3 Months": "3mo",
    "6 Months": "6mo",
    "1 Year": "1y",
    "2 Years": "2y",
    "5 Years": "5y"
}

interval = st.sidebar.selectbox(
    "Interval",
    ["1 Day", "1 Hour", "30 Minutes", "15 Minutes"],
    index=0
)

interval_map = {
    "1 Day": "1d",
    "1 Hour": "1h",
    "30 Minutes": "30m",
    "15 Minutes": "15m"
}

st.sidebar.subheader("EMA")

ema_periods = st.sidebar.multiselect(
    "Select EMA periods",
    [5, 9, 10, 20, 21, 50, 100, 200],
    default=[20, 50, 200]
)

show_volume = st.sidebar.checkbox(
    "Show volume",
    value=True
)

show_candles = st.sidebar.checkbox(
    "Candlestick chart",
    value=True
)

get_data_button = st.sidebar.button(
    "🔄 Get Latest Data",
    type="primary",
    use_container_width=True
)

# -------------------------
# Validation
# -------------------------

if not ticker:
    st.warning("Please enter a stock ticker.")
    st.stop()

if not ema_periods:
    st.warning("Select at least one EMA.")
    st.stop()

# -------------------------
# Download data
# -------------------------

@st.cache_data(ttl=300)
def download_data(ticker, period, interval):

    data = yf.download(
        ticker,
        period=period,
        interval=interval,
        auto_adjust=False,
        progress=False
    )

    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)

    return data


with st.spinner(f"Fetching {ticker} data..."):

    data = download_data(
        ticker,
        period_map[period],
        interval_map[interval]
    )

# -------------------------
# Check data
# -------------------------

if data.empty:

    st.error(
        f"No data found for {ticker}. "
        "Check the ticker symbol and try again."
    )

    st.stop()

# -------------------------
# Calculate EMA
# -------------------------

for ema in ema_periods:

    data[f"EMA {ema}"] = (
        data["Close"]
        .ewm(
            span=ema,
            adjust=False
        )
        .mean()
    )

# -------------------------
# Latest values
# -------------------------

latest = data.iloc[-1]

close = float(latest["Close"])

if len(data) > 1:

    previous_close = float(data.iloc[-2]["Close"])

    change = close - previous_close

    change_percent = (
        change / previous_close
    ) * 100

else:

    change = 0
    change_percent = 0

# -------------------------
# Header
# -------------------------

st.subheader(ticker)

col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "Latest Price",
    f"{close:,.2f}",
    f"{change:+,.2f} ({change_percent:+.2f}%)"
)

for column, ema in zip(
    [col2, col3, col4],
    ema_periods[:3]
):

    ema_value = float(
        latest[f"EMA {ema}"]
    )

    difference = (
        (close / ema_value) - 1
    ) * 100

    column.metric(
        f"EMA {ema}",
        f"{ema_value:,.2f}",
        f"{difference:+.2f}% vs price"
    )

# -------------------------
# EMA table
# -------------------------

st.subheader("EMA Summary")

rows = []

for ema in sorted(ema_periods):

    ema_value = float(
        latest[f"EMA {ema}"]
    )

    difference = (
        (close / ema_value) - 1
    ) * 100

    rows.append({
        "EMA": f"EMA {ema}",
        "Value": round(ema_value, 2),
        "Price vs EMA": f"{difference:+.2f}%",
        "Price Above EMA": "Yes" if close > ema_value else "No"
    })

ema_table = pd.DataFrame(rows)

st.dataframe(
    ema_table,
    use_container_width=True,
    hide_index=True
)

# -------------------------
# Price chart
# -------------------------

st.subheader("Price & EMA Chart")

fig = go.Figure()

if show_candles:

    fig.add_trace(
        go.Candlestick(
            x=data.index,
            open=data["Open"],
            high=data["High"],
            low=data["Low"],
            close=data["Close"],
            name="Price"
        )
    )

else:

    fig.add_trace(
        go.Scatter(
            x=data.index,
            y=data["Close"],
            mode="lines",
            name="Close"
        )
    )

# Add EMA lines

for ema in sorted(ema_periods):

    fig.add_trace(
        go.Scatter(
            x=data.index,
            y=data[f"EMA {ema}"],
            mode="lines",
            name=f"EMA {ema}"
        )
    )

fig.update_layout(
    height=600,
    xaxis_title="Date",
    yaxis_title="Price",
    hovermode="x unified",
    xaxis_rangeslider_visible=False
)

st.plotly_chart(
    fig,
    use_container_width=True
)

# -------------------------
# Volume
# -------------------------

if show_volume and "Volume" in data.columns:

    st.subheader("Volume")

    volume_fig = go.Figure()

    volume_fig.add_trace(
        go.Bar(
            x=data.index,
            y=data["Volume"],
            name="Volume"
        )
    )

    volume_fig.update_layout(
        height=300,
        xaxis_rangeslider_visible=False
    )

    st.plotly_chart(
        volume_fig,
        use_container_width=True
    )

# -------------------------
# Raw data
# -------------------------

with st.expander("View latest data"):

    st.dataframe(
        data.tail(30).sort_index(
            ascending=False
        ),
        use_container_width=True
    )

st.divider()

st.caption(
    "Market data provided through Yahoo Finance via yfinance. "
    "Data availability and accuracy may vary."
)