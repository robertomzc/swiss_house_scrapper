from __future__ import annotations

from email.message import EmailMessage
import re

from .common import (
    email_html_soups,
    email_to_text,
    extract_price,
    extract_rooms,
    find_urls,
    parse_generic_listing,
    split_listing_blocks,
)


def _parse_html_listings(msg: EmailMessage) -> list[dict]:
    entries = []
    seen: set[str] = set()

    for soup in email_html_soups(msg):
        for heading in soup.find_all(class_='listing-title'):
            row = heading.find_parent('tr')
            if row is None:
                continue
            title = re.sub(r'\s+', ' ', heading.get_text(' ', strip=True))
            row_text = re.sub(r'\s+', ' ', ' '.join(row.stripped_strings))
            location = row_text.split(title, 1)[-1].split('Appartement', 1)[0].strip()
            street_first = re.match(
                r'^(?P<commune>[^,]+),\s*(?P<street>(?:Avenue|Rue|Route|Chemin|Place|Boulevard)\b.+)$',
                location,
                re.I,
            )
            if street_first:
                address = f"{street_first.group('street')}, {street_first.group('commune')}"
            else:
                address = location.split(',', 1)[0].strip()
            if not address:
                continue

            current_price = row.find(class_='price-value')
            price = (
                extract_price(current_price.get_text(' ', strip=True))
                if current_price
                else extract_price(row_text)
            )
            rooms = extract_rooms(row_text)
            if price is None or rooms is None:
                continue

            listing_link = row.find('a', href=re.compile(r'/listing/'))
            url = listing_link['href'] if listing_link else 'https://www.properstar.ch'
            key = f'{url}|{price}|{rooms}'
            if key in seen:
                continue
            seen.add(key)
            entries.append({
                'price': price,
                'rooms': rooms,
                'surface_m2': None,
                'address': address,
                'url': url,
                'source_site': 'properstar',
                'source': 'email_alert',
                'title': title,
            })

    return entries


def parse_email(msg: EmailMessage) -> list[dict]:
    html_entries = _parse_html_listings(msg)
    if html_entries:
        return html_entries

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
