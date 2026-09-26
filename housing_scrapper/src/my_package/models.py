from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Optional


@dataclass
class SearchCriteria:
    max_price_chf: Optional[float] = None
    min_price_chf: Optional[float] = None
    min_rooms: Optional[float] = None
    min_area_m2: Optional[float] = None
    cities: list[str] = field(default_factory=list)
    property_types: list[str] = field(default_factory=list)
    
    def matches(self, prop: Property) -> bool:
        if self.max_price_chf and prop.price_chf and prop.price_chf > self.max_price_chf:
            return False
        if self.min_price_chf and prop.price_chf and prop.price_chf < self.min_price_chf:
            return False
        if self.min_rooms and prop.rooms and prop.rooms < self.min_rooms:
            return False
        if self.min_area_m2 and prop.area_m2 and prop.area_m2 < self.min_area_m2:
            return False
        if self.cities and prop.city not in self.cities:
            return False
        if self.property_types and prop.property_type not in self.property_types:
            return False
        return True


@dataclass
class Property:
    title: str
    source: str
    city: str
    url: str = ""
    price_chf: Optional[float] = None
    rooms: Optional[float] = None
    area_m2: Optional[float] = None
    property_type: str = "apartment"
    zip_code: Optional[str] = None
    address: Optional[str] = None
    description: Optional[str] = None
    available_from: Optional[date] = None
    agency: Optional[str] = None
    raw_data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "source": self.source,
            "city": self.city,
            "url": self.url,
            "price_chf": self.price_chf,
            "rooms": self.rooms,
            "area_m2": self.area_m2,
            "property_type": self.property_type,
            "zip_code": self.zip_code,
            "address": self.address,
            "description": self.description,
            "available_from": self.available_from.isoformat() if self.available_from else None,
            "agency": self.agency,
            "raw_data": self.raw_data,
        }
