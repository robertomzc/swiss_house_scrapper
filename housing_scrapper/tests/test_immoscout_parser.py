from email.message import EmailMessage

from my_package.email_poc.ingestion.parsers.immoscout24 import parse_email


def make_email(body: str) -> EmailMessage:
    msg = EmailMessage()
    msg.set_payload(body)
    return msg


def test_parse_email_extracts_address_price_rooms_and_surface():
    body = """Here is a new property that meets your search criteria.

Sale - Lausanne 5km - 1.25M

https://u38864477.ct.sendgrid.net/ls/click?upn=test

A Lausanne, 1005 Lausanne
98 m2
3.5 rooms
CHF 1,190,000.–

Search criteria
"""
    msg = make_email(body)

    entries = parse_email(msg)

    assert len(entries) == 1
    assert entries[0]['address'] == 'A Lausanne, 1005 Lausanne'
    assert entries[0]['price'] == 1190000
    assert entries[0]['rooms'] == 3.5
    assert entries[0]['surface_m2'] == 98.0
    assert entries[0]['source_site'] == 'immoscout24'


def test_parse_email_handles_postal_code_location_format():
    body = """Here are 2 new properties that meet your search criteria.

Sale - Lausanne 5km - 1.25M

https://u38864477.ct.sendgrid.net/ls/click?upn=test

1081 Montpreveyres
77 m2
3.5 rooms
CHF 740,000.–

Delete search alert
"""
    msg = make_email(body)

    entries = parse_email(msg)

    assert len(entries) == 1
    assert entries[0]['address'] == '1081 Montpreveyres'
    assert entries[0]['price'] == 740000
    assert entries[0]['rooms'] == 3.5
    assert entries[0]['surface_m2'] == 77.0
