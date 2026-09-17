import json
import os
from urllib import response

import requests
import yfinance as yf


WATCHLIST_FILE = "watchlist.json"


def load_watchlist():
    with open(WATCHLIST_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def calculate_ema(data, period):
    return data["Close"].ewm(
        span=period,
        adjust=False
    ).mean()


def send_telegram_message(message):
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    TELEGRAM_CHAT_IDS = os.getenv("TELEGRAM_CHAT_IDS").split(",")

    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_IDS:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_IDS is missing."
        )

    url = (
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    )

    for chat_id in TELEGRAM_CHAT_IDS:
        response = requests.post(url, json={
            "chat_id": chat_id.strip(),
            "text": message
        })
        response.raise_for_status()


def check_stock(stock, ema_periods, threshold):
    ticker = stock["ticker"]
    name = stock["name"]

    print(f"Checking {name} ({ticker})...")

    try:
        data = yf.download(
            ticker,
            period="2y",
            interval="1d",
            auto_adjust=False,
            progress=False,
            threads=False
        )

        if data.empty:
            print(f"No data found for {ticker}")
            return None

        # Handle yfinance MultiIndex columns.
        if hasattr(data.columns, "levels"):
            data.columns = data.columns.get_level_values(0)

        data = data.dropna(subset=["Close"])

        if len(data) < 200:
            print(f"Not enough data for {ticker}")
            return None

        latest_price = float(data["Close"].iloc[-1])

        alerts = []

        for period in ema_periods:

            ema_series = calculate_ema(data, period)

            ema_value = float(ema_series.iloc[-1])

            distance_percent = (
                (latest_price - ema_value)
                / ema_value
            ) * 100

            absolute_distance = abs(distance_percent)

            print(
                f"{name}: Price={latest_price:.2f}, "
                f"EMA{period}={ema_value:.2f}, "
                f"Distance={distance_percent:.2f}%"
            )

            if absolute_distance <= threshold:

                if distance_percent > 0:
                    direction = "ABOVE"
                elif distance_percent < 0:
                    direction = "BELOW"
                else:
                    direction = "AT"

                alerts.append({
                    "period": period,
                    "ema": ema_value,
                    "distance": distance_percent,
                    "direction": direction
                })

        if not alerts:
            return None

        message = (
            f"📈 EMA ALERT\n\n"
            f"{name}\n"
            f"Ticker: {ticker}\n"
            f"Price: {latest_price:,.2f}\n\n"
        )

        for alert in alerts:

            message += (
                f"EMA {alert['period']}: "
                f"{alert['ema']:,.2f}\n"
                f"Price is {abs(alert['distance']):.2f}% "
                f"{alert['direction']} EMA "
                f"{alert['period']}\n\n"
            )

        return message

    except Exception as error:

        print(
            f"Error checking {ticker}: {error}"
        )

        return None


def main():

    config = load_watchlist()

    threshold = config["settings"][
        "alert_threshold_percent"
    ]

    ema_periods = config["settings"][
        "ema_periods"
    ]

    stocks = config["stocks"]

    messages = []

    for stock in stocks:

        message = check_stock(
            stock,
            ema_periods,
            threshold
        )

        if message:
            messages.append(message)

    if messages:

        final_message = (
            "🔔 Daily Stock EMA Alerts\n\n"
            + "\n--------------------\n\n".join(messages)
        )

        send_telegram_message(final_message)

        print("Telegram alert sent.")

    else:

        print("No EMA alerts today.")


if __name__ == "__main__":
    main()