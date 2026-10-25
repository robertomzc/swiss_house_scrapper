"""Email-based property ingestion package."""

from .imap_client import fetch_unread_messages
from .parsers import parse_email

__all__ = ["fetch_unread_messages", "parse_email"]
