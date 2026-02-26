# Pipeline Integration Guide

How chart-scout connects to alpha-vantage and technical-analyst skills.

## Architecture

```
alpha-vantage (fetch OHLCV, RSI, MACD data)
       ↓
chart-scout (Playwright → screenshot)
       ↓
technical-analyst (LLM visual analysis → report)
```

## Step-by-Step

### 1. Fetch Data (alpha-vantage skill)

```python
import requests, os

API_KEY = os.environ["ALPHAVANTAGE_API_KEY"]
base = "https://www.alphavantage.co/query"

# Get daily prices
prices = requests.get(base, params={
    "function": "TIME_SERIES_DAILY", "symbol": "RELIANCE.NSE",
    "apikey": API_KEY, "outputsize": "compact"
}).json()

# Get RSI
rsi = requests.get(base, params={
    "function": "RSI", "symbol": "RELIANCE.NSE", "interval": "daily",
    "time_period": 14, "series_type": "close", "apikey": API_KEY
}).json()
```

### 2. Capture Chart (chart-scout)

```bash
# CLI
uv run python scripts/chart_scout.py --symbol RELIANCE --exchange NSE --timeframe 1Y --output ./charts/

# Or use the pipeline script
uv run python scripts/pipeline_run.py --symbol RELIANCE --exchange NSE --fetch-data
```

```python
# Programmatic
from scripts.chart_scout import capture_with_fallback, load_registry
import asyncio

registry = load_registry()
screenshot = asyncio.run(capture_with_fallback("RELIANCE", "NSE", registry))
```

### 3. Analyze (technical-analyst skill)

Pass the screenshot to Claude with a prompt like:

> Analyze this stock chart for RELIANCE (NSE). Identify trends, support/resistance levels, and chart patterns. RSI(14) is currently 58.3.

The `pipeline_run.py` script generates this prompt automatically and saves it alongside the screenshot.

## Auto Site Selection

The pipeline automatically picks the best site based on exchange:

| Exchange | Primary Site | Fallback Chain |
|----------|-------------|----------------|
| NSE, BSE | screener.in | chartink → google_finance → tradingview |
| NASDAQ, NYSE | google_finance | tradingview |
| Other | google_finance | tradingview |

## Output Files

After running `pipeline_run.py`, you get:

```
charts/
├── RELIANCE_NSE_screener_in_1Y.png      # Chart screenshot
└── RELIANCE_NSE_pipeline_result.json     # Metadata + analysis prompt
```
