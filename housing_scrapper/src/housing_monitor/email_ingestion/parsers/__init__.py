"""Parsers for inbound listing email alerts."""

from .immoscout24 import parse_email

__all__ = ["parse_email"]
