import json
from collections import Counter
from email import policy
from email.parser import BytesParser
from pathlib import Path

import pytest

from housing_monitor.email_ingestion.parsers import parse_email
from housing_monitor.email_ingestion.parsers.common import extract_address, extract_price


TRAINING_SET = Path(__file__).parents[1] / 'data' / 'email_training_set'
EMAIL_SAMPLES = sorted(TRAINING_SET.glob('*/*.eml'))


def test_training_set_contains_email_samples():
    assert EMAIL_SAMPLES


@pytest.mark.parametrize('email_path', EMAIL_SAMPLES, ids=lambda path: path.name)
def test_training_email_parses_using_expected_source(email_path):
    expected_path = email_path.with_suffix('.expected.json')
    assert expected_path.is_file(), f'Missing expected output for {email_path.name}'

    expected = json.loads(expected_path.read_text(encoding='utf-8'))
    assert expected, f'Expected output is empty for {email_path.name}'
    expected_sources = {listing['source_site'] for listing in expected}

    message = BytesParser(policy=policy.default).parsebytes(email_path.read_bytes())
    parsed = parse_email(message)

    assert parsed, f'No listings parsed from {email_path.name}'
    assert {listing['source_site'] for listing in parsed} == expected_sources


@pytest.mark.parametrize('email_path', EMAIL_SAMPLES, ids=lambda path: path.name)
def test_training_listing_count_and_numeric_fields_match_expected(email_path):
    expected = json.loads(
        email_path.with_suffix('.expected.json').read_text(encoding='utf-8')
    )
    message = BytesParser(policy=policy.default).parsebytes(email_path.read_bytes())
    parsed = parse_email(message)

    expected_signatures = Counter(
        (
            listing.get('rooms'),
            listing.get('surface_m2'),
            (listing.get('observations') or [{}])[-1].get('price'),
            listing.get('address'),
            listing.get('title'),
        )
        for listing in expected
    )
    actual_signatures = Counter(
        (
            listing.get('rooms'),
            listing.get('surface_m2'),
            listing.get('price'),
            listing.get('address'),
            listing.get('title'),
        )
        for listing in parsed
    )

    assert len(parsed) == len(expected)
    assert actual_signatures == expected_signatures


@pytest.mark.parametrize(
    ('price_text', 'expected_price'),
    [
        ('CHF 960,000', 960000),
        ('CHF 1,190,000.–', 1190000),
        ('CHF 1’190’000', 1190000),
        ('CHF 850,000.–', 850000),
        ('CHF 800 000', 800000),
        ('CHF 800\u202f000', 800000),
    ],
)
def test_training_price_formats_parse_as_chf_integers(price_text, expected_price):
    assert extract_price(price_text) == expected_price


def test_address_extraction_drops_trailing_rooms_from_postcode_location():
    assert extract_address('1003 Lausanne 4.5') == '1003 Lausanne'


@pytest.mark.parametrize(
    ('sample', 'price', 'surface', 'expected_title'),
    [
        (
            'immobilier/immobilier_001.eml',
            1190000,
            117,
            'Appartement 4.5 pièces - Denges',
        ),
        (
            'immoscout24/immoscout24_001.eml',
            850000,
            112,
            '4.5 rooms - Vufflens-la-Ville',
        ),
        (
            'immoscout24/immoscout24_001.eml',
            970000,
            121,
            '4.5 rooms - Poliez-Pittet',
        ),
        (
            'poperstar/poperstar_001.eml',
            1060000,
            None,
            'COUP DE COEUR ATTIQUE NEUF AVEC GRANDE TERRASSE',
        ),
        (
            'poperstar/poperstar_001.eml',
            995000,
            None,
            'COUP DE CŒUR NOUVEAU QUARTIER ÉCOLOGIQUE DANS UN ECRIN DE VERDURE',
        ),
    ],
)
def test_training_listing_titles_are_extracted_without_layout_noise(
    sample, price, surface, expected_title
):
    email_path = TRAINING_SET / sample
    message = BytesParser(policy=policy.default).parsebytes(email_path.read_bytes())
    parsed = parse_email(message)

    matches = [
        listing
        for listing in parsed
        if listing.get('price') == price and listing.get('surface_m2') == surface
    ]
    assert len(matches) == 1
    assert matches[0]['title'] == expected_title


def test_properstar_district_address_does_not_include_listing_title():
    email_path = TRAINING_SET / 'poperstar' / 'poperstar_001.eml'
    message = BytesParser(policy=policy.default).parsebytes(email_path.read_bytes())
    parsed = parse_email(message)

    district_listings = [
        listing
        for listing in parsed
        if listing.get('price') in (1060000, 995000)
    ]
    assert len(district_listings) == 2
    assert {listing['address'] for listing in district_listings} == {
        'Lausanne (district)'
    }
