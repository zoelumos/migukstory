# Live validation update — 2026-07-21 19:56 UTC

**최신 헤드리스/우회 수집 완료.** Redfin 검색 HTML embedded cards 기준 active-like 후보 24건, 예산권/근거리 후보 8건을 추출했다. 단, Redfin detail은 WAF challenge, Zillow 403, Realtor 429, NJMLS AJAX는 rows 미반환이므로 **공식 Active 확정은 아님**.

핵심 발견:

- **439 Bergen Blvd, Palisades Park — $925,000 — 0.34mi from church — Redfin live search card present.** 현재 조건상 1순위 live lead.
- 기존 리포트의 439 Bergen MLS/source id와 최신 Redfin card의 source id가 불일치해서 **outdated 리스크가 실제 확인됨**.
- Fort Lee proper sub-$1M 2-4 family는 공개 수집상 확인되지 않음.
- 도보권 active-like lead는 Palisades Park 쪽에 집중됨: 439 Bergen, 304 E Palisades, 261 10th.

자세한 표: [LIVE_CANDIDATES.md](./live-validation/LIVE_CANDIDATES.md)

---

# Fort Lee Real Estate Live Validation Status

Updated: 2026-07-21

## Deployment

Static visual report deployed under `/real-estate/fortlee/`.

## Biggest risk

The largest issue is **outdated listing status**. Web snippets and Claude artifacts can show sold or pending properties as active. Use only sources with explicit `status`, `daysOnMarket`, and `mlsNumber` fields for final candidate screening.

## Best data path

1. **NJMLS / RESO feed via licensed agent** — best and legally authoritative.
2. **Bridge Interactive RESO API** — best if Steve's token has NJMLS/Bergen dataset approval. Run `bridge_listings.py --datasets` first.
3. **RentCast API** — best non-MLS consumer-friendly fallback. Needs active subscription/API key; current test returned inactive subscription / missing GitHub secret.
4. **Redfin GIS CSV** — useful free cross-check, but unofficial.
5. **Zillow MCP** — useful for Zestimate/photos/saved searches; not primary source for active/pending/sold validation.

## MCP/skill recommendation

- Prefer the repo-local `real-estate/fortlee/tools/redfin_mcp.py` for a controlled MCP wrapper.
- Add RentCast as a tool only after an active `RENTCAST_API_KEY` is stored as an environment variable or GitHub secret.
- Do not rely on generic Zillow scraping MCPs as the source of truth for purchase decisions.

## Live validation attempt log

- 2026-07-21: RentCast direct API test returned subscription inactive / GitHub Actions secret missing, so no live RentCast listing validation completed.
- 2026-07-21: Repo Redfin GIS CSV tool was run for Fort Lee, Palisades Park, and Cliffside Park from this environment; all returned HTTP 403.
- Therefore the deployed report intentionally downgrades property rows to **leads**, not verified active candidates.
