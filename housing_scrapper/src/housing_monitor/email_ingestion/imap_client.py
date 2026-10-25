from __future__ import annotations

import email
import imaplib
from email import policy
from typing import List


def fetch_messages(host: str, username: str, password: str, label: str, unread_only: bool) -> List[email.message.EmailMessage]:
    """Connect to an IMAP host and return messages from the configured label."""
    mailbox = imaplib.IMAP4_SSL(host)
    mailbox.login(username, password)

    try:
        target = f'"{label}"' if ' ' in label else label
        typ, _ = mailbox.select(target, readonly=True)
        if typ != 'OK':
            typ, _ = mailbox.select(label, readonly=True)
        if typ != 'OK':
            mailbox.logout()
            return []

        search_criteria = 'UNSEEN' if unread_only else 'ALL'
        typ, data = mailbox.search(None, search_criteria)
        if typ != 'OK':
            return []

        messages: List[email.message.EmailMessage] = []
        for num in data[0].split():
            typ, msg_data = mailbox.fetch(num, '(RFC822)')
            if typ != 'OK':
                continue
            raw = msg_data[0][1]
            messages.append(email.message_from_bytes(raw, policy=policy.default))
        return messages
    finally:
        try:
            mailbox.logout()
        except Exception:
            pass
