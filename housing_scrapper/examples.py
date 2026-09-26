#!/usr/bin/env python3
"""Example: Run scraper with different criteria."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[0] / "src"))

from my_package.models import SearchCriteria, Property
from my_package.main import scrape_multiple_sources
from my_package.utils import export_to_csv


def example_zurich_2bedroom():
    """Find 2-room+ apartments in Zurich under CHF 3500."""
    criteria = SearchCriteria(
        max_price_chf=3500,
        min_rooms=2.0,
        cities=["Zurich"],
    )
    
    print("Searching for 2+ room apartments in Zurich, max CHF 3500...")
    results = scrape_multiple_sources(criteria, max_results=10)
    
    if results:
        export_to_csv(results, "results/zurich_2bedroom.csv")
        print(f"✓ Found {len(results)} properties (saved to CSV)")
    else:
        print("✗ No properties found")
    
    return results


def example_geneva_studio():
    """Find studio/1-room apartments in Geneva under CHF 2000."""
    criteria = SearchCriteria(
        max_price_chf=2000,
        min_rooms=0.5,
        max_price_chf_per_m2=60,
        cities=["Geneva"],
    )
    
    print("\nSearching for studios/1-room in Geneva, max CHF 2000...")
    results = scrape_multiple_sources(criteria, max_results=5)
    
    if results:
        for prop in results:
            print(f"  • {prop.title} - CHF {prop.price_chf}")
    else:
        print("✗ No properties found")
    
    return results


if __name__ == "__main__":
    example_zurich_2bedroom()
    example_geneva_studio()
    
    print("\n✓ All examples completed")
