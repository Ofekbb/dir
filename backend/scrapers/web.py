"""
Generic SPA apartment scraper.

Strategies (tried in order):
  1. __NEXT_DATA__ — extract SSR hydration JSON from the page (fast, no extra requests)
  2. API interception — listen to all JSON XHR responses during navigation
  3. DOM extraction — parse the rendered apartment cards from the page HTML
"""

import asyncio
import hashlib
import json
import logging
from typing import Any, Optional
from urllib.parse import urljoin, urlparse

from playwright.async_api import Page, Response, async_playwright

from backend.scrapers.base import Apartment, BaseScraper

logger = logging.getLogger(__name__)

_APARTMENT_HINT_KEYS = {
    "price", "rooms", "address", "neighborhood", "rent",
    "מחיר", "חדרים", "כתובת", "שכונה",
    "rentprice", "numprice", "squaremeters",
}


# ── Helpers ──────────────────────────────────────────────────────────────────

def _base_url(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def _looks_like_apartments(data: Any, min_items: int = 2) -> bool:
    items = _extract_apartment_list(data)
    if items and len(items) >= min_items:
        first = items[0]
        if isinstance(first, dict):
            keys = {k.lower() for k in first.keys()}
            return bool(keys & _APARTMENT_HINT_KEYS)
    return False


def _extract_apartment_list(data: Any, depth: int = 0) -> list[dict]:
    if depth > 5:
        return []
    if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
        return data
    if isinstance(data, dict):
        for v in data.values():
            result = _extract_apartment_list(v, depth + 1)
            if result:
                return result
    return []


def _parse_bool_feature(value: Any) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        low = value.strip().lower()
        if low in ("yes", "true", "1", "כן"):
            return True
        if low in ("no", "false", "0", "לא"):
            return False
        if low in ("not mentioned", "לא צויין", ""):
            return None
    return None


def _safe_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    try:
        cleaned = str(value).replace(",", "").replace("₪", "").replace("ILS", "").strip()
        cleaned = "".join(c for c in cleaned if c.isdigit() or c == "-")
        return int(cleaned) if cleaned else None
    except (TypeError, ValueError):
        return None


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        cleaned = str(value).replace(",", "").replace("מ״ר", "").replace("sqm", "").strip()
        cleaned = "".join(c for c in cleaned if c.isdigit() or c in ".-")
        return float(cleaned) if cleaned else None
    except (TypeError, ValueError):
        return None


def _make_id(raw: dict, source: str) -> str:
    for key in ("id", "_id", "listingId", "listing_id", "Id", "postId", "post_id"):
        val = raw.get(key)
        if val:
            return f"{source}_{val}"
    stable = json.dumps(
        {k: raw.get(k) for k in sorted(("address", "price", "rooms", "size", "neighborhood"))},
        sort_keys=True, ensure_ascii=False,
    )
    h = hashlib.sha256(stable.encode()).hexdigest()[:12]
    return f"{source}_{h}"


def _get(raw: dict, *keys: str) -> Any:
    for k in keys:
        if k in raw and raw[k] is not None:
            return raw[k]
    for k in keys:
        for rk, rv in raw.items():
            if rk.lower() == k.lower() and rv is not None:
                return rv
    return None


def _build_apartment(raw: dict, source: str, base: str) -> Apartment:
    apt_id = _make_id(raw, source)

    listing_url = _get(raw, "url", "link", "listingUrl", "listing_url", "postUrl") or ""
    if listing_url and not listing_url.startswith("http"):
        listing_url = urljoin(base, listing_url)
    if not listing_url:
        native_id = _get(raw, "id", "_id", "listingId", "postId")
        if native_id:
            listing_url = f"{base}/listing/{native_id}"

    return Apartment(
        id=apt_id,
        source=source,
        listing_url=listing_url or base,
        title=_get(raw, "title", "שם", "headline"),
        address=_get(raw, "address", "כתובת", "street", "fullAddress"),
        price=_safe_int(_get(raw, "price", "מחיר", "rent", "rentPrice", "numPrice")),
        rooms=_safe_float(_get(raw, "rooms", "חדרים", "roomsCount", "numRooms")),
        size_sqm=_safe_float(_get(raw, "size", "גודל", "squareMeters", "sqm", "area")),
        neighborhood=_get(raw, "neighborhood", "שכונה", "location", "area"),
        balcony=_parse_bool_feature(_get(raw, "balcony", "מרפסת", "hasBalcony")),
        parking=_parse_bool_feature(_get(raw, "parking", "חניה", "hasParking")),
        furnished=_parse_bool_feature(_get(raw, "furnished", "מרוהט", "isFurnished")),
        mamad=_parse_bool_feature(_get(raw, "mamad", "ממד", "safeRoom", "hasMamad")),
        agent=_parse_bool_feature(_get(raw, "agent", "תיווך", "broker", "isAgent")),
        image_url=_get(raw, "image", "imageUrl", "photo", "thumbnail", "mainImage"),
    )


def _dedup(apartments: list[Apartment]) -> list[Apartment]:
    seen: set[str] = set()
    result: list[Apartment] = []
    for apt in apartments:
        if apt.id not in seen:
            seen.add(apt.id)
            result.append(apt)
    return result


# ── Strategy 1: __NEXT_DATA__ ────────────────────────────────────────────────

async def _scrape_via_next_data(page: Page, source: str, base: str) -> Optional[list[Apartment]]:
    try:
        next_data_raw = await page.evaluate("""
        () => {
            const el = document.getElementById('__NEXT_DATA__');
            if (!el) return null;
            try { return JSON.parse(el.textContent); }
            catch { return null; }
        }
        """)
    except Exception:
        return None

    if not next_data_raw:
        logger.info("No __NEXT_DATA__ found on page")
        return None

    logger.info("Found __NEXT_DATA__, searching for apartment listings...")

    raw_list = _extract_apartment_list(next_data_raw)
    if not raw_list:
        logger.info("__NEXT_DATA__ found but no apartment list detected. Keys at top: %s",
                     list(next_data_raw.get("props", {}).get("pageProps", {}).keys())[:10])
        page_props = next_data_raw.get("props", {}).get("pageProps", {})
        for key, val in page_props.items():
            if isinstance(val, list) and len(val) > 0:
                logger.info("  pageProps['%s'] is a list with %d items. First item keys: %s",
                            key, len(val),
                            list(val[0].keys())[:15] if isinstance(val[0], dict) else type(val[0]))
        return None

    apartments = [_build_apartment(r, source, base) for r in raw_list]
    logger.info("__NEXT_DATA__ strategy: found %d apartments", len(apartments))
    return _dedup(apartments)


# ── Strategy 2: API interception ─────────────────────────────────────────────

async def _scrape_via_api(page: Page, url: str, source: str, base: str) -> Optional[list[Apartment]]:
    captured: list[dict] = []

    async def on_response(response: Response) -> None:
        try:
            ct = response.headers.get("content-type", "")
            if "json" not in ct and "javascript" not in ct:
                return
            body = await response.json()
            if _looks_like_apartments(body, min_items=1):
                items = _extract_apartment_list(body)
                logger.info("API: captured %d items from %s", len(items), response.url[:120])
                captured.extend(items)
        except Exception:
            pass

    page.on("response", on_response)
    await page.goto(url, wait_until="networkidle", timeout=60_000)
    await asyncio.sleep(4)

    next_result = await _scrape_via_next_data(page, source, base)
    if next_result:
        return next_result

    if not captured:
        return None

    apartments = [_build_apartment(r, source, base) for r in captured]
    logger.info("API interception strategy: found %d apartments", len(apartments))
    return _dedup(apartments)


# ── Strategy 3: DOM extraction ───────────────────────────────────────────────

async def _scrape_via_dom(page: Page, source: str, base: str) -> list[Apartment]:
    await asyncio.sleep(3)

    for _ in range(5):
        await page.evaluate("window.scrollBy(0, window.innerHeight)")
        await asyncio.sleep(0.8)

    raw_cards: list[dict] = await page.evaluate("""
    () => {
        function findCardContainers() {
            const candidates = document.querySelectorAll('a[href*="/listing/"]');
            if (candidates.length > 0) return Array.from(candidates);

            const keywords = ['card', 'listing', 'apartment', 'item', 'result', 'property'];
            for (const kw of keywords) {
                const els = document.querySelectorAll(`[class*="${kw}" i]`);
                const filtered = Array.from(els).filter(el => {
                    const text = el.textContent || '';
                    return (text.includes('₪') || /\\d{4,}/.test(text)) && text.length < 2000;
                });
                if (filtered.length >= 2) return filtered;
            }
            return [];
        }

        const cards = findCardContainers();
        return cards.map(card => {
            const text = card.textContent || '';
            const href = card.tagName === 'A' ? card.href : (card.querySelector('a')?.href || null);
            const img = card.querySelector('img')?.src || null;

            const priceMatch = text.match(/₪\\s?([\\d,]+)/) || text.match(/([\\d,]+)\\s?₪/);
            const price = priceMatch ? priceMatch[1].replace(/,/g, '') : null;

            const roomsMatch = text.match(/(\\d+\\.?\\d*)\\s*חד/) || text.match(/(\\d+\\.?\\d*)\\s*rooms/i);
            const rooms = roomsMatch ? roomsMatch[1] : null;

            const sizeMatch = text.match(/(\\d+\\.?\\d*)\\s*מ[״"]ר/) || text.match(/(\\d+\\.?\\d*)\\s*sqm/i);
            const size = sizeMatch ? sizeMatch[1] : null;

            const idMatch = href ? href.match(/\\/listing\\/([^/?]+)/) : null;
            const id = idMatch ? idMatch[1] : null;

            const parts = text.split('•').map(p => p.trim()).filter(Boolean);
            const neighborhood = parts.length > 0 ? parts[0].substring(0, 50) : null;

            const hasBalcony = /מרפסת/.test(text) ? (/(?:יש|כן).*מרפסת|מרפסת.*(?:יש|כן)|✓.*מרפסת|מרפסת.*✓/.test(text) || null) : null;
            const hasParking = /חניה/.test(text) ? (/(?:יש|כן).*חניה|חניה.*(?:יש|כן)|✓.*חניה|חניה.*✓/.test(text) || null) : null;

            return {
                id: id,
                url: href,
                image: img,
                price: price,
                rooms: rooms,
                size: size,
                neighborhood: neighborhood,
                title: text.substring(0, 100).trim(),
                balcony: hasBalcony,
                parking: hasParking,
                raw_text: text.substring(0, 300),
            };
        }).filter(c => c.price || c.url);
    }
    """)

    if not raw_cards:
        logger.warning("DOM fallback: no apartment cards extracted")
        return []

    apartments = [_build_apartment(r, source, base) for r in raw_cards]
    logger.info("DOM strategy: found %d apartments", len(apartments))
    return _dedup(apartments)


# ── Main scraper class ───────────────────────────────────────────────────────

class WebScraper(BaseScraper):
    async def scrape(self, url: str) -> list[Apartment]:
        base = _base_url(url)
        source = urlparse(url).netloc.split(".")[0]

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                locale="he-IL",
                viewport={"width": 1280, "height": 800},
            )
            page = await context.new_page()

            try:
                logger.info("Trying API interception + __NEXT_DATA__...")
                result = await _scrape_via_api(page, url, source, base)
                if result and len(result) > 0:
                    return result

                logger.info("API/NEXT_DATA yielded nothing, trying DOM extraction...")
                result = await _scrape_via_dom(page, source, base)
                if result and len(result) > 0:
                    return result

                logger.info("DOM yielded nothing on first page, retrying with fresh navigation...")
                page2 = await context.new_page()
                await page2.goto(url, wait_until="networkidle", timeout=60_000)
                return await _scrape_via_dom(page2, source, base)

            finally:
                await browser.close()
