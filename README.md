# 미국 스토리 — Korean Immigrant Guide

Production site: **https://migukstory.com**

Static blog for Korean-American immigrants — informative posts on immigration, taxes, healthcare, and Korean diaspora culture, sourced from legitimate news (USCIS, IRS, NPR, CNN, Korea Times, JoongAng, etc.).

## Stack

- **Framework:** [Astro](https://astro.build) 6.x — static site generator with content collections
- **Hosting:** [Cloudflare Pages](https://pages.cloudflare.com/) (free, global CDN)
- **Domain:** [migukstory.com](https://migukstory.com) (Cloudflare Registrar)
- **Content:** Markdown files in `src/content/blog/`
- **Diagrams:** [Mermaid.js](https://mermaid.js.org/) (client-side, lazy-loaded only when needed)
- **Fonts:** Noto Sans KR + Noto Serif KR via Google Fonts (preloaded)
- **Sitemap:** Auto-generated via `@astrojs/sitemap`
- **RSS:** `/rss.xml`

## Local development

Requires Node.js >= 22.12

```bash
npm install
npm run dev        # http://localhost:4321
npm run build      # outputs to dist/
npm run preview    # preview built site
```

## Add a new post

1. Create `src/content/blog/your-slug-here.md` with frontmatter:

```yaml
---
title: '한국어 제목'
description: '메타 설명 120-155자'
pubDate: '2026-05-17'
tags: ['태그1', '태그2']
ageGroup: '20-35' | '35-55' | '55+' | 'all'
---
```

2. Write Korean markdown. Use Mermaid for diagrams:

  ````markdown
  ```mermaid
  flowchart LR
      A[시작] --> B[다음]
  ```
  ````

3. `git commit -am "add: your-slug-here"` → `git push` → Cloudflare auto-builds.

## Manual deploy

```bash
# Requires CLOUDFLARE_API_TOKEN with Pages:Edit + Account:Read
npx wrangler pages deploy dist --project-name=migukstory --branch=main
```

## Search indexing

New posts are submitted to search engines automatically — no manual step:

- **IndexNow** (Bing, Yandex, Naver, …) — no secret needed; the key file lives
  at `public/<key>.txt`.
- **Google Indexing API** — needs the repo secret **`GSC_SERVICE_ACCOUNT`**: a
  Google service-account JSON (Indexing API enabled, account added as a Search
  Console owner), **base64-encoded**. Rotate it with:

  ```bash
  base64 -i .secrets/gsc-service-account.json | gh secret set GSC_SERVICE_ACCOUNT
  ```

Three workflows cover every publish path, all using `GSC_SERVICE_ACCOUNT`:

| Workflow | Trigger | What it submits |
|---|---|---|
| `google-index.yml` | daily 09:00 UTC · push to `src/content/**`,`src/pages/**` · manual | sitemap + every site URL |
| `cloudflare-deploy.yml` | push to `main` (content/code) | URLs added in the last commit |
| `daily-post.yml` | daily queue publish | URL(s) the queue-publish commit added |

The `daily-post.yml` ping is required because its publish commit is pushed with
the default `GITHUB_TOKEN`, which by design does **not** trigger the other two
workflows. `scripts/notify_indexes.py` also accepts a raw-JSON
`GOOGLE_SERVICE_ACCOUNT_JSON` as a legacy fallback when `GSC_SERVICE_ACCOUNT`
is unset.

## Editorial principles

- **Source every claim** — government (USCIS, IRS, SSA), major news (NYT, NPR, CNN, Korea Times, JoongAng)
- **No legal/tax/medical advice** — recommend "전문가 상담 권장"
- **AI-assisted, human-verified** — drafts may be AI-generated but every fact is checked
- **Disclose sponsorships** — mark `#광고`
