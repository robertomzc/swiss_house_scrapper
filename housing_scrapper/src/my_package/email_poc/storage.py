from __future__ import annotations

import json
import os
from dataclasses import asdict
from datetime import datetime, timezone
from tempfile import NamedTemporaryFile
from typing import Dict

from .model import Listing, PriceObservation


def _dt_from_iso(s: str) -> datetime:
    value = datetime.fromisoformat(s)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def load_listings(path: str) -> Dict[str, Listing]:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    out: Dict[str, Listing] = {}
    for url, item in data.items():
        obs = []
        for o in item.get("observations", []):
            obs.append(PriceObservation(observed_at=_dt_from_iso(o["observed_at"]), price=o.get("price"), status=o.get("status"), source=o.get("source")))
        listing = Listing(
            url=url,
            source_site=item.get("source_site", "unknown"),
            external_id=item.get("external_id"),
            title=item.get("title"),
            listing_type=item.get("listing_type"),
            address=item.get("address"),
            npa=item.get("npa"),
            commune=item.get("commune"),
            canton=item.get("canton"),
            lat=item.get("lat"),
            lng=item.get("lng"),
            rooms=item.get("rooms"),
            surface_m2=item.get("surface_m2"),
            land_m2=item.get("land_m2"),
            year_built=item.get("year_built"),
            first_seen=_dt_from_iso(item["first_seen"]) if item.get("first_seen") else datetime.utcnow(),
            last_seen=_dt_from_iso(item["last_seen"]) if item.get("last_seen") else datetime.utcnow(),
            is_active=item.get("is_active", True),
            observations=obs,
        )
        out[url] = listing
    return out


def _atomic_write(path: str, data: str) -> None:
    dirpath = os.path.dirname(path) or "."
    with NamedTemporaryFile("w", delete=False, dir=dirpath, encoding="utf-8") as tf:
        tf.write(data)
        tempname = tf.name
    os.replace(tempname, path)


def save_listings(listings: Dict[str, Listing], path: str) -> None:
    serializable = {url: listing.to_dict() for url, listing in listings.items()}
    _atomic_write(path, json.dumps(serializable, ensure_ascii=False, indent=2))


def upsert(listings: Dict[str, Listing], new_listing: Listing, observation: PriceObservation) -> None:
    existing = listings.get(new_listing.url)
    now = datetime.now(timezone.utc)
    if not existing:
        new_listing.observations.append(observation)
        new_listing.first_seen = now
        new_listing.last_seen = now
        listings[new_listing.url] = new_listing
        return

    if new_listing.address and not existing.address:
        existing.address = new_listing.address
    if new_listing.title and not existing.title:
        existing.title = new_listing.title
    if new_listing.rooms is not None and existing.rooms is None:
        existing.rooms = new_listing.rooms
    if new_listing.surface_m2 is not None and existing.surface_m2 is None:
        existing.surface_m2 = new_listing.surface_m2
    if new_listing.source_site:
        existing.source_site = new_listing.source_site

    last_obs = existing.observations[-1] if existing.observations else None
    same_price_on_same_day = any(
        obs.price == observation.price and obs.source == observation.source and obs.observed_at.date() == observation.observed_at.date()
        for obs in existing.observations
    )
    if same_price_on_same_day:
        return

    existing.observations.append(observation)
    existing.last_seen = now
    existing.is_active = True
