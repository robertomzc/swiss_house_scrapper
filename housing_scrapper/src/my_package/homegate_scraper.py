from __future__ import annotations

import re
from typing import Optional

try:
    import requests
except ImportError:
    requests = None

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

try:
    from .models import Property
except ImportError:
    from my_package.models import Property


class HomegateScraper:
    """Scraper for Homegate.ch listings."""

    def __init__(self, timeout: int = 20):
        self.timeout = timeout
        self.session = requests.Session() if requests is not None else None
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
            ),
        }

    @staticmethod
    def _clean_number(value: Optional[str]) -> Optional[float]:
        if value is None:
            return None
        cleaned = re.sub(r"[^0-9.]", "", value.replace(",", "."))
        if not cleaned:
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None

    def fetch_page(self, url: str) -> str:
        if requests is None:
            raise RuntimeError("requests package is not installed.")
        response = self.session.get(url, headers=self.headers, timeout=self.timeout)
        response.raise_for_status()
        return response.text

    def parse_listings(self, html: str, source_url: str) -> list[Property]:
        if BeautifulSoup is None:
            return []

        soup = BeautifulSoup(html, "html.parser")
        properties: list[Property] = []

        listing_cards = soup.find_all("article", {"data-testid": re.compile(".*listing.*")}) or soup.find_all("div", class_=re.compile(".*listing.*"))

        for card in listing_cards[:20]:
            try:
                text = card.get_text(" ", strip=True)
                if not text:
                    continue

                link = card.find("a", href=True)
                url = link["href"] if link else source_url
                if not url.startswith("http"):
                    url = f"https://www.homegate.ch{url}"

                title_elem = card.find("h2") or card.find("h3")
                title = title_elem.get_text(strip=True) if title_elem else "Unknown"

                price_text = re.search(r"CHF\s*([\d']+)", text, re.IGNORECASE)
                price = self._clean_number(price_text.group(1)) if price_text else None

                rooms_text = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:rooms?|zimmer)", text, re.IGNORECASE)
                rooms = self._clean_number(rooms_text.group(1)) if rooms_text else None

                area_text = re.search(r"(\d+(?:[.,]\d+)?)\s*m[²2]", text, re.IGNORECASE)
                area = self._clean_number(area_text.group(1)) if area_text else None

                zip_text = re.search(r"\b(\d{4})\b", text)
                zip_code = zip_text.group(1) if zip_text else None

                city = "Unknown"
                for c in ["Zurich", "Zürich", "Geneva", "Genève", "Lausanne", "Bern", "Basel"]:
                    if c in text:
                        city = c.replace("ü", "u") if c == "Zürich" else c
                        break

                prop = Property(
                    title=title,
                    source="Homegate",
                    city=city,
                    url=url,
                    price_chf=price,
                    rooms=rooms,
                    area_m2=area,
                    zip_code=zip_code,
                    property_type="apartment",
                )
                properties.append(prop)
            except Exception:
                continue

        return properties

    def scrape(self, url: str, max_results: int = 10) -> list[Property]:
        try:
            html = self.fetch_page(url)
            listings = self.parse_listings(html, source_url=url)
            return listings[:max_results]
        except Exception:
            return []
