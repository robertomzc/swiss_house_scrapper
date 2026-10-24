"""IMAP ingestion package for email PoC."""

from .imap_client import fetch_unread_messages

__all__ = ["fetch_unread_messages"]
