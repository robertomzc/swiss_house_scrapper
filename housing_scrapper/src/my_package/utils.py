from pathlib import Path

try:
    from .models import Property, SearchCriteria
except ImportError:
    from my_package.models import Property, SearchCriteria


def load_properties_from_storage(filepath: str) -> list[Property]:
    """Load properties from JSONL storage file."""
    import json
    properties = []
    path = Path(filepath)
    if path.exists():
        with open(path) as f:
            for line in f:
                try:
                    data = json.loads(line)
                    prop = Property(
                        title=data.get("title", ""),
                        source=data.get("source", ""),
                        city=data.get("city", ""),
                        url=data.get("url", ""),
                        price_chf=data.get("price_chf"),
                        rooms=data.get("rooms"),
                        area_m2=data.get("area_m2"),
                        zip_code=data.get("zip_code"),
                    )
                    properties.append(prop)
                except (json.JSONDecodeError, ValueError):
                    pass
    return properties


def export_to_csv(properties: list[Property], filepath: str) -> None:
    """Export properties to CSV file."""
    import csv
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "title", "source", "city", "url", "price_chf", 
                "rooms", "area_m2", "zip_code"
            ]
        )
        writer.writeheader()
        for prop in properties:
            writer.writerow({
                "title": prop.title,
                "source": prop.source,
                "city": prop.city,
                "url": prop.url,
                "price_chf": prop.price_chf,
                "rooms": prop.rooms,
                "area_m2": prop.area_m2,
                "zip_code": prop.zip_code,
            })


def price_per_m2(prop: Property) -> float | None:
    """Calculate price per square meter."""
    if prop.price_chf and prop.area_m2 and prop.area_m2 > 0:
        return prop.price_chf / prop.area_m2
    return None
    pass  # Implement the functionality here as needed.