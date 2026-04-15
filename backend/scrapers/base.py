from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class Apartment:
    id: str
    source: str
    listing_url: str
    title: Optional[str] = None
    address: Optional[str] = None
    price: Optional[int] = None
    rooms: Optional[float] = None
    size_sqm: Optional[float] = None
    neighborhood: Optional[str] = None
    balcony: Optional[bool] = None
    parking: Optional[bool] = None
    furnished: Optional[bool] = None
    mamad: Optional[bool] = None
    agent: Optional[bool] = None
    image_url: Optional[str] = None


class BaseScraper(ABC):
    @abstractmethod
    async def scrape(self, url: str) -> list[Apartment]:
        """Scrape the given filtered search URL and return a list of Apartment objects."""
        ...
