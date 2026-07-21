# 부동산 "최신 데이터"를 실제로 얻는 법 — 소스 비교 (2026-07 조사)

## 왜 이 문서가 필요한가

Zillow·Redfin·Realtor **웹페이지 스니펫은 캐시가 낡아** 이미 팔리거나 계약중인 매물이
"판매중"으로 섞여 나온다(우리가 244 Lincoln·1612 Anderson에서 반복해 당한 문제).
**status(Active/Pending/Sold) 필드가 있는 진짜 API**를 써야만 최신 상태를 신뢰할 수 있다.

## 소스 비교

| 소스 | 최신성 | 라이선스 | 비용 | Claude 연동 | 비고 |
|---|---|---|---|---|---|
| **RentCast API** ⭐ | 매일 갱신·신규 12–24h·**status·DOM·MLS#** | 불필요 | **무료 50건/월**, 유료 확장 | MCP 있음: `robcerda/rentcast-mcp-server`, `tandat8503/mcp_rentcast` · 본 레포 `rentcast_listings.py` | 라이선스 없이 최신 status 얻는 최선 |
| Realtor.com (RapidAPI / Apify) | 일 단위·sold/pending/active/rent | 불필요 | 무료 티어→유료 | Apify "Real Estate MCP" | 필터 풍부, ToS 주의 |
| Zillow MCP (`sap156`, `EmilyThaHuman`) | 비공식·불안정 | 불필요 | 무료/스크레이핑 | 있음 | Zillow 공식 API 없음(회색지대) |
| Redfin gis-csv (본 레포 `fetch_listings.py`) | Active만·무료 | 불필요 | 무료 | 본 레포 | Active만 반환 → 매각/계약중 자동 제외(장점), 비공식 |
| **Bridge Interactive (Zillow Group)** ✅형이 키 보유 | **MLS 원본·StandardStatus·DOM·ListingId** | 데이터셋별 MLS 승인 | 계정에 따라 | 본 레포 `bridge_listings.py` | RESO Web API. **NJMLS 데이터셋 승인 여부가 관건** |
| **NJMLS 실시간 (RESO Web API / RETS)** — SimplyRETS·Bridge(Rets.ly)·MLS Grid·Trestle | **진짜 실시간·가장 정확** | **에이전트/브로커 필요** | 유료 | 직접 연동 | 미국 MLS ~93% RESO 인증. 법적으로 라이선스 전문가용 |

## 🔵 Bridge Interactive (형이 방금 준 키 = 이것, Zillow Group 소유)

Client ID/Secret + **Server Token** + Browser Token 형식은 Bridge 고유. Bridge는 RESO Web API로
MLS 데이터를 준다. **핵심: 데이터셋(=MLS)별로 승인**돼 있어야 그 지역 매물이 나온다.

```bash
# 🔐 토큰은 절대 코드/레포에 넣지 말 것. 환경변수로만:
export BRIDGE_SERVER_TOKEN="<Server Token>"
cd real-estate/fortlee/tools
python3 bridge_listings.py --datasets        # ① 내 토큰이 접근 가능한 데이터셋 목록
export BRIDGE_DATASET="<NJMLS 데이터셋 이름>"  # ② 위 목록에서 NJMLS/버건 것 선택
python3 bridge_listings.py "Fort Lee"         # ③ Active 멀티패밀리(status·DOM·MLS#)
```

- 결과 0건이면: 그 토큰 데이터셋에 **NJMLS가 없을 가능성**이 큼(Zestimate 등 다른 데이터만 승인).
  → `--datasets`로 확인하고, 없으면 NJMLS를 Bridge에 신청하거나 RentCast로 대체.
- Browser Token은 클라이언트(웹)용, Server Token은 서버/스크립트용 — 이 툴은 Server Token 사용.

## 추천 경로

1. **지금 당장, 라이선스 없이 (권장):** RentCast 무료 키 → `rentcast_listings.py`
   ```bash
   # https://www.rentcast.io/api 에서 무료 키 발급 (50건/월)
   export RENTCAST_API_KEY="발급받은키"
   cd real-estate/fortlee/tools
   python3 rentcast_listings.py            # 6개 동네 Active 멀티패밀리
   python3 rentcast_listings.py "Fort Lee" # 도보권만(콜 절약)
   ```
   → status·daysOnMarket·mlsNumber 포함. **Active만 나오므로 계약중/매각은 자동 제외.**

2. **로컬 Claude가 직접 호출:** `redfin_mcp.py`에 RentCast 도구가 포함됨(키 있으면 활성).
   ```bash
   pip3 install "mcp[cli]"
   claude mcp add realestate -- python3 "$(pwd)/redfin_mcp.py"
   # Claude Code에서: "realestate로 Fort Lee Active 멀티패밀리 rentcast로 뽑아줘"
   ```

3. **가장 정확한 실시간(NJMLS):** 형의 부동산 **에이전트에게 IDX/RESO 피드**(SimplyRETS 또는
   Bridge) 요청 → 그 키를 주면 이 툴킷에 소스로 붙여준다. 라이선스가 있어야 가능.

## 프리 티어 아끼기

RentCast 무료는 월 50콜. `rentcast_listings.py`는 동네당 1콜(6콜/실행)로 설계.
도보권만 급하면 `python3 rentcast_listings.py "Fort Lee"` (1콜)만 쓰자.

> 결론: **"최신이냐"의 답은 소스가 status 필드를 주느냐다.** 스니펫 = No, RentCast/RESO = Yes.
> 개인이 라이선스 없이 최신을 얻는 실질적 정답은 **RentCast**, 완벽한 실시간은 **에이전트의 NJMLS**.
