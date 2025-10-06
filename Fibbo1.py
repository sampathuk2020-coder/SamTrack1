import yfinance as yf
import pandas as pd
import numpy as np
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import io
import os
from datetime import datetime

# --- 1️⃣ Full NASDAQ-100 ticker list (2025) ---
tickers = [
    "AAPL", "MSFT", "AMZN", "NVDA", "META", "GOOGL", "GOOG", "AVGO", "COST", "PEP",
    "ADBE", "NFLX", "AMD", "CSCO", "TMUS", "INTC", "TXN", "QCOM", "HON", "AMGN",
    "INTU", "AMAT", "SBUX", "BKNG", "MDLZ", "ADI", "LRCX", "ISRG", "PYPL", "MU",
    "PANW", "REGN", "VRTX", "GILD", "ABNB", "KLAC", "MELI", "CSX", "MRVL", "ADP",
    "SNPS", "PDD", "ORLY", "CHTR", "KDP", "NXPI", "AEP", "IDXX", "MAR", "FTNT",
    "MNST", "MSCI", "CDNS", "ODFL", "CTAS", "ROP", "PCAR", "DXCM", "EXC", "KHC",
    "LULU", "PAYX", "WDAY", "XEL", "PANW", "CTSH", "VRSK", "ILMN", "EBAY", "CRWD",
    "TEAM", "ZS", "BKR", "ANSS", "LCID", "VERX", "SPLK", "DDOG", "BIDU", "DOCU",
    "ALGN", "MTCH", "ROST", "SGEN", "JD", "BIIB", "CEG", "MRNA", "OKTA", "FAST",
    "CHKP", "VRSN", "DLTR", "EXPE", "LBTYK", "LBTYA", "SIRI", "EA", "WBA", "FOX", "FOXA"
]

# --- 2️⃣ Parameters ---
SMA_PERIOD = 100
TOLERANCE = 0.01   # 1%
LOOKBACK = 15      # Days to check for SMA touches

# --- 3️⃣ Scan each ticker ---
rows = []

for t in tickers:
    try:
        df = yf.download(t, period=f"{SMA_PERIOD + LOOKBACK + 50}d", interval="1d", progress=False)
        if df.empty or len(df) < SMA_PERIOD:
            continue

        # Flatten MultiIndex columns if needed
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        price_col = 'Adj Close' if 'Adj Close' in df.columns else 'Close'
        df['Close'] = pd.to_numeric(df[price_col], errors='coerce')
        df['SMA100'] = df['Close'].rolling(SMA_PERIOD).mean()

        df = df.dropna(subset=['Close', 'SMA100'])
        recent = df.tail(LOOKBACK)

        close_arr = np.asarray(recent['Close'], dtype=float).ravel()
        sma_arr = np.asarray(recent['SMA100'], dtype=float).ravel()

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
        print(f"Error processing {t}: {e}")

# --- 4️⃣ Results ---
result_df = pd.DataFrame(rows)
if result_df.empty:
    print("\n🚫 No NASDAQ-100 tickers touched the 100-day SMA within the last 15 days.")
else:
    result_df = result_df.sort_values(["Date", "Ticker"], ascending=[False, True])
    print("\n📊 NASDAQ-100 tickers touching 100-day SMA (±1%) in last 15 days:")
    print(result_df.to_string(index=False))

# --- 5️⃣ Email the results (SAME STYLE AS FIRST FILE) ---
if not result_df.empty:
    sender_email = os.environ.get("EMAIL_USER")
    sender_password = os.environ.get("EMAIL_PASSWORD")
    recipient_email = "sampath.uk2020@gmail.com"
    subject = f"NASDAQ-100 SMA100 Touch Report — {datetime.now().strftime('%Y-%m-%d')}"

    # HTML table
    html_table = result_df.to_html(index=False)

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = recipient_email
    msg['Subject'] = subject
    msg.attach(MIMEText(html_table, 'html'))

    # CSV attachment
    csv_buffer = io.StringIO()
    result_df.to_csv(csv_buffer, index=False)
    csv_buffer.seek(0)

    part = MIMEBase('application', 'octet-stream')
    part.set_payload(csv_buffer.read())
    encoders.encode_base64(part)
    part.add_header('Content-Disposition', 'attachment',
                    filename=f"SMA100_Touch_Report_{datetime.now().strftime('%Y-%m-%d')}.csv")
    msg.attach(part)

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        print(f"✅ Email sent to {recipient_email}")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
else:
    print("No matches found — no email sent.")
