from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from tempfile import NamedTemporaryFile
from typing import Dict

from .model import Listing, PriceObservation, build_property_key


def load_listings(path: str) -> Dict[str, Listing]:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {key: Listing.from_dict(item) for key, item in data.items()}


def _atomic_write(path: str, data: str) -> None:
    dirpath = os.path.dirname(path) or "."
    with NamedTemporaryFile("w", delete=False, dir=dirpath, encoding="utf-8") as tf:
        tf.write(data)
        tempname = tf.name
    os.replace(tempname, path)


def save_listings(listings: Dict[str, Listing], path: str) -> None:
    serializable = {key: listing.to_dict() for key, listing in listings.items()}
    _atomic_write(path, json.dumps(serializable, ensure_ascii=False, indent=2))


def _dedupe_observation(existing: Listing, observation: PriceObservation) -> bool:
    for obs in existing.observations:
        if (
            obs.price == observation.price
            and obs.source == observation.source
            and obs.observed_at.date() == observation.observed_at.date()
        ):
            return True
    return False


def upsert(listings: Dict[str, Listing], new_listing: Listing, observation: PriceObservation) -> None:
    key = new_listing.property_key or build_property_key(new_listing)
    new_listing.property_key = key
    existing = listings.get(key)
    now = datetime.now(timezone.utc)

    if existing is None:
        new_listing.first_seen = now
        new_listing.last_seen = now
        new_listing.observations.append(observation)
        listings[key] = new_listing
        return

    if new_listing.address and not existing.address:
        existing.address = new_listing.address
    if new_listing.title and not existing.title:
        existing.title = new_listing.title
    if new_listing.rooms is not None and existing.rooms is None:
        existing.rooms = new_listing.rooms
    if new_listing.surface_m2 is not None and existing.surface_m2 is None:
        existing.surface_m2 = new_listing.surface_m2
    if new_listing.commune and not existing.commune:
        existing.commune = new_listing.commune
    if new_listing.canton and not existing.canton:
        existing.canton = new_listing.canton

    if _dedupe_observation(existing, observation):
        return

    existing.observations.append(observation)
    existing.last_seen = now
    existing.is_active = True
