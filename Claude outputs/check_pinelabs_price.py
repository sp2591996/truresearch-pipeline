"""
check_pinelabs_price.py -- quick one-off diagnostic, not part of the
regular pipeline. Prints exactly what Yahoo Finance is reporting for
PINELABS right now, so we can see if the ₹202.17 vs ₹198.85 gap is a
timing issue or just a genuine difference between data providers.

Run from inside TrueResearch Code (same venv as everything else):
    python check_pinelabs_price.py
"""
import yfinance as yf

t = yf.Ticker("PINELABS.NS")
info = t.info

print("regularMarketPrice:", info.get("regularMarketPrice"))
print("previousClose:", info.get("previousClose"))
print("regularMarketPreviousClose:", info.get("regularMarketPreviousClose"))
print("regularMarketTime:", info.get("regularMarketTime"))
print("postMarketPrice:", info.get("postMarketPrice"))

hist = t.history(period="5d", interval="1d")
print("\nLast 5 daily bars (from Yahoo):")
print(hist[["Open", "High", "Low", "Close", "Volume"]])
