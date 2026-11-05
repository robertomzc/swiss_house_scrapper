from __future__ import annotations

import json
import math
import re
from collections import Counter
from html import escape
from pathlib import Path
from statistics import mean, median
from typing import Any, Iterable
from urllib.parse import urlsplit


_LAUSANNE_POSTCODE_CENTERS = {
    "1000": (46.5291, 6.6524),
    "1000-25": (46.5737, 6.6987),
    "1000-26": (46.5534, 6.6971),
    "1000-27": (46.5417, 6.6815),
    "1003": (46.5200, 6.6300),
    "1004": (46.5285, 6.6187),
    "1005": (46.5199, 6.6425),
    "1006": (46.5112, 6.6371),
    "1007": (46.5177, 6.6090),
    "1010": (46.5362, 6.6589),
    "1011": (46.5249, 6.6431),
    "1012": (46.5263, 6.6570),
    "1015": (46.5211, 6.5759),
    "1018": (46.5379, 6.6293),
}

_LISTING_FIELDS = (
    ("Title", "title"),
    ("Address", "address"),
    ("Source", "source_site"),
    ("Listing type", "listing_type"),
    ("Postal code", "npa"),
    ("Commune", "commune"),
    ("Canton", "canton"),
    ("Rooms", "rooms"),
    ("Surface (m²)", "surface_m2"),
    ("Land (m²)", "land_m2"),
    ("Year built", "year_built"),
    ("Latitude", "lat"),
    ("Longitude", "lng"),
    ("First seen", "first_seen"),
    ("Last seen", "last_seen"),
    ("Active", "is_active"),
    ("External ID", "external_id"),
    ("Property key", "property_key"),
)


def _as_listing_records(entries: Iterable[Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for item in entries:
        if hasattr(item, "to_dict"):
            item = item.to_dict()
        if isinstance(item, dict):
            records.append(item)
    return records


def _price_for(record: dict[str, Any]) -> float | None:
    obs = record.get("observations") or []
    if obs:
        last_obs = obs[-1]
        if isinstance(last_obs, dict):
            price = last_obs.get("price")
            if price is not None:
                return float(price)
    for key in ("current_price", "price_chf", "price"):
        value = record.get(key)
        if value is not None:
            return float(value)
    return None


def _rooms_for(record: dict[str, Any]) -> float | None:
    value = record.get("rooms")
    if value is not None:
        return float(value)
    return None


def _surface_for(record: dict[str, Any]) -> float | None:
    for key in ("surface_m2", "area_m2"):
        value = record.get(key)
        if value is not None:
            return float(value)
    return None


def _listing_url(record: dict[str, Any]) -> str | None:
    value = record.get("url")
    if not isinstance(value, str):
        return None
    parsed = urlsplit(value)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return None
    return value


def _lausanne_postcode(record: dict[str, Any]) -> str | None:
    explicit_postcode = record.get("npa")
    candidates = [str(explicit_postcode)] if explicit_postcode else []
    candidates.extend(str(record.get(field) or "") for field in ("address", "title", "commune"))
    for candidate in candidates:
        district = re.search(r"\b1000\s+lausanne\s+(25|26|27)\b", candidate, re.IGNORECASE)
        if district:
            return f"1000-{district.group(1)}"
        match = re.search(
            r"(?<!\d)(1000|1003|1004|1005|1006|1007|1010|1011|1012|1015|1018)(?!\d)",
            candidate,
        )
        if match:
            return match.group(1)
    return None


def _lausanne_map_location(record: dict[str, Any], index: int) -> tuple[float, float, str] | None:
    location = " ".join(
        str(record.get(field) or "") for field in ("address", "title", "commune", "npa")
    ).lower()
    postcode = _lausanne_postcode(record)
    if postcode is None and "lausanne" not in location:
        return None

    latitude = record.get("lat")
    longitude = record.get("lng")
    if latitude is not None and longitude is not None:
        latitude = float(latitude)
        longitude = float(longitude)
        if math.isfinite(latitude) and math.isfinite(longitude):
            return latitude, longitude, "Exact listing coordinates"

    if postcode is None:
        return None

    latitude, longitude = _LAUSANNE_POSTCODE_CENTERS[postcode]
    angle = index * 2.399963229728653
    radius = 0.00035 + (index % 5) * 0.00012
    latitude += math.sin(angle) * radius
    longitude += math.cos(angle) * radius / math.cos(math.radians(latitude))
    postcode_label = postcode.replace("-", ", district ")
    return latitude, longitude, f"Approximate center of Lausanne {postcode_label}"


def _listing_details(record: dict[str, Any]) -> str:
    details = []
    for label, key in _LISTING_FIELDS:
        value = record.get(key)
        if value is not None and value != "":
            details.append(f"<strong>{escape(label)}:</strong> {escape(str(value))}")

    price = _price_for(record)
    if price is not None:
        details.append(f"<strong>Current price:</strong> {price:,.0f} CHF")

    observations = record.get("observations") or []
    if observations:
        history = []
        for observation in observations:
            if not isinstance(observation, dict):
                continue
            observed_at = observation.get("observed_at") or "Unknown date"
            observed_price = observation.get("price")
            price_text = f"{float(observed_price):,.0f} CHF" if observed_price is not None else "No price"
            kind = observation.get("kind") or "unknown"
            source = observation.get("source") or "unknown"
            history.append(
                f"{escape(str(observed_at))}: {price_text} ({escape(str(kind))}, {escape(str(source))})"
            )
        if history:
            details.append(f"<strong>Price history:</strong> {'; '.join(history)}")

    return "<br>".join(details)


def _listing_tooltip(record: dict[str, Any]) -> str:
    address = record.get("address") or record.get("title") or "-"
    source = record.get("source_site") or record.get("source") or "-"
    surface = _surface_for(record)
    rooms = _rooms_for(record)
    price = _price_for(record)
    values = (
        ("Address", address),
        ("Surface", f"{surface:g} m²" if surface is not None else "-"),
        ("Rooms", f"{rooms:g}" if rooms is not None else "-"),
        ("Source", source),
        ("Current price", f"{price:,.0f} CHF" if price is not None else "-"),
    )
    return "<br>".join(
        f"<b>{label}:</b> {escape(str(value))}" for label, value in values
    )


def _band_distribution(values: list[float], bands: list[tuple[str, float, float | None]]) -> dict[str, int]:
    counts = {label: 0 for label, _, _ in bands}
    for value in values:
        for label, lower, upper in bands:
            if upper is None:
                if value >= lower:
                    counts[label] += 1
                    break
            elif lower <= value < upper:
                counts[label] += 1
                break
    return counts


def summarize_listings(listings: Any, alert_count: int | None = None) -> dict[str, Any]:
    if isinstance(listings, (str, Path)):
        path = Path(listings)
        if not path.exists():
            return {
                "alert_count": alert_count or 0,
                "total_listings": 0,
                "active_listings": 0,
                "average_price_chf": None,
                "median_price_chf": None,
                "average_rooms": None,
                "average_surface_m2": None,
                "price_per_m2": None,
                "by_source": {},
                "price_bands": {},
                "room_bands": {},
                "surface_bands": {},
                "latest_listing": None,
            }
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        listings = data

    records = _as_listing_records(listings.values() if isinstance(listings, dict) else listings)
    valid_prices = [value for value in (_price_for(record) for record in records) if value is not None]
    valid_rooms = [value for value in (_rooms_for(record) for record in records) if value is not None]
    valid_surface = [value for value in (_surface_for(record) for record in records) if value is not None]

    by_source = Counter()
    for record in records:
        key = str(record.get("source_site") or record.get("source") or "unknown")
        by_source[key] += 1

    price_bands = _band_distribution(
        valid_prices,
        [("< 500k", 0, 500000), ("500k - 1.0M", 500000, 1000000), ("1.0M - 1.5M", 1000000, 1500000), ("> 1.5M", 1500000, None)],
    )
    room_bands = _band_distribution(valid_rooms, [("< 2 rooms", 0, 2), ("2 - 3 rooms", 2, 4), ("3 - 4 rooms", 3, 5), ("> 4 rooms", 4, None)])
    surface_bands = _band_distribution(valid_surface, [("< 40 m²", 0, 40), ("40 - 60 m²", 40, 60), ("60 - 90 m²", 60, 90), ("> 90 m²", 90, None)])

    summary = {
        "alert_count": alert_count if alert_count is not None else len(records),
        "total_listings": len(records),
        "active_listings": sum(1 for record in records if record.get("is_active", True)),
        "average_price_chf": round(mean(valid_prices), 2) if valid_prices else None,
        "median_price_chf": round(median(valid_prices), 2) if valid_prices else None,
        "average_rooms": round(mean(valid_rooms), 2) if valid_rooms else None,
        "average_surface_m2": round(mean(valid_surface), 2) if valid_surface else None,
        "price_per_m2": round(mean([p / s for p, s in zip(valid_prices, valid_surface) if s and s > 0]), 2)
        if valid_prices and valid_surface else None,
        "by_source": dict(sorted(by_source.items())),
        "price_bands": price_bands,
        "room_bands": room_bands,
        "surface_bands": surface_bands,
        "latest_listing": None,
    }

    if records:
        newest = max(records, key=lambda rec: rec.get("last_seen") or rec.get("first_seen") or "")
        summary["latest_listing"] = {
            "title": newest.get("title") or newest.get("address") or "Listing",
            "source_site": newest.get("source_site") or newest.get("source") or "unknown",
            "price_chf": _price_for(newest),
            "address": newest.get("address"),
        }
    return summary


def _bar_chart(items: dict[str, int], max_value: int) -> str:
    if not items:
        return "<div class='empty'>No data</div>"
    width = max(max_value, 1)
    html = []
    for label, value in sorted(items.items()):
        pct = (value / width) * 100 if width else 0
        html.append(
            f"<div class='bar-row'><span>{escape(label)}</span><div class='bar-track'><div class='bar-fill' style='width:{pct}%;'></div></div><strong>{value}</strong></div>"
        )
    return "".join(html)


def _format_axis_value(value: float) -> str:
    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:g}M"
    if abs(value) >= 10_000:
        return f"{value / 1_000:g}k"
    return f"{value:g}"


def _tooltip_text(point: dict[str, Any]) -> str:
    return re.sub(r"<br>|</?b>", "\n", str(point.get("tooltip") or ""))


def _svg_scatter_chart(
    points: list[dict[str, Any]],
    x_key: str,
    y_key: str,
    x_title: str,
    y_title: str,
    chart_title: str,
    color: str,
) -> str:
    chart_points = []
    for point in points:
        x_value, y_value = point.get(x_key), point.get(y_key)
        if (
            isinstance(x_value, (int, float))
            and isinstance(y_value, (int, float))
            and math.isfinite(x_value)
            and math.isfinite(y_value)
        ):
            chart_points.append((point, float(x_value), float(y_value)))
    if not chart_points:
        return "<div class='empty'>Not enough listing data for this chart.</div>"

    width, height = 640, 360
    left, top, plot_width, plot_height = 72, 24, 540, 270
    x_values = [x for _, x, _ in chart_points]
    y_values = [y for _, _, y in chart_points]
    x_min, x_max = min(x_values), max(x_values)
    y_min, y_max = min(y_values), max(y_values)
    if x_min == x_max:
        padding = abs(x_min) * 0.05 or 1
        x_min, x_max = x_min - padding, x_max + padding
    if y_min == y_max:
        padding = abs(y_min) * 0.05 or 1
        y_min, y_max = y_min - padding, y_max + padding

    pieces = [
        f'<svg class="scatter-chart" viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="{escape(chart_title, quote=True)}">',
        f'<title>{escape(chart_title)}</title>',
    ]
    for tick in range(5):
        x_ratio = tick / 4
        y_ratio = tick / 4
        x = left + x_ratio * plot_width
        y = top + plot_height - y_ratio * plot_height
        x_label = x_min + x_ratio * (x_max - x_min)
        y_label = y_min + y_ratio * (y_max - y_min)
        pieces.extend(
            (
                f'<line class="chart-gridline" x1="{x:.2f}" y1="{top}" x2="{x:.2f}" y2="{top + plot_height}"/>',
                f'<line class="chart-gridline" x1="{left}" y1="{y:.2f}" x2="{left + plot_width}" y2="{y:.2f}"/>',
                f'<text class="chart-tick" x="{x:.2f}" y="{top + plot_height + 22}" text-anchor="middle">{escape(_format_axis_value(x_label))}</text>',
                f'<text class="chart-tick" x="{left - 10}" y="{y + 4:.2f}" text-anchor="end">{escape(_format_axis_value(y_label))}</text>',
            )
        )

    pieces.append(
        f'<text class="chart-axis-title" x="{left + plot_width / 2}" y="{height - 8}" text-anchor="middle">{escape(x_title)}</text>'
        f'<text class="chart-axis-title" transform="translate(18 {top + plot_height / 2}) rotate(-90)" text-anchor="middle">{escape(y_title)}</text>'
    )
    for point, x_value, y_value in chart_points:
        x = left + (x_value - x_min) / (x_max - x_min) * plot_width
        y = top + plot_height - (y_value - y_min) / (y_max - y_min) * plot_height
        title = escape(_tooltip_text(point))
        circle = (
            f'<circle class="scatter-point" cx="{x:.2f}" cy="{y:.2f}" r="6" '
            f'fill="{color}" aria-label="{escape(str(point.get("title") or "Listing"), quote=True)}">'
            f"<title>{title}</title></circle>"
        )
        url = point.get("url")
        if url:
            pieces.append(
                f'<a href="{escape(url, quote=True)}" target="_blank" rel="noopener noreferrer">{circle}</a>'
            )
        else:
            pieces.append(circle)
    pieces.append("</svg>")
    return "".join(pieces)


def _svg_map(map_data: list[dict[str, Any]]) -> str:
    width, height = 800, 500
    west, east, south, north = 6.54, 6.73, 46.49, 46.57
    prices = [
        point["price"]
        for point in map_data
        if point.get("price") is not None and math.isfinite(point["price"])
    ]
    minimum, maximum = min(prices, default=0), max(prices, default=0)
    pieces = [
        f'<svg class="lausanne-map" viewBox="0 0 {width} {height}" role="img" aria-label="Schematic map of Lausanne and Lake Geneva">',
        "<title>Schematic map of Lausanne and Lake Geneva</title>",
        '<rect width="800" height="500" fill="#eef2e8"/>',
        '<path class="map-road" d="M-20 305 C155 260 263 290 405 225 S650 184 830 130"/>',
        '<path class="map-road" d="M90 -20 C180 90 240 180 360 260 S600 355 790 390"/>',
        '<path class="map-road" d="M-20 150 C135 200 260 110 420 150 S660 250 830 210"/>',
        '<path class="map-road map-road-major" d="M20 380 C200 330 310 360 440 310 S660 285 790 240"/>',
        '<path class="map-lake" d="M0 400 C120 385 206 410 315 390 C435 368 500 401 590 378 C680 355 743 365 800 345 L800 500 L0 500 Z"/>',
        '<text class="map-label map-city" x="380" y="280">Lausanne</text>',
        '<text class="map-label" x="157" y="204">Renens</text>',
        '<text class="map-label" x="530" y="174">Epalinges</text>',
        '<text class="map-label" x="574" y="372">Pully</text>',
        '<text class="map-water-label" x="400" y="465">Lake Geneva</text>',
        '<text class="map-disclaimer" x="20" y="28">SCHEMATIC · NOT TO SCALE</text>',
    ]
    for point in map_data:
        latitude, longitude = point["lat"], point["lng"]
        if not (math.isfinite(latitude) and math.isfinite(longitude)):
            continue
        x = (longitude - west) / (east - west) * width
        y = height - (latitude - south) / (north - south) * height
        if not (0 <= x <= width and 0 <= y <= height):
            continue
        price = point.get("price")
        if price is None or not math.isfinite(price):
            color = "#64748b"
        else:
            ratio = 0.5 if minimum == maximum else (price - minimum) / (maximum - minimum)
            color = f"hsl({220 - 220 * ratio:.1f}, 78%, 48%)"
        tooltip = escape(_tooltip_text(point))
        marker = (
            f'<circle class="map-marker" cx="{x:.2f}" cy="{y:.2f}" r="8" fill="{color}" '
            f'data-lat="{latitude:.6f}" data-lng="{longitude:.6f}" '
            f'aria-label="{escape(str(point.get("title") or "Listing"), quote=True)}">'
            f"<title>{tooltip}</title></circle>"
        )
        url = point.get("url")
        if url:
            pieces.append(
                f'<a href="{escape(url, quote=True)}" target="_blank" rel="noopener noreferrer">{marker}</a>'
            )
        else:
            pieces.append(marker)
    pieces.append("</svg>")
    return "".join(pieces)


def generate_dashboard(listings: Any, output_path: str | None = None, alert_count: int | None = None) -> tuple[str, dict[str, Any]]:
    summary = summarize_listings(listings, alert_count=alert_count)
    target = output_path or "data/artifacts/dashboard.html"
    html_path = Path(target)
    html_path.parent.mkdir(parents=True, exist_ok=True)

    records = _as_listing_records(listings.values() if isinstance(listings, dict) else listings)
    if isinstance(listings, (str, Path)):
        path = Path(listings)
        if path.exists():
            with path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            records = _as_listing_records(data.values() if isinstance(data, dict) else data)

    rows = []
    chart_data = []
    map_data = []
    for index, record in enumerate(records):
        price = _price_for(record)
        title = str(record.get("title") or record.get("address") or "Listing")
        source = str(record.get("source_site") or record.get("source") or "unknown")
        address = str(record.get("address") or "-")
        url = _listing_url(record)
        details = _listing_details(record)
        tooltip = _listing_tooltip(record)
        title_cell = escape(title)
        if url:
            title_cell = (
                f'<a href="{escape(url, quote=True)}" target="_blank" rel="noopener noreferrer">'
                f"{title_cell}</a>"
            )
        rows.append(
            """
            <tr>
              <td>{title}</td>
              <td>{source}</td>
              <td>{address}</td>
              <td>{price}</td>
              <td>{rooms}</td>
              <td>{surface}</td>
              <td>{active}</td>
              <td><details><summary>All details</summary><div class="listing-details">{details}</div></details></td>
            </tr>
            """.format(
                title=title_cell,
                source=escape(source),
                address=escape(address),
                price=escape(f"{price:,.0f}" if price is not None else "-"),
                rooms=escape(str(_rooms_for(record)) if _rooms_for(record) is not None else "-"),
                surface=escape(str(_surface_for(record)) if _surface_for(record) is not None else "-"),
                active="Yes" if record.get("is_active", True) else "No",
                details=details or "<span class='empty'>No additional details</span>",
            )
        )

        point = {
            "title": title,
            "url": url,
            "price": price,
            "surface": _surface_for(record),
            "rooms": _rooms_for(record),
            "pricePerM2": price / _surface_for(record)
            if price is not None and _surface_for(record) not in (None, 0)
            else None,
            "tooltip": tooltip,
        }
        chart_data.append(point)
        map_location = _lausanne_map_location(record, index)
        if map_location is not None:
            latitude, longitude, _ = map_location
            map_data.append(
                {
                    **point,
                    "lat": latitude,
                    "lng": longitude,
                }
            )

    price_chart = _bar_chart(summary["price_bands"], max(summary["price_bands"].values(), default=0))
    room_chart = _bar_chart(summary["room_bands"], max(summary["room_bands"].values(), default=0))
    surface_chart = _bar_chart(summary["surface_bands"], max(summary["surface_bands"].values(), default=0))

    unlocated_count = len(records) - len(map_data)
    map_prices = [
        point["price"]
        for point in map_data
        if point["price"] is not None and math.isfinite(point["price"])
    ]
    price_surface_chart = _svg_scatter_chart(
        chart_data, "surface", "price", "Surface (m²)", "Price (CHF)", "Price vs. surface", "#2563eb"
    )
    price_rooms_chart = _svg_scatter_chart(
        chart_data, "rooms", "price", "Rooms", "Price (CHF)", "Price vs. rooms", "#0f766e"
    )
    sqm_surface_chart = _svg_scatter_chart(
        chart_data,
        "surface",
        "pricePerM2",
        "Surface (m²)",
        "Price per m² (CHF)",
        "Price per m² vs. surface",
        "#ea580c",
    )
    if map_prices:
        map_legend = (
            '<div class="map-legend" aria-label="Price color scale">'
            f'<span>{min(map_prices):,.0f} CHF</span>'
            '<div class="price-gradient"></div>'
            f'<span>{max(map_prices):,.0f} CHF</span>'
            '<span class="no-price-key"></span><span>No price</span></div>'
        )
    else:
        map_legend = '<p class="map-note">No listing prices are available for the map.</p>'

    html = f"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Housing Monitor Dashboard</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    :root {{ --bg:#f5f7fb; --panel:#fff; --border:#dfe6f1; --text:#1f2937; --muted:#64748b; --accent:#2563eb; --success:#0f766e; --warn:#a16207; }}
    * {{ box-sizing: border-box; }}
    body {{ font-family: Arial, sans-serif; background: var(--bg); color: var(--text); margin: 0; padding: 24px; }}
    .container {{ max-width: 1280px; margin: 0 auto; }}
    h1 {{ margin-bottom: 8px; }}
    h2 {{ margin-top: 0; margin-bottom: 12px; }}
    .subtitle {{ color: var(--muted); margin-bottom: 24px; }}
    .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; margin-bottom: 24px; }}
    .card {{ background: var(--panel); border: 1px solid var(--border); border-radius: 12px; padding: 18px; box-shadow: 0 2px 10px rgba(15,23,42,.04); }}
    .card small {{ display: block; color: var(--muted); }}
    .card strong {{ display: block; font-size: 1.8rem; margin-top: 8px; }}
    .panel {{ background: var(--panel); border: 1px solid var(--border); border-radius: 12px; padding: 18px; }}
    .two-up {{ display: grid; grid-template-columns: repeat(2, minmax(260px, 1fr)); gap: 20px; margin-bottom: 20px; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 12px; }}
    th, td {{ text-align: left; padding: 10px 8px; border-bottom: 1px solid var(--border); font-size: 0.92rem; }}
    th {{ color: var(--muted); font-weight: 600; }}
    .bar-row {{ display: grid; grid-template-columns: 120px 1fr 32px; gap: 10px; align-items: center; margin-bottom: 10px; }}
    .bar-track {{ background: #edf2ff; border-radius: 999px; height: 12px; overflow: hidden; }}
    .bar-fill {{ background: linear-gradient(90deg, #2563eb, #60a5fa); height: 100%; border-radius: 999px; }}
    .empty {{ color: var(--muted); font-style: italic; }}
    .tabs {{ display: flex; gap: 8px; border-bottom: 1px solid var(--border); margin-bottom: 20px; }}
    .tab-button {{ border: 0; border-bottom: 3px solid transparent; background: transparent; padding: 12px 16px; color: var(--muted); font-size: 1rem; cursor: pointer; }}
    .tab-button[aria-selected="true"] {{ color: var(--accent); border-bottom-color: var(--accent); font-weight: 700; }}
    .tab-panel[hidden] {{ display: none; }}
    .chart-grid {{ display: grid; grid-template-columns: repeat(2, minmax(280px, 1fr)); gap: 20px; margin-bottom: 20px; }}
    .chart {{ min-height: 280px; }}
    .scatter-chart {{ display: block; width: 100%; height: auto; overflow: visible; }}
    .chart-gridline {{ stroke: #e5eaf2; stroke-width: 1; }}
    .chart-tick {{ fill: #64748b; font-size: 12px; }}
    .chart-axis-title {{ fill: #334155; font-size: 13px; }}
    .scatter-point {{ stroke: #fff; stroke-width: 2; opacity: .85; }}
    a .scatter-point, a .map-marker {{ cursor: pointer; }}
    #listing-map {{ border-radius: 8px; overflow: hidden; }}
    .lausanne-map {{ display: block; width: 100%; height: auto; }}
    .map-road {{ fill: none; stroke: #fff; stroke-width: 9; opacity: .85; }}
    .map-road-major {{ stroke: #f8b86b; stroke-width: 5; }}
    .map-lake {{ fill: #b7dce8; }}
    .map-label {{ fill: #64748b; font-size: 14px; text-anchor: middle; }}
    .map-city {{ fill: #334155; font-size: 20px; font-weight: 700; }}
    .map-water-label {{ fill: #4b8091; font-size: 16px; font-style: italic; text-anchor: middle; }}
    .map-disclaimer {{ fill: #64748b; font-size: 11px; font-weight: 700; letter-spacing: .08em; }}
    .map-marker {{ stroke: #fff; stroke-width: 2; cursor: pointer; }}
    .map-note {{ color: var(--muted); margin: 0 0 12px; line-height: 1.5; }}
    .map-legend {{ display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin: 8px 0 14px; color: var(--muted); font-size: 0.85rem; }}
    .price-gradient {{ width: 140px; height: 12px; border-radius: 999px; background: linear-gradient(90deg, hsl(220, 78%, 48%), hsl(0, 78%, 48%)); }}
    .no-price-key {{ width: 12px; height: 12px; border-radius: 50%; background: #64748b; }}
    .listing-details {{ padding: 8px 0; min-width: 220px; line-height: 1.6; }}
    .table-wrap {{ overflow-x: auto; }}
    .listing-table {{ min-width: 1100px; }}
    .listing-table details {{ min-width: 100px; }}
    @media (max-width: 900px) {{ .two-up, .chart-grid {{ grid-template-columns: 1fr; }} body {{ padding: 14px; }} }}
  </style>
</head>
<body>
  <div class="container">
    <h1>Housing Monitor Dashboard</h1>
    <div class="subtitle">Normalized metrics from parsed property alerts. Alerts: {summary['alert_count']}; unique listings: {summary['total_listings']}</div>

    <div class="tabs" role="tablist" aria-label="Dashboard views">
      <button class="tab-button" id="overview-tab" role="tab" aria-controls="overview-panel" aria-selected="true">Overview</button>
      <button class="tab-button" id="listings-tab" role="tab" aria-controls="listings-panel" aria-selected="false">All listings ({summary['total_listings']})</button>
    </div>

    <section class="tab-panel" id="overview-panel" role="tabpanel" aria-labelledby="overview-tab">
    <div class="cards">
      <div class="card"><small>Parsed alerts</small><strong>{summary['alert_count']}</strong></div>
      <div class="card"><small>Unique listings</small><strong>{summary['total_listings']}</strong></div>
      <div class="card"><small>Avg. price</small><strong>{summary['average_price_chf'] if summary['average_price_chf'] is not None else 'n/a'}</strong></div>
      <div class="card"><small>Median price</small><strong>{summary['median_price_chf'] if summary['median_price_chf'] is not None else 'n/a'}</strong></div>
      <div class="card"><small>Avg. rooms</small><strong>{summary['average_rooms'] if summary['average_rooms'] is not None else 'n/a'}</strong></div>
      <div class="card"><small>Avg. m²</small><strong>{summary['average_surface_m2'] if summary['average_surface_m2'] is not None else 'n/a'}</strong></div>
      <div class="card"><small>CHF / m²</small><strong>{summary['price_per_m2'] if summary['price_per_m2'] is not None else 'n/a'}</strong></div>
      <div class="card"><small>Active listings</small><strong>{summary['active_listings']}</strong></div>
      <div class="card"><small>Source mix</small><strong>{len(summary['by_source'])}</strong></div>
    </div>

    <div class="chart-grid">
      <div class="panel"><h2>Price vs. surface</h2><div id="price-surface-chart" class="chart">{price_surface_chart}</div></div>
      <div class="panel"><h2>Price vs. rooms</h2><div id="price-rooms-chart" class="chart">{price_rooms_chart}</div></div>
      <div class="panel"><h2>Price per m² vs. surface</h2><div id="sqm-surface-chart" class="chart">{sqm_surface_chart}</div></div>
      <div class="panel">
      <h2>Lausanne listing map</h2>
      <p class="map-note">Schematic view, not to scale. Approximate locations use Lausanne postcode-area centers, not exact addresses; markers are spread slightly to avoid overlap. {len(map_data)} shown; {unlocated_count} listings have no mappable Lausanne location.</p>
      {map_legend}
      <div id="listing-map">{_svg_map(map_data)}</div>
      </div>
    </div>

    <div class="two-up">
      <div class="panel">
        <h2>Price bands</h2>
        {price_chart}
      </div>
      <div class="panel">
        <h2>Room bands</h2>
        {room_chart}
      </div>
    </div>

    <div class="two-up">
      <div class="panel">
        <h2>Surface bands</h2>
        {surface_chart}
      </div>
    </div>
    </section>

    <section class="tab-panel" id="listings-panel" role="tabpanel" aria-labelledby="listings-tab" hidden>
      <div class="panel">
        <h2>All listings</h2>
        <div class="table-wrap"><table class="listing-table">
          <thead><tr><th>Title / link</th><th>Source</th><th>Address</th><th>Price</th><th>Rooms</th><th>Surface (m²)</th><th>Active</th><th>Details</th></tr></thead>
          <tbody>{''.join(rows) if rows else '<tr><td colspan="8">No listing data available.</td></tr>'}</tbody>
        </table></div>
      </div>
    </section>
  </div>
  <script>
    document.querySelectorAll('.tab-button').forEach(button => {{
      button.addEventListener('click', () => {{
        document.querySelectorAll('.tab-button').forEach(tab => tab.setAttribute('aria-selected', 'false'));
        document.querySelectorAll('.tab-panel').forEach(panel => panel.hidden = true);
        button.setAttribute('aria-selected', 'true');
        document.getElementById(button.getAttribute('aria-controls')).hidden = false;
      }});
    }});
  </script>
</body>
</html>
"""

    html_path.write_text(html, encoding="utf-8")
    return str(html_path), summary


__all__ = ["summarize_listings", "generate_dashboard"]
