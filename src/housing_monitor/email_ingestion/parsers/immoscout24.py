from __future__ import annotations

import re
from email.message import EmailMessage
from html import unescape
from typing import Optional
from urllib.parse import unquote, urlsplit
from urllib.request import Request, urlopen

from .common import email_to_text, extract_address, extract_price, extract_rooms, extract_surface, find_urls, split_listing_blocks

URL_RE = re.compile(r'https?://[^\s<>"\']+', re.IGNORECASE)
PRICE_RE = re.compile(r'CHF\s*([\d\s\.",\']+)', re.IGNORECASE)
ROOMS_RE = re.compile(r'(\d+(?:[.,]\d+)?)\s*(?:Zimmer|rooms|room)', re.IGNORECASE)
SURFACE_RE = re.compile(r'(\d+(?:[.,]\d+)?)\s*(?:m²|m2|sqm|square\s*meters|surface)', re.IGNORECASE)
ADDRESS_RE = re.compile(r'^(?:[A-Za-zÀ-ÖØ-öø-ÿ][^\n]*?,\s*\d{4}\s+[A-Za-zÀ-ÖØ-öø-ÿ][^\n]*|\d{4}\s+[A-Za-zÀ-ÖØ-öø-ÿ][^\n]*)$')
BLOCK_STOP_TOKENS = (
    'search criteria',
    'delete search alert',
    'unsubscribe',
    'municipality guide',
    'order free of charge now:',
    'looking for a new tenant?',
    'what is the population of lausanne?',
)


def _normalize_number(value: str) -> float:
    s = value.strip()
    s = s.replace("'", "").replace(" ", "")
    s = s.replace('CHF', '').replace('Fr', '').replace('–', '').replace('€', '')
    if not s:
        return 0.0
    if ',' in s and '.' in s:
        if s.rfind(',') > s.rfind('.'):
            s = s.replace('.', '').replace(',', '.')
        else:
            s = s.replace(',', '')
    elif ',' in s:
        if s.count(',') > 1:
            s = s.replace(',', '')
        else:
            s = s.replace(',', '.')
    elif '.' in s and s.count('.') > 1:
        s = s.replace('.', '')
    try:
        return float(s)
    except ValueError:
        cleaned = re.sub(r'[^0-9.]', '', s)
        return float(cleaned) if cleaned else 0.0


def _strip_html(raw: str) -> str:
    if not raw:
        return ""
    raw = raw.replace('\r\n', '\n').replace('\r', '\n')
    raw = re.sub(r'<br\s*/?>', '\n', raw, flags=re.I)
    raw = re.sub(r'</p>|</div>|</li>|</tr>', '\n', raw, flags=re.I)
    raw = re.sub(r'<[^>]+>', ' ', raw)
    raw = unescape(raw)
    raw = re.sub(r'[ \t]+', ' ', raw)
    raw = re.sub(r'\n{3,}', '\n\n', raw)
    return raw.strip()


def _canonicalize_immoscout_url(raw_url: str) -> str:
    if not raw_url:
        return ""
    if _is_direct_listing_url(raw_url):
        return raw_url
    if 'sendgrid.net' in raw_url.lower():
        try:
            req = Request(raw_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urlopen(req, timeout=15) as resp:
                final_url = resp.geturl()
                if _is_direct_listing_url(final_url):
                    return final_url
        except Exception:
            pass
    return raw_url


def _is_direct_listing_url(url: str) -> bool:
    parts = urlsplit(url)
    hostname = (parts.hostname or '').lower()
    if hostname != 'immoscout24.ch' and not hostname.endswith('.immoscout24.ch'):
        return False
    return re.match(r'^/(?:buy|rent)/\d+(?:/|$)', parts.path, re.IGNORECASE) is not None


def _is_footer_line(line: str) -> bool:
    lowered = line.lower()
    if any(token in lowered for token in BLOCK_STOP_TOKENS):
        return True
    return 'http' in lowered and ('unsubscribe' in lowered or 'cancel' in lowered or 'search-alerts' in lowered)


def _prefer_better_address(candidates: list[str]) -> Optional[str]:
    if not candidates:
        return None
    preferred = sorted(
        candidates,
        key=lambda value: (
            0 if re.search(r',\s*\d{4}\s+[A-Za-zÀ-ÖØ-öø-ÿ]', value) else 1,
            0 if re.search(r'\d{4}\s+[A-Za-zÀ-ÖØ-öø-ÿ]', value) else 1,
            len(value),
        ),
    )
    return preferred[0]


def _extract_tracking_urls(text: str) -> list[str]:
    urls = []
    for candidate in URL_RE.findall(text):
        lower = candidate.lower()
        if any(token in lower for token in ['search-alerts', 'municipality-guide', 'unsubscribe', 'cancel?']):
            continue
        if 'sendgrid.net' in lower or 'immoscout24.ch' in lower:
            urls.append(candidate.rstrip(')'))
    return urls


def _clean_address(line: str) -> str:
    cleaned = line.strip().strip(',:;')
    cleaned = re.sub(r'\s+', ' ', cleaned)
    if cleaned.lower().startswith(('sale -', 'here are', 'here is')):
        return ""
    if any(token in cleaned.lower() for token in ['search criteria', 'municipality guide', 'delete search alert', 'unsubscribe']):
        return ""
    if cleaned.lower().startswith(('https://', 'http://')):
        return ""
    if cleaned.startswith(':'):
        return ""
    return cleaned


def _extract_address_from_text(text: str) -> Optional[str]:
    if not text:
        return None
    candidates: list[str] = []
    for line in text.splitlines():
        candidate = line.strip()
        if not candidate:
            continue
        lowered = candidate.lower()
        if lowered.startswith(('sale -', 'here are', 'here is', 'search criteria', 'municipality guide', 'delete search alert', 'unsubscribe', 'order free of charge now', 'looking for a new tenant?', 'what is the population of')):
            continue
        if lowered.startswith('contact the advertiser'):
            continue
        if 'http' in lowered:
            continue
        if 'CHF' in candidate or 'rooms' in lowered or 'm2' in lowered or 'room' in lowered:
            continue
        if ADDRESS_RE.match(candidate):
            candidates.append(candidate)
    return _prefer_better_address(candidates)


def _extract_values_for_block(block: str) -> dict:
    price = None
    rooms = None
    surface = None
    address = _extract_address_from_text(block) or extract_address(block)
    match = PRICE_RE.search(block)
    if match:
        raw = match.group(1)
        price = int(float(_normalize_number(raw)))

    room_match = ROOMS_RE.search(block)
    if room_match:
        rooms = float(room_match.group(1).replace(',', '.'))

    surface_match = SURFACE_RE.search(block)
    if surface_match:
        surface = float(surface_match.group(1).replace(',', '.'))

    if not address:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        found: list[str] = []
        for line in reversed(lines):
            cleaned = _clean_address(line)
            if cleaned and 'CHF' not in cleaned and 'rooms' not in cleaned.lower() and 'm2' not in cleaned.lower():
                if ADDRESS_RE.match(cleaned) or re.search(r',\s*\d{4}\s+[A-Za-zÀ-ÖØ-öø-ÿ]', cleaned):
                    found.append(cleaned)
        if not found:
            for line in lines:
                cleaned = _clean_address(line)
                if cleaned and 'sale -' not in cleaned.lower() and 'CHF' not in cleaned and 'rooms' not in cleaned.lower() and 'm2' not in cleaned.lower():
                    if ADDRESS_RE.match(cleaned) or re.search(r',\s*\d{4}\s+[A-Za-zÀ-ÖØ-öø-ÿ]', cleaned):
                        found.append(cleaned)
        address = _prefer_better_address(found)

    return {'price': price, 'rooms': rooms, 'surface_m2': surface, 'address': address}


def _listing_title(result: dict) -> str:
    address = result.get('address') or ''
    locality_match = re.search(r'\b\d{4}\s+(.+)$', address)
    if result.get('rooms') is not None and locality_match:
        return f"{result['rooms']:g} rooms - {locality_match.group(1).strip()}"
    return address or 'ImmoScout24 listing'


def _parse_property_blocks(text: str) -> list[dict]:
    blocks = split_listing_blocks(text, ('immoscout24.ch', 'tracking.notification.immoscout24.ch'))
    parsed = []
    for block in blocks:
        lowered = block.lower()
        has_property_data = any(token in lowered for token in ['chf', 'm2', 'rooms', 'room', 'appartement', 'maison', 'villa', 'studio'])
        if 'search criteria' in lowered and not has_property_data:
            continue
        if 'here are' in lowered and not has_property_data:
            continue
        if 'delete search alert' in lowered and not has_property_data:
            continue
        if 'unsubscribe' in lowered and not has_property_data:
            continue
        item = _extract_values_for_block(block)
        if item['price'] is None and item['rooms'] is None and item['surface_m2'] is None and item['address'] is None:
            if 'room' not in lowered and 'm2' not in lowered and 'chf' not in lowered and 'price' not in lowered:
                continue
        parsed.append(item)
    return parsed


def _extract_listing_urls(text: str) -> list[str]:
    urls: list[str] = []
    for raw_url in _extract_tracking_urls(text):
        resolved = _canonicalize_immoscout_url(raw_url)
        if _is_direct_listing_url(resolved):
            urls.append(resolved)
            continue

        nested_listing = re.search(
            r'https?://(?:www\.)?immoscout24\.ch/(?:buy|rent)/\d+',
            unquote(resolved),
            re.IGNORECASE,
        )
        if nested_listing:
            urls.append(nested_listing.group(0))
    return urls


def parse_email(msg: EmailMessage) -> list[dict]:
    text = _strip_html(email_to_text(msg))
    if not text:
        return []

    urls = _extract_listing_urls(text)
    parsed_blocks = _parse_property_blocks(text)
    if not parsed_blocks:
        return []

    entries: list[dict] = []
    for result in parsed_blocks:
        if result['price'] is None and result['surface_m2'] is None and result['address'] is None:
            continue
        index = len(entries)
        result['url'] = urls[index] if index < len(urls) else (urls[0] if urls else 'https://www.immoscout24.ch')
        result['source_site'] = 'immoscout24'
        result['source'] = 'email_alert'
        result['title'] = _listing_title(result)
        entries.append(result)

    return entries


__all__ = ['parse_email', 'ImmoScout24EmailParser']


class ImmoScout24EmailParser:
    def parse(self, msg: EmailMessage) -> list[dict]:
        return parse_email(msg)
