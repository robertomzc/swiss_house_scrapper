# Housing Monitor

This project reads apartment alerts from email, extracts the listing details, and stores the results so they can be tracked over time.

## What it does
- connects to the configured Gmail label
- reads ImmoScout24 alert emails
- extracts address, price, rooms, and area information
- normalizes the data into a reusable property model
- keeps the latest listing state in JSON so changes can be observed later

## Project layout
- `src/housing_monitor/models.py`: shared property and filter models
- `src/housing_monitor/utils.py`: reusable helpers
- `src/housing_monitor/email_ingestion/imap_client.py`: Gmail IMAP access
- `src/housing_monitor/email_ingestion/parsers/immoscout24.py`: email parser
- `src/housing_monitor/email_ingestion/model.py`: stored listing/history model
- `src/housing_monitor/email_ingestion/storage.py`: JSON persistence logic
- `src/housing_monitor/pipeline.py`: main processing flow
- `run_pipeline.py`: script to run the pipeline manually
- `config.yaml`: mailbox and storage settings
- `data/artifacts/listings.json`: saved listing data
- `data/artifacts/email_archive/`: archived source emails
- `data/artifacts/processed_messages.json`: processed email index
- `data/artifacts/dashboard.html`: generated dashboard
- `data/sources.csv`: configured listing sources
- `data/email_training_set/`: parser training samples and expected outputs

## Setup
```bash
poetry env use 3.13
poetry install
poetry run python --version
```
The project requires Python 3.13. Run Python and test commands through Poetry
(`poetry run python ...`, `poetry run pytest ...`) so they use the project's
virtual environment instead of a potentially different system interpreter.

## Run
```bash
poetry run housing-monitor
```

The pipeline generates `data/artifacts/dashboard.html` with price/surface and price/room charts, a schematic Lausanne map, summary histograms, and an all-listings table. The dashboard is self-contained and can be opened directly as a `file://` URL without network access. The map is a fixed illustration rather than a street map; locations inferred from Lausanne postcodes are approximate, while exact coordinates are used when available. Listing links remain clickable and need internet only when opened.

## Parser validation
Downloaded email samples and their expected outputs live under `data/email_training_set/<source>/` and remain separate from generated artifacts.
The corpus-backed parser checks are in `tests/test_email_training_set.py` and can be run with:
```bash
poetry run pytest tests/test_email_training_set.py
```

## Notes
- The project is intentionally simple and focused on email-based listing tracking.
- It is designed to be easy to extend with more parsers or alert sources later.