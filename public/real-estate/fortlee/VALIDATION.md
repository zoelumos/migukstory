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
