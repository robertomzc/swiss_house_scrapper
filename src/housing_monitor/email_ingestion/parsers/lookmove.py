from __future__ import annotations

import re
from email.message import EmailMessage

from .common import (
    email_html_soups,
    email_to_text,
    extract_address,
    extract_price,
    extract_rooms,
    extract_surface,
    find_urls,
    split_listing_blocks,
)


def _is_summary_block(block: str) -> bool:
    lowered = block.lower()
    if any(token in lowered for token in [
        'newly added properties match your search',
        'following properties correspond to your search',
        'you have new alerts',
        'manage notifications',
        'the lookmove team',
        'support:',
        'linkedin:',
        'facebook:',
        'see more',
        'property suggestions',
        'tailored properties based on your property preferences',
    ]):
        return True
    if 'lookmove' in lowered and 'notification' in lowered and 'search' in lowered:
        return True
    return False


def _extract_lookmove_blocks(text: str) -> list[str]:
    blocks = split_listing_blocks(text, ('lookmove.ch', 'email.support.lookmove.ch'))
    cleaned: list[str] = []
    for block in blocks:
        lowered = block.lower()
        if _is_summary_block(block):
            continue
        if any(token in lowered for token in ['manage notifications', 'the lookmove team', 'support:', 'linkedin:', 'facebook:', 'new listings that may interest you', 'copyright ©', 'se désinscrire']):
            continue
        if any(token in lowered for token in ['newly added properties match your search', 'following properties correspond to your search', 'you have new alerts']):
            continue
        if 'property suggestions' in lowered and 'tailored properties based on your property preferences' in lowered:
            continue
        if not (
            any(token in lowered for token in ['rooms', 'chf', 'price on request', 'm²', 'm2', 'pièces', 'zimmer', 'appartement', 'maison', 'villa'])
            or re.search(r'\b\d{4}\s+[A-Za-zÀ-ÖØ-öø-ÿ]', block)
            or re.search(r'\b\d{4}\s+\S+', block)
            or re.search(r'\b\d+(?:[.,]\d+)?\s*(?:rooms?|pièces?|zimmer)\b', block, re.I)
        ):
            continue
        cleaned.append(block)
    return cleaned


def parse_email(msg: EmailMessage) -> list[dict]:
    html_entries = []
    seen_html_cards: set[str] = set()
    for soup in email_html_soups(msg):
        card_tables = []
        for table in soup.find_all('table'):
            text = ' '.join(table.stripped_strings)
            lowered = text.lower()
            if 'rooms:' in lowered and 'm²' in lowered and (
                'chf' in lowered or 'price on request' in lowered
            ):
                card_tables.append((table, text))

        qualified_tables = {id(table) for table, _ in card_tables}
        for table, text in card_tables:
            if any(id(child) in qualified_tables for child in table.find_all('table')):
                continue

            location = text.split('Rooms:', 1)[0].strip()
            address = extract_address(location)
            if not address:
                continue

            rooms = extract_rooms(text)
            surface = extract_surface(text)
            price = extract_price(text)
            key = f'{address}|{rooms}|{surface}|{price}'
            if key in seen_html_cards:
                continue
            seen_html_cards.add(key)

            urls = find_urls(
                '\n'.join(anchor.get('href', '') for anchor in table.find_all('a', href=True)),
                ('lookmove.ch', 'email.support.lookmove.ch'),
            )
            locality = address.rsplit(',', 1)[-1].strip()
            if re.match(r'\d{4}\s+', locality):
                locality = re.sub(r'^\d{4}\s+', '', locality)
            elif re.match(r'\d{4}\s+', address):
                locality = re.sub(r'^\d{4}\s+', '', address)
            html_entries.append({
                'price': price,
                'rooms': rooms,
                'surface_m2': surface,
                'address': address,
                'url': urls[0] if urls else 'https://www.lookmove.ch',
                'source_site': 'lookmove',
                'source': 'email_alert',
                'title': f'Property - {locality}',
            })
    if html_entries:
        return html_entries

    text = email_to_text(msg)
    if not text:
        return []

    lower_text = text.lower()
    summary_markers = [
        'newly added properties match your search',
        'following properties correspond to your search',
        'you have new alerts',
        'manage notifications',
        'property suggestions',
        'tailored properties based on your property preferences',
        'the lookmove team',
        'support:',
        'linkedin:',
        'facebook:',
    ]
    if any(token in lower_text for token in summary_markers):
        if not find_urls(text, ('lookmove.ch', 'email.support.lookmove.ch')):
            return []

    urls = find_urls(text, ('lookmove.ch', 'email.support.lookmove.ch'))
    default_url = urls[0] if urls else 'https://www.lookmove.ch'
    entries: list[dict] = []

    for block in _extract_lookmove_blocks(text):
        if _is_summary_block(block):
            continue
        price = extract_price(block)
        rooms = extract_rooms(block)
        surface = extract_surface(block)
        address = extract_address(block)
        if not address:
            # Keep only real postcode/locality-based property addresses; reject summary cards.
            if not re.search(r'\b\d{4}\b', block):
                continue
            address = re.search(r'\b\d{4}\s+[A-Za-zÀ-ÖØ-öø-ÿ][^\n]*', block)
            if address:
                address = address.group(0).strip()
            else:
                continue
        if price is None and rooms is None and surface is None:
            continue
        listing_urls = find_urls(block, ('lookmove.ch', 'email.support.lookmove.ch'))
        entries.append({
            'price': price,
            'rooms': rooms,
            'surface_m2': surface,
            'address': address,
            'url': listing_urls[0] if listing_urls else default_url,
            'source_site': 'lookmove',
            'source': 'email_alert',
            'title': address or 'Lookmove listing',
        })

    if not entries:
        lower_text = text.lower()
        if any(token in lower_text for token in summary_markers):
            return []
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
        if fallback['address'] is not None or fallback['price'] is not None or fallback['rooms'] is not None or fallback['surface_m2'] is not None:
            if fallback['address'] is not None:
                entries.append(fallback)

    return entries


__all__ = ['parse_email']
