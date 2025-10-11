import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import os

# --- 1️⃣ Parameters ---
ticker = "^GSPC"  # S&P 500 Index
start_date = "2005-01-01"
end_date = datetime.today().strftime("%Y-%m-%d")

print(f"Fetching {ticker} data from {start_date} to {end_date}...")

# --- 2️⃣ Download historical data ---
data = yf.download(ticker, start=start_date, end=end_date, progress=False)

# Flatten columns if multi-index (e.g., when downloading multiple tickers)
if isinstance(data.columns, pd.MultiIndex):
    data.columns = data.columns.get_level_values(0)

df = data.copy()

# --- 3️⃣ Calculate daily returns ---
df["prev_close"] = df["Close"].shift(1)
df["one_day_ret"] = df["Close"] / df["prev_close"] - 1

# --- 4️⃣ Identify big one-day drops (>3%) ---
threshold = -0.03
big_drop_days = df[df["one_day_ret"] <= threshold].copy()

results = []

# --- 5️⃣ Calculate 7-day forward returns after each big drop ---
for idx in big_drop_days.index:
    idx_pos = df.index.get_loc(idx)
    if idx_pos + 7 < len(df):
        today_close = df.iloc[idx_pos]["Close"]
        future_close = df.iloc[idx_pos + 7]["Close"]
        fwd_ret = (future_close / today_close) - 1
        results.append({
            "Date": idx.date(),
            "Drop_%": df.loc[idx, "one_day_ret"] * 100,
            "7d_FwdRet_%": fwd_ret * 100
        })

# --- 6️⃣ Summarize results ---
res_df = pd.DataFrame(results)
mean_fwd_ret = res_df["7d_FwdRet_%"].mean() if not res_df.empty else np.nan

print(f"\n📊 Analysis Summary for {ticker}")
print(f"Period: {start_date} → {end_date}")
print(f"Days with >3% single-day loss: {len(res_df)}")
print(f"Average 7-day forward return: {mean_fwd_ret:.2f}%")

print("\nLast 5 Events:")
print(res_df.tail())

# --- 7️⃣ Save results to CSV ---
csv_path = "spx_7day_correction_stats.csv"
res_df.to_csv(csv_path, index=False)
print(f"\n✅ Saved detailed stats to: {csv_path}")

# --- 8️⃣ Plot distribution ---
if not res_df.empty:
    plt.figure(figsize=(10,6))
    plt.hist(res_df["7d_FwdRet_%"], bins=20, edgecolor="black")
    plt.title("Distribution of 7-Day Forward Returns after >3% Down Days")
    plt.xlabel("7-Day Forward Return (%)")
    plt.ylabel("Frequency")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig("spx_correction_distribution.png")
    print("✅ Saved plot as: spx_correction_distribution.png")
else:
    print("⚠️ No qualifying events found for analysis.")
