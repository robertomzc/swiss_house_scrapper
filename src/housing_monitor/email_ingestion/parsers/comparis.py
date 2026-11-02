from __future__ import annotations

import re
from email.message import EmailMessage

from .common import (
    email_to_text,
    extract_address,
    extract_price,
    extract_rooms,
    extract_surface,
    email_html_soups,
    find_urls,
    split_listing_blocks,
)


def _normalize_entry_key(entry: dict) -> str:
    address = (entry.get('address') or '').lower().strip()
    price = entry.get('price')
    rooms = entry.get('rooms')
    surface = entry.get('surface_m2')
    return f"{address}|{price}|{rooms}|{surface}"


def _parse_plain_listing_cards(text: str, msg: EmailMessage) -> list[dict]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    entries: list[dict] = []
    seen: set[str] = set()

    for index, line in enumerate(lines):
        price = extract_price(line)
        if price is None or not re.search(r'\b(?:CHF|Fr\.?|€)\b', line, re.I):
            continue

        before = lines[max(0, index - 5):index]
        after = lines[index + 1:index + 5]
        address = extract_address('\n'.join(after))
        if not address:
            continue

        title = next(
            (
                candidate
                for candidate in reversed(before)
                if not candidate.lower().startswith(('http://', 'https://'))
                and not any(
                    marker in candidate.lower()
                    for marker in ('your search alert', 'new properties', 'property with updated price')
                )
            ),
            None,
        )
        if not title:
            continue

        listing_details = '\n'.join(after)
        entry = {
            'price': price,
            'rooms': extract_rooms(listing_details),
            'surface_m2': extract_surface(listing_details),
            'address': address,
            'url': 'https://www.comparis.ch',
            'source_site': 'comparis',
            'source': 'email_alert',
            'title': title,
        }
        key = _normalize_entry_key(entry)
        if key not in seen:
            seen.add(key)
            entries.append(entry)

    if entries:
        title_urls = {}
        for soup in email_html_soups(msg):
            for anchor in soup.find_all('a', href=True):
                label = anchor.get_text(' ', strip=True)
                if label:
                    title_urls.setdefault(label, anchor['href'])
        for entry in entries:
            entry['url'] = title_urls.get(entry['title'], entry['url'])

    return entries


def parse_email(msg: EmailMessage) -> list[dict]:
    text = email_to_text(msg)
    if not text:
        return []

    plain_entries = _parse_plain_listing_cards(text, msg)
    if plain_entries:
        return plain_entries

    hosts = ('comparis.ch', 'en.comparis.ch', 'links.comparis.ch')
    urls = find_urls(text, hosts)
    default_url = urls[0] if urls else 'https://www.comparis.ch'
    blocks = split_listing_blocks(text, hosts)
    entries: list[dict] = []

    for block in blocks:
        lowered = block.lower()
        if any(token in lowered for token in [
            'your search alert',
            'new properties',
            'property with updated price',
            'we wish you all success with your search',
            'recommend comparis',
            'more information',
            'online version',
            'manage search alerts',
            'delete search alert',
            'search criteria',
            'rate us now',
            'your feedback helps us',
            'all results',
        ]):
            if not re.search(r'\b\d{4}\s+[A-Za-zÀ-ÖØ-öø-ÿ]|\b(?:appartement|maison|villa|studio|attique|duplex)\b|\b\d+(?:[.,]\d+)?\s*(?:rooms?|pièces?|zimmer)\b', block, re.I):
                continue
        if any(token in lowered for token in ['your search alert', 'new properties', 'search criteria', 'manage search alerts', 'delete search alert', 'we wish you all success with your search', 'rate us now', 'online version', 'all results']):
            if not re.search(r'\b\d{4}\s+[A-Za-zÀ-ÖØ-öø-ÿ]|\b(?:appartement|maison|villa|studio|attique|duplex)\b|\b\d+(?:[.,]\d+)?\s*(?:rooms?|pièces?|zimmer)\b', block, re.I):
                continue
        block_urls = find_urls(block, hosts)
        if not block_urls and 'CHF' not in block.upper() and 'Fr.' not in block and '€' not in block:
            continue
        if not any(token in block.lower() for token in ['chf', 'rooms', 'pièces', 'zimmer', 'm²', 'm2', 'appartement', 'maison', 'villa', 'attique', 'duplex', 'studio']):
            continue
        price = extract_price(block)
        rooms = extract_rooms(block)
        surface = extract_surface(block)
        address = extract_address(block)
        if not address and price is None and rooms is None and surface is None:
            continue
        # Ignore summary lines that happened to contain a price but no actual listing address.
        if address is None and (price is not None or rooms is not None or surface is not None):
            if not re.search(r'\b\d{4}\b', block):
                continue
        entry = {
            'price': price,
            'rooms': rooms,
            'surface_m2': surface,
            'address': address,
            'url': block_urls[0] if block_urls else default_url,
            'source_site': 'comparis',
            'source': 'email_alert',
            'title': address or 'Comparis listing',
        }
        entries.append(entry)

    deduped: list[dict] = []
    seen: set[str] = set()
    for entry in entries:
        key = _normalize_entry_key(entry)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(entry)

    if not deduped and text:
        fallback = {
            'price': extract_price(text),
            'rooms': extract_rooms(text),
            'surface_m2': extract_surface(text),
            'address': extract_address(text),
            'url': default_url,
            'source_site': 'comparis',
            'source': 'email_alert',
            'title': extract_address(text) or 'Comparis listing',
        }
        if any(v is not None for v in [fallback['price'], fallback['rooms'], fallback['surface_m2'], fallback['address']]):
            deduped.append(fallback)

    return deduped


__all__ = ['parse_email']
