from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from tempfile import NamedTemporaryFile
from typing import Dict

from .model import Listing, Observation, build_property_key


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


def _matches_observation(obs: Observation, observation: Observation) -> bool:
    return (
        obs.price == observation.price
        and obs.source == observation.source
        and obs.observed_at.date() == observation.observed_at.date()
    )


def _dedupe_observation(existing: Listing, observation: Observation) -> bool:
    for obs in existing.observations:
        if _matches_observation(obs, observation):
            return True
    return False


def _classify_observation(existing: Listing | None, observation: Observation) -> Observation:
    if existing is None:
        return Observation(
            observed_at=observation.observed_at,
            price=observation.price,
            kind="new",
            source=observation.source,
        )

    if _dedupe_observation(existing, observation):
        return Observation(
            observed_at=observation.observed_at,
            price=observation.price,
            kind="duplicate",
            source=observation.source,
        )

    current_price = existing.current_price
    if observation.price is not None and current_price is not None and observation.price != current_price:
        return Observation(
            observed_at=observation.observed_at,
            price=observation.price,
            kind="price_change",
            source=observation.source,
        )

    return Observation(
        observed_at=observation.observed_at,
        price=observation.price,
        kind="active",
        source=observation.source,
    )


def upsert(listings: Dict[str, Listing], new_listing: Listing, observation: Observation) -> None:
    key = new_listing.property_key or build_property_key(new_listing)
    new_listing.property_key = key
    existing = listings.get(key)
    now = datetime.now(timezone.utc)

    if existing is None:
        new_listing.first_seen = now
        new_listing.last_seen = now
        new_listing.observations.append(_classify_observation(None, observation))
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

    classified = _classify_observation(existing, observation)
    if classified.kind == "duplicate":
        if not any(
            obs.kind == "duplicate"
            and _matches_observation(obs, classified)
            for obs in existing.observations
        ):
            existing.observations.append(classified)
        existing.last_seen = now
        existing.is_active = True
        return

    existing.observations.append(classified)
    existing.last_seen = now
    existing.is_active = True
