"""Parsers for inbound listing email alerts."""

from .comparis import parse_email as parse_comparis_email
from .immoscout24 import parse_email as parse_immoscout_email
from .lookmove import parse_email as parse_lookmove_email
from .newhome import parse_email as parse_newhome_email
from .properstar import parse_email as parse_properstar_email

# Keep the legacy site name working explicitly for immobilien emails.
from .properstar import parse_email as _properstar_alias


def parse_immobilier_email(msg):
    """Immobilier.ch alerts are parsed as a dedicated source, not as Properstar."""
    from .common import detect_source_site

    source = detect_source_site(msg)
    if source != 'immobilier':
        return _properstar_alias(msg)
    # The previous module file was removed; keep the source_site stable by using the generic logic.
    from .common import email_to_text, extract_address, extract_price, extract_rooms, extract_surface, find_urls, parse_generic_listing, split_listing_blocks

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
