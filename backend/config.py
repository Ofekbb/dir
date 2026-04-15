import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"


@dataclass
class SourceConfig:
    name: str
    scraper: str
    url: str
    enabled: bool = True


@dataclass
class TelegramConfig:
    enabled: bool = True
    bot_token: Optional[str] = None
    chat_id: Optional[str] = None


@dataclass
class AppSettings:
    max_apartment_age_days: int = 30


@dataclass
class Config:
    sources: list[SourceConfig] = field(default_factory=list)
    telegram: TelegramConfig = field(default_factory=TelegramConfig)
    settings: AppSettings = field(default_factory=AppSettings)


def load_config() -> Config:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    # Application Security Requirement: scrape URLs loaded from env vars, falling back to config file
    all_urls = [u.strip() for u in os.environ.get("APT_URLS", "").split(",") if u.strip()]

    sources = []
    for i, s in enumerate(raw.get("sources", [])):
        url = all_urls[i] if i < len(all_urls) else s.get("url", "")
        sources.append(SourceConfig(
            name=s["name"],
            scraper=s["scraper"],
            url=url,
            enabled=s.get("enabled", True) and bool(url),
        ))

    tg_raw = raw.get("telegram", {})
    telegram = TelegramConfig(
        enabled=tg_raw.get("enabled", True),
        # Application Security Requirement: secrets loaded from env vars; never hardcoded
        bot_token=os.environ.get("TELEGRAM_BOT_TOKEN"),
        chat_id=os.environ.get("TELEGRAM_CHAT_ID"),
    )

    settings_raw = raw.get("settings", {})
    settings = AppSettings(
        max_apartment_age_days=settings_raw.get("max_apartment_age_days", 30),
    )

    return Config(sources=sources, telegram=telegram, settings=settings)
