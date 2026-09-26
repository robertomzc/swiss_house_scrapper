# Housing scraper notes

## Short version
- This project is a Swiss housing scraper prototype.
- Goal: look for apartments by price/rooms/city with a simple filter model.
- The repo contains a basic scraper structure and a small data model.

## Problems found
- Public ImmoScout24/Homegate APIs do not appear to be available for normal users.
- Direct HTTP access to listing pages often returns 403 Forbidden.
- HTML parsing is fragile because listing pages are dynamic and may change often.
- Playwright is the realistic browser-based fallback, but it needs a supported browser runtime.

## What was tested
- Simple requests-based scrape: failed with 403.
- Browser-based Playwright path: code is in place, but the local environment does not have a working Chromium install.
- The browser install also fails on this Ubuntu 20.04 environment, so no live data extraction could be validated here.

## Current recommendation
- Keep the project structure but treat the scraper as browser-based rather than pure HTTP.
- Use Playwright with a supported OS/runtime when running on a real machine or Docker image.
- Keep selectors and filters simple and easy to adjust.
- Do not rely on public official APIs unless a partner/private endpoint is available.

## Important detail
- This is a scraping project for public websites, not a stable product API.
- Expect frequent breaks when the target sites change frontend structure or block automated access.
