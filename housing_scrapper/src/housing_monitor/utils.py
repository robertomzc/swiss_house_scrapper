from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


def load_properties_from_storage(filepath: str) -> list[dict[str, Any]]:
    """Load properties from a JSONL storage file."""
    properties: list[dict[str, Any]] = []
    path = Path(filepath)
    if path.exists():
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    data = json.loads(line)
                    properties.append(data)
                except (json.JSONDecodeError, ValueError):
                    pass
    return properties


def export_to_csv(properties: list[dict[str, Any]], filepath: str) -> None:
    """Export properties to CSV."""
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["title", "source", "city", "url", "price_chf", "rooms", "area_m2", "zip_code"],
        )
        writer.writeheader()
        for prop in properties:
            writer.writerow(
                {
                    "title": prop.get("title", ""),
                    "source": prop.get("source", ""),
                    "city": prop.get("city", ""),
                    "url": prop.get("url", ""),
                    "price_chf": prop.get("price_chf"),
                    "rooms": prop.get("rooms"),
                    "area_m2": prop.get("area_m2"),
                    "zip_code": prop.get("zip_code"),
                }
            )


def price_per_m2(prop: dict[str, Any]) -> float | None:
    """Calculate price per square meter."""
    price = prop.get("price_chf")
    area = prop.get("area_m2")
    if price is not None and area and area > 0:
        return float(price) / float(area)
    return None


__all__ = ["load_properties_from_storage", "export_to_csv", "price_per_m2"]
