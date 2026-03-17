"""
부동산 실거래가 CSV 수집기
- CSV 파일에서 주소/아파트명 읽기
- 국토교통부 API로 실거래가 조회
- 결과를 CSV로 출력

사용법:
    python realestate_csv.py --input input.csv --output output.csv --months 3
    python realestate_csv.py --input input.csv --months 6 --type rent

입력 CSV 형식:
    주소,아파트명
    서울특별시 강남구,은마아파트
    서울특별시 서초구,반포자이

환경변수:
    MOLIT_API_KEY=발급받은_API_키
"""

import asyncio
import csv
import os
import sys
import argparse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from urllib.parse import unquote, quote

import httpx
from dotenv import load_dotenv

load_dotenv()

# ───────────────────────────────────────────────
# 지역코드 매핑
# ───────────────────────────────────────────────

SIDO_MAP = {
    "서울": "11", "서울특별시": "11",
    "부산": "26", "부산광역시": "26",
    "대구": "27", "대구광역시": "27",
    "인천": "28", "인천광역시": "28",
    "광주": "29", "광주광역시": "29",
    "대전": "30", "대전광역시": "30",
    "울산": "31", "울산광역시": "31",
    "세종": "36", "세종특별자치시": "36",
    "경기": "41", "경기도": "41",
    "충북": "43", "충청북도": "43",
    "충남": "44", "충청남도": "44",
    "전북": "52", "전북특별자치도": "52", "전라북도": "45",
    "전남": "46", "전라남도": "46",
    "경북": "47", "경상북도": "47",
    "경남": "48", "경상남도": "48",
    "제주": "50", "제주특별자치도": "50",
    "강원": "51", "강원특별자치도": "51",
}

# 시군구 코드 전체 (5자리)
SIGUNGU_MAP = {
    # 서울
    "강남구": "11680", "강동구": "11740", "강북구": "11305", "강서구": "11500",
    "관악구": "11620", "광진구": "11215", "구로구": "11530", "금천구": "11545",
    "노원구": "11350", "도봉구": "11320", "동대문구": "11230", "동작구": "11590",
    "마포구": "11440", "서대문구": "11410", "서초구": "11650", "성동구": "11200",
    "성북구": "11290", "송파구": "11710", "양천구": "11470", "영등포구": "11560",
    "용산구": "11170", "은평구": "11380", "종로구": "11110", "중구": "11140",
    "중랑구": "11260",
    # 경기
    "수원시 영통구": "41131", "수원시 팔달구": "41133", "수원시 장안구": "41135", "수원시 권선구": "41137",
    "성남시 수정구": "41171", "성남시 중원구": "41173", "성남시 분당구": "41175",
    "의정부시": "41190", "안양시 만안구": "41210", "안양시 동안구": "41220",
    "부천시": "41250", "광명시": "41270", "평택시": "41285", "안산시 상록구": "41310",
    "안산시 단원구": "41312", "고양시 덕양구": "41360", "고양시 일산동구": "41364",
    "고양시 일산서구": "41365", "과천시": "41390", "구리시": "41410", "남양주시": "41430",
    "오산시": "41450", "시흥시": "41460", "군포시": "41480", "의왕시": "41500",
    "하남시": "41550", "용인시 처인구": "41570", "용인시 기흥구": "41571",
    "용인시 수지구": "41573", "파주시": "41590", "이천시": "41610", "안성시": "41630",
    "김포시": "41650", "화성시": "41670", "광주시": "41800", "양주시": "41820",
    "포천시": "41830",
    # 부산
    "부산 중구": "26110", "서구": "26140", "동구": "26170", "영도구": "26200",
    "부산진구": "26230", "동래구": "26260", "남구": "26290", "북구": "26320",
    "해운대구": "26350", "사하구": "26380", "금정구": "26410", "부산 강서구": "26440",
    "연제구": "26470", "수영구": "26500", "사상구": "26530", "기장군": "26710",
    # 인천
    "인천 중구": "28110", "인천 동구": "28140", "미추홀구": "28177", "연수구": "28185",
    "남동구": "28200", "부평구": "28237", "계양구": "28245", "인천 서구": "28260",
    "강화군": "28710", "옹진군": "28720",
    # 대구
    "대구 중구": "27110", "대구 동구": "27140", "대구 서구": "27170", "대구 남구": "27200",
    "대구 북구": "27230", "수성구": "27260", "달서구": "27290", "달성군": "27710",
    # 기타 광역시
    "광주 동구": "29110", "광주 서구": "29140", "광주 남구": "29155",
    "광주 북구": "29170", "광산구": "29200",
    "대전 동구": "30110", "대전 중구": "30140", "대전 서구": "30170",
    "유성구": "30200", "대덕구": "30230",
    "울산 중구": "31110", "울산 남구": "31140", "울산 동구": "31170",
    "울산 북구": "31200", "울주군": "31710",
    "세종시": "36110",
    # 제주
    "제주시": "50110", "서귀포시": "50130",
}

# ───────────────────────────────────────────────
# 주소 → 지역코드 변환
# ───────────────────────────────────────────────

def address_to_lawd_cd(address: str) -> Optional[str]:
    """
    주소 문자열에서 5자리 지역코드(LAWD_CD) 추출.
    예) "서울특별시 강남구 대치동 901" → "11680"
    """
    parts = address.strip().split()
    if len(parts) < 2:
        return None

    sigungu_part = parts[1]  # 두 번째 토큰 = 시군구

    # 직접 매칭 (단순 구 이름)
    if sigungu_part in SIGUNGU_MAP:
        return SIGUNGU_MAP[sigungu_part]

    # 세 번째 토큰까지 합쳐서 매칭 (예: "수원시 영통구")
    if len(parts) >= 3:
        combined = f"{sigungu_part} {parts[2]}"
        if combined in SIGUNGU_MAP:
            return SIGUNGU_MAP[combined]

    # 시도 코드만이라도 반환 (구 정보 없을 때)
    sido_part = parts[0]
    sido_cd = SIDO_MAP.get(sido_part)
    if sido_cd:
        # 해당 시도에 속한 시군구 중 매칭 시도
        for name, code in SIGUNGU_MAP.items():
            if code.startswith(sido_cd) and sigungu_part in name:
                return code

    return None


def get_month_range(start_ym: str | None, months: int | None) -> list[str]:
    """
    start_ym(YYYYMM) ~ 이번달까지 월 리스트 반환.
    start_ym 없으면 최근 months개월.
    """
    now = datetime.now()
    end_year, end_month = now.year, now.month

    if start_ym:
        sy, sm = int(start_ym[:4]), int(start_ym[4:6])
    else:
        n = months or 3
        start = now - timedelta(days=30 * (n - 1))
        sy, sm = start.year, start.month

    result = []
    y, m = sy, sm
    while (y, m) <= (end_year, end_month):
        result.append(f"{y}{m:02d}")
        m += 1
        if m > 12:
            m = 1
            y += 1
    return result


# ───────────────────────────────────────────────
# 국토교통부 API 호출
# ───────────────────────────────────────────────

ENDPOINTS = {
    "trade": "https://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev",
    "rent":  "https://apis.data.go.kr/1613000/RTMSDataSvcAptRent/getRTMSDataSvcAptRent",
}

def parse_xml(xml_text: str) -> list[dict]:
    """XML 응답 → dict 리스트"""
    try:
        root = ET.fromstring(xml_text)
        items = []
        for item in root.findall(".//item"):
            row = {child.tag: (child.text or "").strip() for child in item}
            items.append(row)
        return items
    except ET.ParseError as e:
        print(f"  [경고] XML 파싱 실패: {e}", file=sys.stderr)
        return []


async def fetch_trades(
    client: httpx.AsyncClient,
    api_key: str,
    lawd_cd: str,
    deal_ymd: str,
    trade_type: str = "trade",
) -> list[dict]:
    """단일 지역/월 실거래가 조회 (페이지네이션 포함)"""
    base_url = ENDPOINTS.get(trade_type, ENDPOINTS["trade"])
    all_items = []
    page = 1
    page_size = 1000

    while True:
        url = (
            f"{base_url}?serviceKey={api_key}"
            f"&LAWD_CD={lawd_cd}&DEAL_YMD={deal_ymd}"
            f"&numOfRows={page_size}&pageNo={page}"
        )
        try:
            resp = await client.get(url, timeout=30.0)
            resp.raise_for_status()
            items = parse_xml(resp.text)
            all_items.extend(items)
            # 반환 건수가 page_size 미만이면 마지막 페이지
            if len(items) < page_size:
                break
            page += 1
        except httpx.HTTPStatusError as e:
            print(f"  [오류] HTTP {e.response.status_code} - {lawd_cd} {deal_ymd}", file=sys.stderr)
            break
        except Exception as e:
            print(f"  [오류] {lawd_cd} {deal_ymd}: {e}", file=sys.stderr)
            break

    return all_items


_APT_SUFFIXES = ["아파트", "APT", "apt"]

def _strip_suffix(name: str) -> str:
    """'아파트' 등 일반 접미사 제거 후 공백 제거"""
    n = name.strip()
    for s in _APT_SUFFIXES:
        if n.endswith(s):
            n = n[: -len(s)]
    return n.replace(" ", "")


def filter_by_apt_name(items: list[dict], apt_name: str) -> list[dict]:
    """
    아파트 단지명 유연 매칭.
    1) 접미사('아파트') 제거 후 부분 일치
    2) 매칭 0건이면 전체 반환 + 후보 목록 출력
    """
    if not apt_name:
        return items

    key = _strip_suffix(apt_name)
    matched = []
    for item in items:
        raw = (item.get("aptNm") or item.get("아파트") or item.get("아파트명") or "")
        item_key = _strip_suffix(raw)
        if key in item_key or item_key in key:
            matched.append(item)

    if not matched:
        # 후보 목록 출력 (상위 10개)
        names = sorted({
            (item.get("aptNm") or "").strip()
            for item in items
            if (item.get("aptNm") or "").strip()
        })
        print(f"    [주의] '{apt_name}' 매칭 없음. 해당 지역 아파트 목록 (일부):")
        for n in names[:10]:
            print(f"           - {n}")
        print(f"    → 전체 {len(items)}건 반환 (필터 미적용)")
        return items  # 필터 없이 전체 반환

    return matched


# ───────────────────────────────────────────────
# 출력 컬럼 정규화
# ───────────────────────────────────────────────

def normalize_trade_row(row: dict, source_address: str, source_apt: str, trade_type: str) -> dict:
    """API 응답 row를 표준 컬럼으로 변환 (매매/전월세 통합)"""
    if trade_type == "trade":
        price_raw = row.get("dealAmount", "").replace(",", "").strip()
        return {
            "입력주소": source_address,
            "입력아파트명": source_apt,
            "아파트명": row.get("aptNm", ""),
            "동": row.get("aptDong", ""),
            "법정동": row.get("umdNm", ""),
            "지번": row.get("jibun", ""),
            "도로명": row.get("roadNm", ""),
            "거래유형": "매매",
            "계약년": row.get("dealYear", ""),
            "계약월": row.get("dealMonth", ""),
            "계약일": row.get("dealDay", ""),
            "거래금액(만원)": price_raw,
            "전용면적(㎡)": row.get("excluUseAr", ""),
            "층": row.get("floor", ""),
            "건축년도": row.get("buildYear", ""),
            "거래구분": row.get("dealingGbn", ""),
            "보증금(만원)": "",
            "월세(만원)": "",
        }
    else:  # rent
        return {
            "입력주소": source_address,
            "입력아파트명": source_apt,
            "아파트명": row.get("aptNm", ""),
            "동": row.get("aptDong", ""),
            "법정동": row.get("umdNm", ""),
            "지번": row.get("jibun", ""),
            "도로명": row.get("roadNm", ""),
            "거래유형": "전월세",
            "계약년": row.get("dealYear", ""),
            "계약월": row.get("dealMonth", ""),
            "계약일": row.get("dealDay", ""),
            "거래금액(만원)": "",
            "전용면적(㎡)": row.get("excluUseAr", ""),
            "층": row.get("floor", ""),
            "건축년도": row.get("buildYear", ""),
            "거래구분": row.get("dealingGbn", ""),
            "보증금(만원)": row.get("deposit", "").replace(",", ""),
            "월세(만원)": row.get("monthlyRent", "").replace(",", ""),
        }


# ───────────────────────────────────────────────
# CSV 처리 메인 로직
# ───────────────────────────────────────────────

async def process_csv(
    input_path: str,
    output_path: str,
    api_key: str,
    months: int = None,
    start_ym: str = None,
    trade_type: str = "trade",
):
    # 입력 CSV 읽기
    rows = []
    with open(input_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    if not rows:
        print("입력 CSV가 비어 있습니다.")
        return

    # 컬럼명 확인
    sample = rows[0]
    addr_col = next((c for c in sample if "주소" in c), None)
    apt_col  = next((c for c in sample if "아파트" in c or "단지" in c or "명" in c), None)

    if not addr_col:
        print(f"[오류] '주소' 컬럼을 찾을 수 없습니다. 컬럼: {list(sample.keys())}")
        return

    if not api_key:
        print("[오류] API 키가 없습니다. MOLIT_API_KEY 환경변수 또는 --key 옵션을 설정하세요.")
        return

    # Decoding 키 → URL-safe 인코딩 (+ → %2B, / → %2F)
    api_key = quote(unquote(api_key), safe='')

    deal_months = get_month_range(start_ym, months)
    range_desc = f"{deal_months[0]}~{deal_months[-1]} ({len(deal_months)}개월)"
    print(f"입력: {len(rows)}건 | 조회범위: {range_desc} | 유형: {'매매' if trade_type=='trade' else '전월세'}")
    output_rows = []

    async with httpx.AsyncClient(verify=False) as client:
        for i, row in enumerate(rows, 1):
            address = row.get(addr_col, "").strip()
            apt_name = row.get(apt_col, "").strip() if apt_col else ""

            lawd_cd = address_to_lawd_cd(address)
            if not lawd_cd:
                print(f"  [{i}/{len(rows)}] 지역코드 변환 실패: '{address}'")
                continue

            print(f"  [{i}/{len(rows)}] {address} / {apt_name} → LAWD_CD={lawd_cd}")

            for ymd in deal_months:
                items = await fetch_trades(client, api_key, lawd_cd, ymd, trade_type)

                if apt_name:
                    items = filter_by_apt_name(items, apt_name)

                for item in items:
                    output_rows.append(normalize_trade_row(item, address, apt_name, trade_type))

                if items:
                    print(f"    {ymd}: {len(items)}건")

    # 출력 CSV 저장
    if not output_rows:
        print("\n수집된 데이터가 없습니다. API 키와 주소를 확인하세요.")
        return

    fieldnames = list(output_rows[0].keys())
    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    print(f"\n완료: {len(output_rows)}건 → {output_path}")


# ───────────────────────────────────────────────
# CLI 진입점
# ───────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="부동산 실거래가 CSV 수집기")
    parser.add_argument("--input",  "-i", required=True, help="입력 CSV 파일 경로")
    parser.add_argument("--output", "-o", default="output.csv", help="출력 CSV 파일 경로 (기본: output.csv)")
    parser.add_argument("--months", "-m", type=int, default=None,
                        help="최근 몇 개월치 조회 (기본: 12). --start 지정 시 무시됨")
    parser.add_argument("--start",  "-s", default=None,
                        help="조회 시작 년월 YYYYMM (예: 200601). 전체 기록은 200601 입력")
    parser.add_argument("--type",   "-t", choices=["trade", "rent"], default="trade",
                        help="거래 유형: trade=매매, rent=전월세 (기본: trade)")
    parser.add_argument("--key",    "-k", help="국토교통부 API 키 (없으면 MOLIT_API_KEY 환경변수 사용)")
    args = parser.parse_args()

    api_key = args.key or os.getenv("MOLIT_API_KEY", "")
    if not api_key:
        print("[오류] API 키가 없습니다. --key 옵션 또는 MOLIT_API_KEY 환경변수를 설정하세요.")
        sys.exit(1)

    if not Path(args.input).exists():
        print(f"[오류] 입력 파일을 찾을 수 없습니다: {args.input}")
        sys.exit(1)

    # --start 없고 --months 없으면 기본 12개월
    months = args.months if not args.start else None
    if not args.start and not args.months:
        months = 12

    asyncio.run(process_csv(args.input, args.output, api_key, months, args.start, args.type))


if __name__ == "__main__":
    main()
