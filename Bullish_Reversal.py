import yfinance as yf
import pandas as pd
import numpy as np
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import io
import os
from datetime import datetime

# ================================
# 📌 Ticker List (NASDAQ Top 30)
# ================================
NASDAQ_TOP30 = [
    "AAPL", "MSFT", "AMZN", "NVDA", "META", "GOOGL", "GOOG", "AVGO", "COST", "ADBE",
    "NFLX", "PEP", "AMD", "CSCO", "INTC", "TMUS", "AMAT", "QCOM", "TXN", "HON",
    "AMGN", "INTU", "SBUX", "VRTX", "REGN", "MU", "PANW", "ADI", "LRCX", "MAR"
]

# ================================
# 🟩 Pattern Detection
# ================================
def detect_bullish_reversal(df):
    """Detect bullish engulfing or piercing patterns."""
    signals = []
    if len(df) < 3:
        return signals

    df = df.tail(10).copy()
    for i in range(1, len(df)):
        prev = df.iloc[i - 1]
        curr = df.iloc[i]

        # --- Bullish Engulfing ---
        engulf = (
            prev['Close'] < prev['Open'] and
            curr['Close'] > curr['Open'] and
            curr['Close'] > prev['Open'] and
            curr['Open'] < prev['Close']
        )

        # --- Piercing Pattern ---
        piercing = (
            prev['Close'] < prev['Open'] and
            curr['Open'] < prev['Low'] and
            curr['Close'] > (prev['Open'] + prev['Close']) / 2 and
            curr['Close'] < prev['Open']
        )

        if engulf or piercing:
            signals.append({
                "Date": curr.name.date(),
                "Pattern": "Bullish Engulfing" if engulf else "Piercing",
                "Prev_Close": prev['Close'],
                "Curr_Close": curr['Close']
            })
    return signals

# ================================
# 📈 Screener Logic
# ================================
def run_bullish_reversal_screener():
    results = []
    print(f"\n📅 Running Bullish Reversal Screener — {datetime.now():%Y-%m-%d %H:%M:%S}\n")

    for ticker in NASDAQ_TOP30:
        try:
            df = yf.download(ticker, period="3mo", interval="1d", progress=False)
            if df.empty:
                continue
            patterns = detect_bullish_reversal(df)
            if patterns:
                for p in patterns:
                    results.append({
                        "Ticker": ticker,
                        "Date": p["Date"],
                        "Pattern": p["Pattern"],
                        "Prev_Close": round(p["Prev_Close"], 2),
                        "Curr_Close": round(p["Curr_Close"], 2)
                    })
        except Exception as e:
            print(f"❌ Error fetching {ticker}: {e}")

    return pd.DataFrame(results)

# ================================
# 🖌️ HTML Utilities
# ================================
def highlight_most_recent(df, date_col="Date", ticker_col="Ticker"):
    if df.empty:
        return df.copy()
    df_copy = df.copy()
    df_copy[date_col] = pd.to_datetime(df_copy[date_col])
    recent_dates = df_copy.groupby(ticker_col)[date_col].transform("max")
    df_copy["__highlight__"] = df_copy[date_col] == recent_dates
    return df_copy

def df_to_html_highlighted(df, color="#0070f3"):
    if df.empty:
        return "<p>No signals found today.</p>"

    df_copy = df.copy()
    if "__highlight__" not in df_copy.columns:
        df_copy["__highlight__"] = False

    headers = "".join([f"<th>{col}</th>" for col in df_copy.columns if col != "__highlight__"])
    body = ""
    for _, row in df_copy.iterrows():
        row_html = ""
        for col, val in row.items():
            if col == "__highlight__":
                continue
            val_str = f"<b style='color:{color};'>{val}</b>" if row["__highlight__"] else str(val)
            row_html += f"<td>{val_str}</td>"
        body += f"<tr>{row_html}</tr>"

    return f"""
    <table border="1" cellpadding="6" cellspacing="0"
           style="border-collapse:collapse; font-family:Arial; font-size:13px;">
        <thead style="background-color:#f2f2f2;">{headers}</thead>
        <tbody>{body}</tbody>
    </table>
    """

# ================================
# 📧 Email Logic (same as MACD/SMA)
# ================================
def send_email_bullish_reversal(df, recipient_email):
    sender_email = os.environ.get("EMAIL_USER")
    sender_password = os.environ.get("EMAIL_PASSWORD")

    subject = f"📈 NASDAQ-30 Bullish Reversal Patterns — {datetime.now():%Y-%m-%d}"
    df = df.sort_values(by="Date", ascending=False)
    df = highlight_most_recent(df, "Date")

    html_table = df_to_html_highlighted(df, color="#00A86B")
    html_body = f"""
    <html>
      <body>
        <h2>🟩 Bullish Reversal Patterns (Engulfing or Piercing)</h2>
        {html_table}
        <p style="font-size:12px;color:#555;">
          * Most recent signal per ticker is <b style='color:#0070f3;'>highlighted</b>.
        </p>
      </body>
    </html>
    """

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = recipient_email
    msg['Subject'] = subject
    msg.attach(MIMEText(html_body, 'html'))

    # Attach CSV
    if not df.empty:
        buffer = io.StringIO()
        df.drop(columns=["__highlight__"], errors="ignore").to_csv(buffer, index=False)
        buffer.seek(0)
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(buffer.read())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', 'attachment',
                        filename=f"Bullish_Reversals_{datetime.now():%Y-%m-%d}.csv")
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

# ================================
# 🚀 Main
# ================================
if __name__ == "__main__":
    df = run_bullish_reversal_screener()

    if df.empty:
        print("\n🚫 No bullish reversal patterns found today.")
    else:
        print(df)
        send_email_bullish_reversal(df, "sampath.uk2020@gmail.com")
