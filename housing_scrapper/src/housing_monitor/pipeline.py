"""Email-first housing monitor pipeline.

This module is the canonical entrypoint for the project. It fetches unread
ImmoScout24 email alerts, normalizes them into listing records, and stores the
result in JSON for later analysis.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from housing_monitor.email_ingestion.imap_client import fetch_unread_messages
from housing_monitor.email_ingestion.parsers.immoscout24 import parse_email
from housing_monitor.email_ingestion.model import Listing, PriceObservation
from housing_monitor.email_ingestion.storage import load_listings, save_listings, upsert


def load_config(path='config.yaml'):
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    return {}


def _message_observed_at(msg) -> datetime:
    date_header = msg.get('Date')
    if not date_header:
        return datetime.now(timezone.utc)
    try:
        parsed = parsedate_to_datetime(date_header)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


def main():
    cfg = load_config()
    label = cfg.get('gmail_label', 'Lausanne Housing')
    data_path = cfg.get('data_path', 'data/listings.json')
    imap_host = cfg.get('imap_host', 'imap.gmail.com')

    user = os.getenv('EMAIL_USER')
    password = os.getenv('EMAIL_PASSWORD')
    if not user or not password:
        print('Please set EMAIL_USER and EMAIL_PASSWORD in your environment.')
        return

    listings = load_listings(data_path)

    msgs = fetch_unread_messages(imap_host, user, password, label)
    print(f'Found {len(msgs)} unread messages in label "{label}"')

    for msg in msgs:
        parsed_entries = parse_email(msg)
        if not parsed_entries:
            print('Skipped a message — could not parse')
            continue

        observed_at = _message_observed_at(msg)

        for entry in parsed_entries:
            url = entry['url']
            price = entry.get('price')
            address = entry.get('address')
            rooms = entry.get('rooms')
            surface = entry.get('surface_m2')

            listing = Listing(
                url=url,
                source_site='immoscout24',
                title=address or entry.get('title') or 'ImmoScout24 listing',
                address=address,
                rooms=rooms,
                surface_m2=surface,
            )
            obs = PriceObservation(
                observed_at=observed_at,
                price=price,
                status='new',
                source='email_alert',
            )
            upsert(listings, listing, obs)
            print(f'Upserted: {listing.title} | price={price} | rooms={rooms} | surface={surface} | email_date={observed_at.date()}')

    os.makedirs(os.path.dirname(data_path) or '.', exist_ok=True)
    save_listings(listings, data_path)

    print(f'\nSummary ({len(listings)} listings):')
    for listing in listings.values():
        print({
            'address': listing.address or listing.title,
            'current_price': listing.current_price,
            'rooms': listing.rooms,
            'surface_m2': listing.surface_m2,
            'days_on_market': listing.days_on_market,
            'price_change_pct': listing.price_change_pct,
        })


if __name__ == '__main__':
    main()
