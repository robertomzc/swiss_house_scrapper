# Project notes

This project reads rental alerts from email and stores them as structured listing records.

The main flow is:
1. connect to Gmail
2. read the configured label
3. parse ImmoScout24 alert content
4. normalize the result into a property model
5. save or update the listing in JSON storage

The current implementation is intentionally small and focused on reliability rather than complexity.
