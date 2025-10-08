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
# 📌 Ticker Lists
# ================================
# NASDAQ100_TICKERS = [
#    "AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "NVDA", "META", "AVGO", "TSLA", "PEP",
#    "COST", "ADBE", "CSCO", "TMUS", "INTC", "TXN", "QCOM", "AMGN", "SBUX", "INTU",
#    "BKNG", "MDLZ", "ADI", "GILD", "ADP", "NFLX", "PLTR", "ASML", "AMD", "SNPS", "TTWO",
#    "ISRG", "ROST", "IDXX", "KDP", "KLAC", "LULU", "MAR", "MCHP", "MU", "MRNA", "MRVL",
#    "NXPI", "OKTA", "ORLY", "PAYX", "PYPL", "REGN", "SPLK", "SWKS", "TTWO", "TXN",
#    "VRSK", "VRTX", "WDC", "WDAY", "XEL", "ZS"
#]

NASDAQ100_TICKERS = [
    "3AAP", "3BAL", "3CON", "3EDF", "3GOO", "3ITL", "3KWE", "3LDE", "3LEU", "3LGO",
    "3LNP", "3LOI", "3NFL", "3NVD", "3PLT", "3UKL", "5EUS", "5LUS", "5ULS", "AAPL",
    "ACHR", "ADBE", "AMAT", "AMD", "AMGN", "AMZN", "ANET", "APP", "ASML", "AXP",
    "BKNG", "BLK", "BLKC", "CCJ", "CON3", "DAGB", "DAVV", "EQIX", "FSLR", "FWRG",
    "GLDW", "GOOGL", "HOOD", "HUT", "IBKR", "JPM", "KLAC", "LLY", "LQQ3", "LQS5",
    "MAG5", "MSFT", "MST3", "MSTR", "NFLX", "NVDA", "ORCL", "PLTR", "QCOM", "R1VL",
    "SNOW", "SNV3", "SPY4", "SQS5", "TLN", "TSLA", "UNH", "V", "VST", "VUAG",
    "VUKG", "XNIF", "3AMZ", "3FB", "3AMD", "3SLV", "3HCL", "3TSM", "3MSF", "3GDX"
]

# ================================
# 📈 MACD Functions
# ================================
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

    for ticker in NASDAQ100_TICKERS:
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


# ================================
# 📊 SMA100 Screener
# ================================
SMA_PERIOD = 100
TOLERANCE = 0.01
LOOKBACK = 15

def run_sma_screener():
    rows = []
    print(f"\n📅 Running SMA100 Touch Screener — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    for t in NASDAQ100_TICKERS:
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

    return pd.DataFrame(rows)


# ================================
# 🖌️ Highlight + HTML Table
# ================================
def highlight_most_recent(df, date_col, ticker_col="Ticker"):
    if df.empty:
        return df.copy()
    df_copy = df.copy()
    df_copy[date_col] = pd.to_datetime(df_copy[date_col])
    recent_dates = df_copy.groupby(ticker_col)[date_col].transform("max")
    df_copy["__highlight__"] = df_copy[date_col] == recent_dates
    return df_copy

def df_to_html_highlighted(df):
    if df.empty:
        return "<p>No data available.</p>"

    def format_row(row):
        html = ""
        for col, val in row.items():
            if col == "__highlight__":
                continue
            cell_val = str(val)
            if row["__highlight__"]:
                cell_val = f"<b style='color: #0070f3;'>{cell_val}</b>"
            html += f"<td>{cell_val}</td>"
        return f"<tr>{html}</tr>"

    headers = "".join([f"<th>{col}</th>" for col in df.columns if col != "__highlight__"])
    body = "".join([format_row(row) for _, row in df.iterrows()])

    return f"""
    <table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse; font-family:Arial; font-size:13px; margin-bottom:20px;">
        <thead style="background-color:#f2f2f2;">{headers}</thead>
        <tbody>{body}</tbody>
    </table>
    """


# ================================
# 📧 Email Function
# ================================
def send_email_two_csv_html(macd_df, sma_df, recipient_email):
    sender_email = os.environ.get("EMAIL_USER")
    sender_password = os.environ.get("EMAIL_PASSWORD")

    subject = f"NASDAQ-100 Technical Signals — {datetime.now().strftime('%Y-%m-%d')}"

    html_macd = df_to_html_highlighted(macd_df)
    html_sma = df_to_html_highlighted(sma_df)

    html_body = f"""
    <html>
      <body>
        <h2>📈 MACD Negative Territory Crossovers</h2>
        {html_macd}

        <h2>📊 SMA100 Touches (±1%)</h2>
        {html_sma}

        <p style="font-size:12px;color:#555;">* Most recent signal per ticker is <b style='color:#0070f3;'>highlighted</b>.</p>
      </body>
    </html>
    """

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = recipient_email
    msg['Subject'] = subject
    msg.attach(MIMEText(html_body, 'html'))

    # Attach CSVs
    for df, name in [(macd_df, "MACD_Negative_Crossovers"), (sma_df, "SMA100_Touch_Report")]:
        if not df.empty:
            buffer = io.StringIO()
            df.drop(columns=["__highlight__"], errors="ignore").to_csv(buffer, index=False)
            buffer.seek(0)
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(buffer.read())
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', 'attachment', filename=f"{name}_{datetime.now().strftime('%Y-%m-%d')}.csv")
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
    macd_df = run_macd_screener()
    sma_df = run_sma_screener()

    # Sort & highlight
    if not macd_df.empty:
        macd_df = macd_df.sort_values(by="Most_Recent_Crossover", ascending=False)
        macd_df = highlight_most_recent(macd_df, "Most_Recent_Crossover")

    if not sma_df.empty:
        sma_df = sma_df.sort_values(by="Date", ascending=False)
        sma_df = highlight_most_recent(sma_df, "Date")

    if macd_df.empty:
        print("\n🚫 No MACD Negative Territory crossovers found.")
    if sma_df.empty:
        print("\n🚫 No SMA100 touches found.")

    if not macd_df.empty or not sma_df.empty:
        send_email_two_csv_html(macd_df, sma_df, "sampath.uk2020@gmail.com")
