import re

from housing_monitor.dashboard import generate_dashboard, summarize_listings


def test_generate_dashboard_is_self_contained_and_includes_charts_map_and_listings(tmp_path):
    listings = {
        "one": {
            "url": "https://example.com/one",
            "source_site": "example",
            "title": "Lausanne apartment",
            "address": "1000 Lausanne 27",
            "rooms": 3.5,
            "surface_m2": 80,
            "is_active": True,
            "observations": [
                {"observed_at": "2026-10-01", "price": 800000, "kind": "new", "source": "example"}
            ],
        },
        "two": {
            "url": "https://example.com/two",
            "source_site": "example",
            "title": "Second apartment",
            "address": "Route de Lausanne",
            "rooms": 2,
            "surface_m2": 55,
            "is_active": False,
            "observations": [
                {"observed_at": "2026-10-02", "price": 550000, "kind": "new", "source": "example"}
            ],
        },
    }
    output = tmp_path / "dashboard.html"

    dashboard_path, summary = generate_dashboard(listings, str(output), alert_count=7)
    html = output.read_text(encoding="utf-8")

    assert dashboard_path == str(output)
    assert summary["alert_count"] == 7
    assert summary["total_listings"] == 2
    assert "price-surface-chart" in html
    assert "price-rooms-chart" in html
    assert "sqm-surface-chart" in html
    assert 'class="scatter-chart"' in html
    assert 'class="lausanne-map"' in html
    assert "map-legend" in html
    assert "1 shown; 1 listings have no mappable Lausanne location." in html
    assert "Schematic view, not to scale." in html
    assert "plotly_click" not in html
    assert "https://example.com/one" in html
    assert 'href="https://example.com/one"' in html
    assert "Second apartment" in html
    assert 'id="listings-panel"' in html
    assert "Price bands" in html
    assert "Room bands" in html
    assert "Surface bands" in html
    assert "Latest entry" not in html
    assert "Recent listings" not in html
    assert "<h2>Highlights</h2>" not in html
    assert "Active listings" in html
    assert "Source mix" in html
    assert not re.search(r"<script\b[^>]*\bsrc\s*=", html, re.IGNORECASE)
    assert not re.search(r"<link\b[^>]*\bhref\s*=", html, re.IGNORECASE)
    assert not re.search(r"<img\b[^>]*\bsrc\s*=", html, re.IGNORECASE)
    assert not re.search(r"@import|url\(\s*['\"]?https?://|fetch\(|XMLHttpRequest", html, re.IGNORECASE)
    assert "plotly" not in html.lower()
    assert "maplibre" not in html.lower()
    assert "openfreemap" not in html.lower()
    assert "<th>Land (m²)</th>" not in html
    assert "<th>Year built</th>" not in html
    assert "<td>800,000</td>" in html
    assert "Listing URL:" not in html
    assert "<b>Address:</b>" not in html
    assert "Current price:" in html
    assert "800,000 CHF" in html
    marker = re.search(r'class="map-marker"[^>]*data-lat="([^"]+)"', html)
    assert marker
    assert float(marker.group(1)) > 46.53


def test_dashboard_escapes_listing_content_in_html_and_inline_data(tmp_path):
    listing = {
        "url": "https://example.com/listing",
        "source_site": "example",
        "title": "Safe title",
        "address": "Lausanne </script><img src=x onerror=alert(1)>",
        "rooms": 2,
        "surface_m2": 50,
        "lat": 46.52,
        "lng": 6.63,
        "observations": [{"price": 500000}],
    }
    output = tmp_path / "dashboard.html"

    generate_dashboard([listing], str(output))
    html = output.read_text(encoding="utf-8")

    assert "</script><img src=x" not in html
    assert "&lt;/script&gt;&lt;img" in html
    assert "Latitude:" in html
    assert "Longitude:" in html


def test_map_supports_other_lausanne_postcode_areas(tmp_path):
    output = tmp_path / "dashboard.html"

    generate_dashboard(
        [
            {
                "url": "https://example.com/lausanne-1015",
                "address": "1015 Lausanne",
                "observations": [{"price": 600000}],
            }
        ],
        str(output),
    )
    html = output.read_text(encoding="utf-8")

    assert "1 shown; 0 listings have no mappable Lausanne location." in html
    marker = re.search(r'class="map-marker"[^>]*data-lat="([^"]+)"', html)
    assert marker
    assert float(marker.group(1)) > 46.51


def test_summary_values_remain_available():
    summary = summarize_listings(
        [
            {"rooms": 2, "surface_m2": 50, "observations": [{"price": 500000}]},
            {"rooms": 4, "surface_m2": 100, "observations": [{"price": 1000000}]},
        ]
    )

    assert summary["average_price_chf"] == 750000
    assert summary["median_price_chf"] == 750000
    assert summary["average_rooms"] == 3
    assert summary["average_surface_m2"] == 75
