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
- `data/listings.json`: saved listing data

## Setup
```bash
cd housing_scrapper
poetry install
```

## Run
```bash
cd housing_scrapper
poetry run housing-monitor
```

## Notes
- The project is intentionally simple and focused on email-based listing tracking.
- It is designed to be easy to extend with more parsers or alert sources later.