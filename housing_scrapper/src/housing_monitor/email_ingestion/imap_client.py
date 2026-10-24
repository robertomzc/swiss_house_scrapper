from __future__ import annotations

import email
import imaplib
from email import policy
from typing import List


def fetch_unread_messages(host: str, username: str, password: str, label: str) -> List[email.message.EmailMessage]:
    """Connect to an IMAP host and return all messages in the configured label."""
    mailbox = imaplib.IMAP4_SSL(host)
    mailbox.login(username, password)
    typ, _ = mailbox.select(f'"{label}"' if ' ' in label else label, readonly=False)
    if typ != 'OK':
        typ, _ = mailbox.select(label, readonly=False)

    messages: List[email.message.EmailMessage] = []
    typ, data = mailbox.search(None, 'ALL')
    if typ != 'OK':
        mailbox.logout()
        return []

    for num in data[0].split():
        typ, msg_data = mailbox.fetch(num, '(RFC822)')
        if typ != 'OK':
            continue
        raw = msg_data[0][1]
        messages.append(email.message_from_bytes(raw, policy=policy.default))

    mailbox.logout()
    return messages
