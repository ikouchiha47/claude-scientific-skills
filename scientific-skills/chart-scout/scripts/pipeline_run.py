#!/usr/bin/env python3
"""
pipeline_run.py — End-to-end: symbol → chart screenshot → analysis handoff.

Orchestrates the full pipeline:
  1. (Optional) Fetch data via Alpha Vantage
  2. Capture chart screenshot via chart_scout
  3. Hand off screenshot path for technical-analyst skill analysis

Usage:
    python pipeline_run.py --symbol RELIANCE --exchange NSE
    python pipeline_run.py --symbol AAPL --exchange NASDAQ --timeframe 1Y --fetch-data
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
from chart_scout import capture_with_fallback, load_registry


def fetch_alpha_vantage_data(symbol: str, exchange: str) -> dict | None:
    """Fetch key indicators from Alpha Vantage (if API key is set)."""
    api_key = os.environ.get("ALPHAVANTAGE_API_KEY")
    if not api_key:
        print("Warning: ALPHAVANTAGE_API_KEY not set, skipping data fetch.")
        return None

    try:
        import requests
    except ImportError:
        print("Warning: requests not installed, skipping data fetch.")
        return None

    base_url = "https://www.alphavantage.co/query"

    # Map exchange to Alpha Vantage symbol format
    av_symbol = symbol
    if exchange in ("NSE", "BSE"):
        av_symbol = f"{symbol}.{exchange}"

    data = {}

    # Fetch daily prices
    try:
        resp = requests.get(
            base_url,
            params={"function": "TIME_SERIES_DAILY", "symbol": av_symbol, "apikey": api_key, "outputsize": "compact"},
            timeout=15,
        )
        ts = resp.json().get("Time Series (Daily)", {})
        if ts:
            latest_date = sorted(ts.keys())[-1]
            data["latest_price"] = ts[latest_date]
            data["latest_date"] = latest_date
    except Exception as e:
        print(f"Warning: Failed to fetch daily prices: {e}")

    # Fetch RSI
    try:
        resp = requests.get(
            base_url,
            params={
                "function": "RSI", "symbol": av_symbol, "interval": "daily",
                "time_period": 14, "series_type": "close", "apikey": api_key,
            },
            timeout=15,
        )
        rsi_data = resp.json().get("Technical Analysis: RSI", {})
        if rsi_data:
            latest_date = sorted(rsi_data.keys())[-1]
            data["rsi_14"] = rsi_data[latest_date]["RSI"]
    except Exception as e:
        print(f"Warning: Failed to fetch RSI: {e}")

    return data if data else None


def generate_analysis_prompt(symbol: str, exchange: str, screenshot_path: Path, av_data: dict | None) -> str:
    """Generate a prompt for the technical-analyst skill."""
    prompt = f"""Analyze the chart for {symbol} ({exchange}).

Screenshot saved at: {screenshot_path}

Please provide:
1. Trend identification (bullish/bearish/sideways)
2. Key support and resistance levels visible on the chart
3. Notable chart patterns (head & shoulders, double top/bottom, triangles, etc.)
4. Volume analysis if visible
5. Overall technical outlook and suggested action
"""
    if av_data:
        prompt += f"\nAlpha Vantage data:\n{json.dumps(av_data, indent=2)}\n"
        if "rsi_14" in av_data:
            prompt += f"\nRSI(14): {av_data['rsi_14']}"

    return prompt


async def run_pipeline(
    symbol: str,
    exchange: str,
    site: str | None = None,
    timeframe: str | None = None,
    output_dir: Path = Path("./charts"),
    fetch_data: bool = False,
) -> dict:
    """Run the full chart-scout pipeline."""
    result = {
        "symbol": symbol,
        "exchange": exchange,
        "timestamp": datetime.now().isoformat(),
        "screenshot": None,
        "av_data": None,
        "analysis_prompt": None,
    }

    # Step 1: Fetch Alpha Vantage data (optional)
    if fetch_data:
        print("\n--- Step 1: Fetching Alpha Vantage data ---")
        result["av_data"] = fetch_alpha_vantage_data(symbol, exchange)
    else:
        print("\n--- Step 1: Skipping data fetch (use --fetch-data to enable) ---")

    # Step 2: Capture chart screenshot
    print("\n--- Step 2: Capturing chart screenshot ---")
    registry = load_registry()
    screenshot = await capture_with_fallback(
        symbol=symbol, exchange=exchange, registry=registry,
        site=site, timeframe=timeframe, output_dir=output_dir,
    )

    if screenshot:
        result["screenshot"] = str(screenshot)
        print(f"Screenshot: {screenshot}")
    else:
        print("Failed to capture chart.")
        return result

    # Step 3: Generate analysis prompt for technical-analyst
    print("\n--- Step 3: Generating analysis prompt ---")
    prompt = generate_analysis_prompt(symbol, exchange, screenshot, result["av_data"])
    result["analysis_prompt"] = prompt
    print(f"\nAnalysis prompt:\n{prompt}")
    print(
        "\nTo complete the analysis, use the technical-analyst skill with the screenshot above."
        "\nExample: Ask Claude to analyze the chart image using the technical-analyst skill."
    )

    # Save pipeline result
    result_path = output_dir / f"{symbol}_{exchange}_pipeline_result.json"
    with open(result_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"\nPipeline result saved: {result_path}")

    return result


def main():
    parser = argparse.ArgumentParser(description="Chart Scout Pipeline: screenshot → analysis")
    parser.add_argument("--symbol", required=True, help="Stock symbol")
    parser.add_argument("--exchange", required=True, help="Exchange (NSE, NASDAQ, etc.)")
    parser.add_argument("--site", default=None, help="Force specific site")
    parser.add_argument("--timeframe", default=None, help="Chart timeframe (1Y, 5Y, Max)")
    parser.add_argument("--output", default="./charts", help="Output directory")
    parser.add_argument("--fetch-data", action="store_true", help="Fetch Alpha Vantage data too")
    args = parser.parse_args()

    asyncio.run(
        run_pipeline(
            symbol=args.symbol,
            exchange=args.exchange,
            site=args.site,
            timeframe=args.timeframe,
            output_dir=Path(args.output),
            fetch_data=args.fetch_data,
        )
    )


if __name__ == "__main__":
    main()
