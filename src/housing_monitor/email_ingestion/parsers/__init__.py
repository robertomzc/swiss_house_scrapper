"""Parsers for inbound listing email alerts."""

import re

from .comparis import parse_email as parse_comparis_email
from .common import (
    email_html_soups,
    extract_address,
    extract_price,
    extract_rooms,
    extract_surface,
    find_urls,
)
from .immoscout24 import parse_email as parse_immoscout_email
from .lookmove import parse_email as parse_lookmove_email
from .newhome import parse_email as parse_newhome_email
from .properstar import parse_email as parse_properstar_email

# Keep the legacy site name working explicitly for immobilien emails.
from .properstar import parse_email as _properstar_alias


def _parse_immobilier_html(msg):
    entries = []
    seen = set()
    hosts = ('immobilier.ch', 'brevo.immobilier.ch')

    for soup in email_html_soups(msg):
        card_tables = []
        for table in soup.find_all('table'):
            text = ' '.join(table.stripped_strings)
            if not all(token in text.lower() for token in ('chf', 'm²', 'pièce')):
                continue
            card_tables.append((table, text))

        for table, text in card_tables:
            if any(
                descendant in [candidate for candidate, _ in card_tables]
                for descendant in table.find_all('table')
            ):
                continue

            address = extract_address(text)
            if not address:
                location_match = re.search(
                    r'pi[eè]ces?\s+(.+?)\s+\d+(?:[.,]\d+)?\s*m²',
                    text,
                    re.I,
                )
                if location_match:
                    address = extract_address(location_match.group(1).strip())
                    if not address:
                        address = location_match.group(1).strip()
            price = extract_price(text)
            rooms = extract_rooms(text)
            surface = extract_surface(text)
            if not address or price is None:
                continue

            normalized = ' '.join(text.lower().split())
            if normalized in seen:
                continue
            seen.add(normalized)
            urls = [
                anchor.get('href', '')
                for anchor in table.find_all('a', href=True)
                if any(host in anchor['href'].lower() for host in hosts)
            ]
            location = address.split(',', 1)[0].strip()
            title = f"Appartement {rooms:g} pièces - {location}" if rooms is not None else location
            entries.append({
                'price': price,
                'rooms': rooms,
                'surface_m2': surface,
                'address': address,
                'url': urls[0] if urls else 'https://www.immobilier.ch',
                'source_site': 'immobilier',
                'source': 'email_alert',
                'title': title,
            })

    return entries


def parse_immobilier_email(msg):
    """Immobilier.ch alerts are parsed as a dedicated source, not as Properstar."""
    from .common import detect_source_site

    source = detect_source_site(msg)
    if source != 'immobilier':
        return _properstar_alias(msg)
    from .common import email_to_text, parse_generic_listing, split_listing_blocks

    html_entries = _parse_immobilier_html(msg)
    if html_entries:
        return html_entries

    text = email_to_text(msg)
    if not text:
        return []
    hosts = ('immobilier.ch', 'brevo.immobilier.ch')
    urls = find_urls(text, hosts)
    default_url = urls[0] if urls else 'https://www.immobilier.ch'
    blocks = split_listing_blocks(text, hosts)
    entries = []
    for block in blocks:
        lower = block.lower()
        if 'body{' in lower or 'html' in lower or 'nouvelles images' in lower:
            continue
        if any(token in lower for token in ['new listings', 'new properties', 'property suggestions', 'manage notifications', 'see more']):
            if not any(token in lower for token in ['chf', 'rooms', 'pièces', 'zimmer', 'm²', 'm2', 'surface', 'appartement', 'maison', 'villa', 'terrain', 'nouveau quartier', 'route du lac', 'avenue', 'lausanne', 'prilly', 'denges']):
                continue
        if not any(token in lower for token in ['chf', 'rooms', 'pièces', 'zimmer', 'm²', 'm2', 'surface', 'appartement', 'maison', 'villa', 'terrain', 'lausanne', 'prilly', 'denges']):
            continue
        address = extract_address(block)
        if not address:
            continue
        parsed = parse_generic_listing(block, (find_urls(block, hosts) or [default_url])[0], 'immobilier', hosts)
        for entry in parsed:
            entry['source_site'] = 'immobilier'
            entry['title'] = entry.get('address') or 'immobilier.ch listing'
            entries.append(entry)
    if not entries:
        lowered = text.lower()
        if any(token in lowered for token in ['new listings', 'new properties', 'property suggestions', 'manage notifications', 'see more']):
            return []
        fallback = parse_generic_listing(text, default_url, 'immobilier', hosts)
        for entry in fallback:
            entry['source_site'] = 'immobilier'
            entry['title'] = entry.get('address') or 'immobilier.ch listing'
        return fallback
    # Ignore generic summary addresses that look like outbound contact info instead of a property.
    entries = [entry for entry in entries if entry.get('address') and not any(token in (entry.get('address') or '').lower() for token in ['se désinscrire', 'contactez l\'agence', 'properstar.com', 'contact', 'unsubscribe'])]
    return entries


PARSER_MAP = {
    'immoscout24': parse_immoscout_email,
    'immobilier': parse_immobilier_email,
    'lookmove': parse_lookmove_email,
    'comparis': parse_comparis_email,
    'newhome': parse_newhome_email,
    'properstar': parse_properstar_email,
}


def parse_email(msg):
    """Parse a message using the site-specific parser corresponding to the sender/domain."""
    from .common import detect_source_site

    source = detect_source_site(msg)
    parser = PARSER_MAP.get(source, parse_immoscout_email)
    return parser(msg)


__all__ = [
    'parse_email',
    'PARSER_MAP',
    'parse_immoscout_email',
    'parse_immobilier_email',
    'parse_lookmove_email',
    'parse_comparis_email',
    'parse_newhome_email',
    'parse_properstar_email',
]
