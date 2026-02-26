#!/usr/bin/env python3
"""
chart_scout.py — Capture stock chart screenshots using Playwright.

Usage:
    python chart_scout.py --symbol RELIANCE --exchange NSE
    python chart_scout.py --symbol AAPL --exchange NASDAQ --site google_finance
    python chart_scout.py --symbol TCS --exchange NSE --timeframe 5Y --output ./charts/
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import yaml
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
from popup_cleaner import clean_popups


def load_registry() -> dict:
    registry_path = Path(__file__).parent.parent / "assets" / "site_registry.yaml"
    with open(registry_path) as f:
        return yaml.safe_load(f)


def select_site(registry: dict, exchange: str, site: str | None) -> str:
    """Pick the best site for the given exchange, or use explicit choice."""
    if site:
        if site not in registry["sites"]:
            print(f"Error: Unknown site '{site}'. Available: {list(registry['sites'].keys())}")
            sys.exit(1)
        return site

    region = registry.get("exchange_region", {}).get(exchange, "global")
    chain = registry.get("fallback_chains", {}).get(region, ["google_finance"])
    return chain[0]


def build_url(site_config: dict, symbol: str, exchange: str) -> str:
    """Build the URL for the given site, symbol, and exchange."""
    url = site_config["base_url"]
    url = url.replace("{symbol}", symbol)
    url = url.replace("{exchange}", exchange)
    return url


async def capture_chart(
    symbol: str,
    exchange: str,
    site_key: str,
    site_config: dict,
    timeframe: str | None = None,
    output_dir: Path = Path("."),
) -> Path | None:
    """Launch browser, navigate to chart, remove popups, take viewport screenshot."""

    url = build_url(site_config, symbol, exchange)
    viewport = site_config.get("viewport", {"width": 1280, "height": 900})
    wait_for = site_config.get("wait_for", "canvas")
    wait_timeout = site_config.get("wait_timeout_ms", 15000)
    popup_strategy = site_config.get("popup_strategy", "generic")
    settle_ms = site_config.get("settle_ms", 3000)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport=viewport,
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        page = await context.new_page()

        try:
            print(f"Navigating to {url} ...")
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)

            # Wait for chart to render (canvas or svg)
            try:
                await page.wait_for_selector(wait_for, timeout=wait_timeout)
            except PlaywrightTimeout:
                print(f"Warning: Timed out waiting for '{wait_for}', proceeding anyway.")

            # Remove popups
            await clean_popups(page, popup_strategy)

            # Click timeframe button if requested
            if timeframe:
                tf_selectors = site_config.get("timeframe_buttons", {})
                if timeframe in tf_selectors:
                    selector = tf_selectors[timeframe]
                    for sel in selector.split(","):
                        sel = sel.strip()
                        try:
                            await page.click(sel, timeout=3000)
                            print(f"Switched to {timeframe} timeframe.")
                            await page.wait_for_timeout(2000)
                            break
                        except (PlaywrightTimeout, Exception):
                            continue

            # Clean popups again after interaction, then let page settle
            await clean_popups(page, popup_strategy)
            await page.wait_for_timeout(settle_ms)

            # Viewport screenshot — simple and robust
            output_dir.mkdir(parents=True, exist_ok=True)
            filename = f"{symbol}_{exchange}_{site_key}"
            if timeframe:
                filename += f"_{timeframe}"
            filename += ".png"
            output_path = output_dir / filename

            await page.screenshot(path=str(output_path), full_page=False)
            print(f"Screenshot saved: {output_path}")
            return output_path

        except Exception as e:
            print(f"Error capturing chart from {site_key}: {e}")
            return None
        finally:
            await browser.close()


async def capture_with_fallback(
    symbol: str,
    exchange: str,
    registry: dict,
    site: str | None = None,
    timeframe: str | None = None,
    output_dir: Path = Path("."),
) -> Path | None:
    """Try capturing from the selected site, falling back through the chain."""
    if site:
        sites_to_try = [site]
    else:
        region = registry.get("exchange_region", {}).get(exchange, "global")
        sites_to_try = registry.get("fallback_chains", {}).get(region, ["google_finance"])

    for site_key in sites_to_try:
        site_config = registry["sites"].get(site_key)
        if not site_config:
            continue
        result = await capture_chart(
            symbol, exchange, site_key, site_config, timeframe, output_dir
        )
        if result:
            return result
        print(f"Failed on {site_key}, trying next...")

    print("All sites failed.")
    return None


def main():
    parser = argparse.ArgumentParser(description="Capture stock chart screenshots")
    parser.add_argument("--symbol", required=True, help="Stock symbol (e.g., RELIANCE, AAPL)")
    parser.add_argument("--exchange", required=True, help="Exchange (e.g., NSE, NASDAQ)")
    parser.add_argument("--site", default=None, help="Force a specific site (e.g., google_finance)")
    parser.add_argument("--timeframe", default=None, help="Chart timeframe (e.g., 1Y, 5Y, Max)")
    parser.add_argument("--output", default="./charts", help="Output directory for screenshots")
    args = parser.parse_args()

    registry = load_registry()
    output_dir = Path(args.output)

    result = asyncio.run(
        capture_with_fallback(
            symbol=args.symbol,
            exchange=args.exchange,
            registry=registry,
            site=args.site,
            timeframe=args.timeframe,
            output_dir=output_dir,
        )
    )

    if result:
        print(f"\nSuccess: {result}")
    else:
        print("\nFailed to capture chart.")
        sys.exit(1)


if __name__ == "__main__":
    main()
