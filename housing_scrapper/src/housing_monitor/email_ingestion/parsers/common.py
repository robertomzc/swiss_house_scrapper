from __future__ import annotations

import re
from email.message import EmailMessage
from html import unescape
from typing import Optional

URL_RE = re.compile(r'https?://[^\s<>"\']+', re.IGNORECASE)
PRICE_RE = re.compile(r'(?:CHF|Fr\.?|€)\s*((?:\d{1,3}(?:[\s.,\'’\u202f]\d{3})+|\d{4,})(?:[.,]\d{1,2})?)', re.IGNORECASE)
ROOMS_RE = re.compile(r'(\d+(?:[.,]\d+)?)\s*(?:Zimmer|rooms?|room|chambres?|pi(?:[èée]|c)?ces?)', re.IGNORECASE)
SURFACE_RE = re.compile(r'(\d+(?:[.,]\d+)?)\s*(?:m(?:\s*[²2])|m2|m²|sqm|square\s*meters|surface|superficie)', re.IGNORECASE)
ADDRESS_RE = re.compile(r'\b\d{4}\s+[A-Za-zÀ-ÖØ-öø-ÿ][^\n]*\b')
ADDRESS_PATH_RE = re.compile(r'(?i)(?:\b\d{4}\s+[A-Za-zÀ-ÖØ-öø-ÿ][^\n]*|(?:[A-Za-zÀ-ÖØ-öø-ÿ][^\n]*?(?:avenue|rue|route|chemin|boulevard|place|square|allée|allee|impasse|quai|voie|street|road)[^\n]*?(?:\d{1,5}(?:\s*,\s*\d{4})?)))')

HOST_ALIASES = {
    'immoscout24.ch': 'immoscout24',
    'tracking.notification.immoscout24.ch': 'immoscout24',
    'immobilier.ch': 'immobilier',
    'brevo.immobilier.ch': 'immobilier',
    'lookmove.ch': 'lookmove',
    'email.support.lookmove.ch': 'lookmove',
    'comparis.ch': 'comparis',
    'en.comparis.ch': 'comparis',
    'links.comparis.ch': 'comparis',
    'newhome.ch': 'newhome',
    'r.mailing.newhome.ch': 'newhome',
    'poperstar.ch': 'properstar',
    'poperstar.com': 'properstar',
    'properstar.com': 'properstar',
    'properstar.ch': 'properstar',
    'properstar': 'properstar',
    'poperstar': 'properstar',
}


def _decode_quoted_printable(value: str) -> str:
    value = value.replace('\r\n', '\n').replace('\r', '\n')
    value = re.sub(r'=\r?\n', '', value)
    value = re.sub(r'=([A-Fa-f0-9]{2})', lambda m: chr(int(m.group(1), 16)), value)
    return value


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
    body = _decode_quoted_printable(body)
    body = body.replace('\r\n', '\n').replace('\r', '\n')
    body = re.sub(r'<br\s*/?>', '\n', body, flags=re.I)
    body = re.sub(r'</p>|</div>|</li>|</tr>', '\n', body, flags=re.I)
    body = re.sub(
        r'<a\s+[^>]*href=["\']?([^"\'\s>]+)["\']?[^>]*>(.*?)</a>',
        lambda m: f"{m.group(2).strip()} {m.group(1)}" if m.group(2).strip() else m.group(1),
        body,
        flags=re.I | re.S,
    )
    body = re.sub(r'<[^>]+>', ' ', body)
    body = unescape(body)
    body = re.sub(r'[ \t]+', ' ', body)
    body = re.sub(r'\n{3,}', '\n\n', body)
    return body.strip()


def find_urls(text: str, allowed_hosts: tuple[str, ...] = ()) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    for raw in URL_RE.findall(text):
        cleaned = raw.rstrip(').,;')
        lower = cleaned.lower()
        if not cleaned:
            continue

        if 'sendgrid.net' in lower or 'mailto:' in lower:
            continue

        # Keep listing links, but discard subscription/unsubscribe/footer pages.
        if any(token in lower for token in (
            'unsubscribe', 'cancel?', 'privacy', 'newsletter', 'list-unsubscribe',
            'manage search', 'delete search', 'municipality-guide', 'facebook.com',
            'linkedin.com', 'youtube.com', 'instagram.com', 'trustpilot.com',
            'whatsapp.com', 'search-alerts', 'cancel?search', '/default', 'track=',
        )):
            continue

        if allowed_hosts and not any(host in lower for host in allowed_hosts):
            continue

        if not any(marker in lower for marker in ('/listing/', '/buy/', '/dispatcher/go', '/tr/cl/', '/c/en/', '/c/', '/s/c/', '/s/vb/', '/s/eo/', '/s/01/')):
            if 'properstar' in lower or 'immoscout24' in lower or 'comparis' in lower or 'lookmove' in lower or 'newhome' in lower:
                continue

        norm = cleaned.split('?', 1)[0].rstrip('/');
        if norm in seen:
            continue
        seen.add(norm)
        urls.append(cleaned)
    return urls


def split_listing_blocks(text: str, allowed_hosts: tuple[str, ...] = ()) -> list[str]:
    if not text:
        return []
    urls = find_urls(text, allowed_hosts)
    if not urls:
        return [text]

    segments: list[str] = []
    cursor = 0
    for url in urls:
        idx = text.lower().find(url.lower(), cursor)
        if idx == -1:
            continue
        prefix = text[cursor:idx].strip()
        if prefix:
            segments.append(prefix)
        cursor = idx + len(url)

    tail = text[cursor:].strip()
    if tail:
        segments.append(tail)

    blocks: list[str] = []
    seen: set[str] = set()
    for segment in segments:
        cleaned = re.sub(r'\s+', ' ', segment).strip()
        if not cleaned or cleaned.lower() in seen:
            continue
        seen.add(cleaned.lower())
        blocks.append(cleaned)
    return blocks or [text]


def extract_price(text: str) -> Optional[int]:
    if not text:
        return None
    match = PRICE_RE.search(text)
    if not match:
        return None
    value = match.group(1)
    value = re.sub(r'(?i)(?<=\d)[=A-Za-z].*$', '', value)
    value = re.sub(r'[^0-9,\.\'’\u202f\s]', '', value)
    value = re.sub(r'\s+(?:\d{3,5})(?=\s*(?:$|[A-Za-zÀ-ÖØ-öø-ÿ]))', '', value)
    value = re.sub(r'\s*[-–]\s*\d+(?:[.,\s]\d+)?$', '', value)
    value = value.strip()
    if not value:
        return None
    value = normalize_number(value)
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
    if re.search(r'\b(?:body|img|table|td|tr|div|span|p)\b', lowered):
        return True
    if 'contactez l\'agence' in lowered or 'contactez l’agence' in lowered:
        return True
    return False


def _normalize_address_line(line: str) -> str:
    cleaned = line.strip(',:;').strip()
    cleaned = re.sub(r'\s+', ' ', cleaned)
    cleaned = cleaned.replace('’', "'")

    if re.search(r'\b(?:CHF|Fr\.?|€)\b', cleaned, re.I):
        return ''

    lowered = cleaned.lower()
    if 'contactez l\'agence' in lowered or 'contactez l’agence' in lowered:
        cleaned = re.split(r',\s*(?:contactez\s+l(?:\'|’)?agence|contactez\s+l(?:\'|’)?agence\s+pour\s+l(?:\'|’)?adresse)', cleaned, maxsplit=1, flags=re.I)[0]
        cleaned = re.split(r',\s*(?:pour\s+l(?:\'|’)?adresse)', cleaned, maxsplit=1, flags=re.I)[0]
        cleaned = cleaned.strip(' ,;')
        return cleaned

    cleaned = re.sub(r'\s*,\s*(?:contactez.*|pour\s+l(?:\'|’)?adresse.*|adresse.*)$', '', cleaned, flags=re.I)
    cleaned = cleaned.strip(' ,;')
    return cleaned


def _strip_property_suffix(line: str) -> str:
    candidate = line.strip(' ,;')
    if not candidate:
        return candidate

    if re.search(r'\b\d{4}\b', candidate):
        return candidate

    if re.search(r'(?:avenue|rue|route|chemin|boulevard|place|square|allée|allee|impasse|quai|voie|street|road)\b', candidate, re.I):
        if re.search(r'\d{1,5}\s*$', candidate):
            return candidate

    for pattern in [
        r'\s+(?:Appartement|Appart|Maison|Villa|Studio|Duplex|Terrain|Loft|Chambre|Pi(?:è|e)ces?|rooms?|zimmer|salles\s+de\s+bains|bathrooms?|m2|m²|\u00b7|•).*$',
        r'\s*[:\-–]\s*(?:Appartement|Appart|Maison|Villa|Studio|Duplex|Terrain|Loft|Chambre|Pi(?:è|e)ces?|rooms?|zimmer|salles\s+de\s+bains|bathrooms?|m2|m²).*$',
        r'\s+\d+(?:[.,]\d+)?\s*(?:rooms?|room|zimmer|pi(?:[èée]|c)?ces?|m2|m²|m\s*²|surface)\s*$',
    ]:
        cleaned = re.split(pattern, candidate, flags=re.I)[0].strip(' ,;')
        if cleaned and cleaned != candidate:
            return cleaned
    return candidate


def _strip_url_and_trailing_meta(value: str) -> str:
    cleaned = re.sub(r'https?://\S+', ' ', value, flags=re.I)
    cleaned = re.sub(r'\b(?:see\s+details|see\s+more|rooms?|room|price\s+on\s+request|chf|m2|m\s*²)\b.*$', '', cleaned, flags=re.I)
    cleaned = cleaned.replace('–', '-')
    cleaned = re.sub(r'\s+', ' ', cleaned).strip(' ,;:')
    return cleaned


def _address_variants(value: str) -> list[str]:
    variants = [value]
    pattern = r'^(?P<street>[A-Za-zÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ\' .\-]*?)(?:\s+)(?P<number>\d{1,5})(?:\s*,\s*(?P<zip>\d{4}))?\s*$'
    match = re.match(pattern, value, flags=re.I)
    if match:
        street = match.group('street').strip(' ,;:')
        number = match.group('number')
        zip_code = match.group('zip')
        if street and number:
            ordered = f"{number} {street}"
            if zip_code:
                ordered = f"{ordered}, {zip_code}"
            variants.insert(0, ordered)
    return variants


def extract_address(text: str) -> Optional[str]:
    if not text:
        return None

    for match in ADDRESS_PATH_RE.finditer(text):
        candidate = _strip_url_and_trailing_meta(match.group(0))
        candidate = _normalize_address_line(candidate)
        candidate = _strip_property_suffix(candidate)
        if not candidate:
            continue
        for variant in _address_variants(candidate):
            variant = _normalize_address_line(variant)
            variant = _strip_property_suffix(variant)
            if not variant:
                continue
            if _valid_address_candidate(variant):
                return variant

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines:
        candidate = _strip_url_and_trailing_meta(line)
        if not candidate:
            continue
        candidate = re.split(r'(?i)\b(?:rooms?|room|price\s+on\s+request|chf)\b.*$', candidate, maxsplit=1)[0].strip(' ,;:')
        if not candidate:
            continue
        candidate = _normalize_address_line(candidate)
        if not candidate:
            continue
        candidate = _strip_property_suffix(candidate)
        if not candidate:
            continue
        for variant in _address_variants(candidate):
            variant = _normalize_address_line(variant)
            variant = _strip_property_suffix(variant)
            if not variant:
                continue
            if _valid_address_candidate(variant):
                return variant
    return None


def detect_source_site(msg: EmailMessage) -> str:
    source_text = f"{msg.get('From', '')} {msg.get('Subject', '')} {email_to_text(msg)}".lower()
    for host, site_name in HOST_ALIASES.items():
        if host in source_text:
            return site_name
    if 'properstar' in source_text:
        return 'properstar'
    return 'immoscout24'


def _looks_like_property_description(line: str) -> bool:
    lowered = line.lower()
    if re.search(r'\b(?:appartement|maison|villa|studio|duplex|terrain|chambre|loft|flat)\b', lowered):
        return True
    if re.search(r'\b\d+(?:[.,]\d+)?\s*(?:pi(?:[èée]|c)?ces?|rooms?|zimmer|m\s*²|m2|surface)\b', lowered):
        return True
    return False


def parse_generic_listing(text: str, default_url: str, source_site: str, allowed_hosts: tuple[str, ...] = ()) -> list[dict]:
    blocks = split_listing_blocks(text, allowed_hosts or (f'{source_site}.ch',)) if source_site else [text]
    entries: list[dict] = []
    for block in blocks:
        price = extract_price(block)
        rooms = extract_rooms(block)
        surface = extract_surface(block)
        address = extract_address(block)
        if address is None:
            text_has_real_address = bool(re.search(r'\b(?:avenue|rue|route|chemin|boulevard|place|square|allée|allee|impasse|quai|voie|street|road)\b', block, re.I) or re.search(r'\b\d{4}\b', block))
            if not text_has_real_address:
                continue
        if price is None and rooms is None and surface is None and address is None:
            continue
        entries.append({
            'price': price,
            'rooms': rooms,
            'surface_m2': surface,
            'address': address,
            'url': default_url,
            'source_site': source_site,
            'source': 'email_alert',
            'title': address or f'{source_site.title()} listing',
        })
    return entries


def _valid_address_candidate(value: str) -> bool:
    candidate = (value or '').strip(' ,;:')
    if not candidate or len(candidate) > 180:
        return False

    lowered = candidate.lower()
    if any(token in lowered for token in ['alertes pour ta recherche', 'découvre toutes les mises à jour', 'voir toutes les mises à jour', 'property suggestions', 'newly added properties match your search', 'following properties correspond to your search', 'you have new alerts', 'search alert', 'manage notifications', 'all results', 'search criteria', 'se désinscrire', 'properstar.com', 'lookmove team', 'this is an automatically generated e-mail']):
        return False
    if _is_noise_address(candidate):
        return False
    if re.search(r'\b(?:search alert|manage notifications|new results in your search subscription|delete search subscription|unsubscribe|contact|all results|this is an automatically generated e-mail|se désinscrire|properstar\.com|lookmove team)\b', lowered):
        return False
    if candidate.startswith(('http://', 'https://', 'www.', 'mailto:')):
        return False
    if re.fullmatch(r'[\d\s,.;:/\-]+', candidate):
        return False
    if re.search(r'\b(?:CHF|Fr\.?|€)\b', candidate, re.I):
        return False

    has_digit = bool(re.search(r'\d', candidate))
    if not has_digit:
        if re.search(r'\b(?:avenue|rue|route|chemin|boulevard|place|square|allée|allee|impasse|quai|voie|street|road|court|passage)\b', candidate, re.I):
            return False

    has_postal = bool(re.search(r'\b\d{4}\b', candidate))
    has_street = bool(re.search(r'\b(?:avenue|rue|route|chemin|boulevard|place|square|allée|allee|impasse|quai|voie|street|road|court|passage)\b', candidate, re.I))
    has_locality = bool(re.search(r'\b(?:lausanne|geneva|zurich|zürich|yverdon|montreux|nyon|lausanne|prilly|sullens|lutry|bussigny|denges|epalinges|vufflens|poliez|pittet|villy|romanel|vevey|carouge)\b', lowered))

    if has_postal:
        return True
    if has_street and has_digit:
        return True
    if has_locality and len(candidate.split()) <= 6:
        return True
    if re.search(r'^\d{4}\s+[A-Za-zÀ-ÖØ-öø-ÿ]', candidate):
        return True
    if re.search(r'^(?:[A-Za-zÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ\-\'\s]+)\s*\([^)]*\)$', candidate):
        return True
    return False
