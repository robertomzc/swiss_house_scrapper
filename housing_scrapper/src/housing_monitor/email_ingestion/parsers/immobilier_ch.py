from __future__ import annotations

from email.message import EmailMessage

from .common import email_to_text, extract_address, find_urls, parse_generic_listing, split_listing_blocks


def parse_email(msg: EmailMessage) -> list[dict]:
    text = email_to_text(msg)
    if not text:
        return []

    hosts = ('immobilier.ch', 'brevo.immobilier.ch')
    urls = find_urls(text, hosts)
    default_url = urls[0] if urls else 'https://www.immobilier.ch'
    blocks = split_listing_blocks(text, hosts)
    entries: list[dict] = []

    for block in blocks:
        lower = block.lower()
        if 'body{' in lower or 'html' in lower or 'nouvelles images' in lower:
            continue
        if not any(token in lower for token in ['chf', 'rooms', 'pièces', 'zimmer', 'm²', 'm2', 'surface', 'appartement', 'maison', 'villa', 'terrain']):
            continue
        address = extract_address(block)
        if not address:
            continue
        block_urls = find_urls(block, hosts)
        parsed = parse_generic_listing(block, block_urls[0] if block_urls else default_url, 'immobilier', hosts)
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

    return entries


__all__ = ['parse_email']
