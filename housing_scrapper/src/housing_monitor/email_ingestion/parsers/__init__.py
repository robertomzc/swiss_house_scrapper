"""Parsers for inbound listing email alerts."""

from .comparis import parse_email as parse_comparis_email
from .immobilier_ch import parse_email as parse_immobilier_email
from .immoscout24 import parse_email as parse_immoscout_email
from .lookmove import parse_email as parse_lookmove_email
from .newhome import parse_email as parse_newhome_email
from .poperstar import parse_email as parse_poperstar_email

PARSER_MAP = {
    'immoscout24': parse_immoscout_email,
    'immobilier': parse_immobilier_email,
    'lookmove': parse_lookmove_email,
    'comparis': parse_comparis_email,
    'newhome': parse_newhome_email,
    'poperstar': parse_poperstar_email,
}


def parse_email(msg):
    """Parse a message using the site-specific parser corresponding to the sender/domain."""
    from .common import detect_source_site

    source = detect_source_site(msg)
    parser = PARSER_MAP.get(source, parse_immoscout_email)
    return parser(msg)


__all__ = [
    'parse_email',
    'PARSER_MAP',
    'parse_immoscout_email',
    'parse_immobilier_email',
    'parse_lookmove_email',
    'parse_comparis_email',
    'parse_newhome_email',
    'parse_poperstar_email',
]
