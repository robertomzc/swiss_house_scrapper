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
        if 'search subscription' in lowered or 'all results' in lowered or 'extend search subscription' in lowered or 'delete search subscription' in lowered:
            if current:
                blocks.append('\n'.join(current))
                current = []
            continue
        if 'selling price' in lowered or 'CHF ' in stripped or re.search(r'CHF\s*[\d\u202f\s\.,\']+', stripped, re.I):
            current.append(stripped)
            blocks.append('\n'.join(current))
            current = []
            continue
        if len(stripped) < 180 and re.search(r'\b\d+(?:[.,]\d+)?\s*room|room\b|\d{4}\s+[A-Za-zÀ-ÖØ-öø-ÿ]', stripped, re.I):
            current.append(stripped)
            continue
        if current and ('http' in lowered or 'newhome' in lowered or 'property app' in lowered):
            continue
        if any(token in lowered for token in ['your search subscription', 'contains', 'automatically generated', 'all results', 'extend search subscription', 'delete search subscription']):
            continue
        current.append(stripped)
    if current:
        blocks.append('\n'.join(current))
    cleaned = [block for block in blocks if any(token in block.lower() for token in ['CHF', 'room', 'lausanne', 'saint', 'morges', 'prilly'])]
    cleaned = [block for block in cleaned if not any(token in block.lower() for token in ['your search subscription', 'all results', 'extend search subscription', 'delete search subscription'])]
    return [block for block in cleaned if not re.search(r'\b(?:new results in your search subscription|this is an automatically generated e-mail)\b', block, re.I)]


def parse_email(msg: EmailMessage) -> list[dict]:
    text = email_to_text(msg)
    if not text:
        return []

    urls = find_urls(text, ('newhome.ch',))
    default_url = urls[0] if urls else 'https://www.newhome.ch'
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
            'source_site': 'newhome',
            'source': 'email_alert',
            'title': address or 'Newhome listing',
        })

    if not entries:
        fallback = {
            'price': extract_price(text),
            'rooms': extract_rooms(text),
            'surface_m2': extract_surface(text),
            'address': extract_address(text),
            'url': default_url,
            'source_site': 'newhome',
            'source': 'email_alert',
            'title': extract_address(text) or 'Newhome listing',
        }
        if any(v is not None for v in [fallback['price'], fallback['rooms'], fallback['surface_m2'], fallback['address']]):
            entries.append(fallback)

    return entries


__all__ = ['parse_email']
