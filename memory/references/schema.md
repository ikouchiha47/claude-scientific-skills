# Memory Schema Reference

## observations

Facts and findings discovered during research.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Auto-increment |
| created_at | TEXT | ISO timestamp |
| content | TEXT | The observation (required) |
| tags | TEXT | Comma-separated tags for filtering |
| source | TEXT | Which skills/data sources produced this |
| confidence | TEXT | high/medium/low |

**Examples:**
- "Coal India stock drops 2-4% within 48h of M5+ earthquakes in Jharkhand/Odisha mining belt"
- "HDFC Bank and ICICI Bank are cointegrated (p=0.02) over 3-year window"
- "RSI(14) < 25 on NIFTY has preceded 5%+ bounces 73% of the time since 2015"

## analyses

Completed analysis results for stocks/markets.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Auto-increment |
| created_at | TEXT | ISO timestamp |
| symbol | TEXT | Stock symbol (e.g., RELIANCE.NS) |
| analysis_type | TEXT | technical, fundamental, quant, geo |
| timeframe | TEXT | 1D, 1W, 1M, 1Y, etc. |
| findings | TEXT | What was found (required) |
| recommendation | TEXT | buy/sell/hold with reasoning |
| data_sources | TEXT | Skills used |
| confidence | TEXT | high/medium/low |

## strategies

Backtest results and strategy performance.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Auto-increment |
| created_at | TEXT | ISO timestamp |
| name | TEXT | Strategy name (required) |
| description | TEXT | What the strategy does |
| symbols | TEXT | Symbols tested on |
| parameters | TEXT | JSON string of params |
| total_return | REAL | Total return (0.23 = 23%) |
| sharpe_ratio | REAL | Annualized Sharpe |
| max_drawdown | REAL | Max drawdown (-0.12 = -12%) |
| win_rate | REAL | Win rate (0.55 = 55%) |
| backtest_period | TEXT | e.g., "2020-01-01 to 2025-01-01" |
| notes | TEXT | Additional notes |

## correlations

Discovered signal-asset relationships.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Auto-increment |
| created_at | TEXT | ISO timestamp |
| signal_type | TEXT | earthquake, weather, flights, trade, etc. (required) |
| signal_source | TEXT | USGS, Open-Meteo, OpenSky, etc. |
| asset | TEXT | Stock/index affected (required) |
| correlation_strength | REAL | -1 to 1 |
| direction | TEXT | positive/negative |
| lag_days | INTEGER | Days between signal and price reaction |
| timeframe | TEXT | Over what period |
| evidence | TEXT | Supporting evidence |
| confidence | TEXT | high/medium/low |

## sessions

Session history for continuity.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Auto-increment |
| created_at | TEXT | ISO timestamp |
| query | TEXT | What the user asked |
| skills_used | TEXT | Comma-separated skill names |
| summary | TEXT | What was accomplished |
| status | TEXT | active/completed/abandoned |
