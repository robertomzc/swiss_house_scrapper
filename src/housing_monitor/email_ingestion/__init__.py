"""Email-based property ingestion package."""

from .imap_client import fetch_messages
from .parsers import parse_email

__all__ = ["fetch_messages", "parse_email"]
