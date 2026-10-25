from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timezone
from typing import Literal, Optional

from housing_monitor.models import Property


def _normalize_text(value: Optional[str]) -> str:
    if value is None:
        return ""
    cleaned = value.lower().strip()
    cleaned = re.sub(r"[^a-z0-9]+", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def _dt_from_iso(s: str) -> datetime:
    value = datetime.fromisoformat(s)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def build_property_key(listing: "Listing") -> str:
    identity_parts = [
        _normalize_text(listing.address),
        _normalize_text(listing.commune),
        _normalize_text(listing.canton),
        str(listing.rooms).replace(".", ",") if listing.rooms is not None else "",
        str(listing.surface_m2).replace(".", ",") if listing.surface_m2 is not None else "",
        _normalize_text(listing.listing_type),
    ]
    return "|".join(identity_parts)  # Changed to return a readable key instead of a hash


@dataclass
class PriceObservation:
    observed_at: datetime
    price: Optional[int]
    status: Literal["new", "active", "price_change", "delisted"]
    source: Literal["email_alert", "detail_fetch", "scraper"]


@dataclass
class Listing:
    url: str
    source_site: str
    external_id: Optional[str] = None
    title: Optional[str] = None
    listing_type: Optional[str] = None
    address: Optional[str] = None
    npa: Optional[str] = None
    commune: Optional[str] = None
    canton: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    rooms: Optional[float] = None
    surface_m2: Optional[float] = None
    land_m2: Optional[float] = None
    year_built: Optional[int] = None
    first_seen: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_seen: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    is_active: bool = True
    property_key: str = ""
    observations: list[PriceObservation] = field(default_factory=list)

    def __post_init__(self):
        if not self.property_key:
            self.property_key = build_property_key(self)

    @classmethod
    def from_dict(cls, item: dict) -> "Listing":
        payload = {
            field.name: item.get(field.name)
            for field in fields(cls)
            if field.name in item and field.name != "observations"
        }

        payload["first_seen"] = _dt_from_iso(item["first_seen"]) if item.get("first_seen") else datetime.now(timezone.utc)
        payload["last_seen"] = _dt_from_iso(item["last_seen"]) if item.get("last_seen") else datetime.now(timezone.utc)
        payload["observations"] = [
            PriceObservation(
                observed_at=_dt_from_iso(obs["observed_at"]),
                price=obs.get("price"),
                status=obs.get("status", "active"),
                source=obs.get("source", "email_alert"),
            )
            for obs in item.get("observations", [])
        ]

        return cls(**payload)

    def to_property(self) -> Property:
        return Property(
            title=self.title or self.address or "Listing",
            source=self.source_site,
            city=self.commune or self.canton or "Unknown",
            url=self.url,
            price_chf=self.current_price,
            rooms=self.rooms,
            area_m2=self.surface_m2,
            property_type=self.listing_type or "apartment",
            address=self.address,
            raw_data={"external_id": self.external_id, "observations": [obs.__dict__ for obs in self.observations]},
        )

    @property
    def current_price(self) -> Optional[int]:
        return self.observations[-1].price if self.observations else None

    @property
    def days_on_market(self) -> int:
        return (datetime.now(timezone.utc) - self.first_seen).days

    @property
    def price_change_pct(self) -> Optional[float]:
        prices = [o.price for o in self.observations if o.price is not None]
        if len(prices) < 2:
            return None
        try:
            return (prices[-1] - prices[0]) / prices[0] * 100
        except Exception:
            return None

    def to_dict(self):
        d = asdict(self)
        d["first_seen"] = self.first_seen.isoformat()
        d["last_seen"] = self.last_seen.isoformat()
        d["observations"] = [
            {"observed_at": o.observed_at.isoformat(), "price": o.price, "status": o.status, "source": o.source}
            for o in self.observations
        ]
        return d
