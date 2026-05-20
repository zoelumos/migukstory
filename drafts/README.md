# drafts/

AI-generated Korean post drafts awaiting **human review**.

## Pipeline

```
RSS / API source
      │
      ▼
scripts/draft_from_rss.py   (cron: daily-draft.yml)
      │
      ▼
drafts/<slug>.md            ← you are here
      │
      │  human review (edit, fact-check, trim, add hero)
      ▼
queue/<slug>.md             ← only a human moves it here
      │
      ▼
scripts/publish_from_queue.py  (cron: daily-post.yml)
      │
      ▼
src/content/blog/<slug>.md
```

## Rules

1. **Never** publish straight from `drafts/`. Every file in this folder
   must be reviewed by a human before it moves to `queue/`.
2. `draft_from_rss.py` **only writes to this folder**. It must never
   touch `queue/` or `src/content/blog/`.
3. Each draft includes a `## 출처 (Sources)` footer with the canonical
   source URL. Keep it intact when you promote the draft.
4. Quotes from source material are length-limited at generation time.
   If you add longer quotes during review, confirm fair-use and
   attribution.

## Review checklist

- [ ] Headline matches the actual claim in the source
- [ ] Numbers, names, dates verified against the linked source
- [ ] Tone reads like a Korean immigrant-community paper, not a translation
- [ ] No legal / tax / medical advice — recommend "전문가 상담 권장"
- [ ] Category and `ageGroup` make sense
- [ ] Move to `queue/` (or delete) — do **not** leave stale drafts here

## Promoting a draft

```bash
git mv drafts/<slug>.md queue/<slug>.md
git commit -m "queue: <slug>"
```

The next run of `publish_from_queue.py` will pick it up.
