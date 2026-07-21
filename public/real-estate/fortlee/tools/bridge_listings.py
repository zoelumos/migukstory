#!/usr/bin/env python3
"""
bridge_listings.py — Bridge Interactive(Zillow Group) API로 MLS 매물 조회.

Bridge는 RESO Web API로 MLS 데이터를 준다. status(StandardStatus)·DaysOnMarket·
ListingId(MLS#) 포함이라 '최신'을 신뢰할 수 있다. 단 **데이터셋별 MLS 승인**이 필요 —
형 Server Token이 NJMLS 데이터셋에 승인돼 있어야 뉴저지 매물이 나온다.

🔐 보안: 토큰을 코드/레포에 저장하지 말 것. 환경변수로만 넣는다.
  export BRIDGE_SERVER_TOKEN="ce9175...(형 Server Token)"
  export BRIDGE_DATASET="njmls"      # ← 실제 데이터셋 이름(대시보드에서 확인)

사용:
  python3 bridge_listings.py --datasets           # 내 토큰이 접근 가능한 데이터셋 목록
  python3 bridge_listings.py                       # 기본 6개 동네 Active 멀티패밀리
  python3 bridge_listings.py "Fort Lee"            # 특정 동네

동작 안 하면 십중팔구 (a) 토큰 오타, (b) BRIDGE_DATASET 이름 틀림, (c) 그 데이터셋에
NJMLS가 없음. --datasets 로 접근 가능 목록부터 확인.
"""
import os, sys, json, csv, urllib.request, urllib.parse, urllib.error

BASE = "https://api.bridgedataoutput.com/api/v2"
TOKEN = os.environ.get("BRIDGE_SERVER_TOKEN", "").strip()
DATASET = os.environ.get("BRIDGE_DATASET", "").strip()

TOWNS = ["Fort Lee", "Palisades Park", "Cliffside Park", "Ridgefield", "Leonia", "Edgewater"]


def _get(url):
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {TOKEN}", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def list_datasets():
    """토큰이 접근 가능한 데이터셋(=MLS) 목록."""
    return _get(f"{BASE}/datasets")


def fetch_town(city, top=100):
    """RESO OData Property 조회: Active + 멀티패밀리(수익형) + 해당 city."""
    filt = (f"StandardStatus eq 'Active' and City eq '{city}' and "
            f"PropertyType eq 'Residential Income'")
    q = urllib.parse.urlencode({
        "access_token": TOKEN,
        "$filter": filt,
        "$top": top,
        "$select": ("ListingId,ListingKey,UnparsedAddress,City,ListPrice,"
                    "BedroomsTotal,BathroomsTotalInteger,LivingArea,YearBuilt,"
                    "StandardStatus,DaysOnMarket,PropertyType,PropertySubType"),
    })
    url = f"{BASE}/OData/{DATASET}/Property?{q}"
    data = _get(url)
    return data.get("value", data if isinstance(data, list) else [])


def norm(x, town):
    return {
        "town": town,
        "address": x.get("UnparsedAddress", ""),
        "price": x.get("ListPrice", ""),
        "beds": x.get("BedroomsTotal", ""),
        "baths": x.get("BathroomsTotalInteger", ""),
        "sqft": x.get("LivingArea", ""),
        "year_built": x.get("YearBuilt", ""),
        "status": x.get("StandardStatus", ""),
        "dom": x.get("DaysOnMarket", ""),
        "mls": x.get("ListingId", ""),
        "subtype": x.get("PropertySubType", ""),
    }


def money(v):
    try:
        return "$" + format(int(float(v)), ",")
    except Exception:
        return str(v) if v else "?"


def main():
    if not TOKEN:
        sys.exit('환경변수 BRIDGE_SERVER_TOKEN 없음.\n  export BRIDGE_SERVER_TOKEN="..."')

    if "--datasets" in sys.argv:
        try:
            d = list_datasets()
            print(json.dumps(d, ensure_ascii=False, indent=2)[:4000])
            print("\n↑ 여기서 NJMLS/버건 데이터셋의 'name'을 골라 "
                  'export BRIDGE_DATASET="그이름" 하세요.')
        except urllib.error.HTTPError as e:
            print(f"HTTP {e.code} {e.reason} — 토큰 확인. 본문: {e.read()[:300]}",
                  file=sys.stderr)
        return

    if not DATASET:
        sys.exit('환경변수 BRIDGE_DATASET 없음. 먼저:  python3 bridge_listings.py --datasets')

    towns = [sys.argv[1]] if (len(sys.argv) > 1 and not sys.argv[1].startswith("-")) else TOWNS
    rows = []
    for t in towns:
        try:
            got = [norm(x, t) for x in fetch_town(t)]
            rows.extend(got)
            print(f"  ✓ {t:16s} Active 멀티패밀리 {len(got)}건")
        except urllib.error.HTTPError as e:
            body = e.read()[:200].decode("utf-8", "replace")
            print(f"  ✗ {t:16s} HTTP {e.code} {e.reason} — "
                  f"{'데이터셋/승인 확인' if e.code in (401,403,404) else body}",
                  file=sys.stderr)
        except Exception as e:
            print(f"  ✗ {t:16s} {e}", file=sys.stderr)

    rows.sort(key=lambda r: (r["dom"] if isinstance(r["dom"], int) else 9999))
    with open("bridge_listings.json", "w") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    if rows:
        with open("bridge_listings.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader(); w.writerows(rows)

    print(f"\n총 {len(rows)}건 (bridge_listings.csv/.json 저장)\n")
    print(f"{'STATUS':<9}{'MLS#':>11}  {'동네':<13}{'가격':>11} {'침/욕':>6}{'년식':>6}{'DOM':>5}  주소")
    print("-" * 100)
    for r in rows:
        print(f"{(r['status'] or '?'):<9}{str(r['mls'] or '?'):>11}  "
              f"{r['town'][:12]:<13}{money(r['price']):>11} "
              f"{str(r['beds'] or '?')+'/'+str(r['baths'] or '?'):>6}"
              f"{str(r['year_built'] or '?'):>6}{str(r['dom'] or '?'):>5}  {r['address']}")
    print("\n✅ Bridge=RESO Web API. StandardStatus/DaysOnMarket/ListingId 는 MLS 원본. "
          "결과 0건이면 BRIDGE_DATASET에 NJMLS가 포함됐는지 --datasets 로 확인.")


if __name__ == "__main__":
    main()
