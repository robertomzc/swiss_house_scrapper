"""Email-first housing monitor pipeline.

This module is the canonical entrypoint for the project. It fetches unread
email alerts, normalizes them into listing records, and stores the result in
JSON for later analysis.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import yaml
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

load_dotenv()

from housing_monitor.email_ingestion.archives import mark_message_processed, load_processed_messages
from housing_monitor.email_ingestion.imap_client import fetch_messages
from housing_monitor.email_ingestion.parsers import parse_email
from housing_monitor.email_ingestion.model import Listing, PriceObservation
from housing_monitor.email_ingestion.storage import load_listings, save_listings, upsert
from housing_monitor.dashboard import generate_dashboard


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


def _process_message(msg, listings, seen_index, archive_dir='data/email_archive', processed_path='data/processed_messages.json'):
    key = msg.get('Message-ID') or msg.get('Subject') or str(msg.as_bytes()[:128])
    if key in seen_index:
        return 0

    created, meta = mark_message_processed(msg, archive_dir=archive_dir, processed_path=processed_path)
    if created:
        seen_index[key] = meta
    else:
        return 0

    parsed_entries = parse_email(msg)
    if not parsed_entries:
        print('Skipped a message — could not parse')
        return 0

    observed_at = _message_observed_at(msg)
    source_site = parsed_entries[0].get('source_site', 'unknown')

    for entry in parsed_entries:
        url = entry['url']
        price = entry.get('price')
        address = entry.get('address')
        rooms = entry.get('rooms')
        surface = entry.get('surface_m2')
        source_site = entry.get('source_site', source_site)

        listing = Listing(
            url=url,
            source_site=source_site,
            title=address or entry.get('title') or f'{source_site} listing',
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
        print(f'Upserted: {listing.title} | source={source_site} | price={price} | rooms={rooms} | surface={surface} | email_date={observed_at.date()}')

    return len(parsed_entries)


def main():
    cfg = load_config()
    label = cfg.get('gmail_label', 'Lausanne Housing')
    data_path = cfg.get('data_path', 'data/listings.json')
    imap_host = cfg.get('imap_host', 'imap.gmail.com')
    archive_dir = cfg.get('email_archive_dir', 'data/email_archive')
    processed_path = cfg.get('processed_messages_path', 'data/processed_messages.json')
    unread_only = cfg.get('unread_only', True)

    user = os.getenv('EMAIL_USER')
    password = os.getenv('EMAIL_PASSWORD')
    if not user or not password:
        print('Please set EMAIL_USER and EMAIL_PASSWORD in your environment.')
        return

    listings = load_listings(data_path)
    seen_index = load_processed_messages(processed_path)
    msgs = fetch_messages(imap_host, user, password, label, unread_only)
    mode_label = 'unread' if unread_only else 'all'
    print(f'Found {len(msgs)} {mode_label} messages in label "{label}"')

    total_items = 0
    for msg in msgs:
        total_items += _process_message(msg, listings, seen_index, archive_dir=archive_dir, processed_path=processed_path)

    os.makedirs(os.path.dirname(data_path) or '.', exist_ok=True)
    save_listings(listings, data_path)

    dashboard_path = cfg.get('dashboard_path', 'data/dashboard.html')
    generated_dashboard, _ = generate_dashboard(listings, output_path=dashboard_path, alert_count=total_items)
    print(f'Generated dashboard: {generated_dashboard}')

    print(f'\nSummary ({len(listings)} listings):')
    for listing in listings.values():
        print({
            'address': listing.address or listing.title,
            'source_site': listing.source_site,
            'current_price': listing.current_price,
            'rooms': listing.rooms,
            'surface_m2': listing.surface_m2,
            'days_on_market': listing.days_on_market,
            'price_change_pct': listing.price_change_pct,
        })


if __name__ == '__main__':
    main()
