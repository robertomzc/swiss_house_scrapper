from __future__ import annotations

from email.message import EmailMessage

from .common import detect_source_site, email_to_text, find_urls, parse_generic_listing


def parse_email(msg: EmailMessage) -> list[dict]:
    text = email_to_text(msg)
    if not text:
        return []
    urls = find_urls(text, ('immobilier.ch',))
    default_url = urls[0] if urls else 'https://www.immobilier.ch'
    entries = parse_generic_listing(text, default_url, 'immobilier')
    for entry in entries:
        entry['source_site'] = 'immobilier'
        entry['title'] = entry.get('address') or 'immobilier.ch listing'
    return entries


__all__ = ['parse_email']
