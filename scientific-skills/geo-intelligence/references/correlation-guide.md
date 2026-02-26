# Correlation Guide — Geo Signals + Financial Data

How to combine geo-intelligence signals with stock/market data for analysis.

## Pattern: Event → Impact Assessment

```python
import requests
import yfinance as yf
import pandas as pd

# 1. Fetch earthquake data
quakes = requests.get("https://earthquake.usgs.gov/fdsnws/event/1/query", params={
    "format": "geojson", "starttime": "2023-01-01", "minmagnitude": 6.0,
}).json()["features"]

# 2. Extract dates of significant earthquakes
quake_dates = [pd.Timestamp(q["properties"]["time"], unit="ms").date() for q in quakes]

# 3. Check insurance stock reaction
stock = yf.download("GICRE.NS", period="2y")  # General Insurance Corp
stock["Return"] = stock["Close"].pct_change()

# 4. Average return on earthquake days vs normal days
eq_returns = stock[stock.index.date.isin(quake_dates)]["Return"]
normal_returns = stock[~stock.index.date.isin(quake_dates)]["Return"]

print(f"Avg return on earthquake days: {eq_returns.mean():.4f}")
print(f"Avg return on normal days:     {normal_returns.mean():.4f}")
```

## Pattern: Weather → Agriculture Stocks

```python
# Monsoon rainfall vs agriculture stock performance
import requests
import yfinance as yf

# Historical monsoon rainfall (Jun-Sep)
resp = requests.get("https://archive-api.open-meteo.com/v1/archive", params={
    "latitude": 20.5937, "longitude": 78.9629,  # Central India
    "start_date": "2023-06-01", "end_date": "2023-09-30",
    "daily": "precipitation_sum",
})
rain_data = resp.json()["daily"]
total_rain = sum(r for r in rain_data["precipitation_sum"] if r)

# Agriculture/fertilizer stocks during monsoon
agri = yf.download(["UPL.NS", "PIIND.NS", "CHAMBLFERT.NS"], start="2023-06-01", end="2023-09-30")["Close"]
monsoon_return = (agri.iloc[-1] / agri.iloc[0] - 1)
print(f"Total monsoon rainfall: {total_rain:.0f}mm")
print(f"Monsoon stock returns:\n{monsoon_return}")
```

## Pattern: Flight Volume → Economic Activity

```python
# Track daily flights as economic proxy
# (Requires historical data collection over time)
import requests
import time

now = int(time.time())
resp = requests.get("https://opensky-network.org/api/flights/arrival", params={
    "airport": "VABB",  # Mumbai
    "begin": now - 86400,
    "end": now,
})
mumbai_flights = len(resp.json())

# Compare with NIFTY performance
nifty = yf.download("^NSEI", period="5d")["Close"]
print(f"Mumbai arrivals (24h): {mumbai_flights}")
print(f"NIFTY last close: {nifty.iloc[-1]:.0f}")
```

## Pattern: Geopolitical Tone → Market Sentiment

```python
# GDELT sentiment vs market returns
resp = requests.get("https://api.gdeltproject.org/api/v2/doc/doc", params={
    "query": "India economy",
    "mode": "timelinetone",
    "format": "json",
    "timespan": "90d",
})
# Correlate daily tone with NIFTY returns
```

## Signal Strength Guide

| Signal | Lead Time | Strength | Noise |
|--------|-----------|----------|-------|
| Major earthquake (M7+) | Same day | Strong (insurance) | Low |
| Oil inventory report | Same day | Strong (energy) | Low |
| Monsoon forecast | Weeks | Moderate (agri) | Medium |
| Flight volume trends | Weeks-months | Weak (macro) | High |
| GDELT sentiment | Days | Weak-moderate | High |
| Trade flow changes | Months | Moderate | Medium |

Stronger signals (earthquakes, oil reports) are already priced in quickly. Weaker signals (flights, sentiment) need longer time horizons and combination with other data to be useful.
