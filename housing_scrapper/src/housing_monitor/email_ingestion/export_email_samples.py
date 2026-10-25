from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from housing_monitor.email_ingestion.archives import save_email_message
from housing_monitor.email_ingestion.imap_client import fetch_messages
from housing_monitor.email_ingestion.parsers.common import detect_source_site


def _safe_name(value: str) -> str:
    cleaned = re.sub(r'[^a-zA-Z0-9_.-]+', '_', value).strip('_')
    return cleaned[:80] or 'email'


def export_email_samples(label: str, output_dir: str, host: str, username: str, password: str, unread_only: bool) -> dict[str, int]:
    os.makedirs(output_dir, exist_ok=True)
    msgs = fetch_messages(host, username, password, label, unread_only)
    counts: dict[str, int] = {}

    for index, msg in enumerate(msgs):
        source = detect_source_site(msg)
        counts[source] = counts.get(source, 0) + 1
        sender = msg.get('From', 'unknown').replace('@', '_at_')
        subject = msg.get('Subject', 'no_subject')
        filename = f"{index + 1:03d}_{source}_{_safe_name(sender)}_{_safe_name(subject)}.eml"
        save_email_message(msg, output_dir, source_site=source, filename=filename)

    return counts


if __name__ == '__main__':
    import yaml

    cfg_path = os.path.join(os.getcwd(), 'config.yaml')
    cfg = yaml.safe_load(open(cfg_path, 'r', encoding='utf-8')) if os.path.exists(cfg_path) else {}

    label = cfg.get('gmail_label', 'Lausanne Housing')
    output_dir = cfg.get('sample_emails_dir', 'data/sample_emails')
    host = cfg.get('imap_host', 'imap.gmail.com')
    unread_only = cfg.get('fetch_unread_only', True)
    user = os.getenv('EMAIL_USER')
    password = os.getenv('EMAIL_PASSWORD')

    if not user or not password:
        raise SystemExit('Please set EMAIL_USER and EMAIL_PASSWORD before exporting sample emails.')

    counts = export_email_samples(label, output_dir, host, user, password, unread_only)
    print(f'Exported sample emails to {output_dir}')
    for source, total in sorted(counts.items()):
        print(f'  {source}: {total}')
