from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
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


class ImmoScout24Scraper:
    """Scraper for ImmoScout24.ch listings."""

    def __init__(self, timeout: int = 20):
        self.timeout = timeout
        self.session = requests.Session() if requests is not None else None
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        }

    @staticmethod
    def _clean_number(value: Optional[str]) -> Optional[float]:
        if value is None:
            return None
        cleaned = value.strip()
        cleaned = cleaned.replace("CHF", "").replace("'", "").replace("'", "")
        cleaned = re.sub(r"[^0-9.]", "", cleaned.replace(",", "."))
        if not cleaned:
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None

    @staticmethod
    def _extract_price(text: str) -> Optional[float]:
        match = re.search(r"CHF\s*[\d'.\s]+", text, flags=re.IGNORECASE)
        if not match:
            return None
        return ImmoScout24Scraper._clean_number(match.group(0))

    @staticmethod
    def _extract_rooms(text: str) -> Optional[float]:
        match = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:rooms?|zimmer|chambres?)", text, flags=re.IGNORECASE)
        if not match:
            return None
        return float(match.group(1).replace(",", "."))

    @staticmethod
    def _extract_area(text: str) -> Optional[float]:
        match = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:m2|m²|sqm)", text, flags=re.IGNORECASE)
        if not match:
            return None
        return float(match.group(1).replace(",", "."))

    @staticmethod
    def _extract_zip(text: str) -> Optional[str]:
        match = re.search(r"\b(\d{4})\b", text)
        return match.group(1) if match else None

    def fetch_page(self, url: str) -> str:
        if requests is None:
            raise RuntimeError("requests package is not installed.")
        response = self.session.get(url, headers=self.headers, timeout=self.timeout)
        response.raise_for_status()
        return response.text

    def fetch_page_with_playwright(self, url: str, wait_for_selector: str = "article, a[href*='/en/rent/']") -> str:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError("playwright package is not installed") from exc

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(
                viewport={"width": 1440, "height": 2000},
                user_agent=self.headers["User-Agent"],
            )
            page.goto(url, wait_until="domcontentloaded", timeout=120000)
            try:
                page.wait_for_selector(wait_for_selector, timeout=20000)
            except Exception:
                pass
            page.wait_for_timeout(6000)
            html = page.content()
            browser.close()

        return html

    def parse_listings(self, html: str, source_url: str) -> list[Property]:
        if BeautifulSoup is None:
            return []

        soup = BeautifulSoup(html, "html.parser")
        properties: list[Property] = []
        cards = soup.find_all("article") or soup.find_all("div", {"data-testid": re.compile(".*listing.*")})

        for card in cards[:20]:
            try:
                text = card.get_text(" ", strip=True)
                if not text or ("CHF" not in text and "chf" not in text):
                    continue

                link = card.find("a", href=re.compile(r"/en/(rent|buy)/"))
                url = link["href"] if link else source_url
                if not url.startswith("http"):
                    url = f"https://www.immoscout24.ch{url}"

                title = card.find("h1") or card.find("h2") or card.find("h3")
                title = title.get_text(strip=True) if title else "Unknown property"

                price = self._extract_price(text)
                rooms = self._extract_rooms(text)
                area = self._extract_area(text)
                zip_code = self._extract_zip(text)

                city = "Unknown"
                for c in ["Zurich", "Zürich", "Geneva", "Genève", "Lausanne", "Bern", "Basel"]:
                    if c in text:
                        city = c
                        break

                prop = Property(
                    title=title,
                    source="ImmoScout24",
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
            if listings:
                return listings[:max_results]
        except Exception:
            pass

        try:
            html = self.fetch_page_with_playwright(url)
            listings = self.parse_listings(html, source_url=url)
            return listings[:max_results]
        except Exception:
            return []


class PropertyStorage:
    """Simple file-based storage for properties."""

    def __init__(self, filepath: str = "properties.jsonl"):
        self.filepath = Path(filepath)
        self.filepath.parent.mkdir(parents=True, exist_ok=True)

    def save(self, properties: list[Property]) -> None:
        with open(self.filepath, "a") as f:
            for prop in properties:
                data = {
                    "title": prop.title,
                    "source": prop.source,
                    "url": prop.url,
                    "price_chf": prop.price_chf,
                    "rooms": prop.rooms,
                    "area_m2": prop.area_m2,
                    "city": prop.city,
                    "zip_code": prop.zip_code,
                    "timestamp": datetime.now().isoformat(),
                }
                f.write(json.dumps(data) + "\n")

    def load_unique_urls(self) -> set[str]:
        urls = set()
        if self.filepath.exists():
            with open(self.filepath) as f:
                for line in f:
                    try:
                        data = json.loads(line)
                        urls.add(data.get("url", ""))
                    except json.JSONDecodeError:
                        pass
        return urls

    def filter_new(self, properties: list[Property]) -> list[Property]:
        known_urls = self.load_unique_urls()
        return [p for p in properties if p.url and p.url not in known_urls]
