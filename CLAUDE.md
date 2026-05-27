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

## Non-negotiable editorial rule: visualization first

Migukstory articles must not be plain text news rewrites. The core product difference is **visual explanation**.

When drafting, editing, auditing, or reviewing any Migukstory post, Claude must treat visualization as a required quality gate:

- If the topic includes a process, deadline, visa path, benefit path, policy rollout, court/policy sequence, or eligibility decision, include a **flowchart**.
- If the topic includes dates or staged changes, include a **timeline**.
- If the topic compares old vs new rules, agencies, visa/status types, options, risks, or reader choices, include a **comparison table**.
- Immigration articles, especially H-1B, PERM, I-140, I-485, visa bulletin, DACA/TPS/asylum, green card, and USCIS/DOL/State Department updates, must include at least one visual element unless there is a documented reason it would be misleading.
- Claude audits must explicitly answer: `Does this post have the right flowchart/timeline/table? If not, FAIL the review.`

Steve's instruction: **"플로우 차트도 중요해. 여기 뉴스의 가장 핵심 포인트는 시각화."**

## Preferred visual formats

Use whichever format best fits the article:

1. Mermaid flowchart for step-by-step legal/benefit/immigration processes.
2. Mermaid timeline or ordered stage cards for date-driven updates.
3. Markdown comparison tables for old/new, option A/B, and eligibility/risk comparisons.
4. Short Korean labels; mobile-readable; avoid giant diagrams that wrap badly.

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
- [ ] Live URL returns 200.
- [ ] RSS includes new posts.
- [ ] Sitemap includes new canonical URLs.
- [ ] Search Console sitemap submission / indexing notification path is verified where configured.
- [ ] Steve receives a concise Korean status if anything fails or needs attention.
