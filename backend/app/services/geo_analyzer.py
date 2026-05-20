"""A2: Geo-location anomaly detection — new country and impossible travel."""

from __future__ import annotations

import logging
import math
import uuid
from datetime import UTC, datetime
from typing import Any

from app.models.drift import DriftAlert, DriftSeverity, DriftStatus, DriftType
from app.models.identity import IdentityProfile

logger = logging.getLogger(__name__)

_IMPOSSIBLE_TRAVEL_KM = 500
_IMPOSSIBLE_TRAVEL_HOURS = 1
_EARTH_RADIUS_KM = 6371.0


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute great-circle distance in km between two lat/lon points."""
    lat1_r, lon1_r = math.radians(lat1), math.radians(lon1)
    lat2_r, lon2_r = math.radians(lat2), math.radians(lon2)
    dlat = lat2_r - lat1_r
    dlon = lon2_r - lon1_r
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
    return 2 * _EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def parse_sign_in_location(raw_data: dict[str, Any]) -> dict[str, Any] | None:
    """Extract location info from a sign-in log raw_data payload."""
    location = raw_data.get("location")
    if not location or not isinstance(location, dict):
        return None

    country = location.get("countryOrRegion", "")
    city = location.get("city", "")
    geo = location.get("geoCoordinates")
    lat = lon = None
    if isinstance(geo, dict):
        lat = geo.get("latitude")
        lon = geo.get("longitude")

    if not country:
        return None

    result: dict[str, Any] = {"country": country, "city": city}
    if lat is not None and lon is not None:
        try:
            result["latitude"] = float(lat)
            result["longitude"] = float(lon)
        except (ValueError, TypeError):
            pass

    return result


class GeoAnalyzer:
    """Detects geo-location anomalies: new country sign-in and impossible travel."""

    def detect_new_country(
        self,
        tenant_id: str,
        identity: IdentityProfile,
        sign_in_locations: list[dict[str, Any]],
    ) -> list[DriftAlert]:
        now = datetime.now(UTC)
        alerts: list[DriftAlert] = []

        known_countries = {
            loc.get("country", "").lower()
            for loc in identity.known_locations
            if loc.get("country")
        }

        if not known_countries:
            return alerts

        for loc in sign_in_locations:
            country = loc.get("country", "")
            if not country or country.lower() in known_countries:
                continue

            alerts.append(
                DriftAlert(
                    id=str(uuid.uuid4()),
                    tenant_id=tenant_id,
                    identity_id=identity.id,
                    identity_display_name=identity.display_name,
                    drift_type=DriftType.GEO_ANOMALY,
                    action="Sign-in",
                    severity=DriftSeverity.HIGH,
                    status=DriftStatus.OPEN,
                    location_country=country,
                    location_city=loc.get("city", ""),
                    details=(
                        f"Sign-in from new country '{country}' for "
                        f"'{identity.display_name}'. Known countries: "
                        f"{', '.join(sorted(known_countries))}."
                    ),
                    detected_at=now,
                )
            )
            known_countries.add(country.lower())

        return alerts

    def detect_impossible_travel(
        self,
        tenant_id: str,
        identity: IdentityProfile,
        sign_in_events: list[dict[str, Any]],
    ) -> list[DriftAlert]:
        now = datetime.now(UTC)
        alerts: list[DriftAlert] = []

        located_events: list[tuple[datetime, float, float, str]] = []
        for event in sign_in_events:
            lat = event.get("latitude")
            lon = event.get("longitude")
            ts_str = event.get("timestamp")
            country = event.get("country", "")
            if lat is None or lon is None or ts_str is None:
                continue
            try:
                ts = datetime.fromisoformat(str(ts_str).replace("Z", "+00:00"))
                located_events.append((ts, float(lat), float(lon), country))
            except (ValueError, TypeError):
                continue

        located_events.sort(key=lambda x: x[0])

        for i in range(1, len(located_events)):
            prev_ts, prev_lat, prev_lon, prev_country = located_events[i - 1]
            curr_ts, curr_lat, curr_lon, curr_country = located_events[i]

            time_diff_hours = (curr_ts - prev_ts).total_seconds() / 3600
            if time_diff_hours <= 0 or time_diff_hours > _IMPOSSIBLE_TRAVEL_HOURS:
                continue

            distance_km = _haversine(prev_lat, prev_lon, curr_lat, curr_lon)
            if distance_km < _IMPOSSIBLE_TRAVEL_KM:
                continue

            speed_kmh = distance_km / time_diff_hours

            alerts.append(
                DriftAlert(
                    id=str(uuid.uuid4()),
                    tenant_id=tenant_id,
                    identity_id=identity.id,
                    identity_display_name=identity.display_name,
                    drift_type=DriftType.IMPOSSIBLE_TRAVEL,
                    action="Sign-in",
                    severity=DriftSeverity.CRITICAL,
                    status=DriftStatus.OPEN,
                    location_country=curr_country,
                    details=(
                        f"Impossible travel detected for '{identity.display_name}': "
                        f"{distance_km:.0f}km in {time_diff_hours:.1f}h "
                        f"({speed_kmh:.0f} km/h). From '{prev_country}' to "
                        f"'{curr_country}'."
                    ),
                    detected_at=now,
                )
            )
            break

        return alerts
