---
name: chart-scout
description: Automate stock chart screenshot capture from financial websites (Screener.in, Chartink, Google Finance, TradingView) using Playwright. Captures clean chart images with popup/modal removal, timeframe switching, and element-level screenshots. Pairs with alpha-vantage (data) and technical-analyst (LLM visual analysis) for a full pipeline from symbol to analysis report.
license: MIT
metadata:
    skill-author: Iko Uchiha
---

# Chart Scout — Automated Stock Chart Screenshots

Capture clean stock chart screenshots from financial websites using Playwright. Works standalone — just provide a symbol and exchange to get a chart screenshot. Optionally pairs with alpha-vantage (numerical data) and technical-analyst (LLM visual analysis) for a richer pipeline.

## Installation

```bash
uv pip install playwright pyyaml requests
uv run python -m playwright install chromium
```

## Quick Start

```bash
# Indian equity (auto-selects screener.in)
uv run python scripts/chart_scout.py --symbol RELIANCE --exchange NSE

# US equity on Google Finance
uv run python scripts/chart_scout.py --symbol AAPL --exchange NASDAQ --site google_finance

# With timeframe
uv run python scripts/chart_scout.py --symbol TCS --exchange NSE --timeframe 5Y

# Full pipeline: data fetch + screenshot + analysis prompt
uv run python scripts/pipeline_run.py --symbol RELIANCE --exchange NSE --fetch-data
```

## Supported Sites

| Site | Region | Best For |
|------|--------|----------|
| screener.in | India | Indian equities (primary) |
| chartink.com | India | Indian screener charts |
| google.com/finance | Global | Quick global lookups |
| tradingview.com | Global | Best chart quality |

Auto site selection: NSE/BSE symbols → screener.in; US symbols → Google Finance.

## Features

- **Popup removal**: Cookie banners, modals, subscription nags — all removed via JS injection
- **Timeframe switching**: Click 1Y/5Y/Max buttons per site
- **Fallback chain**: If primary site fails, tries next in order
- **Element-level screenshots**: Captures just the chart div, not the full page
- **Pipeline integration**: Generates analysis prompts for the technical-analyst skill

## Pipeline Usage

```python
from scripts.chart_scout import capture_with_fallback, load_registry
import asyncio

registry = load_registry()
screenshot = asyncio.run(capture_with_fallback(
    symbol="RELIANCE", exchange="NSE", registry=registry,
    timeframe="1Y", output_dir=Path("./charts")
))
# screenshot → pass to technical-analyst skill for LLM analysis
```

## Configuration

Site configs live in `assets/site_registry.yaml`. Each site defines:
- URL pattern, chart selectors, timeframe button selectors
- Popup removal strategy, viewport size, wait timeouts
- Fallback selectors for chart element capture

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ALPHAVANTAGE_API_KEY` | Optional | For pipeline data fetch via alpha-vantage |

Environment variables should be set before running scripts. If a `.env` file exists in the project root, source it first:

```bash
source .env
uv run python scripts/pipeline_run.py --symbol RELIANCE --exchange NSE --fetch-data
```

## File Structure

```
scripts/chart_scout.py     — Main: symbol + site → screenshot
scripts/popup_cleaner.py   — Popup/modal removal strategies
scripts/pipeline_run.py    — End-to-end pipeline orchestrator
assets/site_registry.yaml  — Machine-readable site configs
references/                — Detailed docs on Playwright, popups, sites, pipeline
```
