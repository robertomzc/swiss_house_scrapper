from __future__ import annotations

from email.message import EmailMessage

from .common import email_to_text, find_urls, parse_generic_listing


def parse_email(msg: EmailMessage) -> list[dict]:
    text = email_to_text(msg)
    if not text:
        return []
    urls = find_urls(text, ('poperstar',))
    default_url = urls[0] if urls else 'https://www.poperstar.ch'
    entries = parse_generic_listing(text, default_url, 'poperstar')
    for entry in entries:
        entry['source_site'] = 'poperstar'
        entry['title'] = entry.get('address') or 'Poperstar listing'
    return entries


__all__ = ['parse_email']
