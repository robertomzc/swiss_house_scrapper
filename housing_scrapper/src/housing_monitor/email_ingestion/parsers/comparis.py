from __future__ import annotations

import re
from email.message import EmailMessage

from .common import email_to_text, extract_address, extract_price, extract_rooms, extract_surface, find_urls


def _iter_listing_blocks(text: str) -> list[str]:
    blocks: list[str] = []
    current: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        lowered = stripped.lower()
        if any(token in lowered for token in ['search alert', 'search criteria', 'manage search alerts', 'delete search alert', 'your search alert', 'results based on updated prices']):
            if current:
                blocks.append('\n'.join(current))
                current = []
            continue
        if any(token in lowered for token in ['more information', 'rate us now', 'share with friends', 'kind regards', 'comparis property app', 'we wish you all success']):
            if current:
                blocks.append('\n'.join(current))
                current = []
            continue
        if 'CHF ' in stripped or re.search(r'CHF\s*\d', stripped):
            if current:
                current.append(stripped)
                blocks.append('\n'.join(current))
                current = []
                continue
        current.append(stripped)
    if current:
        blocks.append('\n'.join(current))
    return [block for block in blocks if re.search(r'CHF|rooms|m²|m2|\d{4}\s+[A-Za-zÀ-ÖØ-öø-ÿ]', block, re.I)]


def parse_email(msg: EmailMessage) -> list[dict]:
    text = email_to_text(msg)
    if not text:
        return []

    urls = find_urls(text, ('comparis.ch',))
    default_url = urls[0] if urls else 'https://www.comparis.ch'
    entries: list[dict] = []

    for block in _iter_listing_blocks(text):
        price = extract_price(block)
        rooms = extract_rooms(block)
        surface = extract_surface(block)
        address = extract_address(block)
        if price is None and rooms is None and surface is None and address is None:
            continue
        entries.append({
            'price': price,
            'rooms': rooms,
            'surface_m2': surface,
            'address': address,
            'url': default_url,
            'source_site': 'comparis',
            'source': 'email_alert',
            'title': address or 'Comparis listing',
        })

    if not entries:
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
            entries.append(fallback)

    return entries


__all__ = ['parse_email']
