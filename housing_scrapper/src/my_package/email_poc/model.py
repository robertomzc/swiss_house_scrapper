from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Literal, Optional


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
    observations: list[PriceObservation] = field(default_factory=list)

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
