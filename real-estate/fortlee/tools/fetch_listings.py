#!/usr/bin/env python3
"""
fetch_listings.py — 맥미니(또는 일반 네트워크)에서 실행하는 라이브 매물 수집기.

포트리 온누리교회 프로젝트용. Redfin의 공개 gis-csv 엔드포인트를 이용해
Fort Lee / Palisades Park / Cliffside Park / Ridgefield / Leonia / Edgewater 의
현재 활성(active) 멀티패밀리(2·3가구) 매물을 CSV로 받아 정리한다.

⚠️ 왜 로컬(맥미니)에서 돌려야 하나:
  이 스크립트를 작성한 Claude의 클라우드 컨테이너는 정책 프록시가 redfin.com 을
  차단(403)해서 거기서는 못 돈다. 형 맥미니처럼 차단 없는 네트워크에서는 정상 동작한다.

의존성: 표준 라이브러리만 사용(requests 불필요). 파이썬 3.8+.

사용법:
  python3 fetch_listings.py                 # 기본 6개 동네, 멀티패밀리
  python3 fetch_listings.py "Fort Lee, NJ"  # 특정 동네만
  결과: 콘솔 표 + listings.csv + listings.json 저장

MLS 접두 25=2025년 / 26=2026년(최신). DAYS ON MARKET, STATUS, URL, MLS# 포함.
최종 판단 전 라이선스 에이전트가 NJMLS로 재확인할 것.
"""
import json, sys, csv, io, time, urllib.request, urllib.parse

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

TOWNS = [
    "Fort Lee, NJ", "Palisades Park, NJ", "Cliffside Park, NJ",
    "Ridgefield, NJ", "Leonia, NJ", "Edgewater, NJ",
]

# Redfin property-type ids: 1=House 2=Condo 3=Townhouse 4=Multi-Family 5=Land 6=Other
UIPT_MULTIFAMILY = "4"
# Redfin markets to try (Bergen County sits in the NY metro market on Redfin)
MARKETS = ["new-york", "newjersey", "northern-nj"]


def _get(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept": "text/csv,application/json,*/*",
        "Accept-Language": "en-US,en;q=0.9",
    })
    with urllib.request.urlopen(req, timeout=45) as r:
        return r.read().decode("utf-8", "replace")


def resolve_region(town):
    """동네 이름 -> (region_id, region_type). Redfin autocomplete 사용."""
    q = urllib.parse.quote(town)
    url = f"https://www.redfin.com/stingray/do/location-autocomplete?location={q}&v=2&al=1"
    raw = _get(url)
    if raw.startswith("{}&&"):
        raw = raw[4:]
    data = json.loads(raw)
    for sec in data.get("payload", {}).get("sections", []) or []:
        for row in sec.get("rows", []) or []:
            rid = row.get("id", "")           # e.g. "6_6283"  ->  type_id
            if "_" in rid:
                rtype, rnum = rid.split("_", 1)
                if rtype == "6":              # 6 = place/city
                    return rnum, rtype, row.get("name", town)
    raise RuntimeError(f"region not found for {town!r}")


def fetch_csv(region_id, region_type):
    for market in MARKETS:
        url = ("https://www.redfin.com/stingray/api/gis-csv?al=1"
               f"&market={market}&num_homes=350&ord=days-on-redfin-asc"
               f"&page_number=1&region_id={region_id}&region_type={region_type}"
               f"&status=9&uipt={UIPT_MULTIFAMILY}&v=8")
        try:
            body = _get(url)
        except Exception as e:
            continue
        if body.lstrip().upper().startswith("SALE TYPE") or "ADDRESS" in body[:200].upper():
            return body
    return ""  # no market returned rows


def parse(body, town):
    out = []
    for row in csv.DictReader(io.StringIO(body)):
        addr = (row.get("ADDRESS") or "").strip()
        if not addr:
            continue
        out.append({
            "town": town,
            "address": addr,
            "city": row.get("CITY", ""),
            "price": row.get("PRICE", ""),
            "beds": row.get("BEDS", ""),
            "baths": row.get("BATHS", ""),
            "sqft": row.get("SQUARE FEET", ""),
            "year_built": row.get("YEAR BUILT", ""),
            "dom": row.get("DAYS ON MARKET", ""),
            "status": row.get("STATUS", ""),
            "property_type": row.get("PROPERTY TYPE", ""),
            "mls": row.get("MLS#", ""),
            "url": row.get("URL", "") or row.get(
                "URL (SEE https://www.redfin.com/buy-a-home/comparative-market-analysis FOR INFO ON PRICING)", ""),
        })
    return out


def money(v):
    try:
        return "$" + format(int(float(v)), ",")
    except Exception:
        return v or "?"


def main():
    towns = [sys.argv[1]] if len(sys.argv) > 1 else TOWNS
    allrows = []
    for t in towns:
        try:
            rid, rtype, name = resolve_region(t)
            body = fetch_csv(rid, rtype)
            rows = parse(body, name)
            print(f"  ✓ {name:20s} region={rid}  멀티패밀리 {len(rows)}건")
            allrows.extend(rows)
            time.sleep(1.0)  # 예의상 딜레이
        except Exception as e:
            print(f"  ✗ {t:20s} 실패: {e}", file=sys.stderr)

    # MLS 접두(연도)로 최신 우선 정렬, 그다음 DOM 오름차순
    def sortkey(r):
        mls = (r["mls"] or "")
        yr = mls[:2] if mls[:2].isdigit() else "00"
        try:
            dom = int(r["dom"])
        except Exception:
            dom = 9999
        return (-int(yr), dom)
    allrows.sort(key=sortkey)

    with open("listings.json", "w") as f:
        json.dump(allrows, f, ensure_ascii=False, indent=2)
    if allrows:
        with open("listings.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(allrows[0].keys()))
            w.writeheader(); w.writerows(allrows)

    print(f"\n총 {len(allrows)}건 (listings.csv / listings.json 저장)\n")
    print(f"{'MLS#':>10}  {'동네':<14} {'가격':>11}  {'침/욕':>6}  {'년식':>5} {'DOM':>4}  주소")
    print("-" * 96)
    for r in allrows:
        print(f"{r['mls']:>10}  {r['town'][:13]:<14} {money(r['price']):>11}  "
              f"{(r['beds'] or '?')+'/'+(r['baths'] or '?'):>6}  {r['year_built'] or '?':>5} "
              f"{r['dom'] or '?':>4}  {r['address']}, {r['city']}")
    print("\n⚠️ Redfin 공개 데이터 기반. 최종 확인은 라이선스 에이전트가 NJMLS로. "
          "결과 0건이면 MARKETS 리스트나 status/uipt 파라미터를 조정하세요.")


if __name__ == "__main__":
    main()
