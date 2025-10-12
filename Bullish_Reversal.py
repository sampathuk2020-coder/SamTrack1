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
# 📌 NASDAQ Top 30
# ================================
NASDAQ_TOP30 = [
    "AAPL", "MSFT", "AMZN", "NVDA", "META", "GOOGL", "GOOG", "AVGO", "COST", "ADBE",
    "NFLX", "PEP", "AMD", "CSCO", "INTC", "TMUS", "AMAT", "QCOM", "TXN", "HON",
    "AMGN", "INTU", "SBUX", "VRTX", "REGN", "MU", "PANW", "ADI", "LRCX", "MAR"
]


# ================================
# 🟩 Bullish Reversal Detection
# ================================
def detect_bullish_reversal(df):
    """
    Detects bullish engulfing and piercing patterns robustly using .iloc indexing.
    """
    signals = []
    if df.shape[0] < 2:
        return signals

    df = df.tail(10).copy()
    df.reset_index(drop=True, inplace=True)

    for i in range(1, len(df)):
        # safely extract previous and current candle values via .iloc
        prev_open = float(df.iloc[i - 1]["Open"])
        prev_close = float(df.iloc[i - 1]["Close"])
        prev_low = float(df.iloc[i - 1]["Low"])
        prev_high = float(df.iloc[i - 1]["High"])

        curr_open = float(df.iloc[i]["Open"])
        curr_close = float(df.iloc[i]["Close"])
        curr_low = float(df.iloc[i]["Low"])
        curr_high = float(df.iloc[i]["High"])

        # --- Bullish Engulfing ---
        engulf = (
            prev_close < prev_open and
            curr_close > curr_open and
            curr_close > prev_open and
            curr_open < prev_close
        )

        # --- Piercing Pattern ---
        piercing = (
            prev_close < prev_open and
            curr_open < prev_low and
            curr_close > (prev_open + prev_close) / 2 and
            curr_close < prev_open
        )

        if engulf or piercing:
            signals.append({
                "Date": df.index[i],  # now integer, fine for tracking
                "Pattern": "Bullish Engulfing" if engulf else "Piercing",
                "Prev_Close": round(prev_close, 2),
                "Curr_Close": round(curr_close, 2)
            })

    return signals


# ================================
# 📈 Screener
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
                        "Date": df.index[-1].date(),
                        "Pattern": p["Pattern"],
                        "Prev_Close": p["Prev_Close"],
                        "Curr_Close": p["Curr_Close"]
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
# 📧 Email Logic
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

    if not df.empty:
        buffer = io.StringIO()
        df.drop(columns=["__highlight__"], errors="ignore").to_csv(buffer, index=False)
        buffer.seek(0)
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(buffer.read())
        encoders.encode_base64(part)
        part.add_header(
            'Content-Disposition',
            'attachment',
            filename=f"Bullish_Reversals_{datetime.now():%Y-%m-%d}.csv"
        )
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
