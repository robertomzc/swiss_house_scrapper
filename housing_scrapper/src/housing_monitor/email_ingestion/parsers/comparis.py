from __future__ import annotations

import re
from email.message import EmailMessage

from .common import (
    email_to_text,
    extract_address,
    extract_price,
    extract_rooms,
    extract_surface,
    find_urls,
    split_listing_blocks,
)


def _normalize_entry_key(entry: dict) -> str:
    address = (entry.get('address') or '').lower().strip()
    price = entry.get('price')
    rooms = entry.get('rooms')
    surface = entry.get('surface_m2')
    return f"{address}|{price}|{rooms}|{surface}"


def parse_email(msg: EmailMessage) -> list[dict]:
    text = email_to_text(msg)
    if not text:
        return []

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
        ]):
            if not any(token in lowered for token in ['chf', 'rooms', 'pièces', 'zimmer', 'm²', 'm2', 'appartement', 'maison', 'villa', 'attique', 'studio']):
                continue
        block_urls = find_urls(block, hosts)
        if not block_urls and 'CHF' not in block.upper() and 'Fr.' not in block:
            continue
        if not any(token in block.lower() for token in ['chf', 'rooms', 'pièces', 'zimmer', 'm²', 'm2', 'appartement', 'maison', 'villa', 'attique', 'duplex', 'studio']):
            continue
        price = extract_price(block)
        rooms = extract_rooms(block)
        surface = extract_surface(block)
        address = extract_address(block)
        if not address and price is None and rooms is None and surface is None:
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
