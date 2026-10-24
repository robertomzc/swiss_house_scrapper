from __future__ import annotations

import re
from email.message import EmailMessage
from html import unescape
from typing import Optional

URL_RE = re.compile(r'https?://[^\s<>"\']+', re.IGNORECASE)
PRICE_RE = re.compile(r'(?:CHF|Fr\.?|€)\s*([\d\s\.",\']+)', re.IGNORECASE)
ROOMS_RE = re.compile(r'(\d+(?:[.,]\d+)?)\s*(?:Zimmer|rooms?|room|chambres?)', re.IGNORECASE)
SURFACE_RE = re.compile(r'(\d+(?:[.,]\d+)?)\s*(?:m²|m2|sqm|square\s*meters|surface|superficie)', re.IGNORECASE)
ADDRESS_RE = re.compile(r'\b\d{4}\s+[A-Za-zÀ-ÖØ-öø-ÿ][^\n]*\b')

HOST_ALIASES = {
    'immoscout24.ch': 'immoscout24',
    'immobilier.ch': 'immobilier',
    'lookmove.ch': 'lookmove',
    'comparis.ch': 'comparis',
    'newhome.ch': 'newhome',
    'poperstar.ch': 'poperstar',
    'poperstar': 'poperstar',
    'properstar.com': 'poperstar',
    'properstar': 'poperstar',
}


def normalize_number(value: str) -> float:
    s = value.strip().replace("'", "").replace("’", "").replace("\u202f", "").replace("\u00a0", "")
    s = s.replace(" ", "")
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


def email_to_text(msg: EmailMessage) -> str:
    if msg.is_multipart():
        parts = []
        for part in msg.walk():
            if part.get_content_type() in {'text/plain', 'text/html'}:
                payload = part.get_payload(decode=True)
                if payload is None:
                    payload = part.get_payload()
                if isinstance(payload, bytes):
                    charset = part.get_content_charset() or 'utf-8'
                    parts.append(payload.decode(charset, errors='ignore'))
                elif isinstance(payload, str):
                    parts.append(payload)
        body = '\n'.join(parts)
    else:
        payload = msg.get_payload(decode=True)
        if isinstance(payload, bytes):
            body = payload.decode(msg.get_content_charset() or 'utf-8', errors='ignore')
        else:
            body = str(payload or '')
    body = body.replace('\r\n', '\n').replace('\r', '\n')
    body = re.sub(r'<br\s*/?>', '\n', body, flags=re.I)
    body = re.sub(r'</p>|</div>|</li>|</tr>', '\n', body, flags=re.I)
    body = re.sub(r'<[^>]+>', ' ', body)
    body = unescape(body)
    body = re.sub(r'[ \t]+', ' ', body)
    body = re.sub(r'\n{3,}', '\n\n', body)
    return body.strip()


def find_urls(text: str, allowed_hosts: tuple[str, ...] = ()) -> list[str]:
    urls: list[str] = []
    for raw in URL_RE.findall(text):
        cleaned = raw.rstrip(').,;')
        lower = cleaned.lower()
        if not cleaned:
            continue
        if allowed_hosts and not any(host in lower for host in allowed_hosts):
            continue
        if any(token in lower for token in ['unsubscribe', 'cancel', 'search-alerts', 'privacy', 'newsletter']):
            continue
        if 'sendgrid.net' in lower:
            continue
        urls.append(cleaned)
    return urls


def extract_price(text: str) -> Optional[int]:
    match = PRICE_RE.search(text)
    if not match:
        return None
    value = normalize_number(match.group(1))
    return int(value) if value else None


def extract_rooms(text: str) -> Optional[float]:
    match = ROOMS_RE.search(text)
    if not match:
        return None
    return float(match.group(1).replace(',', '.'))


def extract_surface(text: str) -> Optional[float]:
    match = SURFACE_RE.search(text)
    if not match:
        return None
    return float(match.group(1).replace(',', '.'))


def _is_noise_address(line: str) -> bool:
    lowered = line.lower()
    if not line or len(line) > 160:
        return True
    if any(token in lowered for token in ['@media', '#outlook', 'webkit-text-size-adjust', 'background-color', 'padding:', 'font-family', 'body {', 'search subscription', 'selling price', 'all results', 'delete search subscription', 'extend search subscription', 'manage notifications', 'lookmove team', 'support:', 'linkedin:', 'facebook:', 'list unsubscribe', 'this is an automatically generated e-mail']):
        return True
    if lowered.startswith(('http://', 'https://', 'mailto:', 'www.', 'new results in your search subscription')):
        return True
    if re.search(r'\b(?:body|img|table|td|tr|div|span|p|a)\b', lowered):
        return True
    return False


def extract_address(text: str) -> Optional[str]:
    if not text:
        return None
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines:
        cleaned = line.strip(',:;')
        if _is_noise_address(cleaned):
            continue
        if re.search(r'\b\d{4}\b', cleaned) and re.search(r'[A-Za-zÀ-ÖØ-öø-ÿ]', cleaned):
            return cleaned
        if re.search(r'\b[A-Za-zÀ-ÖØ-öø-ÿ]+\s+\d{1,5}\b', cleaned) and not re.search(r'\b(?:new results|search subscription|selling price|all results)\b', cleaned, re.I):
            return cleaned
    return None


def detect_source_site(msg: EmailMessage) -> str:
    source_text = f"{msg.get('From', '')} {msg.get('Subject', '')} {email_to_text(msg)}".lower()
    for host, site_name in HOST_ALIASES.items():
        if host in source_text:
            return site_name
    if 'properstar' in source_text:
        return 'poperstar'
    return 'immoscout24'


def parse_generic_listing(text: str, default_url: str, source_site: str) -> list[dict]:
    price = extract_price(text)
    rooms = extract_rooms(text)
    surface = extract_surface(text)
    address = extract_address(text)

    if price is None and rooms is None and surface is None and address is None:
        return []

    return [{
        'price': price,
        'rooms': rooms,
        'surface_m2': surface,
        'address': address,
        'url': default_url,
        'source_site': source_site,
        'source': 'email_alert',
        'title': address or f'{source_site.title()} listing',
    }]
