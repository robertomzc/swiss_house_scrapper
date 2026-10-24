from __future__ import annotations

import re
from email.message import EmailMessage

from .common import email_to_text, extract_address, extract_price, extract_rooms, extract_surface, find_urls


def _extract_lookmove_blocks(text: str) -> list[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    blocks: list[str] = []
    current: list[str] = []
    for line in lines:
        lowered = line.lower()
        if 'lookmove notification' in lowered or 'new listings' in lowered or 'manage notifications' in lowered:
            if current:
                blocks.append('\n'.join(current))
                current = []
            continue
        if 'support:' in lowered or 'linkedin:' in lowered or 'facebook:' in lowered or 'the lookmove team' in lowered:
            if current:
                blocks.append('\n'.join(current))
                current = []
            continue
        if 'rooms:' in lowered or 'CHF ' in line or 'price on request' in lowered:
            current.append(line)
            blocks.append('\n'.join(current))
            current = []
            continue
        if re.search(r'\b\d+(?:[.,]\d+)?\s*[-–]\s*\d+(?:[.,]\d+)?\s*(?:m²|m2|sqm)', line, re.I):
            current.append(line)
            continue
        if re.search(r'\b\d{4}\b', line) and re.search(r'[A-Za-zÀ-ÖØ-öø-ÿ]', line):
            current.append(line)
            continue
        if current and ('http' in lowered or 'see more' in lowered):
            continue
        current.append(line)
    if current:
        blocks.append('\n'.join(current))
    return [block for block in blocks if any(token in block.lower() for token in ['rooms:', 'CHF', 'price on request', 'm²', 'm2'])]


def parse_email(msg: EmailMessage) -> list[dict]:
    text = email_to_text(msg)
    if not text:
        return []

    urls = find_urls(text, ('lookmove.ch',))
    default_url = urls[0] if urls else 'https://www.lookmove.ch'
    entries: list[dict] = []

    for block in _extract_lookmove_blocks(text):
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
            'source_site': 'lookmove',
            'source': 'email_alert',
            'title': address or 'Lookmove listing',
        })

    if not entries:
        fallback = {
            'price': extract_price(text),
            'rooms': extract_rooms(text),
            'surface_m2': extract_surface(text),
            'address': extract_address(text),
            'url': default_url,
            'source_site': 'lookmove',
            'source': 'email_alert',
            'title': extract_address(text) or 'Lookmove listing',
        }
        if any(v is not None for v in [fallback['price'], fallback['rooms'], fallback['surface_m2'], fallback['address']]):
            entries.append(fallback)

    return entries


__all__ = ['parse_email']
