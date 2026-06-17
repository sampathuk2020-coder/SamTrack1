import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import pandas as pd
import yfinance as yf
from ta.trend import MACD
from concurrent.futures import ThreadPoolExecutor, as_completed


# ==========================================================
# Get Current S&P 500 Constituents
# ==========================================================
    # ==========================================================
# Stock Universe (No Wikipedia Dependency)
# ==========================================================
def get_sp500_companies():

    tickers = [
        "AAPL","MSFT","NVDA","AMZN","META","GOOGL","GOOG","BRK-B","AVGO","TSLA",
        "JPM","LLY","V","MA","NFLX","COST","WMT","XOM","ORCL","UNH",
        "JNJ","PG","HD","ABBV","BAC","KO","CRM","CVX","MRK","AMD",
        "PEP","ACN","TMO","LIN","CSCO","ABT","MCD","WFC","IBM","GE",
        "DIS","PM","CAT","QCOM","TXN","INTU","DHR","NOW","GS","RTX",
        "AMGN","SPGI","BKNG","ISRG","HON","BLK","AMAT","SYK","TJX","PGR",
        "ADBE","C","LOW","ETN","SCHW","COP","BSX","LRCX","PANW","ADP",
        "VRTX","MMC","ANET","UPS","DE","BA","CB","MDT","MO","ELV",
        "CI","GILD","SO","CME","BMY","NEE","PLD","ICE","CMCSA","REGN",
        "DUK","AON","APD","EQIX","SHW","CL","EOG","CDNS","PYPL","TT",
        "WM","CRWD","EMR","PH","APH","ZTS","MCK","ROP","CVS","USB",
        "FDX","ITW","HCA","GD","MAR","MSI","CARR","AJG","COF","NXPI",
        "MMM","NOC","ECL","TGT","PCAR","FTNT","OXY","SLB","FCX","AIG",
        "PLTR","COIN","MSTR","HOOD","SMCI"
    ]

    return pd.DataFrame({
        "Symbol": tickers,
        "GICS Sector": ["Large Cap"] * len(tickers)
    })


# ==========================================================
# Bullish Engulfing
# ==========================================================
def bullish_engulfing(df):
    prev = df.iloc[-2]
    curr = df.iloc[-1]

    return (
        prev["Close"] < prev["Open"]
        and curr["Close"] > curr["Open"]
        and curr["Open"] < prev["Close"]
        and curr["Close"] > prev["Open"]
    )


# ==========================================================
# Three White Soldiers
# ==========================================================
def three_white_soldiers(df):
    if len(df) < 4:
        return False

    c1 = df.iloc[-3]
    c2 = df.iloc[-2]
    c3 = df.iloc[-1]

    return (
        c1["Close"] > c1["Open"]
        and c2["Close"] > c2["Open"]
        and c3["Close"] > c3["Open"]
        and c1["Close"] < c2["Close"] < c3["Close"]
        and c2["Open"] > c1["Open"]
        and c2["Open"] < c1["Close"]
        and c3["Open"] > c2["Open"]
        and c3["Open"] < c2["Close"]
    )


# ==========================================================
# Hammer Pattern
# ==========================================================
def hammer(df):
    candle = df.iloc[-1]

    open_price = candle["Open"]
    close_price = candle["Close"]
    high_price = candle["High"]
    low_price = candle["Low"]

    body = abs(close_price - open_price)

    if body == 0:
        return False

    upper_shadow = high_price - max(open_price, close_price)
    lower_shadow = min(open_price, close_price) - low_price
    range_size = high_price - low_price

    return (
        lower_shadow >= body * 2
        and upper_shadow <= body * 0.3
        and body >= range_size * 0.20
    )


# ==========================================================
# MACD Conditions (Past 10 Days)
# ==========================================================
def macd_conditions_past_10_days(df):
    macd = MACD(close=df["Close"])

    df["MACD"] = macd.macd()
    df["MACD_SIGNAL"] = macd.macd_signal()
    df["MACD_HIST"] = macd.macd_diff()

    # Check past 10 days for MACD below 0 with rising histogram
    past_10_days = df.tail(10)
    
    macd_found = False
    for i in range(2, len(past_10_days)):
        curr_macd = past_10_days["MACD"].iloc[i]
        hist_rising = (
            past_10_days["MACD_HIST"].iloc[i-2]
            < past_10_days["MACD_HIST"].iloc[i-1]
            < past_10_days["MACD_HIST"].iloc[i]
        )
        
        if curr_macd < 0 and hist_rising:
            macd_found = True
            break
    
    latest_macd = df["MACD"].iloc[-1]
    return macd_found, round(float(latest_macd), 3)


# ==========================================================
# Bullish Patterns in Past 10 Days
# ==========================================================
def bullish_patterns_past_10_days(df):
    """Check for bullish patterns (Engulfing, Three White Soldiers, Hammer) in past 10 days"""
    past_10_days = df.tail(10)
    patterns_found = []
    
    # Check Hammer pattern in past 10 days
    for i in range(len(past_10_days) - 1, -1, -1):
        candle = past_10_days.iloc[i]
        
        open_price = candle["Open"]
        close_price = candle["Close"]
        high_price = candle["High"]
        low_price = candle["Low"]
        
        body = abs(close_price - open_price)
        
        if body > 0:
            upper_shadow = high_price - max(open_price, close_price)
            lower_shadow = min(open_price, close_price) - low_price
            range_size = high_price - low_price
            
            if (lower_shadow >= body * 2 
                and upper_shadow <= body * 0.3 
                and body >= range_size * 0.20):
                patterns_found.append("Hammer")
                break
    
    # Check Bullish Engulfing in past 10 days
    for i in range(1, len(past_10_days)):
        prev = past_10_days.iloc[i-1]
        curr = past_10_days.iloc[i]
        
        if (prev["Close"] < prev["Open"]
            and curr["Close"] > curr["Open"]
            and curr["Open"] < prev["Close"]
            and curr["Close"] > prev["Open"]):
            patterns_found.append("Bullish Engulfing")
            break
    
    # Check Three White Soldiers in past 10 days
    for i in range(2, len(past_10_days)):
        c1 = past_10_days.iloc[i-2]
        c2 = past_10_days.iloc[i-1]
        c3 = past_10_days.iloc[i]
        
        if (c1["Close"] > c1["Open"]
            and c2["Close"] > c2["Open"]
            and c3["Close"] > c3["Open"]
            and c1["Close"] < c2["Close"] < c3["Close"]
            and c2["Open"] > c1["Open"]
            and c2["Open"] < c1["Close"]
            and c3["Open"] > c2["Open"]
            and c3["Open"] < c2["Close"]):
            patterns_found.append("Three White Soldiers")
            break
    
    return len(patterns_found) > 0, list(set(patterns_found))


# ==========================================================
# Volume Spike
# ==========================================================
def volume_spike(df):
    avg_volume = df["Volume"].rolling(20).mean().iloc[-1]

    if avg_volume == 0:
        return False, 0

    ratio = df["Volume"].iloc[-1] / avg_volume

    return ratio > 1.5, round(float(ratio), 2)


# ==========================================================
# Close Above Previous High
# ==========================================================
def close_above_prev_high(df):
    return df["Close"].iloc[-1] > df["High"].iloc[-2]


# ==========================================================
# Email Results
# ==========================================================
def send_email(df_results):
    sender_email = os.environ["EMAIL_ADDRESS"]
    receiver_email = os.environ.get("EMAIL_RECIPIENT", sender_email)
    app_password = os.environ["EMAIL_PASSWORD"]

    date_str = datetime.now().strftime("%Y-%m-%d")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"S&P 500 Bullish Reversal Scan - {date_str}"
    msg["From"] = sender_email
    msg["To"] = receiver_email

    html_table = df_results.to_html(index=False, border=1, justify="center")

    html = f"""
    <html>
    <head>
    <style>
    body {{font-family: Arial, sans-serif;}}
    table {{border-collapse: collapse;}}
    th, td {{padding: 8px; text-align: center;}}
    th {{background-color: #f2f2f2;}}
    </style>
    </head>
    <body>
    <h2>S&P 500 Bullish Reversal Candidates</h2>
    {html_table}
    <br>
    <h3>Scan Criteria</h3>
    <ul>
      <li>MACD below 0 with rising histogram (past 10 days)</li>
      <li>Bullish Engulfing OR Three White Soldiers OR Hammer (past 10 days)</li>
    </ul>
    </body>
    </html>
    """

    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender_email, app_password)
        server.send_message(msg)

    print("Email sent successfully.")


# ==========================================================
# Scan One Stock
# ==========================================================
def scan_stock(ticker, sector):
    try:
        df = yf.download(
            ticker,
            period="6mo",
            interval="1d",
            auto_adjust=True,
            progress=False,
        )

        if len(df) < 50:
            return None

        macd_ok, macd_value = macd_conditions_past_10_days(df)
        pattern_ok, patterns = bullish_patterns_past_10_days(df)

        if macd_ok and pattern_ok:
            return {
                "Ticker": ticker,
                "Sector": sector,
                "Pattern": ", ".join(patterns),
                "Close": round(float(df["Close"].iloc[-1]), 2),
                "MACD": macd_value,
            }

    except Exception:
        pass

    return None


def main():
    print("Loading S&P 500 constituents...")

    sp500 = get_sp500_companies()

    tickers = sp500["Symbol"].tolist()
    ticker_sector_map = dict(zip(sp500["Symbol"], sp500["GICS Sector"]))

    print(f"Scanning {len(tickers)} S&P 500 stocks...")

    results = []

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {
            executor.submit(scan_stock, ticker, ticker_sector_map[ticker]): ticker
            for ticker in tickers
        }

        for future in as_completed(futures):
            result = future.result()
            if result:
                results.append(result)

    if len(results) == 0:
        send_email(pd.DataFrame([{
            "Message": "No stocks matched all criteria today."
        }]))
        print("No stocks matched all criteria today.")
        return

    df_results = pd.DataFrame(results)
    df_results = df_results.sort_values(
        by="Close",
        ascending=False
    )

    print(df_results.to_string(index=False))
    send_email(df_results)


if __name__ == "__main__":
    main()
