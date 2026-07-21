# 포트리(Fort Lee, NJ) 온누리교회 도보권 멀티패밀리 매입·순수익 분석

부모님 노후 대비를 위한 **뉴저지 포트리 2가구(멀티패밀리) 주택 매입** 의사결정 리포트.
공개 웹 데이터(2026년 7월 기준) 기반의 인터랙티브 순수익 계산 모델.

## 목표 조건 (Steve)

| 항목 | 조건 |
|---|---|
| 위치 | 뉴저지 포트리 **온누리교회(1449 Anderson Ave) 도보권** |
| 예산 | ~$1,000,000 (협상) |
| 자금 | 현금 최대 **$750,000**, 나머지 모기지 |
| 유형 | **멀티패밀리(2가구)** — 한 층 렌트, 한 층 거주 |
| 명의 | 65세+ 부모님 → **시니어 세금 혜택** 활용 |
| 순수익 | 렌트아웃 후 **월 +$1,000 이상** (노후 대비) |

## 핵심 결론

- 기존 예시였던 `1154`/`1612 Anderson` 계열은 outdated 리스크가 확인됨. 2026-07-21 live scrape 기준 1순위 active-like lead는 `439 Bergen Blvd, Palisades Park`($925k, 교회 직선 0.34mi)이며 공식 MLS/RentCast/Bridge 재확정 필요.
- **$1M을 다 쓰면 목표 미달.** 포트리 재산세가 **연 2.11%(~$21k)**라 렌트 한 층으로는 적자에 가까움.
- **$925k 이하 협상 매입 + 좋은 층 월 $3,500~3,700 렌트 + 시니어 혜택(StayNJ 등)** 조합이면 목표 가능성이 생긴다. 단, 후보 매물 Active/Legal 2-family 여부 확정 전 매입 후보로 확정 금지.
- 부모님은 이와 별개로 **거주비(월 ~$3,000)까지 절약**.

## 반드시 확인할 리스크

1. **맨션세 1%** — $1M 이상 매입 시 $10,000 추가. $1M 미만으로 협상.
2. **매입 후 재평가** — 실제 세금 고지서 확인 필수.
3. **렌트컨트롤·임대등록·CO** — 포트리 시청 확인.
4. **년식** — 1905년 등 노후 주택은 인스펙션·수선충당 상향.
5. **시니어 혜택 타이밍** — 1년차는 혜택 없음(직전 1년 소유·거주 요건), 2년차부터 적용.

## 파일

- `index.html` — 인터랙티브 리포트 (매입가·렌트·금리·시니어 혜택 조정 → 실시간 월 순수익). 단일 HTML, 외부 의존성 없음.

## 배포

정적 HTML 한 파일. 로컬은 브라우저로 `index.html`을 열면 되고,
GitHub Pages / Vercel / Netlify에 이 폴더를 그대로 올리면 배포됨.

## 출처 (2026-07 조회)

- [뉴저지 온누리교회](http://vision.onnuri.org/nj/) · [Redfin 포트리 멀티패밀리](https://www.redfin.com/city/6283/NJ/Fort-Lee/multi-family-homes-for-sale) · [Walk Score](https://www.walkscore.com/score/anderson-ave-and-whiteman-st-fort-lee-nj-07024)
- [Fort Lee 재산세율](https://propertytaxbystate.com/new-jersey/bergen-county/fort-lee) · [Apartments.com 렌트](https://www.apartments.com/fort-lee-nj/2-bedrooms/)
- [NJ Stay NJ](https://www.nj.gov/treasury/taxation/staynj/index.shtml) · [Senior Freeze](https://www.nj.gov/treasury/taxation/ptr/eligibility.shtml)

> ⚠️ 추정 모델입니다. 최종 판단 전 부동산 에이전트·모기지 브로커·회계사·홈 인스펙터 확인 필요.
