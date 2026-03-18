"""
MOLIT (국토교통부) API client for real estate transaction data.

CRITICAL IMPLEMENTATION NOTES:
1. serviceKey MUST be embedded directly in the URL string — never via params={} dict.
   httpx double-encodes special characters in params={}, causing 401 errors that look
   like registration failures. The key already contains URL-unsafe chars (+, /).

2. HTTP 200 does NOT mean success. MOLIT always returns HTTP 200, encoding errors
   in the XML body as <resultCode>. Always call _check_result_code() before parsing items.

3. Pagination: districts like 강남구 can exceed 1,000 rows/month. Always loop until
   len(items) < page_size.

Source: realestate_csv.py fetch_trades() (serviceKey pattern from line 362)
"""
from __future__ import annotations

import base64
import xml.etree.ElementTree as ET
from urllib.parse import unquote, quote

import httpx

ENDPOINTS: dict[str, str] = {
    "trade": "https://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev",
    "rent":  "https://apis.data.go.kr/1613000/RTMSDataSvcAptRent/getRTMSDataSvcAptRent",
}


class MolitClient:
    """
    Async client for MOLIT real estate transaction APIs.

    Usage:
        client = MolitClient(os.getenv("MOLIT_API_KEY"))
        async with httpx.AsyncClient() as http:
            items = await client.fetch_all(http, "11680", "202401", "trade")
    """

    def __init__(self, raw_api_key: str) -> None:
        # Pre-encode: decode any existing URL encoding, then re-encode unsafe chars.
        # CRITICAL: do NOT pass serviceKey via params={} — httpx will double-encode it.
        # This pattern is taken verbatim from realestate_csv.py line 362.
        # NOTE: API key contains Base64-like chars (+, /) but those are literal characters, not encoding
        self.safe_key = quote(unquote(raw_api_key), safe="")

    async def fetch_all(
        self,
        client: httpx.AsyncClient,
        lawd_cd: str,
        deal_ym: str,
        deal_type: str = "trade",
        page_size: int = 1000,
    ) -> list[dict]:
        """
        Fetch all pages for (lawd_cd, deal_ym, deal_type) from the MOLIT API.

        Args:
            client: An open httpx.AsyncClient (caller manages lifecycle).
            lawd_cd: 5-digit district code, e.g. "11680". Must be exactly 5 digits.
            deal_ym: Year-month string, e.g. "202401" (YYYYMM format, no separator).
            deal_type: "trade" (매매) or "rent" (전세/월세).
            page_size: Items per page. Default 1000 (MOLIT maximum).

        Returns:
            List of dicts, one per <item> element. Keys are camelCase XML tag names,
            e.g. {"aptNm": "은마아파트", "dealAmount": "55,000", ...}.

        Raises:
            ValueError: If deal_type is not "trade" or "rent".
            RuntimeError: If MOLIT returns a non-00 resultCode in the response body.
            httpx.HTTPStatusError: If HTTP status is not 2xx.
        """
        assert len(lawd_cd) == 5 and lawd_cd.isdigit(), (
            f"lawd_cd must be 5 digits, got: {lawd_cd!r}"
        )
        if deal_type not in ENDPOINTS:
            raise ValueError(f"deal_type must be 'trade' or 'rent', got: {deal_type!r}")

        base_url = ENDPOINTS[deal_type]
        all_items: list[dict] = []
        page = 1

        while True:
            # serviceKey embedded in URL string — do NOT move to params={}
            url = (
                f"{base_url}?serviceKey={self.safe_key}"
                f"&LAWD_CD={lawd_cd}&DEAL_YMD={deal_ym}"
                f"&numOfRows={page_size}&pageNo={page}"
            )
            resp = await client.get(url, timeout=30.0)
            resp.raise_for_status()

            # MOLIT always returns HTTP 200, even for errors — check resultCode in body
            ok, err = _check_result_code(resp.text)
            if not ok:
                raise RuntimeError(f"MOLIT API error: {err}")

            items = _parse_items(resp.text)
            all_items.extend(items)

            if len(items) < page_size:
                break  # Last page (or empty response)
            page += 1

        return all_items


def _check_result_code(xml_text: str) -> tuple[bool, str]:
    """
    Detect HTTP-200 error responses from the MOLIT API.

    MOLIT encodes errors in the XML body, not in the HTTP status code.
    resultCode "00", "0000", or "000" means success. Any other value is an error.

    Args:
        xml_text: Raw XML response body from the MOLIT API.

    Returns:
        (True, "") on success.
        (False, "Code {code}: {msg}") on API error.
        (False, "XML parse failure") if the XML cannot be parsed.
    """
    try:
        root = ET.fromstring(xml_text)
        code = root.findtext(".//resultCode") or ""
        if code and code not in ("00", "0000", "000"):
            msg = root.findtext(".//resultMsg") or "Unknown MOLIT error"
            return False, f"Code {code}: {msg}"
        return True, ""
    except ET.ParseError:
        return False, "XML parse failure"


def _parse_items(xml_text: str) -> list[dict]:
    """
    Parse all <item> elements from a MOLIT API XML response.

    Each <item> is converted to a dict of {tag: stripped_text}.
    XML tag names are camelCase English (e.g. "aptNm", "dealAmount").
    Korean keys are never used — the API always returns camelCase.

    Args:
        xml_text: Raw XML response body from the MOLIT API.

    Returns:
        List of dicts. Returns empty list if no <item> elements found.
    """
    root = ET.fromstring(xml_text)
    return [
        {child.tag: (child.text or "").strip() for child in item}
        for item in root.findall(".//item")
    ]
