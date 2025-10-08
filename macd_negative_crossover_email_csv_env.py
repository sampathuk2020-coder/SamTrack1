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

# -----------------------------
# 📌 NASDAQ-100 Tickers
# -----------------------------
TICKERS = [
    "AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "NVDA", "META", "AVGO", "TSLA", "PEP",
    "COST", "ADBE", "CSCO", "TMUS", "INTC", "TXN", "QCOM", "AMGN", "SBUX", "INTU",
    "BKNG", "MDLZ", "ADI", "GILD", "ADP", "NFLX", "PLTR", "ASML", "AMD", "SNPS", "TTWO",
    "ISRG", "ROST", "IDXX", "KDP", "KLAC", "LULU", "MAR", "MCHP", "MU", "MRNA", "MRVL",
    "MTCH", "NLOK", "NXPI", "OKTA", "ORLY", "PAYX", "PYPL", "REGN", "SPLK", "SWKS",
    "SYMC", "VRSK", "VRTX", "WDC", "WDAY", "XEL", "ZS", "HON", "AMAT", "LRCX", "PANW",
    "ABNB", "MELI", "CSX", "CHTR", "AEP", "FTNT", "MNST", "MSCI", "CDNS", "ODFL",
    "CTAS", "ROP", "PCAR", "DXCM", "EXC", "KHC", "CTSH", "ILMN", "EBAY", "CRWD",
    "TEAM", "BKR", "ANSS", "LCID", "VERX", "DDOG", "BIDU", "DOCU", "ALGN", "FAST",
    "CHKP", "VRSN", "DLTR", "EXPE", "LBTYK", "LBTYA", "SIRI", "EA", "WBA", "FOX", "FOXA", "JD", "BIIB", "CEG"
]

# -----------------------------
# 📌 Email Function (single)
# -----------------------------
def send_email_two_csv(df1, df2, recipient_email):
    sender_email = os.environ.get("EMAIL_USER")
    sender_password = os.environ.get("EMAIL_PASSWORD")

    subject = f"NASDAQ-100 Screener Results — {datetime.now().strftime('%Y-%m-%d')}"

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = recipient_email
    msg['Subject'] = subject

    # Optional HTML summary in email body
    html_body = f"""
    <html>
    <body>
        <h2>NASDAQ-100 Screener Results</h2>
        <p>Attached are two CSV files:</p>
        <ul>
            <li>MACD Negative Territory Crossovers</li>
            <li>SMA100 Touch Report</li>
        </ul>
        <p>Date: {datetime.now().strftime('%Y-%m-%d')}</p>
    </body>
    </html>
    """
    msg.attach(MIMEText(html_body, 'html'))

    # Attach first CSV
    csv_buffer1 = io.StringIO()
    df1.to_csv(csv_buffer1, index=False)
    csv_buffer1.seek(0)
    part1 = MIMEBase('application', 'octet-stream')
    part1.set_payload(csv_buffer1.read())
    encoders.encode_base64(part1)
    part1.add_header('Content-Disposition', 'attachment',
                     filename=f"MACD_Negative_Crossovers_{datetime.now().strftime('%Y-%m-%d')}.csv")
    msg.attach(part1)

    # Attach second CSV
    csv_buffer2 = io.StringIO()
    df2.to_csv(csv_buffer2, index=False)
    csv_buffer2.seek(0)
    part2 = MIMEBase('application', 'octet-stream')
    part2.set_payload(csv_buffer2.read())
    encoders.encode_base64(part2)
    part2.add_header('Content-Disposition', 'attachment',
                     filename=f"SMA100_Touch_Report_{datetime.now().strftime('%Y-%m-%d')}.csv")
    msg.attach(part2)

    # Send email via Gmail
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        print(f"✅ Email sent to {recipient_email}")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")

# -----------------------------
# 1️⃣ MACD Negative Territory Screener
# -----------------------------
def calculate_macd(df, short=12, long=26, signal=9):
    df['EMA_short'] = df['Close'].ewm(span=short, adjust=False).mean()
    df['EMA_long'] = df['Close'].ewm(span=long, adjust=False).mean()
    df['MACD'] = df['EMA_short'] - df['EMA_long']
    df['Signal'] = df['MACD'].ewm(span=signal, adjust=False).mean()
    return df

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

def run_macd_screener():
    results = []
    print(f"\n📅 Running MACD Negative Territory Screener — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    for ticker in TICKERS:
        try:
            data = yf.download(ticker, period="6mo", interval="1d", progress=False)
            if data.empty:
                continue
            data = calculate_macd(data)
            crossover_dates = check_negative_macd_crossover(data, days=100)
            if crossover_dates:
                results.append({"Ticker": ticker, "Most_Recent_Crossover": max(crossover_dates)})
        except Exception as e:
            print(f"❌ Error fetching {ticker}: {e}")
    return pd.DataFrame(results)

# -----------------------------
# 2️⃣ SMA100 Touch Scanner
# -----------------------------
SMA_PERIOD = 100
TOLERANCE = 0.01
LOOKBACK = 15

def run_sma_screener():
    rows = []
    for t in TICKERS:
        try:
            df = yf.download(t, period=f"{SMA_PERIOD + LOOKBACK + 50}d", interval="1d", progress=False)
            if df.empty or len(df) < SMA_PERIOD:
                continue
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            price_col = 'Adj Close' if 'Adj Close' in df.columns else 'Close'
            df['Close'] = pd.to_numeric(df[price_col], errors='coerce')
            df['SMA100'] = df['Close'].rolling(SMA_PERIOD).mean()
            df = df.dropna(subset=['Close', 'SMA100'])
            recent = df.tail(LOOKBACK)
            close_arr = np.asarray(recent['Close'], dtype=float)
            sma_arr = np.asarray(recent['SMA100'], dtype=float)
            mask = np.abs(close_arr - sma_arr) <= (TOLERANCE * sma_arr)
            matched = recent.loc[mask]
            if not matched.empty:
                for ts, row in matched.iterrows():
                    rows.append({
                        "Ticker": t,
                        "Date": ts.date(),
                        "Close": float(row['Close']),
                        "SMA100": float(row['SMA100'])
                    })
        except Exception as e:
            print(f"❌ Error processing {t}: {e}")
    return pd.DataFrame(rows)

# -----------------------------
# 🔹 Main
# -----------------------------
if __name__ == "__main__":
    macd_df = run_macd_screener()
    sma_df = run_sma_screener()

    if macd_df.empty:
        print("\n🚫 No MACD Negative Territory crossovers found.")
    if sma_df.empty:
        print("\n🚫 No SMA100 touches found.")

    if not macd_df.empty or not sma_df.empty:
        send_email_two_csv(macd_df, sma_df, "sampath.uk2020@gmail.com")
