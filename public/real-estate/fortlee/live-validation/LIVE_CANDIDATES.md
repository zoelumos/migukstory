# Live Listing Validation — Fort Lee Onnuri multifamily leads

검증 시각: **2026-07-21 19:56 UTC**  
기준점: **Onnuri / 1449 Anderson Ave, Fort Lee, NJ 07024**

## 결론

헤드리스/우회 수집 결과, 기존 리포트의 가장 큰 리스크인 **매물 outdated 문제는 실제로 확인**됐다.

- Redfin 검색 결과 HTML embedded cards에서는 최신 active-like 후보가 수집됨.
- Redfin 상세 페이지는 CloudFront WAF challenge(`x-amzn-waf-action: challenge`, 202 + 0 byte)로 차단됨.
- Zillow는 403, Realtor는 429, Redfin 브라우저는 robot page.
- NJMLS advanced search/AJAX endpoint는 접근은 되지만 listing rows 대신 “No listings found” fragment만 반환. 즉 공식 Active 확정에는 로그인/에이전트 MLS 또는 RESO/RentCast 필요.
- 따라서 아래 후보는 **확정 Active가 아니라 “Redfin live search에 뜬 Active-like lead”**로 표기한다.

## 도보권/예산권 우선 후보

| 후보 | 가격 | Beds/Baths | 직선거리 | 도보추정 | 등급 | MLS-like source ids | Broker | 링크 |
|---|---:|---|---:|---:|---|---|---|---|
| 439 Bergen Blvd, Palisades Park, NJ 07650 | $925,000 | 5 beds / 3 baths | 0.34 mi | ~7-8 min | A 도보권 | 26021560,26023005 | Corcoran Infinity Properties, (201) 768-6868 | [Redfin](https://www.redfin.com/NJ/Palisades-Park/439-Bergen-Blvd-07650/home/35816935) |
| 304 E Palisades Blvd, Palisades Park, NJ 07650 | $1,190,000 | 4 beds / 3.5 baths | 0.51 mi | ~10-12 min | A 도보권 | 26023005,26023510 | Realmart Realty, LLC, (888) 362-6543 | [Redfin](https://www.redfin.com/NJ/Palisades-Park/304-E-Palisades-Blvd-07650/home/202354130) |
| 261 10th St, Palisades Park, NJ 07650 | $1,249,995 | 6 beds / 3 baths | 0.63 mi | ~13-15 min | A 도보권 | 26023316,26023510 | The Agency One Rock-Paramus, (201) 975-4141 | [Redfin](https://www.redfin.com/NJ/Palisades-Park/261-10th-St-07650/home/35816744) |
| 414 Lafayette Ave, Cliffside Park, NJ 07010 | $859,000 | 4 beds / 3.5 baths | 1.2 mi | ~24-29 min | B 긴 도보/짧은 차량 | 26021560 | Royal Signature Realty, LLC, (201) 943-9400 | [Redfin](https://www.redfin.com/NJ/Cliffside-Park/414-Lafayette-Ave-07010/home/202197591) |
| 281 Marion Ave, Cliffside Park, NJ 07010 | $899,000 | 5 beds / 2 baths | 1.13 mi | ~23-27 min | B 긴 도보/짧은 차량 | 26020258 | Top Realty, (201) 917-5366 | [Redfin](https://www.redfin.com/NJ/Cliffside-Park/281-Marion-Ave-07010/home/35690574) |
| 432 9th St, Fairview, NJ 07022 | $799,000 | 4 beds / 3 baths | 1.92 mi | ~38-46 min | D 도보권 아님 | 26021642,26024497 | Coldwell Banker, Hillsdale, (201) 930-8820 | [Redfin](https://www.redfin.com/NJ/Fairview/432-9th-St-07022/home/35732379) |
| 393 Washington Ave, Cliffside Park, NJ 07010 | $899,000 | 3 beds / 3.5 baths | 1.5 mi | ~30-36 min | C 차량 5분권 | 26020207 | Weichert Realtors, Tenafly-Cresskill, (201) 569-7888 | [Redfin](https://www.redfin.com/NJ/Cliffside-Park/393-Washington-Ave-07010/home/35688469) |
| 516 Anderson Ave, Cliffside Park, NJ 07010 | $1,150,000 | — beds / — baths | 1.81 mi | ~36-43 min | D 도보권 아님 | 26020243,26020540 | Royal Signature Realty, LLC, (201) 943-9400 | [Redfin](https://www.redfin.com/NJ/Cliffside-Park/516-Anderson-Ave-07010/home/82729713) |

## Steve 기준으로 바로 볼 것

1. **439 Bergen Blvd, Palisades Park — $925k — A 도보권 — 0.34mi**  
   기존 리포트의 MLS 번호와 최신 Redfin 카드 source id가 불일치한다. 오래된 자료 리스크가 실제 확인됨. 그래도 위치/가격은 현재 조건상 1순위 live lead.
2. **304 E Palisades Blvd — $1.19M — A 도보권 — 0.51mi**  
   예산 초과지만 협상/수익형 구조 검토 리드.
3. **261 10th St — $1.249995M — A 도보권 — 0.63mi**  
   예산 초과. legal units/임대수익 확인 필요.
4. **414 Lafayette / 281 Marion — $859k~$899k — B 긴 도보/차량 5분권**  
   가격은 좋지만 Cliffside Park라 도보권은 약함. 기존 리포트의 “클리프사이드 1순위” 전략과 일치.

## 검증 등급 정의

- **A 도보권:** 직선거리 0.75mi 이하. 실제 도보는 지도 경로로 재확인 필요.
- **B 긴 도보/짧은 차량:** 0.75~1.25mi.
- **C 차량 5분권:** 1.25~1.75mi.
- **D 도보권 아님:** 1.75mi 초과.

## 공식 확정에 필요한 다음 데이터

- NJMLS/에이전트 화면에서 MLS# 기준 Active/Pending/Sold 확인.
- 또는 RentCast active subscription / Bridge RESO NJMLS dataset 권한.
- Redfin card만으로 계약상태를 확정하지 말 것.

## Artifacts

- JSON: `/real-estate/fortlee/live-validation/redfin-live-candidates-scored.json`
- CSV: `/real-estate/fortlee/live-validation/redfin-live-candidates-scored.csv`
- Raw JSON: `/real-estate/fortlee/live-validation/redfin-live-candidates-raw.json`
