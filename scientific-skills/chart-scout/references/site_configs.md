# Site Configurations

Human-readable documentation for each supported chart site.

## Screener.in

- **URL pattern**: `https://www.screener.in/company/{symbol}/consolidated/`
- **Region**: India (NSE/BSE)
- **Login**: Not required
- **Chart element**: `#chart-container` or `canvas`
- **Timeframes**: 1Y, 5Y, Max (via buttons)
- **Quirks**:
  - Symbol must be the exact NSE/BSE ticker (e.g., `RELIANCE`, `TCS`)
  - Uses `/consolidated/` path for consolidated financials
  - Chart renders via canvas element after JS loads

## Chartink

- **URL pattern**: `https://chartink.com/stocks/{symbol}.html`
- **Region**: India (NSE/BSE)
- **Login**: Not required
- **Chart element**: `#myChart` or `canvas`
- **Timeframes**: 1Y, 5Y, All
- **Quirks**:
  - Symbol format is the plain ticker name
  - May show promotional popups

## Google Finance

- **URL pattern**: `https://www.google.com/finance/quote/{symbol}:{exchange}`
- **Region**: Global
- **Login**: Not required
- **Chart element**: Canvas-based chart in c-wiz component
- **Timeframes**: 1D, 5D, 1M, 6M, YTD, 1Y, 5Y, Max
- **Quirks**:
  - EU regions may show consent page first
  - Symbol format: `AAPL:NASDAQ`, `RELIANCE:NSE`
  - Chart uses custom Google web components, selectors can be fragile

## TradingView

- **URL pattern**: `https://www.tradingview.com/chart/?symbol={exchange}:{symbol}`
- **Region**: Global
- **Login**: Not required for basic charts
- **Chart element**: `.chart-markup-table` or canvas
- **Timeframes**: 1D, 1W, 1M (via toolbar)
- **Quirks**:
  - Best chart quality but most aggressive about popups
  - May require dismissing login prompts
  - Rate-limits or blocks headless browsers after many requests
  - Use a realistic user agent string
  - Larger viewport (1920x1080) recommended
