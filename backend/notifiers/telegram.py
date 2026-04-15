import logging
from typing import Optional

import httpx

from backend.scrapers.base import Apartment

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"

# Application Security Requirement: Telegram MarkdownV2 escaping prevents injection via user-controlled listing data
_MD_SPECIAL = r"_*[]()~`>#+-=|{}.!"


def _escape_md(text: str) -> str:
    for ch in _MD_SPECIAL:
        text = text.replace(ch, f"\\{ch}")
    return text


def _build_message(apt: Apartment) -> str:
    lines = ["🏠 *דירה חדשה נמצאה\\!*\n"]

    if apt.title:
        lines.append(f"*{_escape_md(apt.title)}*")
    if apt.address:
        lines.append(f"📍 {_escape_md(apt.address)}")
    if apt.neighborhood:
        lines.append(f"🏘 {_escape_md(apt.neighborhood)}")
    if apt.price:
        lines.append(f"💰 {_escape_md(f'{apt.price:,}')} ₪/חודש")

    details = []
    if apt.rooms:
        details.append(f"{_escape_md(str(apt.rooms))} חד׳")
    if apt.size_sqm:
        details.append(f"{_escape_md(f'{apt.size_sqm:.0f}')} מ״ר")
    if details:
        lines.append("📐 " + " \\| ".join(details))

    def feat(label: str, val: Optional[bool]) -> str:
        if val is True:
            return f"✅ {_escape_md(label)}"
        if val is False:
            return f"❌ {_escape_md(label)}"
        return ""

    features = [f for f in [
        feat("מרפסת", apt.balcony),
        feat("חניה", apt.parking),
        feat("מרוהט", apt.furnished),
        feat("ממ״ד", apt.mamad),
    ] if f]
    if features:
        lines.append("  ".join(features))

    if apt.agent is False:
        lines.append("🙅 ללא תיווך")
    elif apt.agent is True:
        lines.append("🤝 עם תיווך")

    # MarkdownV2 links: text inside [] is escaped, URL inside () uses only ) and \ escaping
    safe_url = apt.listing_url.replace("\\", "\\\\").replace(")", "\\)")
    lines.append(f"\n[לצפייה במודעה]({safe_url})")

    return "\n".join(lines)


async def send_notification(apt: Apartment, token: str, chat_id: str) -> bool:
    message = _build_message(apt)
    url = TELEGRAM_API.format(token=token)

    async with httpx.AsyncClient(timeout=15) as client:
        try:
            resp = await client.post(url, json={
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "MarkdownV2",
                "disable_web_page_preview": False,
            })
            if resp.status_code == 400:
                logger.warning("MarkdownV2 failed, retrying as plain text: %s", resp.text[:200])
                plain = message.replace("\\", "")
                for ch in "*[]()":
                    plain = plain.replace(ch, "")
                resp = await client.post(url, json={
                    "chat_id": chat_id,
                    "text": plain,
                })
            resp.raise_for_status()
            logger.info("Telegram notification sent for apartment %s", apt.id)
            return True
        except httpx.HTTPStatusError as e:
            logger.error("Telegram API error %s: %s", e.response.status_code, e.response.text)
        except Exception as e:
            logger.error("Failed to send Telegram notification: %s", e)
    return False


async def send_summary(count: int, token: str, chat_id: str) -> None:
    if count <= 1:
        return
    url = TELEGRAM_API.format(token=token)
    message = f"📊 סיכום: נמצאו *{count}* דירות חדשות\\!"
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            resp = await client.post(url, json={
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "MarkdownV2",
            })
            resp.raise_for_status()
        except Exception as e:
            logger.error("Failed to send summary: %s", e)
