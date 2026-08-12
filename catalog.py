"""Lookup RAM kits against a verified manufacturer product catalog."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

Profile = Literal["jedec", "xmp", "expo", "both"]

CATALOG_PATH = Path(__file__).resolve().parent / "data" / "catalog.json"


@dataclass(frozen=True)
class CatalogProduct:
    brand: str
    part_number: str
    product_name: str
    sticks: int
    per_stick_gb: int
    total_gb: int
    generation: int
    speed_mts: int
    cas_latency: int
    profiles: tuple[str, ...]
    rgb: bool
    form_factor: str
    ecc: bool
    source_url: str
    source: str
    verified: str

    @classmethod
    def from_dict(cls, data: dict) -> CatalogProduct:
        profiles = data.get("profiles")
        if profiles is None:
            profile = data.get("profile", "jedec")
            profiles = [profile]
        return cls(
            brand=data["brand"],
            part_number=data["part_number"],
            product_name=data["product_name"],
            sticks=int(data["sticks"]),
            per_stick_gb=int(data["per_stick_gb"]),
            total_gb=int(data["total_gb"]),
            generation=int(data["generation"]),
            speed_mts=int(data["speed_mts"]),
            cas_latency=int(data["cas_latency"]),
            profiles=tuple(profiles),
            rgb=bool(data.get("rgb", False)),
            form_factor=data.get("form_factor", "dimm"),
            ecc=bool(data.get("ecc", False)),
            source_url=data["source_url"],
            source=data.get("source", "manufacturer"),
            verified=data["verified"],
        )

    def profile_label(self, requested: Profile) -> str | None:
        if requested == "both":
            if "xmp" in self.profiles and "expo" in self.profiles:
                return "Intel XMP 3.0 & AMD EXPO"
            if "xmp" in self.profiles:
                return "Intel XMP 3.0"
            if "expo" in self.profiles:
                return "AMD EXPO"
            if "both" in self.profiles:
                return "Intel XMP 3.0 & AMD EXPO"
            return None
        if requested in self.profiles or "both" in self.profiles:
            return {
                "xmp": "Intel XMP 3.0",
                "expo": "AMD EXPO",
                "jedec": "JEDEC",
            }.get(requested)
        return None


def _profile_matches(entry_profiles: tuple[str, ...], requested: Profile) -> bool:
    if requested == "both":
        return bool({"xmp", "expo", "both"} & set(entry_profiles))
    if requested == "jedec":
        return "jedec" in entry_profiles
    return requested in entry_profiles or "both" in entry_profiles


@lru_cache(maxsize=1)
def load_catalog(path: Path | None = None) -> tuple[CatalogProduct, ...]:
    catalog_file = path or CATALOG_PATH
    with catalog_file.open(encoding="utf-8") as fh:
        payload = json.load(fh)
    return tuple(CatalogProduct.from_dict(item) for item in payload["products"])


def catalog_stats(path: Path | None = None) -> dict:
    products = load_catalog(path)
    brands = {p.brand for p in products}
    ddr5 = sum(1 for p in products if p.generation == 5)
    return {
        "product_count": len(products),
        "brand_count": len(brands),
        "ddr5_count": ddr5,
        "ddr4_count": len(products) - ddr5,
        "brands": sorted(brands),
        "version": _catalog_meta(path).get("version"),
        "updated": _catalog_meta(path).get("updated"),
    }


@lru_cache(maxsize=1)
def _catalog_meta(path: Path | None = None) -> dict:
    catalog_file = path or CATALOG_PATH
    with catalog_file.open(encoding="utf-8") as fh:
        payload = json.load(fh)
    return {
        "version": payload.get("version"),
        "updated": payload.get("updated"),
    }


def lookup_catalog(
    *,
    sticks: int,
    total_gb: int,
    generation: int,
    speed_mts: int,
    profile: Profile,
    cas_latency: int | None = None,
    rgb: bool = False,
    ecc: bool = False,
    form_factor: str = "dimm",
    path: Path | None = None,
) -> dict[str, list[CatalogProduct]]:
    per_stick_gb = total_gb // sticks
    matches: dict[str, list[CatalogProduct]] = {}

    for product in load_catalog(path):
        if product.sticks != sticks:
            continue
        if product.per_stick_gb != per_stick_gb:
            continue
        if product.total_gb != total_gb:
            continue
        if product.generation != generation:
            continue
        if product.speed_mts != speed_mts:
            continue
        if product.rgb != rgb:
            continue
        if product.ecc != ecc:
            continue
        if product.form_factor != form_factor:
            continue
        if cas_latency is not None and product.cas_latency != cas_latency:
            continue
        if not _profile_matches(product.profiles, profile):
            continue

        matches.setdefault(product.brand, []).append(product)

    for brand in matches:
        matches[brand].sort(key=lambda p: p.part_number)
    return matches


def catalog_product_to_entry(product: CatalogProduct, requested_profile: Profile) -> dict:
    label = product.profile_label(requested_profile)
    return {
        "part_number": product.part_number,
        "label": label,
        "product_name": product.product_name,
        "catalog_confirmed": True,
        "source_url": product.source_url,
        "source": product.source,
        "verified": product.verified,
        "profiles": list(product.profiles),
    }


def normalize_part_number(part: str) -> str:
    """Normalize a part number for index lookup (case/spacing/punctuation)."""
    return re.sub(r"[\s\-_/]+", "", part.strip().upper())


@lru_cache(maxsize=1)
def part_number_index(path: Path | None = None) -> dict[str, CatalogProduct]:
    index: dict[str, CatalogProduct] = {}
    for product in load_catalog(path):
        key = normalize_part_number(product.part_number)
        index.setdefault(key, product)
    return index


def lookup_by_part_number(
    part_number: str,
    *,
    brand: str | None = None,
    path: Path | None = None,
) -> CatalogProduct | None:
    """Return a catalog product by exact part number match."""
    product = part_number_index(path).get(normalize_part_number(part_number))
    if product is None:
        return None
    if brand is not None and product.brand != brand:
        return None
    return product


def _search_score(query: str, product: CatalogProduct) -> int:
    norm_q = normalize_part_number(query)
    if not norm_q and not query.strip():
        return 0

    pn_norm = normalize_part_number(product.part_number)
    pn_lower = product.part_number.lower()
    name_lower = product.product_name.lower()
    tokens = [t for t in re.split(r"\s+", query.strip().lower()) if t]

    if norm_q and pn_norm == norm_q:
        return 1000
    if norm_q and len(norm_q) >= 4 and pn_norm.startswith(norm_q):
        return 500
    if norm_q and len(norm_q) >= 4 and norm_q in pn_norm:
        return 300
    if tokens and all(t in name_lower or t in pn_lower for t in tokens):
        return 100 + sum(10 for t in tokens if t in name_lower)
    return 0


def search_catalog(
    query: str,
    *,
    limit: int = 50,
    brand: str | None = None,
    path: Path | None = None,
) -> list[CatalogProduct]:
    """Search catalog by part number fragment or product name tokens."""
    query = query.strip()
    if not query:
        return []

    scored: list[tuple[int, CatalogProduct]] = []
    for product in load_catalog(path):
        if brand is not None and product.brand != brand:
            continue
        score = _search_score(query, product)
        if score > 0:
            scored.append((score, product))

    scored.sort(key=lambda item: (-item[0], item[1].part_number))
    seen: set[tuple[str, str]] = set()
    results: list[CatalogProduct] = []
    for _, product in scored:
        key = (product.brand, product.part_number)
        if key in seen:
            continue
        seen.add(key)
        results.append(product)
        if len(results) >= limit:
            break
    return results


def catalog_product_summary(product: CatalogProduct) -> dict:
    return {
        "brand": product.brand,
        "part_number": product.part_number,
        "product_name": product.product_name,
        "sticks": product.sticks,
        "per_stick_gb": product.per_stick_gb,
        "total_gb": product.total_gb,
        "generation": product.generation,
        "speed_mts": product.speed_mts,
        "cas_latency": product.cas_latency,
        "profiles": list(product.profiles),
        "rgb": product.rgb,
        "ecc": product.ecc,
        "form_factor": product.form_factor,
        "verified": product.verified,
    }
