from __future__ import annotations

import sys
from pathlib import Path

try:
    from .immoscout_scraper import ImmoScout24Scraper, PropertyStorage
    from .homegate_scraper import HomegateScraper
    from .models import Property, SearchCriteria
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from my_package.immoscout_scraper import ImmoScout24Scraper, PropertyStorage
    from my_package.homegate_scraper import HomegateScraper
    from my_package.models import Property, SearchCriteria


def scrape_multiple_sources(
    criteria: SearchCriteria | None = None,
    max_results: int = 20,
    storage_file: str = "data/properties.jsonl",
) -> list[Property]:
    """Scrape multiple sources and filter by criteria."""
    
    if criteria is None:
        criteria = SearchCriteria()
    
    storage = PropertyStorage(storage_file)
    all_properties = []
    
    immoscout = ImmoScout24Scraper()
    homegate = HomegateScraper()
    
    print("Scraping ImmoScout24...")
    for url in [
        "https://www.immoscout24.ch/en/rent/apartment/zh/zurich",
        "https://www.immoscout24.ch/en/rent/apartment/ge/geneva",
    ]:
        try:
            props = immoscout.scrape(url, max_results=10)
            all_properties.extend(props)
        except Exception as e:
            print(f"  Error scraping {url}: {e}")
    
    print("Scraping Homegate...")
    for url in [
        "https://www.homegate.ch/rent/apartment/city-zurich",
        "https://www.homegate.ch/rent/apartment/city-geneva",
    ]:
        try:
            props = homegate.scrape(url, max_results=10)
            all_properties.extend(props)
        except Exception as e:
            print(f"  Error scraping {url}: {e}")
    
    filtered = [p for p in all_properties if criteria.matches(p)]
    new_properties = storage.filter_new(filtered)
    
    if new_properties:
        storage.save(new_properties)
    
    return new_properties[:max_results]


if __name__ == "__main__":
    criteria = SearchCriteria(
        max_price_chf=3000,
        min_rooms=2.0,
        min_area_m2=60,
        cities=["Zurich", "Geneva"],
    )
    
    results = scrape_multiple_sources(criteria, max_results=10)
    
    print(f"\nFound {len(results)} new properties matching criteria:")
    for prop in results:
        print(f"  {prop.title}")
        print(f"    Price: CHF {prop.price_chf}, Rooms: {prop.rooms}, Area: {prop.area_m2}m²")
        print(f"    URL: {prop.url}\n")
