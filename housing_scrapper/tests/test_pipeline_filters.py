from email.message import EmailMessage

import housing_monitor.pipeline as pipeline


def test_listing_entry_filter_accepts_inclusive_boundaries():
    listing_filter = {
        'min_price_chf': 400000,
        'max_price_chf': 1500000,
        'min_rooms': 1,
        'max_rooms': 10,
    }

    assert pipeline._should_keep_listing_entry(
        {'price': 400000, 'rooms': 1, 'surface_m2': None, 'address': None},
        listing_filter,
    )
    assert pipeline._should_keep_listing_entry(
        {'price': 1500000, 'rooms': 10, 'surface_m2': None, 'address': None},
        listing_filter,
    )


def test_listing_entry_filter_rejects_out_of_range_price_or_rooms():
    listing_filter = {
        'min_price_chf': 400000,
        'max_price_chf': 1500000,
        'min_rooms': 1,
        'max_rooms': 10,
    }

    assert not pipeline._should_keep_listing_entry(
        {'price': 399999, 'rooms': 2, 'surface_m2': None, 'address': None},
        listing_filter,
    )
    assert not pipeline._should_keep_listing_entry(
        {'price': 1500001, 'rooms': 2, 'surface_m2': None, 'address': None},
        listing_filter,
    )
    assert not pipeline._should_keep_listing_entry(
        {'price': 600000, 'rooms': 0.5, 'surface_m2': None, 'address': None},
        listing_filter,
    )
    assert not pipeline._should_keep_listing_entry(
        {'price': 600000, 'rooms': 10.5, 'surface_m2': None, 'address': None},
        listing_filter,
    )


def test_listing_entry_filter_rejects_all_missing_property_details():
    assert not pipeline._should_keep_listing_entry(
        {'price': None, 'rooms': None, 'surface_m2': None, 'address': None},
        {},
    )


def test_listing_entry_filter_keeps_partial_data_within_default_bounds():
    assert pipeline._should_keep_listing_entry({'price': None, 'rooms': 2}, {})
    assert pipeline._should_keep_listing_entry(
        {'price': 750000, 'rooms': None, 'surface_m2': None, 'address': None},
        {},
    )


def test_process_message_skips_rejected_entries_before_upsert(monkeypatch):
    msg = EmailMessage()
    msg['Subject'] = 'New listings'
    entries = [
        {
            'url': 'https://example.com/out-of-range',
            'price': 1600000,
            'rooms': 3,
            'address': 'Outside range',
        },
        {
            'url': 'https://example.com/no-details',
            'price': None,
            'rooms': None,
            'surface_m2': None,
            'address': None,
        },
        {
            'url': 'https://example.com/accepted',
            'price': 750000,
            'rooms': 3,
            'address': 'Within range',
            'source_site': 'test',
        },
    ]
    upserted = []

    monkeypatch.setattr(pipeline, 'mark_message_processed', lambda *args, **kwargs: (True, {}))
    monkeypatch.setattr(pipeline, 'parse_email', lambda message: entries)
    monkeypatch.setattr(
        pipeline,
        'upsert',
        lambda listings, listing, observation: upserted.append(listing.url),
    )

    count = pipeline._process_message(msg, {}, {}, listing_filter={})

    assert count == 1
    assert upserted == ['https://example.com/accepted']
