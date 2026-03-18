"""
Kakao Local Geocoding API client.

Source: developers.kakao.com/docs/latest/ko/local/dev-guide#address-coord
Free quota: 300,000 calls/day.
Coordinate convention: x=longitude, y=latitude (same as TMAP).

Usage:
    client = KakaoGeoClient(os.getenv("KAKAO_REST_API_KEY"))
    async with httpx.AsyncClient() as http:
        lat, lon = await client.geocode(http, "대치동 984-1") or (None, None)
"""
from __future__ import annotations

import httpx

KAKAO_GEO_URL = "https://dapi.kakao.com/v2/local/search/address.json"


class KakaoGeoClient:
    """
    Async client for Kakao Local Address Geocoding API.
    Returns (latitude, longitude) or None on no-result.
    """

    def __init__(self, rest_api_key: str) -> None:
        self.rest_api_key = rest_api_key

    async def geocode(
        self,
        client: httpx.AsyncClient,
        address: str,
    ) -> tuple[float, float] | None:
        """
        Geocode an address string. Returns (latitude, longitude) or None.

        Args:
            client: Open httpx.AsyncClient.
            address: Korean address string, e.g. "대치동 984-1" or road address.

        Returns:
            (latitude, longitude) tuple or None if not found.
        """
        resp = await client.get(
            KAKAO_GEO_URL,
            headers={"Authorization": f"KakaoAK {self.rest_api_key}"},
            params={"query": address, "analyze_type": "similar"},
            timeout=10.0,
        )
        resp.raise_for_status()
        docs = resp.json().get("documents", [])
        if not docs:
            return None
        # x=longitude, y=latitude (Kakao convention — same as TMAP)
        first = docs[0]
        try:
            return float(first["y"]), float(first["x"])  # (lat, lon)
        except (KeyError, ValueError):
            return None
