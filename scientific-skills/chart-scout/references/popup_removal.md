# Popup & Modal Removal Strategies

## Popup Taxonomy

| Type | Examples | Detection | Removal |
|------|----------|-----------|---------|
| Cookie consent | GDPR banners, "Accept cookies" | `[class*="cookie"]`, `[class*="consent"]` | Remove element |
| Login prompts | "Sign in to continue" | `[class*="signin"]`, `[class*="modal"]` | Remove element |
| Subscription nags | "Subscribe for premium" | `[class*="subscribe"]`, `[class*="paywall"]` | Remove element |
| Scroll blockers | `overflow: hidden` on body | Check `body.style.overflow` | Reset to `auto` |
| Overlay masks | Dark transparent backgrounds | `position: fixed` + high z-index | Remove element |
| Notification bars | Top/bottom sticky bars | `position: sticky/fixed` | Remove element |

## Generic Strategy (works on most sites)

1. Remove elements matching common popup selectors (`cookie`, `consent`, `modal`, `popup`, `overlay`)
2. Only remove if `position: fixed/sticky` or `z-index > 999` (avoids removing nav/header)
3. Reset `overflow: auto` on body and html
4. Final pass: remove any remaining high-z-index fixed elements

## Site-Specific Strategies

### Google Finance
- Google shows a consent page ("Before you continue") in EU regions
- Click "Reject all" or "Accept all" button to dismiss
- Fallback: remove consent overlay elements

### TradingView
- Shows login dialog after a few page loads
- Has bottom ad bars and feature announcement popups
- Remove `dialog`, `popup`, `modal`, `signin` class elements
- Remove bottom widget bar

## Best Practices

- Always run generic cleanup first, then site-specific
- Run cleanup again after any user interaction (clicking timeframe buttons can trigger new popups)
- Add a 1-second delay after cleanup to let DOM settle before screenshotting
- Test with `headless=False` during development to visually verify cleanup works
