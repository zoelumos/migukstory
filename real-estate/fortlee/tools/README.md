# 라이브 매물 수집 툴킷 (맥미니에서 실행)

포트리 온누리교회 프로젝트용. **Redfin 공개 데이터**로 Fort Lee·Palisades Park·
Cliffside Park·Ridgefield·Leonia·Edgewater 의 **현재 활성 멀티패밀리(2·3가구)** 매물을
MLS#·DOM·상태와 함께 라이브로 가져온다.

## 왜 맥미니에서 돌려야 하나

이 툴을 만든 Claude의 클라우드 세션은 **정책 프록시가 redfin.com을 차단(403)**해서
거기선 못 돈다. 형 **맥미니(집 네트워크)**엔 그 차단이 없으니 **로컬에서 정상 동작**한다.
그래서 "네가 다 만들어서 맥미니에서 돌게 해줘"를 이렇게 실현했다: 코드는 여기 다 있고,
형은 맥미니에서 명령 한 줄만 실행하면 된다.

## A. 바로 실행 (MCP 없이, 가장 간단)

```bash
cd real-estate/fortlee/tools
python3 fetch_listings.py                    # 6개 동네 전부
python3 fetch_listings.py "Fort Lee, NJ"     # 특정 동네만
```

- 표준 라이브러리만 사용 → **설치 불필요**(파이썬 3.8+만).
- 콘솔에 표 출력 + `listings.csv`, `listings.json` 저장.
- MLS 접두 **26=2026(최신)**, 25=2025 순으로 정렬, DOM(시장 체류일) 오름차순.

## B. 로컬 Claude Code용 MCP (형이 "매물 뽑아줘" 하면 Claude가 직접 조회)

```bash
pip3 install "mcp[cli]"
cd real-estate/fortlee/tools
claude mcp add realestate -- python3 "$(pwd)/redfin_mcp.py"
# Claude Code에서 /mcp 로 'realestate' 연결 확인
```

이후 맥미니 Claude Code에서:
> "realestate로 Palisades Park 활성 2·3가구 뽑아줘"

도구: `search_multifamily(town)`, `search_town(town, uipt)`
(uipt: 1=단독 2=콘도 3=타운하우스 4=멀티패밀리)

## C. 진짜 실시간 MLS가 필요하면 (가장 정확)

Redfin 공개 데이터도 라이브지만, **NJMLS 원본**이 가장 정확하다. 두 가지 정공법:

1. **라이선스 에이전트의 NJMLS/IDX 계정** — 이 리포트가 넘긴 MLS 번호로 30초 확인.
2. **키 기반 API를 이 MCP에 붙이기**(원하면 Claude가 코드 추가):
   - **RentCast** (`app.rentcast.io`) — 무료 티어, 매물·렌트 추정(AVM)·comps
   - **ATTOM Data** — 물건 상세·세금·소유이력
   - **Bright Data / Apify** Zillow·Redfin 액터 — 대량·안정적 스크레이핑
   키를 발급받아 알려주면 `redfin_mcp.py`에 소스 하나 더 추가해준다.

## 파라미터 튜닝

결과가 0건이면 `fetch_listings.py` 상단에서:
- `MARKETS` (Redfin 마켓 슬러그; 버건카운티는 보통 `new-york` 메트로)
- `status=9`(활성) → 다른 상태값
- `uipt=4`(멀티패밀리) → `1,2,3` 등

> ⚠️ 개인 리서치용. 상업적 재배포 금지. 최종 매수 판단 전 반드시 에이전트·인스펙터·회계사 확인.
