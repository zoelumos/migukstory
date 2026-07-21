#!/usr/bin/env python3
"""
rentcast_listings.py — RentCast API로 '진짜 최신 status' 매물 수집 (권장 소스).

왜 이걸 쓰나:
  Zillow/Redfin 스니펫은 캐시가 낡아 팔린 매물이 '판매중'으로 섞인다(우리가 계속 당한 문제).
  RentCast는 매물마다 status(Active/Pending/...)·daysOnMarket·mlsNumber를 주고 매일 갱신하며,
  라이선스 없이 무료 50건/월로 쓸 수 있다. 이게 형이 직접 최신 데이터를 얻는 가장 현실적 방법.

준비:
  1) https://www.rentcast.io/api 에서 무료 키 발급(50건/월)
  2) 맥미니 터미널:  export RENTCAST_API_KEY="발급받은키"
  3) python3 rentcast_listings.py            # 기본 6개 동네, 멀티패밀리, Active
     python3 rentcast_listings.py "Fort Lee"

출력: 콘솔 표 + rentcast_listings.json / .csv
필드: status · daysOnMarket · mlsNumber · price · beds/baths · year · address

⚠️ 무료 티어는 월 50건이라 동네당 1콜(6콜)로 아껴 씀. 도보권만 보려면 인자로 "Fort Lee"만.
"""
import os, sys, json, csv, urllib.request, urllib.parse

API = "https://api.rentcast.io/v1/listings/sale"
KEY = os.environ.get("RENTCAST_API_KEY", "").strip()

TOWNS = [  # (city, state)
    ("Fort Lee", "NJ"), ("Palisades Park", "NJ"), ("Cliffside Park", "NJ"),
    ("Ridgefield", "NJ"), ("Leonia", "NJ"), ("Edgewater", "NJ"),
]


def fetch(city, state, status="Active", ptype="Multi-Family", limit=100):
    q = urllib.parse.urlencode({
        "city": city, "state": state, "status": status,
        "propertyType": ptype, "limit": limit,
    })
    req = urllib.request.Request(f"{API}?{q}", headers={
        "X-Api-Key": KEY, "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def norm(x, town):
    return {
        "town": town,
        "address": x.get("formattedAddress", ""),
        "price": x.get("price", ""),
        "beds": x.get("bedrooms", ""),
        "baths": x.get("bathrooms", ""),
        "sqft": x.get("squareFootage", ""),
        "year_built": x.get("yearBuilt", ""),
        "property_type": x.get("propertyType", ""),
        "status": x.get("status", ""),
        "dom": x.get("daysOnMarket", ""),
        "listed_date": (x.get("listedDate") or "")[:10],
        "mls": x.get("mlsNumber", ""),
        "mls_name": x.get("mlsName", ""),
    }


def money(v):
    try:
        return "$" + format(int(float(v)), ",")
    except Exception:
        return str(v) if v else "?"


def main():
    if not KEY:
        sys.exit("환경변수 RENTCAST_API_KEY 가 없습니다. "
                 "https://www.rentcast.io/api 에서 무료 키 발급 후:\n"
                 '  export RENTCAST_API_KEY="키"')
    towns = [(sys.argv[1], "NJ")] if len(sys.argv) > 1 else TOWNS
    rows = []
    for city, state in towns:
        try:
            data = fetch(city, state)
            got = [norm(x, city) for x in (data or [])]
            rows.extend(got)
            print(f"  ✓ {city:16s} Active 멀티패밀리 {len(got)}건")
        except urllib.error.HTTPError as e:
            print(f"  ✗ {city:16s} HTTP {e.code} ({e.reason}) "
                  f"— 키/쿼터 확인", file=sys.stderr)
        except Exception as e:
            print(f"  ✗ {city:16s} {e}", file=sys.stderr)

    rows.sort(key=lambda r: (r["dom"] if isinstance(r["dom"], int) else 9999))
    with open("rentcast_listings.json", "w") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    if rows:
        with open("rentcast_listings.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader(); w.writerows(rows)

    print(f"\n총 {len(rows)}건 (rentcast_listings.csv/.json 저장)\n")
    print(f"{'STATUS':<9}{'MLS#':>11}  {'동네':<13}{'가격':>11} {'침/욕':>6} {'년식':>5}{'DOM':>5}  주소")
    print("-" * 100)
    for r in rows:
        print(f"{(r['status'] or '?'):<9}{str(r['mls'] or '?'):>11}  "
              f"{r['town'][:12]:<13}{money(r['price']):>11} "
              f"{str(r['beds'] or '?')+'/'+str(r['baths'] or '?'):>6} "
              f"{str(r['year_built'] or '?'):>5}{str(r['dom'] or '?'):>5}  {r['address']}")
    print("\n✅ status/DOM/MLS# 는 RentCast가 매일 갱신 — Active 만 보이므로 "
          "계약중/매각은 자동 제외됩니다. 최종 확정은 에이전트 NJMLS 권장.")


if __name__ == "__main__":
    main()
