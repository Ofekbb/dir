"""
Main orchestrator.
Run: python -m backend.main
"""

import asyncio
import logging
import sys

from backend.config import load_config
from backend.db import cleanup_old, close, export_json, init_db, upsert
from backend.notifiers.telegram import send_notification, send_summary
from backend.scrapers.base import Apartment, BaseScraper
from backend.scrapers.web import WebScraper

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

SCRAPER_REGISTRY: dict[str, type] = {
    "web": WebScraper,
}

MAX_RETRIES = 2
TELEGRAM_DELAY = 0.5


async def scrape_with_retry(scraper: BaseScraper, url: str, retries: int = MAX_RETRIES) -> list[Apartment]:
    for attempt in range(retries + 1):
        try:
            return await scraper.scrape(url)
        except Exception as e:
            if attempt < retries:
                wait = 5 * (attempt + 1)
                logger.warning("Scrape attempt %d failed: %s — retrying in %ds", attempt + 1, e, wait)
                await asyncio.sleep(wait)
            else:
                raise


async def run() -> None:
    config = load_config()
    init_db()

    tg_ok = (
        config.telegram.enabled
        and config.telegram.bot_token
        and config.telegram.chat_id
    )
    if config.telegram.enabled and not tg_ok:
        logger.warning("Telegram enabled but TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set. Skipping notifications.")

    total_new = 0

    try:
        for source in config.sources:
            if not source.enabled:
                logger.info("Source '%s' disabled, skipping", source.name)
                continue

            scraper_class = SCRAPER_REGISTRY.get(source.scraper)
            if scraper_class is None:
                logger.error("No scraper registered for type '%s'", source.scraper)
                continue

            logger.info("Scraping source: %s", source.name)
            scraper = scraper_class()

            try:
                apartments = await scrape_with_retry(scraper, source.url)
            except Exception as e:
                logger.error("All scrape attempts failed for '%s': %s", source.name, e, exc_info=True)
                continue

            logger.info("Found %d listings from '%s'", len(apartments), source.name)
            new_count = 0

            for apt in apartments:
                is_new = upsert(apt)
                if is_new:
                    new_count += 1
                    total_new += 1
                    logger.info("NEW: %s | %s | %s ILS | %s",
                                apt.id, apt.address or apt.title or "?", apt.price, apt.listing_url[:80])

                    if tg_ok:
                        await send_notification(apt, config.telegram.bot_token, config.telegram.chat_id)
                        await asyncio.sleep(TELEGRAM_DELAY)

            logger.info("Source '%s': %d new / %d total", source.name, new_count, len(apartments))

        if total_new > 1 and tg_ok:
            await send_summary(total_new, config.telegram.bot_token, config.telegram.chat_id)

        removed = cleanup_old(config.settings.max_apartment_age_days)
        if removed:
            logger.info("Cleaned up %d stale listings", removed)

        export_json()
        logger.info("Done — %d new apartments found.", total_new)

    finally:
        close()


if __name__ == "__main__":
    asyncio.run(run())
