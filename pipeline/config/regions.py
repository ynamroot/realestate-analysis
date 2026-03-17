"""
Target region LAWD_CD mapping for the real estate pipeline.

All codes are 5-digit 시군구-level codes as required by MOLIT RTMSOBJSvc endpoints.
Do NOT use 2-digit 시도 codes or 10-digit 법정동 codes — they return 0 results silently.

Sources (both verified):
  - realestate_csv.py SIGUNGU_MAP
  - app/data/region_codes.py SEOUL_SIGUNGU + GYEONGGI_SIGUNGU
"""

PIPELINE_REGIONS: dict[str, str] = {
    # 서울특별시 25개 자치구
    "강남구":     "11680",
    "강동구":     "11740",
    "강북구":     "11305",
    "강서구":     "11500",
    "관악구":     "11620",
    "광진구":     "11215",
    "구로구":     "11530",
    "금천구":     "11545",
    "노원구":     "11350",
    "도봉구":     "11320",
    "동대문구":   "11230",
    "동작구":     "11590",
    "마포구":     "11440",
    "서대문구":   "11410",
    "서초구":     "11650",
    "성동구":     "11200",
    "성북구":     "11290",
    "송파구":     "11710",
    "양천구":     "11470",
    "영등포구":   "11560",
    "용산구":     "11170",
    "은평구":     "11380",
    "종로구":     "11110",
    "중구":       "11140",
    "중랑구":     "11260",
    # 경기도 4개 권역
    "성남시 분당구":  "41175",   # 위례 일부 포함 지역
    "과천시":         "41390",
    "하남시":         "41550",   # 위례신도시 행정구역
    "안양시 동안구":  "41220",   # 인덕원 행정구역
}

# Convenience subsets
SEOUL_REGIONS: dict[str, str] = {
    k: v for k, v in PIPELINE_REGIONS.items() if v.startswith("11")
}

GYEONGGI_REGIONS: dict[str, str] = {
    k: v for k, v in PIPELINE_REGIONS.items() if v.startswith("41")
}
