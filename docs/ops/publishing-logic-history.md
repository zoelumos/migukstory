# Migukstory publishing logic history

_Last updated: 2026-06-27_

This document records how Migukstory posts were generated, reviewed, queued, published, deployed, and indexed.

- **Part 1 — Legacy local Hermes cron pipeline** (paused 2026-06-27): the staged RSS → draft → editor-gate → queue → capped-publish system. This is everything from "Current automation status" down to "How to restart safely later." It is paused, not deleted; the design lessons still apply.
- **Part 2 — Cloud routine automation** (active from 2026-06-27): see the new section ["2026-06-27 — Cloud routine automation"](#2026-06-27--cloud-routine-automation-replaces-local-hermes-cron) below. This is what actually runs now.

> ⚠️ The two systems use **different safety models**. The legacy pipeline gated every post behind `editor_grade.py` (≥70/100), a `drafts/`→`queue/` separation, and a per-run publish cap. The new cloud writer routine publishes directly to `main` from a single session with only in-prompt guardrails. The reconciliation work is tracked in the new section.

## Current automation status

As of 2026-06-26 evening, all Migukstory Hermes cron jobs are paused.

Paused jobs:

| Job | Purpose | Script |
| --- | --- | --- |
| `migukstory-daily-ingest` | Daily RSS/topic ingestion, Claude drafting, Claude editing, queue promotion | `migukstory-daily-ingest.sh` |
| `migukstory-daily-editorial-review` | Follow-up editorial QA | `migukstory-daily-editorial-review.sh` |
| `migukstory-daily-health` | Daily site/automation health check | `migukstory-daily-health.sh` |
| `migukstory-weekly-audit` | Weekly site audit | `migukstory-weekly-audit.sh` |
| `migukstory-monthly-cf-rotate` | Monthly Cloudflare-related maintenance | `migukstory-monthly-cf-rotate.sh` |
| `migukstory-daily-publish` | Publish approved `queue/` items through GitHub Actions | `migukstory-daily-publish.sh` |
| `migukstory-daily-index` | Scheduled indexing submission/status | `migukstory-daily-index.sh` |
| `migukstory-urgent-ingest` | Afternoon urgent/high-impact Tier-1 ingest | `migukstory-urgent-ingest.sh` |
| `migukstory-daily-automerge` | Auto-merge approved automation PRs | `migukstory-daily-automerge.sh` |
| `Migukstory deploy failure Claude fallback` | Watch failed deploys and ask Claude to diagnose | `migukstory-deploy-failure-claude-fallback.sh` |
| `migukstory-drafts-backlog-grade` | Re-grade existing drafts backlog and promote only passing drafts | `migukstory-drafts-backlog-grade.sh` |

No **legacy Hermes** automation should run unless these jobs are explicitly resumed. Note that this no longer means "nothing runs" — the cloud routines in Part 2 below are now the active automation.

## 2026-06-27 — Cloud routine automation (replaces local Hermes cron)

From 2026-06-27, automation moved off the local macOS/Hermes cron jobs onto **claude.ai cloud routines** (managed via the `RemoteTrigger` API / <https://claude.ai/code/routines>). These run in Anthropic-hosted sandboxes on a UTC cron, independent of Steve's machine being on. Each routine clones the repo, runs one Claude session, and exits.

Shared config: environment `Zoe` (`env_01MxfKHroyfCdxNo9BbvmFFA`), model `claude-sonnet-4-6`, source `github.com/zoelumos/migukstory` (auditors also clone their own client repos).

### Active routines

| Time (ET) | Cron (UTC) | Routine | Repo writes? | Routine ID |
| --- | --- | --- | --- | --- |
| 06:00 | `0 10 * * *` | **migukstory — write + publish + index** | **Yes — pushes to `main`** | `trig_013HQUHq5Z2Db27SvjtuUAjm` |
| 09:00 | `0 13 * * *` | migukstory — SEO/content audit report | No (report only) | `trig_012SYNr3iKFiFD7LQjVUTP1D` |
| 09:10 | `10 13 * * *` | zoelumos.com — SEO/GEO/conversion audit | No | `trig_01Cu7qFyHfT9HLGeLEoNkt7V` |
| 09:20 | `20 13 * * *` | konacoffeedonut.com — local SEO audit | No | `trig_01F5WL5xFV9cGGnLAJNztCvN` |
| 09:30 | `30 13 * * *` | vitospizzaandristorante.com — restaurant/local SEO | No | `trig_01Hz1Tf9hDj9oTVDsdeV27QB` |
| 09:40 | `40 13 * * *` | tjflowersandevents.com — e-commerce/seasonal SEO | No | `trig_01GexNJritC689J8y3rTNGKU` |

Only the **06:00 writer** mutates the repo. The five audit routines are read-only and emit a Korean report into the routine's session log (no commits).

> Cron is fixed UTC. The ET times above hold during EDT (UTC−4). Under EST (Nov–Mar) every routine shifts one hour earlier (writer → 05:00 ET, etc.). Adjust the cron minute/hour if a year-round local time is required.

### Writer routine — how it publishes & indexes

```text
06:00 ET cloud session
  -> date + read existing src/content/blog (dedupe titles/slugs)
  -> pick topic (Korean-American search demand + timeliness)
  -> research official sources (IRS / USCIS / travel.state.gov / SSA / Fed) via WebSearch/WebFetch
  -> write 1 post to src/content/blog/<slug>.md in house frontmatter format
  -> best-effort `npm run build` schema check
  -> git push origin main
       ├─ Cloudflare Pages auto-deploys (live publish)
       └─ .github/workflows/google-index.yml triggers on src/content/** push
            -> notify_indexes.py --auto submits the new URL to Google Indexing API + IndexNow
  -> verify via `gh run list --workflow="Google Indexing"`; manual dispatch if not triggered
```

Indexing prerequisites (verified present 2026-06-27): repo secret `GSC_SERVICE_ACCOUNT` set, "Google Indexing" workflow active, `gh` authed as `zoelumos`. The cloud writer never handles the service-account key itself — indexing auth stays inside GitHub Actions.

### ⚠️ Design gap vs the legacy pipeline (open reconciliation item)

The cloud writer was set up in **direct-to-`main`, fully-automatic** mode at Steve's request. It does **not** yet reproduce the legacy safety model, and this contradicts several documented lessons below:

| Safety control | Legacy Hermes pipeline | Current cloud writer |
| --- | --- | --- |
| Editor gate | `editor_grade.py` ≥ 70/100 before promotion | **None** — only in-prompt guardrails |
| Draft/queue separation | `drafts/` → `queue/` → publish; "drafts must not publish directly" | **None** — writes straight into `src/content/blog` and pushes |
| Per-run / per-day cap | `POSTS_PER_RUN_CAP=4` (reduced from 10 to avoid thin-content bursts) | 1 post/run by prompt only |
| Improve pass | `improve_drafts.py` | None |
| Writing model | `claude-opus-4-8` | `claude-sonnet-4-6` |
| Claude-auth hard stop | "no auth → no fallback copy → no publish" | N/A (managed session) |

This is acceptable as a deliberate trade-off but should be revisited. Recommended hardening, cheapest first:

1. **In-session editor gate** — have the writer run `scripts/editor_grade.py` (or inline the rubric) on its own draft and *abort the push* if it scores < 70. Smallest change, keeps direct-publish.
2. **Route through `queue/` + `daily-post.yml`** — writer drops the file in `queue/`; the existing capped, validated publish workflow promotes it. Restores the full legacy gate with the new cloud author.
3. **PR mode** — writer opens a PR instead of pushing to `main`; Steve merges = publish. Strongest human gate for YMYL content.
4. Consider `claude-opus-4-8` for writing if quality on `sonnet-4-6` is insufficient.

Until one of these lands, **the daily output should be spot-checked manually** (see Known risks #1, #2, #7).

## High-level pipeline

The automation used a staged pipeline:

```text
RSS / Google News / official feeds
  -> candidate filtering and dedupe
  -> Claude Opus 4.8 draft generation
  -> Claude improve/validation pass
  -> Claude editor scoring
  -> drafts/ or queue/
  -> GitHub PR auto-merge
  -> daily-post.yml publishes queue -> src/content/blog
  -> Astro build
  -> Cloudflare Pages deploy
  -> RSS/sitemap/news-sitemap update
  -> IndexNow + Google Indexing / Search Console sitemap submit
```

Important rule: drafts were not supposed to publish directly. Only files promoted to `queue/` by the editor gate could enter the publish workflow.

## Source discovery logic

Primary source config:

```text
scripts/config/rss_sources.yml
```

Sources included:

- Federal Register / official agency feeds for immigration, IRS/tax, SSA/social-security.
- State Department travel advisories.
- CDC/FDA health feeds.
- Federal Reserve / BLS / NPR business feeds.
- TechCrunch AI / MIT Technology Review AI.
- IEEE Spectrum / Robot Report.
- Google News watches for practical Korean-American topics.

Recent category expansion added watches for:

- `education`: FAFSA, student aid, 529 plans, college admissions, student visa, international students.
- `consumer`: CFPB newsroom, CPSC product recalls, scams, identity theft, data breach, consumer protection.
- `community`: consular, passport, DMV, bank account immigrants.
- `real-estate`: property tax, rent, home insurance, first-time homebuyer.
- `tax`: state tax, self-employed tax, small business tax, estimated tax.

FTC RSS was tested and left disabled because public FTC RSS candidates returned broken/empty feeds on 2026-06-26.

## Category model

Current category schema lives in several places and must stay synchronized:

- `src/content.config.ts`
- `scripts/validate_markdown_frontmatter.py`
- `scripts/draft_from_rss.py`
- `src/utils/headlinePriority.ts`
- `src/components/Header.astro`
- `src/components/Footer.astro`
- `src/pages/category/[slug].astro`
- `scripts/config/rss_sources.yml`

Categories in use:

```text
immigration

tax

economy

ai

robotics

health

education

retirement

community

real-estate

consumer
```

`consumer` was added on 2026-06-26 as `사기·소비자보호` for scams, identity theft, data breaches, product recalls, CFPB/CPSC/FTC-style consumer protection topics.

## Candidate selection logic

Main script:

```text
scripts/draft_from_rss.py
```

Core selection rules:

1. Load enabled RSS sources from `scripts/config/rss_sources.yml`.
2. Skip invalid categories.
3. Canonicalize URLs and remove tracking params.
4. Deduplicate via `scripts/state/seen_urls.json`.
5. Score by category priority and urgency.
6. Favor Korean-American practical impact:
   - USCIS / green card / immigration status
   - IRS / tax deadlines / state tax
   - Medicare / ACA / insurance
   - Social Security / retirement / elder law / Medicaid planning
   - mortgage / housing affordability / property tax
   - scams / consumer protection / recalls
   - education / FAFSA / student visa
7. Keep economy, AI, and robotics as secondary categories only when tied to household finances, jobs, small business, investing/retirement, education/career, or automation risk.

Recent daily ingest caps before shutdown:

```text
--max-drafts 12
--max-per-category 3
--time-budget 300
--cli-timeout 120
```

Urgent ingest used:

```text
--tier1-only
--urgent-only
```

Tier-1 categories included immigration, tax, health, economy, retirement, real-estate, consumer, education, and community.

## Claude writing path

Claude writing standard:

```text
model: claude-opus-4-8
route: claude -p CLI
```

The ingest scripts performed a Claude preflight before generating or promoting content:

```bash
claude -p "Reply OK only" --model claude-opus-4-8 --max-turns 1 --output-format json
```

If Claude returned auth failure or did not return OK, the ingest refused to generate/publish fallback copy.

Key safety rule:

```text
No Claude auth -> no AI-generated fallback copy -> no queue promotion.
```

This was added after Claude auth failures caused empty daily runs.

## Draft improvement and editor gate

After draft generation, the daily ingest called:

```text
scripts/improve_drafts.py
scripts/editor_grade.py
```

Editor gate:

```text
threshold: 70/100
```

Rubric axes:

1. factuality
2. source_diversity
3. Korean-American angle
4. originality / analysis beyond source rewrite
5. structure / markdown quality / checklist-table-timeline visual utility

The editor prompt penalized:

- missing or weak sources
- generic translated summaries
- no Korean-American practical angle
- missing `## 핵심 요약`
- missing `## 출처 (Sources)`
- Mermaid/flowchart/gantt code blocks that render poorly
- no practical table/checklist/timeline where appropriate

Actions:

```text
score >= 70 -> promote to queue/
score below threshold -> remain in drafts/
very weak -> discard_flag in report, but not auto-deleted
```

The report was written to:

```text
scripts/state/editor_report.json
```

## Backlog grading logic

A backlog grader was added on 2026-06-26 because `drafts/` had a large backlog while `queue/` was often empty.

Script:

```text
~/.hermes/scripts/migukstory-drafts-backlog-grade.sh
```

Behavior:

```text
Claude Opus preflight
  -> editor_grade.py --threshold 70 --max-drafts 6 --time-budget 360 --cli-timeout 120
  -> promote only passing existing drafts to queue/
  -> create/update PR
  -> auto-merge if clean
  -> daily-post.yml later publishes queue items, capped
```

It did not generate new fallback copy.

## Queue publishing logic

GitHub workflow:

```text
.github/workflows/daily-post.yml
```

Triggers:

- push to `main` that changes `queue/**`
- manual `workflow_dispatch`

Publish cap before shutdown:

```text
POSTS_PER_RUN_CAP=4
workflow dispatch default=4
```

This cap was reduced from 10 to 4 to avoid same-day thin-content bursts.

Publish steps:

1. Validate `queue/` markdown with strict publish rules.
2. Determine batch size:
   - queue push drains queue up to cap.
   - manual dispatch honors count, still capped.
3. Run `scripts/publish_from_queue.py`.
4. Validate generated `src/content/blog` markdown.
5. Run `npm ci` and `npm run build`.
6. Commit published posts to `main`.
7. Trigger deploy/indexing workflows through normal repo changes.

## Daily publish fallback logic

Hermes script:

```text
~/.hermes/scripts/migukstory-daily-publish.sh
```

Primary path:

```text
Claude orchestrates the GitHub Actions publish workflow using ops/hermes/prompts/daily-publish.md.
```

Fallback path:

If Claude orchestration failed but `origin/main` had files in `queue/`, the script triggered `daily-post.yml` directly:

```bash
gh workflow run daily-post.yml --repo zoelumos/migukstory -f count="$COUNT"
```

Safety cap:

```text
COUNT <= 4
```

This fallback only published already-approved queue items. It did not write, generate, rewrite, or promote articles.

## Homepage logic

Homepage ranking lived mainly in:

```text
src/utils/headlinePriority.ts
```

Important fix from 2026-06-26:

- `오늘 꼭 읽어야 할 뉴스` should not pull old high-priority evergreen posts just because they score well.
- Lead/above-fold cards should first use the newest publication date group.
- If not enough posts from newest date, backfill only from the immediately recent group, not stale old CPI/Iran/etc.

This fixed the issue where old articles appeared in the “today must-read” rail after a new article was published.

## Deploy and indexing logic

Cloudflare deploy workflow built the Astro site and deployed to Cloudflare Pages.

Indexing workflow submitted:

- sitemap to Search Console
- IndexNow / supported indexing APIs for new URLs
- latest URL status report

Important note: Google Search Console can still show a brand-new URL as `URL is unknown to Google` shortly after successful sitemap/API submission. That is a Google processing delay, not necessarily a failed deploy.

## What was published by this logic recently

Recent commits around shutdown:

```text
8743c32 post: publish living trust guide and fix tax headline
28cc7fe fix: keep must-read rail on latest posts
0c0eabe feat: expand pipeline categories and safe draft backlog grading
c478fa1 / latest main included urgent/backlog output before cron pause
```

On 2026-06-26, automation had already run before being paused and main included a newly published consumer/product-recall article plus additional drafts.

## Known risks / lessons

1. Claude auth is a hard dependency for content creation and editor promotion. If `claude-opus-4-8` auth fails, the correct behavior is to stop, not publish fallback copy.
2. Raising publish caps is not the right way to increase output. Use better sources and backlog grading while keeping editor threshold.
3. New categories require synchronized schema/validator/draft/homepage/nav/RSS changes.
4. Official RSS feeds must be smoke-tested. Some government-looking RSS URLs return broken XML or zero entries.
5. Google News feeds are useful discovery inputs but should remain low-volume and editor-graded.
6. Homepage freshness logic must respect the label “오늘 꼭 읽어야 할 뉴스”; stale high-score content should not occupy that rail.
7. Queue publishing should remain capped to avoid AI/thin-content bursts.

## How to restart safely later

If Steve asks to restart automation:

1. Verify Claude Opus auth:

```bash
claude -p "Reply OK only" --model claude-opus-4-8 --max-turns 1 --output-format json
```

2. Check current queue/drafts:

```bash
python3 - <<'PY'
from pathlib import Path
print('queue', len(list(Path('queue').glob('*.md'))))
print('drafts', len(list(Path('drafts').glob('*.md'))))
PY
```

3. Run dry-runs before resuming cron:

```bash
PY=/tmp/migukstory-draft-venv/bin/python
$PY scripts/draft_from_rss.py --dry-run --max-drafts 8 --max-per-category 3 --time-budget 60 --cli-timeout 30
$PY scripts/draft_from_rss.py --dry-run --tier1-only --urgent-only --max-drafts 8 --max-per-category 3 --time-budget 60 --cli-timeout 30
$PY scripts/editor_grade.py --dry-run --threshold 70 --max-drafts 3 --time-budget 30 --cli-timeout 10
npm run build
```

4. Resume only the needed jobs, not everything blindly.

5. Keep `POSTS_PER_RUN_CAP` at 4 unless Steve explicitly approves a larger publishing burst.
