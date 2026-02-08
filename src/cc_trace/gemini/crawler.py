"""Browser automation for Gemini conversation crawling.

Uses Playwright to:
1. Login to Gemini (visible browser for manual login)
2. Crawl conversation structure (headless)

Requires optional dependency: pip install cc-trace[gemini]
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cc_trace.config import Config

logger = logging.getLogger(__name__)

GEMINI_URL = "https://gemini.google.com"
GEMINI_APP_URL = "https://gemini.google.com/app"


def _check_playwright() -> None:
    """Check if Playwright is installed."""
    try:
        import playwright  # noqa: F401
    except ImportError:
        raise ImportError(
            "Playwright is required for Gemini crawling. "
            "Install with: pip install cc-trace[gemini]"
        )


def login(config: Config, timeout: int = 120) -> bool:
    """Open visible browser for manual Gemini login.

    Args:
        config: Application configuration.
        timeout: Max seconds to wait for login.

    Returns:
        True if login successful and state saved.
    """
    _check_playwright()

    from playwright.sync_api import sync_playwright

    state_file = config.gemini.browser_state

    logger.info("Opening browser for Gemini login...")
    logger.info("Please log in to your Google account.")
    logger.info("The browser will close automatically after login.")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        # Navigate to Gemini
        page.goto(GEMINI_URL)

        # Wait for user to complete login and reach the app
        try:
            page.wait_for_url(f"{GEMINI_APP_URL}**", timeout=timeout * 1000)
            logger.info("Login detected, saving browser state...")
        except Exception:
            logger.warning("Login timeout or navigation failed")
            browser.close()
            return False

        # Save browser state
        state_file.parent.mkdir(parents=True, exist_ok=True)
        context.storage_state(path=str(state_file))

        browser.close()

    logger.info("Browser state saved to %s", state_file)
    return True


def crawl(
    config: Config,
    timeout: int = 30,
    limit: int = 0,
) -> int:
    """Crawl Gemini conversations in headless mode.

    Args:
        config: Application configuration.
        timeout: Page load timeout in seconds.
        limit: Max conversations to crawl (0 = all).

    Returns:
        Number of conversations crawled.
    """
    _check_playwright()

    from playwright.sync_api import sync_playwright

    from cc_trace.gemini.matcher import CrawlCache, CrawledPrompt
    from cc_trace.gemini.sync import save_crawl_cache

    state_file = config.gemini.browser_state
    cache_file = config.gemini.crawl_cache

    if not state_file.exists():
        logger.error("No browser state found. Run 'gemini login' first.")
        return 0

    logger.info("Loading browser state from %s", state_file)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(storage_state=str(state_file))
        page = context.new_page()
        page.set_default_timeout(timeout * 1000)

        # Navigate to Gemini app
        logger.info("Navigating to Gemini...")
        try:
            page.goto(GEMINI_APP_URL, wait_until="networkidle")
        except Exception as e:
            logger.error("Failed to load Gemini: %s", e)
            browser.close()
            return 0

        # Check if still logged in
        if GEMINI_APP_URL not in page.url:
            logger.error("Session expired. Run 'gemini login' again.")
            browser.close()
            return 0

        # Find conversations in sidebar
        cache = CrawlCache()

        try:
            conversations = _extract_conversations(page, limit)
        except Exception as e:
            logger.error("Failed to extract conversations: %s", e)
            browser.close()
            return 0

        logger.info("Found %d conversations", len(conversations))

        # Crawl each conversation
        for conv_id, conv_title in conversations:
            cache.conversations[conv_id] = conv_title

            prompts = _extract_prompts(page, conv_id, timeout)
            for i, text_preview in enumerate(prompts):
                cache.prompts.append(
                    CrawledPrompt(
                        conversation_id=conv_id,
                        conversation_title=conv_title,
                        text_preview=text_preview,
                        order_in_conversation=i,
                    )
                )

            logger.info(
                "Crawled conversation %s: %d prompts", conv_id[:8], len(prompts)
            )

        browser.close()

    # Save crawl cache
    save_crawl_cache(cache_file, cache)
    logger.info("Crawl cache saved to %s", cache_file)

    return len(cache.conversations)


def _extract_conversations(
    page,
    limit: int = 0,
) -> list[tuple[str, str]]:
    """Extract conversation list from sidebar.

    Returns:
        List of (conversation_id, title) tuples.
    """
    conversations: list[tuple[str, str]] = []

    # Wait for sidebar to load
    # The sidebar contains conversation items with data attributes or links
    page.wait_for_selector('[role="navigation"]', timeout=10000)

    # Look for conversation links in the sidebar
    # Gemini uses various selectors; try common patterns
    selectors = [
        'a[href*="/app/"]',  # Direct links to conversations
        '[data-conversation-id]',  # Data attribute based
        '.conversation-item',  # Class based
    ]

    for selector in selectors:
        try:
            items = page.query_selector_all(selector)
            if items:
                for item in items:
                    conv_id, title = _parse_conversation_item(item)
                    if conv_id:
                        conversations.append((conv_id, title))

                        if limit > 0 and len(conversations) >= limit:
                            return conversations
                break
        except Exception:
            continue

    return conversations


def _parse_conversation_item(item) -> tuple[str, str]:
    """Parse a conversation item from the sidebar.

    Returns:
        (conversation_id, title) or ("", "") if not parseable.
    """
    # Try to get href
    href = item.get_attribute("href") or ""

    # Extract conversation ID from URL
    # Format: /app/{conversation_id}
    conv_id = ""
    if "/app/" in href:
        parts = href.split("/app/")
        if len(parts) > 1:
            conv_id = parts[1].split("?")[0].split("/")[0]

    # Try data attribute
    if not conv_id:
        conv_id = item.get_attribute("data-conversation-id") or ""

    # Get title
    title = item.inner_text().strip()[:100] or "Untitled"

    return conv_id, title


def _extract_prompts(
    page,
    conversation_id: str,
    timeout: int,
) -> list[str]:
    """Extract prompts from a conversation page.

    Returns:
        List of prompt text previews (first ~100 chars each).
    """
    prompts: list[str] = []

    # Navigate to conversation
    conv_url = f"{GEMINI_APP_URL}/{conversation_id}"
    try:
        page.goto(conv_url, wait_until="networkidle", timeout=timeout * 1000)
    except Exception as e:
        logger.warning("Failed to load conversation %s: %s", conversation_id[:8], e)
        return prompts

    # Wait for content to load
    try:
        page.wait_for_selector('[data-message-id]', timeout=5000)
    except Exception:
        # Conversation might be empty or use different structure
        pass

    # Find user messages
    # Gemini marks user messages differently than assistant messages
    selectors = [
        '[data-message-author-role="user"]',
        '.user-message',
        '[class*="user"]',
    ]

    for selector in selectors:
        try:
            messages = page.query_selector_all(selector)
            if messages:
                for msg in messages:
                    text = msg.inner_text().strip()
                    # Take first ~100 characters as preview
                    preview = text[:100]
                    if preview:
                        prompts.append(preview)
                break
        except Exception:
            continue

    return prompts
