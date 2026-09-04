"""Stealth browser setup: Playwright with anti-detection hardening.

Launches a headed Chromium with automation flags stripped and
playwright-stealth applied when available. Headed mode is deliberate —
it is both lower-detection and lets the human see exactly what Hermes
filled before they click submit themselves.
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger("hermes.browser")

_STEALTH_LAUNCH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--no-sandbox",
    "--disable-dev-shm-usage",
]

_REALISTIC_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


def _apply_stealth(page) -> bool:
    """Try playwright-stealth; return True if active."""
    try:
        from playwright_stealth import Stealth

        Stealth().apply_stealth(page)
        return True
    except ImportError:
        try:
            from playwright_stealth import stealth_sync  # older API

            stealth_sync(page)
            return True
        except ImportError:
            logger.debug("playwright-stealth not installed — basic mode")
            return False


class StealthBrowser:
    """Context manager wrapping a hardened Playwright chromium session."""

    def __init__(self, headless: bool = False) -> None:
        self.headless = headless
        self._pw = None
        self._browser = None
        self._context = None
        self.page = None

    def __enter__(self) -> "StealthBrowser":
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(
            headless=self.headless,
            args=_STEALTH_LAUNCH_ARGS,
        )
        self._context = self._browser.new_context(
            viewport={"width": 1440, "height": 900},
            user_agent=_REALISTIC_UA,
            locale="en-US",
        )
        self.page = self._context.new_page()
        self.stealth_active = _apply_stealth(self.page)
        return self

    def __exit__(self, *exc) -> None:
        if self._context:
            self._context.close()
        if self._browser:
            self._browser.close()
        if self._pw:
            self._pw.stop()
