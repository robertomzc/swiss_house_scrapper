from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from email.message import EmailMessage
from typing import Any

from housing_monitor.email_ingestion.parsers.common import detect_source_site

DEFAULT_ARCHIVE_DIR = 'data/artifacts/email_archive'
DEFAULT_PROCESSED_PATH = 'data/artifacts/processed_messages.json'


def message_key(msg: EmailMessage) -> str:
    message_id = msg.get('Message-ID')
    if message_id:
        return message_id.strip()
    payload = msg.as_bytes() if hasattr(msg, 'as_bytes') else str(msg).encode('utf-8')
    return hashlib.sha256(payload).hexdigest()


def safe_site_name(site_name: str | None) -> str:
    candidate = (site_name or 'unknown').strip().lower()
    cleaned = ''.join(ch if ch.isalnum() or ch in {'-', '_'} else '_' for ch in candidate)
    return cleaned or 'unknown'


def save_email_message(msg: EmailMessage, target_dir: str, *, source_site: str | None = None, filename: str | None = None) -> str:
    """Persist a raw email message to disk using a consistent filename strategy."""
    os.makedirs(target_dir, exist_ok=True)
    safe_name = safe_site_name(source_site or detect_source_site(msg))
    chosen_name = filename or f'{message_key(msg)}.eml'
    if not chosen_name.lower().endswith('.eml'):
        chosen_name = f'{chosen_name}.eml'

    target_path = os.path.join(target_dir, chosen_name)
    with open(target_path, 'wb') as handle:
        handle.write(msg.as_bytes())
    return target_path


def load_processed_messages(path: str = DEFAULT_PROCESSED_PATH) -> dict[str, dict[str, Any]]:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, 'r', encoding='utf-8') as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            return data
    except (OSError, ValueError):
        return {}
    return {}


def save_processed_messages(index: dict[str, dict[str, Any]], path: str = DEFAULT_PROCESSED_PATH) -> None:
    directory = os.path.dirname(path) or '.'
    os.makedirs(directory, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as handle:
        json.dump(index, handle, indent=2, sort_keys=True)


def archive_email_message(msg: EmailMessage, archive_dir: str = DEFAULT_ARCHIVE_DIR, source_site: str | None = None) -> str:
    site_name = safe_site_name(source_site or detect_source_site(msg))
    archive_root = os.path.join(archive_dir, site_name)
    return save_email_message(msg, archive_root, source_site=site_name, filename=f'{message_key(msg)}.eml')


def mark_message_processed(msg: EmailMessage, archive_dir: str = DEFAULT_ARCHIVE_DIR, processed_path: str = DEFAULT_PROCESSED_PATH) -> tuple[bool, dict[str, Any]]:
    key = message_key(msg)
    processed = load_processed_messages(processed_path)
    if key in processed:
        return False, processed[key]

    source_site = detect_source_site(msg)
    archive_path = archive_email_message(msg, archive_dir=archive_dir, source_site=source_site)
    processed[key] = {
        'message_id': key,
        'source_site': source_site,
        'archive_path': archive_path,
        'subject': msg.get('Subject'),
        'from': msg.get('From'),
        'date': msg.get('Date'),
        'processed_at': datetime.now(timezone.utc).isoformat(),
    }
    save_processed_messages(processed, processed_path)
    return True, processed[key]
