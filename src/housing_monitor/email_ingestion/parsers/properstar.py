from __future__ import annotations

from email.message import EmailMessage
import re

from .common import email_to_text, find_urls, parse_generic_listing, split_listing_blocks


def parse_email(msg: EmailMessage) -> list[dict]:
    text = email_to_text(msg)
    if not text:
        return []

    urls = find_urls(text, ('properstar', 'poperstar', 'properstar.ch', 'poperstar.ch'))
    default_url = urls[0] if urls else 'https://www.properstar.ch'
    blocks = split_listing_blocks(text, ('properstar', 'poperstar'))
    entries: list[dict] = []

    for block in blocks:
        lowered = block.lower()
        if any(token in lowered for token in [
            '5 alertes pour ta recherche',
            'search alert',
            'découvre toutes les mises à jour',
            'discover all updates',
            'manage your search',
            'unsubscribe',
            'contact',
            'all results',
            'se désinscrire',
            'properstar.com',
            'properties match your search',
        ]):
            if not any(token in lowered for token in ['chf', 'pièces', 'rooms', 'zimmer', 'm²', 'm2', 'appartement', 'maison', 'villa', 'address', 'lausanne']):
                continue
        if 'search alert' in lowered and not re.search(r'\b\d{4}\s+[A-Za-zÀ-ÖØ-öø-ÿ]|\b\d+(?:[.,]\d+)?\s*(?:pièces?|rooms?|zimmer)\b|\b(?:appartement|maison|villa|studio|duplex)\b', block, re.I):
            continue
        block_urls = find_urls(block, ('properstar', 'poperstar'))
        if not block_urls and not any(token in block.lower() for token in ['chf', 'pièces', 'rooms', 'zimmer', 'm²', 'm2', 'appartement', 'maison', 'villa', 'lausanne']):
            continue
        from .common import extract_address, extract_price, extract_rooms, extract_surface
        price = extract_price(block)
        rooms = extract_rooms(block)
        surface = extract_surface(block)
        address = extract_address(block)
        if price is None and rooms is None and surface is None and address is None:
            continue
        if address is None and not re.search(r'\b\d{4}\b', block):
            continue
        entries.append({
            'price': price,
            'rooms': rooms,
            'surface_m2': surface,
            'address': address,
            'url': block_urls[0] if block_urls else default_url,
            'source_site': 'properstar',
            'source': 'email_alert',
            'title': address or 'Properstar listing',
        })

    if not entries and text:
        fallback = parse_generic_listing(text, default_url, 'properstar', ('properstar', 'poperstar'))
        for entry in fallback:
            entry['source_site'] = 'properstar'
            entry['title'] = entry.get('address') or 'Properstar listing'
        return fallback

    return entries


__all__ = ['parse_email']
