# Migukstory Claude Instructions

## Prime directive: full automation, not assisted automation

Migukstory must become a **complete end-to-end automated publishing system**.

Steve's instruction, permanently binding for Claude/Hermes work on this repo:

> "Migukstory는 완전한 자동화가 되어야 한다. 사람이 매번 밀어줘야 하는 반자동이면 실패다."

Claude must design, review, and fix this project toward this goal:

```txt
ingest → source validation → Claude draft/review → quality gate → queue/PR/merge → publish → build → deploy → RSS/sitemap → Google Search Console sitemap submit → IndexNow/Indexing API → live URL verification → Korean status/error notification
```

A run is not complete just because content was generated or a PR merged. It is complete only when the live site and discovery surfaces are verified.

## Non-negotiable automation rules

1. **No manual pushing as the normal path**
   - Manual publish/push is only an emergency recovery path.
   - The expected path is cron/GitHub Actions/scripts doing the whole chain automatically.

2. **Publish must happen after ingest without Steve asking**
   - If ingest creates/merges queued posts, publish must follow automatically.
   - If publish fails, the system must surface the failure and preserve enough logs for immediate recovery.

3. **Sitemap is critical**
   - Every published canonical URL must appear in the sitemap.
   - No `draft: true`, no `noindex`, no utility/private URLs in the public sitemap.
   - Robots must point to the sitemap.
   - After publishing, verify sitemap includes the newly published slugs.

4. **Google/new-site discovery is a first-class requirement**
   - For a young site, publishing alone is not enough.
   - Verify: live 200, canonical, RSS, sitemap, Search Console sitemap submit, IndexNow/Indexing API where configured.
   - Avoid spammy shortcuts. Follow Google guidance: crawlable pages, helpful original content, clean sitemap, internal links, stable canonical URLs, no mass thin-content bursts.

5. **Failures must self-report**
   - Cron/Actions should report Korean success/risk/error summaries.
   - Silent failures are unacceptable.
   - A green status must mean live + sitemap/indexing checks passed, not merely "script exited".

6. **Claude review is part of the pipeline**
   - Claude should audit article quality, visual explanations, SEO, and technical publish risk.
   - But Claude review must not become a manual bottleneck; bounded automated Claude checks are preferred.

## Non-negotiable editorial focus: GSC-backed service journalism

Search Console data checked on 2026-05-29 showed that USCIS/immigration articles are already producing real Google impressions and clicks. Tomorrow's and ongoing Claude/Hermes drafting must therefore prioritize high-intent Korean-American service topics:

1. Immigration/USCIS/visa/green-card updates and practical explainers.
2. Tax/IRS/FBAR/credits/deadlines for Korean-American households and small businesses.
3. Retirement/Social Security/Medicare and pension/401(k)/IRA decision guides.
4. Housing, mortgage, rent, home insurance, and real-estate affordability.
5. Health insurance, ACA/Medicare/Medicaid, and insurance claim/coverage explainers.
6. Practical Korean-American life guides: first 90 days, documents, banking, school, DMV, healthcare, consular tasks.

**Do not drop the other lanes.** Economy and AI/robotics must continue every day/week as maintained categories, especially when they affect jobs, small business, markets, retirement accounts, automation risk, immigration workers, or children's education/careers. The rule is priority, not exclusion: service journalism first; economy and AI/robotics still active.

**Lane starvation guard (added 2026-07-06 after economy went 8 days without a
story).** Hard freshness windows: economy ≤ 3 days, ai ≤ 6 days, robotics ≤ 10
days between published posts. `draft_from_rss.py::_starved_categories` boosts a
stale lane to the front of the planning order automatically. Any Claude session
choosing "today's article" directly must apply the same rule: check the newest
`pubDate` per category in `src/content/blog/` first, and if a maintained lane
is past its window, today's pick comes from that lane (framed for Korean-American
households: 물가/금리/환율/401k/소상공인 for economy).

**NY/NJ regional lane (Steve's directive, 2026-07-03).** The tri-state area
(Fort Lee, Palisades Park, Bergen County, Flushing, Bayside…) is the priority
region. When a story concerns New York or New Jersey, write it for the
tri-state Korean community specifically — name affected towns, local offices,
and deadlines — and tag it '뉴저지' and/or '뉴욕' in frontmatter so regional
pages can aggregate. Dedicated NY/NJ RSS feeds live in
`scripts/config/rss_sources.yml`.

## Non-negotiable gate: no duplicate topics

Never publish a second article on a story the site already ran (the 6/29+6/30
Medicare GLP-1 pair is the precedent — SEO cannibalization). Before adding ANY
new article to `src/content/blog/`, run:

```bash
python3 -c "
import sys; sys.path.insert(0, 'scripts')
from topic_dedupe import find_topic_duplicate
print(find_topic_duplicate('<새 기사 제목>', '<new-slug>'))"
```

If it returns a match, **update the existing article instead** (refresh its
content and `updatedDate`) — do not create a new file. `editor_grade.py`
blocks auto-promotion of duplicates and `publish_from_queue.py` hard-fails
them, but any Claude session committing articles directly must run this check
itself.

## Non-negotiable editorial rule: visualization first

Migukstory articles must not be plain text news rewrites. The core product difference is **visual explanation**.

When drafting, editing, auditing, or reviewing any Migukstory post, Claude must treat visualization as a required quality gate:

- If the topic includes a process, deadline, visa path, benefit path, policy rollout, court/policy sequence, or eligibility decision, include a **step-by-step decision guide** (numbered steps or "조건 → 결과" nested bullets).
- If the topic includes dates or staged changes, include a **timeline** (numbered stage list).
- If the topic compares old vs new rules, agencies, visa/status types, options, risks, or reader choices, include a **comparison table**.
- Immigration articles, especially H-1B, PERM, I-140, I-485, visa bulletin, DACA/TPS/asylum, green card, and USCIS/DOL/State Department updates, must include at least one visual element unless there is a documented reason it would be misleading.
- Claude audits must explicitly answer: `Does this post have the right decision guide/timeline/table? If not, FAIL the review.`

Steve's instruction: **"플로우 차트도 중요해. 여기 뉴스의 가장 핵심 포인트는 시각화."**

## Preferred visual formats — static Markdown ONLY, never Mermaid

**HARD RULE: never emit ```mermaid / flowchart / graph / sequenceDiagram / gantt
code blocks in any article.** They rendered broken on the live site for weeks;
the pipeline gates (`editor_grade.py`, `publish_from_queue.py`) reject them and
a build-time transform (`plugins/remark-mermaid-mobile.js`) exists only as a
last-resort safety net. Express every "flowchart" as static Markdown:

1. Numbered step list for step-by-step legal/benefit/immigration processes.
2. "조건 → 결과" nested bullet list for decision trees / eligibility branches.
3. Numbered stage list or short timeline for date-driven updates.
4. Markdown comparison tables for old/new, option A/B, and eligibility/risk comparisons.
5. Short Korean labels; mobile-readable; ✅/⚠️/❌ markers are encouraged.

## Review checklist for every article or pipeline change

Before approving, publishing, or reporting success, verify:

- [ ] The headline is useful for Korean-American readers in the U.S.
- [ ] The first 2 paragraphs explain why this matters now.
- [ ] The article contains a flowchart, timeline, or comparison table where useful.
- [ ] The visual is accurate and not decorative filler.
- [ ] The article has practical next steps.
- [ ] Official sources are cited.
- [ ] Build passes.
- [ ] Published posts are `draft: false`.
- [ ] Frontmatter enums are EXACT — `ageGroup` must be one of `20-35` | `35-55` | `55+` | `all` (never invent values like '전체', '30-60', 'senior' — each of those killed a day's deploy), `category` must be one of the keys in `src/content.config.ts`. `scripts/validate_markdown_frontmatter.py` fails the deploy otherwise.
- [ ] Live URL returns 200.
- [ ] RSS includes new posts.
- [ ] Sitemap includes new canonical URLs.
- [ ] Search Console sitemap submission / indexing notification path is verified where configured.
- [ ] Steve receives a concise Korean status if anything fails or needs attention.
