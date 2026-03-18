"""
TMAP (SK Telecom) Pedestrian Walking Route API client.

CRITICAL IMPLEMENTATION NOTES:
1. COORDINATE ORDER: startX/endX = LONGITUDE, startY/endY = LATITUDE.
   Korean range: lon ~126-130, lat ~34-38.
   Passing (lat, lon) as (X, Y) silently produces routes in the wrong location.
2. totalDistance is in the FIRST feature where pointType == "SP" (start point).
   Do NOT use features[0] directly — iterate and check pointType.
3. Free quota: 1,000 requests/day. Always check DB cache before calling.
   asyncio.sleep(1.0) between calls to stay within rate limit.

Source: skopenapi.readme.io/reference/경로안내-샘플예제
"""
from __future__ import annotations

import httpx

TMAP_PEDESTRIAN_URL = "https://apis.openapi.sk.com/tmap/routes/pedestrian?version=1"
STRAIGHT_LINE_CUTOFF_M = 1500  # Skip TMAP call if haversine > this


def tmap_walk_distance_from_response(data: dict) -> int | None:
    """
    Parse totalDistance (meters) from a TMAP Pedestrian API JSON response.

    Args:
        data: Parsed JSON dict from TMAP response.

    Returns:
        Total walking distance in meters as int, or None if not found.
    """
    for feat in data.get("features", []):
        props = feat.get("properties", {})
        if props.get("pointType") == "SP":
            val = props.get("totalDistance", 0)
            return int(val) if val else None
    return None


class TmapClient:
    """
    Async client for TMAP Pedestrian Walking Route API.

    Usage:
        client = TmapClient(os.getenv("TMAP_APP_KEY"))
        async with httpx.AsyncClient() as http:
            dist_m = await client.walk_distance_m(http, 127.0276, 37.4979, 127.0360, 37.5007)
    """

    def __init__(self, app_key: str) -> None:
        self.app_key = app_key

    async def walk_distance_m(
        self,
        client: httpx.AsyncClient,
        from_lon: float,
        from_lat: float,
        to_lon: float,
        to_lat: float,
    ) -> int | None:
        """
        Call TMAP Pedestrian API. Returns walking distance in meters or None on failure.

        Args:
            client: Open httpx.AsyncClient (caller manages lifecycle).
            from_lon: Start longitude (NOT latitude). Korean range ~126-130.
            from_lat: Start latitude (NOT longitude). Korean range ~34-38.
            to_lon: End longitude.
            to_lat: End latitude.

        Returns:
            Walking distance in meters as int, or None on error/no-route.
        """
        resp = await client.post(
            TMAP_PEDESTRIAN_URL,
            headers={
                "appKey": self.app_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json={
                "startX": from_lon,
                "startY": from_lat,
                "endX": to_lon,
                "endY": to_lat,
                "reqCoordType": "WGS84GEO",
                "resCoordType": "WGS84GEO",
                "startName": "s",
                "endName": "e",
            },
            timeout=15.0,
        )
        resp.raise_for_status()
        return tmap_walk_distance_from_response(resp.json())
