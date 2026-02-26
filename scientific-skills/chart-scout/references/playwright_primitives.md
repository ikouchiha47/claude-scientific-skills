# Playwright Primitives for Chart Screenshots

Quick reference for common Playwright patterns used in chart-scout.

## Installation

```bash
uv pip install playwright
uv run python -m playwright install chromium
```

## Browser Launch

```python
from playwright.async_api import async_playwright

async with async_playwright() as p:
    browser = await p.chromium.launch(headless=True)
    context = await browser.new_context(
        viewport={"width": 1280, "height": 900},
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    )
    page = await context.new_page()
```

## Navigation & Waiting

```python
# Navigate and wait for DOM
await page.goto(url, wait_until="domcontentloaded", timeout=30000)

# Wait for specific element
await page.wait_for_selector("canvas", timeout=15000)

# Wait for network idle (slower but more reliable)
await page.goto(url, wait_until="networkidle", timeout=30000)

# Arbitrary pause for JS rendering
await page.wait_for_timeout(2000)
```

## Screenshots

```python
# Full page screenshot
await page.screenshot(path="full.png", full_page=True)

# Viewport-only screenshot
await page.screenshot(path="viewport.png", full_page=False)

# Element-level screenshot (preferred for charts)
element = page.locator("#chart-container").first
await element.screenshot(path="chart.png")
```

## Clicking & Interaction

```python
# Click by selector
await page.click("button:has-text('1Y')", timeout=3000)

# Click by text content
await page.get_by_text("5 Years").click()

# Handle multiple possible selectors
for sel in ["button.timeframe-1y", "a:has-text('1Y')"]:
    try:
        await page.click(sel, timeout=2000)
        break
    except:
        continue
```

## JS Injection

```python
# Execute JavaScript on the page
await page.evaluate("""
    () => {
        document.querySelectorAll('.popup').forEach(el => el.remove());
        document.body.style.overflow = 'auto';
    }
""")
```

## Error Handling

```python
from playwright.async_api import TimeoutError as PlaywrightTimeout

try:
    await page.wait_for_selector("canvas", timeout=10000)
except PlaywrightTimeout:
    print("Chart didn't load, trying fallback...")
```
