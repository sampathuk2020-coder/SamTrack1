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
# 📌 Ticker List
# ================================
NASDAQ100_TICKERS = [

NASDAQ100 = [
    "AAPL","ABNB","ADBE","ADI","ADP","AEP","ALAB","ALNY",
    "AMD","AMGN","AMZN","ANSS","APP","ARM","ASML","AVGO",
    "AXON","AZN","BIIB","BKNG","CDNS","CEG","CHTR","CMCSA",
    "COST","CPRT","CRWD","CRWV","CSCO","CSX","CTAS","DDOG",
    "DXCM","EA","EXC","FAST","FTNT","GEHC","GILD","GOOG",
    "GOOGL","HON","IDXX","INTC","INTU","ISRG","KDP","KHC",
    "KLAC","LIN","LRCX","MAR","MCHP","MDLZ","MELI","META",
    "MNST","MPWR","MRVL","MSFT","MSTR","MU","NBIS","NFLX",
    "NVDA","NXPI","ODFL","ORLY","PANW","PAYX","PCAR","PDD",
    "PEP","PLTR","PYPL","QCOM","REGN","RKLB","ROP","ROST",
    "SBUX","SHOP","SNPS","STX","TEAM","TER","TMUS","TSLA",
    "TTWO","TXN","VRTX","WBD","WDAY","WDC","WMT","XEL"
]
    
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
    """Bullish crossover in negative MACD region"""
    crossover_dates = []
    for i in range(1, min(days + 1, len(df))):
        macd_prev, signal_prev = df['MACD'].iloc[-i - 1], df['Signal'].iloc[-i - 1]
        macd_curr, signal_curr = df['MACD'].iloc[-i], df['Signal'].iloc[-i]
        if macd_prev < signal_prev and macd_curr > signal_curr and macd_curr < 0 and signal_curr < 0:
            crossover_dates.append(df.index[-i].date())
    return crossover_dates


def check_positive_macd_bearish_crossover(df, days=100):
    """Bearish crossover in positive MACD region"""
    crossover_dates = []
    for i in range(1, min(days + 1, len(df))):
        macd_prev, signal_prev = df['MACD'].iloc[-i - 1], df['Signal'].iloc[-i - 1]
        macd_curr, signal_curr = df['MACD'].iloc[-i], df['Signal'].iloc[-i]
        if macd_prev > signal_prev and macd_curr < signal_curr and macd_curr > 0 and signal_curr > 0:
            crossover_dates.append(df.index[-i].date())
    return crossover_dates


def run_macd_screener():
    bullish, bearish = [], []
    print(f"\n📅 Running MACD Screeners — {datetime.now():%Y-%m-%d %H:%M:%S}\n")

    for ticker in NASDAQ100_TICKERS:
        try:
            data = yf.download(ticker, period="6mo", interval="1d", progress=False)
            if data.empty:
                continue
            data = calculate_macd(data)

            neg_cross = check_negative_macd_crossover(data)
            pos_cross = check_positive_macd_bearish_crossover(data)

            if neg_cross:
                bullish.append({"Ticker": ticker, "Most_Recent_Crossover": max(neg_cross)})
            if pos_cross:
                bearish.append({"Ticker": ticker, "Most_Recent_Crossover": max(pos_cross)})
        except Exception as e:
            print(f"❌ Error fetching {ticker}: {e}")

    return (
        pd.DataFrame(bullish),
        pd.DataFrame(bearish)
    )

# ================================
# 📊 SMA100 Screener
# ================================
SMA_PERIOD = 100
TOLERANCE = 0.01
LOOKBACK = 15

def run_sma_screener():
    rows = []
    print(f"\n📅 Running SMA100 Touch Screener — {datetime.now():%Y-%m-%d %H:%M:%S}\n")

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

            mask = np.abs(recent['Close'] - recent['SMA100']) <= (TOLERANCE * recent['SMA100'])
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


def df_to_html_highlighted(df, color="#0070f3"):
    if df.empty:
        return "<p>No data available.</p>"

    df_copy = df.copy()
    if "__highlight__" not in df_copy.columns:
        df_copy["__highlight__"] = False

    def format_row(row):
        html = ""
        for col, val in row.items():
            if col == "__highlight__":
                continue
            cell_val = str(val)
            if "__highlight__" in row and row["__highlight__"]:
                cell_val = f"<b style='color:{color};'>{cell_val}</b>"
            html += f"<td>{cell_val}</td>"
        return f"<tr>{html}</tr>"

    headers = "".join([f"<th>{col}</th>" for col in df_copy.columns if col != "__highlight__"])
    body = "".join([format_row(row) for _, row in df_copy.iterrows()])

    return f"""
    <table border="1" cellpadding="6" cellspacing="0"
           style="border-collapse:collapse; font-family:Arial; font-size:13px; margin-bottom:20px;">
        <thead style="background-color:#f2f2f2;">{headers}</thead>
        <tbody>{body}</tbody>
    </table>
    """

# ================================
# 📧 Email Function
# ================================
def send_email_three_csv_html(macd_bull_df, macd_bear_df, sma_df, recipient_email):
    sender_email = os.environ.get("EMAIL_USER")
    sender_password = os.environ.get("EMAIL_PASSWORD")

    subject = f"NASDAQ-100 Technical Signals — {datetime.now():%Y-%m-%d}"

    # Safeguard highlight column existence
    for df in [macd_bull_df, macd_bear_df, sma_df]:
        if not df.empty and "__highlight__" not in df.columns:
            df["__highlight__"] = False

    html_bull = df_to_html_highlighted(macd_bull_df, color="#00A86B")  # green
    html_bear = df_to_html_highlighted(macd_bear_df, color="#FF4C4C")  # red
    html_sma = df_to_html_highlighted(sma_df)

    html_body = f"""
    <html>
      <body>
        <h2>🟢 MACD Negative Territory — Bullish Crossovers</h2>
        {html_bull}

        <h2>🔴 MACD Positive Territory — Bearish Crossovers</h2>
        {html_bear}

        <h2>📊 SMA100 Touches (±1%)</h2>
        {html_sma}

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

    # Attach CSVs
    for df, name in [
        (macd_bull_df, "MACD_Bullish_Negative"),
        (macd_bear_df, "MACD_Bearish_Positive"),
        (sma_df, "SMA100_Touch_Report")
    ]:
        if not df.empty:
            buffer = io.StringIO()
            df.drop(columns=["__highlight__"], errors="ignore").to_csv(buffer, index=False)
            buffer.seek(0)
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(buffer.read())
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', 'attachment',
                            filename=f"{name}_{datetime.now():%Y-%m-%d}.csv")
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
    macd_bull_df, macd_bear_df = run_macd_screener()
    sma_df = run_sma_screener()

    # Sort & highlight
    if not macd_bull_df.empty:
        macd_bull_df = macd_bull_df.sort_values(by="Most_Recent_Crossover", ascending=False)
        macd_bull_df = highlight_most_recent(macd_bull_df, "Most_Recent_Crossover")

    if not macd_bear_df.empty:
        macd_bear_df = macd_bear_df.sort_values(by="Most_Recent_Crossover", ascending=False)
        macd_bear_df = highlight_most_recent(macd_bear_df, "Most_Recent_Crossover")

    if not sma_df.empty:
        sma_df = sma_df.sort_values(by="Date", ascending=False)
        sma_df = highlight_most_recent(sma_df, "Date")

    if macd_bull_df.empty:
        print("\n🚫 No MACD Bullish (Negative Territory) crossovers found.")
    if macd_bear_df.empty:
        print("\n🚫 No MACD Bearish (Positive Territory) crossovers found.")
    if sma_df.empty:
        print("\n🚫 No SMA100 touches found.")

    if not (macd_bull_df.empty and macd_bear_df.empty and sma_df.empty):
        send_email_three_csv_html(macd_bull_df, macd_bear_df, sma_df, "sampath.uk2020@gmail.com")
