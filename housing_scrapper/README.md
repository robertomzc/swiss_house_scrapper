# Housing scraper

A small Python project for tracking Swiss rental listings by price, rooms, area and city.

## Goal
- search a few real-estate sites
- filter listings by custom criteria
- keep only new properties
- store results in a simple JSONL file

## Current status
This is a working prototype, not a production-grade listing API.

Important findings from testing:
- public APIs for ImmoScout24/Homegate do not appear to be available to normal users
- direct HTTP requests to the listing pages often return 403
- the pages are dynamic and can change fast
- browser automation via Playwright is the realistic fallback
- the local environment here does not have a working Chromium install, so live extraction is blocked in this machine

## Project structure
- `src/my_package/models.py`: filtering and property model
- `src/my_package/immoscout_scraper.py`: ImmoScout24 scraper
- `src/my_package/homegate_scraper.py`: Homegate scraper
- `src/my_package/main.py`: orchestrator
- `src/my_package/utils.py`: export helpers
- `LLM_NOTES.md`: short project notes for future coding help

## Setup
```bash
cd housing_scrapper
poetry install --no-root
```

## Run
```bash
poetry run python -m src.my_package.main
```

## Notes
- The scraper is intentionally simple and easy to extend.
- For real-world use, run it on a machine/container with a supported Playwright browser runtime.
- Expect frequent maintenance when target sites change their HTML or block bot traffic.