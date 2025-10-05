import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import io
import os

# 📝 Nasdaq-100 Tickers
TICKERS = [
    "AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "NVDA", "META", "AVGO", "TSLA", "PEP",
    "COST", "ADBE", "CSCO", "TMUS", "INTC", "TXN", "QCOM", "AMGN", "SBUX", "INTU",
    "BKNG", "MDLZ", "ADI", "GILD", "ADP", "NFLX", "PLTR", "ASML", "AMD", "SNPS", "TTWO",
    "ISRG", "ROST", "IDXX", "KDP", "KLAC", "LULU", "MAR", "MCHP", "MU", "MRNA", "MRVL",
    "MSFT", "MTCH", "MU", "NLOK", "NVDA", "NXPI", "OKTA", "ORLY", "PAYX", "PEP", "PYPL",
    "QCOM", "REGN", "ROST", "SBUX", "SPLK", "SWKS", "SYMC", "TTWO", "TXN", "VRSK",
    "VRTX", "WDC", "WDAY", "XEL", "ZS"
]

# MACD Calculation
def calculate_macd(df, short=12, long=26, signal=9):
    df['EMA_short'] = df['Close'].ewm(span=short, adjust=False).mean()
    df['EMA_long'] = df['Close'].ewm(span=long, adjust=False).mean()
    df['MACD'] = df['EMA_short'] - df['EMA_long']
    df['Signal'] = df['MACD'].ewm(span=signal, adjust=False).mean()
    return df

# Check MACD bullish crossover in negative territory
def check_negative_macd_crossover(df, days=100):
    crossover_dates = []
    for i in range(1, min(days+1, len(df))):
        macd_prev = df['MACD'].iloc[-i-1]
        signal_prev = df['Signal'].iloc[-i-1]
        macd_curr = df['MACD'].iloc[-i]
        signal_curr = df['Signal'].iloc[-i]
        if macd_prev < signal_prev and macd_curr > signal_curr and macd_curr < 0 and signal_curr < 0:
            crossover_dates.append(df.index[-i].date())
    return crossover_dates

# Send email with CSV attachment
def send_email(df_results, recipient_email):
    sender_email = os.environ.get("EMAIL_USER")
    sender_password = os.environ.get("EMAIL_PASSWORD")

    subject = f"MACD Negative Territory Crossovers — {datetime.now().strftime('%Y-%m-%d')}"

    # Convert DataFrame to HTML table
    html_table = df_results.to_html(index=False)

    # Create MIME message
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = recipient_email
    msg['Subject'] = subject
    msg.attach(MIMEText(html_table, 'html'))

    # Convert DataFrame to CSV in memory
    csv_buffer = io.StringIO()
    df_results.to_csv(csv_buffer, index=False)
    csv_buffer.seek(0)

    part = MIMEBase('application', 'octet-stream')
    part.set_payload(csv_buffer.read())
    encoders.encode_base64(part)
    part.add_header('Content-Disposition', 'attachment',
                    filename=f"MACD_Negative_Crossovers_{datetime.now().strftime('%Y-%m-%d')}.csv")
    msg.attach(part)

    # Send email via Gmail SMTP
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        print(f"✅ Email sent to {recipient_email}")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")

# Main Screener
def run_screener():
    results = []
    print(f"\n📅 Running MACD Negative Territory Screener — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    for ticker in TICKERS:
        try:
            data = yf.download(ticker, period="6mo", interval="1d")
            if data.empty:
                continue

            data = calculate_macd(data)
            crossover_dates = check_negative_macd_crossover(data, days=100)

            if crossover_dates:
                results.append({"Ticker": ticker, "Most_Recent_Crossover": max(crossover_dates)})
        except Exception as e:
            print(f"❌ Error fetching {ticker}: {e}")

    if results:
        df_results = pd.DataFrame(results)
        df_results.sort_values(by="Most_Recent_Crossover", ascending=False, inplace=True)
        print("\n📊 MACD Negative Territory Crossovers Sorted by Most Recent Date:\n")
        print(df_results.to_string(index=False))

        # Send email
        send_email(df_results, "sampath.uk2020@gmail.com")
    else:
        print("\n❌ No negative territory MACD crossovers found in past 100 days.\n")

if __name__ == "__main__":
    run_screener()
