# save as spx_drop_analysis.py and run with: python spx_drop_analysis.py

import pandas as pd
import numpy as np
from datetime import datetime
import yfinance as yf

# --- CONFIG ---
use_csv = False        # set True if you want to use a local CSV instead of yfinance
csv_path = "spx_daily.csv"  # if use_csv == True, CSV must have columns: Date, Close
ticker = "^GSPC"
start_date = "2005-01-01"
end_date = datetime.today().strftime("%Y-%m-%d")
trigger_thresh = -0.03  # -3.0%
window = 7

# --- LOAD DATA ---
if use_csv:
    df = pd.read_csv(csv_path, parse_dates=["Date"])
    df = df.sort_values("Date").reset_index(drop=True)
    df = df[["Date", "Close"]]
else:
    data = yf.download(ticker, start=start_date, end=end_date, progress=False)
    df = data[["Close"]].reset_index()

# make sure clean
df = df.dropna().reset_index(drop=True)
df["prev_close"] = df["Close"].shift(1)
df["one_day_ret"] = df["Close"] / df["prev_close"] - 1

# find trigger days where one_day_ret <= -3%
triggers = df[df["one_day_ret"] <= trigger_thresh].copy()
triggers = triggers.reset_index()  # keep index aligning to df

results = []
for _, row in triggers.iterrows():
    i = int(row["index"])  # position in df
    # ensure there are at least 'window' next trading rows
    if i + window >= len(df):
        continue
    close_t = row["Close"]
    future_window = df.loc[i+1 : i+window, "Close"]
    min_future = future_window.min()
    correction = (min_future - close_t) / close_t  # negative if decline
    results.append({
        "date": row["Date"].date(),
        "one_day_ret_pct": row["one_day_ret"] * 100,
        "next7_min_close": min_future,
        "correction_pct": correction * 100  # negative number
    })

res_df = pd.DataFrame(results)
if res_df.empty:
    print("No trigger events found (or not enough data).")
else:
    # convert correction to positive decline for readability
    res_df["decline_pct"] = -res_df["correction_pct"]

    # Summary stats
    count = len(res_df)
    mean_decline = res_df["decline_pct"].mean()
    median_decline = res_df["decline_pct"].median()
    std_decline = res_df["decline_pct"].std()
    p25 = res_df["decline_pct"].quantile(0.25)
    p75 = res_df["decline_pct"].quantile(0.75)
    max_decline = res_df["decline_pct"].max()
    pct_ge_5 = (res_df["decline_pct"] >= 5.0).mean() * 100
    pct_ge_10 = (res_df["decline_pct"] >= 10.0).mean() * 100

    print(f"Trigger days (one-day <= -3%): {count}")
    print(f"Mean next-7-day decline (from trigger close): {mean_decline:.2f}%")
    print(f"Median: {median_decline:.2f}%, STD: {std_decline:.2f}%")
    print(f"25th / 75th percentiles: {p25:.2f}% / {p75:.2f}%")
    print(f"Worst single case (max decline within next 7 days): {max_decline:.2f}%")
    print(f"% of events with >= 5% further decline in next 7 days: {pct_ge_5:.1f}%")
    print(f"% of events with >= 10% further decline in next 7 days: {pct_ge_10:.1f}%")

    # Optional: print the event table
    pd.set_option("display.max_rows", 200)
    print("\nSample events (date, one-day drop %, max 7-day decline %):")
    print(res_df[["date","one_day_ret_pct","decline_pct"]].sort_values("date", ascending=False).head(20).to_string(index=False))
