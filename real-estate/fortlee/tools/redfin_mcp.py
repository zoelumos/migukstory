#!/usr/bin/env python3
"""
redfin_mcp.py — 맥미니 로컬 Claude Code용 부동산 MCP 서버(선택).

형 맥미니의 Claude Code에서 "포트리 2가구 활성 매물 뽑아줘"라고 하면
이 MCP가 Redfin 라이브 데이터를 직접 조회한다. (클라우드 세션은 프록시 차단이라 불가,
맥미니 로컬 네트워크에선 동작.)

설치 (맥미니 터미널):
  pip3 install "mcp[cli]"
  # 이 폴더에서:
  claude mcp add realestate -- python3 "$(pwd)/redfin_mcp.py"
  # 이후 Claude Code에서: /mcp 로 'realestate' 연결 확인

제공 도구:
  search_multifamily(town)  -> 해당 동네 활성 멀티패밀리(2·3가구) 리스트
  search_town(town, uipt)   -> 임의 property type (1=단독 2=콘도 3=타운 4=멀티)
"""
import json
try:
    from mcp.server.fastmcp import FastMCP
except Exception as e:
    raise SystemExit("먼저 설치: pip3 install 'mcp[cli]'  ("+str(e)+")")

import fetch_listings as F  # 같은 폴더의 수집 로직 재사용

mcp = FastMCP("realestate")


def _pull(town, uipt="4"):
    F.UIPT_MULTIFAMILY = uipt
    rid, rtype, name = F.resolve_region(town)
    rows = F.parse(F.fetch_csv(rid, rtype), name)
    def sk(r):
        yr = (r["mls"] or "")[:2]; yr = int(yr) if yr.isdigit() else 0
        try: dom = int(r["dom"])
        except Exception: dom = 9999
        return (-yr, dom)
    rows.sort(key=sk)
    return rows


@mcp.tool()
def search_multifamily(town: str) -> str:
    """동네(예: 'Fort Lee, NJ')의 현재 활성 2·3가구 매물을 JSON으로 반환.
    MLS#(25=2025/26=2026), 가격, 침실/욕실, 년식, DOM, 상태, URL 포함."""
    rows = _pull(town, "4")
    return json.dumps({"town": town, "count": len(rows), "listings": rows},
                      ensure_ascii=False, indent=2)


@mcp.tool()
def search_town(town: str, uipt: str = "4") -> str:
    """임의 property type 검색. uipt: 1=단독,2=콘도,3=타운하우스,4=멀티패밀리."""
    rows = _pull(town, uipt)
    return json.dumps({"town": town, "uipt": uipt, "count": len(rows),
                       "listings": rows}, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    mcp.run()
