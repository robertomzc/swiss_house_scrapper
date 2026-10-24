from __future__ import annotations

import imaplib
import email
from email import policy
from typing import List


def fetch_unread_messages(host: str, username: str, password: str, label: str) -> List[email.message.EmailMessage]:
    """Connect to IMAP host and fetch messages in `label`.

    Uses ALL messages so the initial alert set can be ingested even if the label
    contains already-read notifications. Existing code only processed UNSEEN.
    """
    M = imaplib.IMAP4_SSL(host)
    M.login(username, password)
    # Select the mailbox (label). Gmail exposes labels as folders.
    typ, data = M.select(f'"{label}"' if ' ' in label else label, readonly=False)
    if typ != 'OK':
        # try without quoting
        typ, data = M.select(label, readonly=False)
    messages = []
    typ, data = M.search(None, 'ALL')
    if typ != 'OK':
        M.logout()
        return []
    for num in data[0].split():
        typ, msg_data = M.fetch(num, '(RFC822)')
        if typ != 'OK':
            continue
        raw = msg_data[0][1]
        msg = email.message_from_bytes(raw, policy=policy.default)
        messages.append(msg)
    M.logout()
    return messages
