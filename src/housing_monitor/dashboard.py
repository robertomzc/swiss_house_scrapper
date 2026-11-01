from __future__ import annotations

import json
from collections import Counter
from html import escape
from pathlib import Path
from statistics import mean, median
from typing import Any, Iterable


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


def generate_dashboard(listings: Any, output_path: str | None = None, alert_count: int | None = None) -> tuple[str, dict[str, Any]]:
    summary = summarize_listings(listings, alert_count=alert_count)
    target = output_path or "data/dashboard.html"
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
    for record in records[:25]:
        price = _price_for(record)
        rows.append(
            """
            <tr>
              <td>{title}</td>
              <td>{source}</td>
              <td>{address}</td>
              <td>{price}</td>
              <td>{rooms}</td>
              <td>{surface}</td>
            </tr>
            """.format(
                title=escape(str(record.get("title") or record.get("address") or "Listing")),
                source=escape(str(record.get("source_site") or record.get("source") or "unknown")),
                address=escape(str(record.get("address") or "-")),
                price=escape(f"{price:,.0f} CHF" if price is not None else "-"),
                rooms=escape(str(_rooms_for(record)) if _rooms_for(record) is not None else "-"),
                surface=escape(str(_surface_for(record)) if _surface_for(record) is not None else "-"),
            )
        )

    source_chart = _bar_chart(summary["by_source"], max(summary["by_source"].values(), default=0))
    price_chart = _bar_chart(summary["price_bands"], max(summary["price_bands"].values(), default=0))
    room_chart = _bar_chart(summary["room_bands"], max(summary["room_bands"].values(), default=0))
    surface_chart = _bar_chart(summary["surface_bands"], max(summary["surface_bands"].values(), default=0))

    latest = summary.get("latest_listing") or {}
    latest_title = escape(str(latest.get("title") or "-"))
    latest_source = escape(str(latest.get("source_site") or "-"))
    latest_address = escape(str(latest.get("address") or "-"))
    latest_price = escape(f"{latest.get('price_chf'):,.0f} CHF" if latest.get("price_chf") is not None else "-")

    html = f"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Housing Monitor Dashboard</title>
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
    .layout {{ display: grid; grid-template-columns: 1.2fr 0.8fr; gap: 20px; margin-bottom: 20px; }}
    .panel {{ background: var(--panel); border: 1px solid var(--border); border-radius: 12px; padding: 18px; }}
    .two-up {{ display: grid; grid-template-columns: repeat(2, minmax(260px, 1fr)); gap: 20px; margin-bottom: 20px; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 12px; }}
    th, td {{ text-align: left; padding: 10px 8px; border-bottom: 1px solid var(--border); font-size: 0.92rem; }}
    th {{ color: var(--muted); font-weight: 600; }}
    ul {{ list-style: none; margin: 0; padding: 0; }}
    .bar-row {{ display: grid; grid-template-columns: 120px 1fr 32px; gap: 10px; align-items: center; margin-bottom: 10px; }}
    .bar-track {{ background: #edf2ff; border-radius: 999px; height: 12px; overflow: hidden; }}
    .bar-fill {{ background: linear-gradient(90deg, #2563eb, #60a5fa); height: 100%; border-radius: 999px; }}
    .latest {{ margin-top: 16px; line-height: 1.8; }}
    .empty {{ color: var(--muted); font-style: italic; }}
    @media (max-width: 900px) {{ .layout, .two-up {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
  <div class="container">
    <h1>Housing Monitor Dashboard</h1>
    <div class="subtitle">Normalized metrics from parsed property alerts. Alerts: {summary['alert_count']}; unique listings: {summary['total_listings']}</div>

    <div class="cards">
      <div class="card"><small>Parsed alerts</small><strong>{summary['alert_count']}</strong></div>
      <div class="card"><small>Unique listings</small><strong>{summary['total_listings']}</strong></div>
      <div class="card"><small>Avg. price</small><strong>{summary['average_price_chf'] if summary['average_price_chf'] is not None else 'n/a'}</strong></div>
      <div class="card"><small>Median price</small><strong>{summary['median_price_chf'] if summary['median_price_chf'] is not None else 'n/a'}</strong></div>
      <div class="card"><small>Avg. rooms</small><strong>{summary['average_rooms'] if summary['average_rooms'] is not None else 'n/a'}</strong></div>
      <div class="card"><small>Avg. m²</small><strong>{summary['average_surface_m2'] if summary['average_surface_m2'] is not None else 'n/a'}</strong></div>
      <div class="card"><small>CHF / m²</small><strong>{summary['price_per_m2'] if summary['price_per_m2'] is not None else 'n/a'}</strong></div>
    </div>

    <div class="layout">
      <div class="panel">
        <h2>Recent listings</h2>
        <table>
          <thead>
            <tr><th>Title</th><th>Source</th><th>Address</th><th>Price</th><th>Rooms</th><th>m²</th></tr>
          </thead>
          <tbody>
            {''.join(rows) if rows else '<tr><td colspan="6">No listing data available.</td></tr>'}
          </tbody>
        </table>
      </div>

      <div class="panel">
        <h2>By source</h2>
        {source_chart}
        <div class="latest">
          <h3>Latest entry</h3>
          <div><strong>{latest_title}</strong></div>
          <div>{latest_source}</div>
          <div>{latest_address}</div>
          <div>{latest_price}</div>
        </div>
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
      <div class="panel">
        <h2>Highlights</h2>
        <ul>
          <li><span>Source mix</span><strong>{len(summary['by_source'])}</strong></li>
          <li><span>Active listings</span><strong>{summary['active_listings']}</strong></li>
          <li><span>Price / m²</span><strong>{summary['price_per_m2'] if summary['price_per_m2'] is not None else 'n/a'}</strong></li>
          <li><span>Avg. surface</span><strong>{summary['average_surface_m2'] if summary['average_surface_m2'] is not None else 'n/a'}</strong></li>
        </ul>
      </div>
    </div>
  </div>
</body>
</html>
"""

    html_path.write_text(html, encoding="utf-8")
    return str(html_path), summary


__all__ = ["summarize_listings", "generate_dashboard"]
