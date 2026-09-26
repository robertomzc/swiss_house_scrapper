# Housing Scraper

Scrape real estate listings from Swiss platforms (ImmoScout24, Homegate) with flexible criteria filtering.

## Setup

Install dependencies with Poetry:
```bash
poetry install --no-root
```

## Usage

Basic usage with default criteria (max CHF 3000, min 2 rooms, min 60 m², Zurich/Geneva):
```bash
poetry run python -m src.my_package.main
```

### Custom Criteria

Create a Python script:
```python
from src.my_package.models import SearchCriteria
from src.my_package.main import scrape_multiple_sources

criteria = SearchCriteria(
    max_price_chf=2500,
    min_rooms=1.0,
    min_area_m2=50,
    cities=["Zurich"],
)

results = scrape_multiple_sources(criteria, max_results=20)
for prop in results:
    print(f"{prop.title}: CHF {prop.price_chf}, {prop.rooms} rooms, {prop.area_m2}m²")
```

### Export Results

```python
from src.my_package.utils import export_to_csv
export_to_csv(results, "listings.csv")
```

## Features

- **Multiple sources**: ImmoScout24, Homegate
- **Flexible filtering**: Price, rooms, area, location
- **Deduplication**: Tracks seen listings to avoid re-reporting
- **Data export**: Save to CSV or JSONL
- **Price analytics**: Calculate price per m²

## Data Location

Listings are stored in `data/properties.jsonl` (JSONL format)
Contributions are welcome! Please feel free to submit a pull request or open an issue for any suggestions or improvements.

## License
This project is licensed under the MIT License. See the LICENSE file for more details.