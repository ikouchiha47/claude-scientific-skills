"""
Popup/modal/cookie-banner removal for financial chart sites.

Injects JS to remove common overlays before taking screenshots.
"""

from __future__ import annotations
from playwright.async_api import Page


# Generic removal: hides fixed/sticky overlays, cookie banners, modals
GENERIC_POPUP_JS = """
() => {
    // Remove elements by common popup/modal selectors
    const selectors = [
        '[class*="cookie"]', '[id*="cookie"]',
        '[class*="consent"]', '[id*="consent"]',
        '[class*="modal"]', '[id*="modal"]',
        '[class*="popup"]', '[id*="popup"]',
        '[class*="overlay"]', '[id*="overlay"]',
        '[class*="banner"]', '[id*="banner"]',
        '[class*="subscribe"]', '[id*="subscribe"]',
        '[class*="notification"]', '[id*="notification"]',
        '[class*="gdpr"]', '[id*="gdpr"]',
        '.intercom-lightweight-app',
        '#onetrust-consent-sdk',
        '.fc-consent-root',
    ];
    for (const sel of selectors) {
        document.querySelectorAll(sel).forEach(el => {
            const style = window.getComputedStyle(el);
            if (style.position === 'fixed' || style.position === 'sticky' || style.zIndex > 999) {
                el.remove();
            }
        });
    }

    // Restore scrolling on body/html
    document.body.style.overflow = 'auto';
    document.documentElement.style.overflow = 'auto';
    document.body.style.position = '';

    // Remove any remaining fixed-position overlays with high z-index
    document.querySelectorAll('*').forEach(el => {
        const style = window.getComputedStyle(el);
        if ((style.position === 'fixed' || style.position === 'sticky') &&
            parseInt(style.zIndex) > 999 &&
            el.tagName !== 'NAV' && el.tagName !== 'HEADER') {
            el.remove();
        }
    });
}
"""

# Google consent page ("Before you continue") bypass
GOOGLE_CONSENT_JS = """
() => {
    // Click "Reject all" or "Accept all" if consent form present
    const buttons = document.querySelectorAll('button');
    for (const btn of buttons) {
        const text = btn.textContent.toLowerCase();
        if (text.includes('reject all') || text.includes('accept all')) {
            btn.click();
            return;
        }
    }
    // Fallback: remove consent overlay
    document.querySelectorAll('[class*="consent"], [id*="consent"]').forEach(el => el.remove());
    document.body.style.overflow = 'auto';
}
"""

# TradingView: dismiss login prompts and feature popups
TRADINGVIEW_JS = """
() => {
    // Close popup dialogs
    document.querySelectorAll('[class*="dialog"], [class*="popup"], [class*="modal"]').forEach(el => el.remove());

    // Remove sign-in overlay
    document.querySelectorAll('[class*="signin"], [class*="sign-in"]').forEach(el => el.remove());

    // Remove bottom bar ads
    document.querySelectorAll('[class*="bottom-widgetbar"], [class*="ad-"]').forEach(el => el.remove());

    document.body.style.overflow = 'auto';
}
"""

STRATEGIES = {
    "generic": GENERIC_POPUP_JS,
    "google_consent": GOOGLE_CONSENT_JS,
    "tradingview": TRADINGVIEW_JS,
}


async def clean_popups(page: Page, strategy: str = "generic") -> None:
    """Remove popups/modals from the page using the specified strategy.

    Always runs the generic cleaner first, then the site-specific one.
    """
    await page.evaluate(GENERIC_POPUP_JS)
    if strategy != "generic" and strategy in STRATEGIES:
        await page.evaluate(STRATEGIES[strategy])
