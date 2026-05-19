# migukstory.com — Architecture (2026-05-19)

**Status:** Site is live at https://migukstory.com. Deploy pipeline is fully automated. AI ingest pipeline has 2 known blockers (documented below).

> GitHub renders Mermaid diagrams inline in `.md` files. If you're viewing raw text, paste any of the code blocks into <https://mermaid.live>.

---

## TL;DR — what's working and what isn't

| Layer | Component | Status | Notes |
|---|---|---|---|
| **Site deploy** | `cloudflare-deploy.yml` | 🟢 working | push to main → CF Pages auto-deploys, ~50s |
| **Indexing** | `notify_indexes.py` (IndexNow + Google) | 🟢 working | runs post-deploy, IndexNow free |
| **AI ingest** | `daily-draft.yml` (RSS → Claude) | 🔴 blocked | needs `ANTHROPIC_API_KEY` (separate from Max) |
| **Editor grading** | `editor_grade.py` | 🔴 blocked | depends on ingest producing drafts |
| **Manual publish** | `daily-post.yml` | 🟢 working | triggered by routine or manually |
| **Routine: daily-publish** | claude.ai cron | 🔴 blocked | needs GitHub MCP attached |
| **Routine: editorial-review** | claude.ai cron | 🟢 working | will show "no data" until ingest fixed |
| **Routine: daily-health** | claude.ai cron | 🟡 partial | site/queue checks work; workflow listing blocked w/o GH MCP |
| **Routine: weekly-audit** | claude.ai cron | 🟢 working | runs every Monday |
| **Routine: monthly-cf-rotate** | claude.ai cron | 🟢 working | sends Slack reminder 1st of each month |
| **Local cron via Hermes** | `ops/hermes/` folder | ⚫ legacy | merged but unused; routines replace this |

---

## 1. Full system — what runs where

```mermaid
flowchart TB
    classDef gha fill:#dcfce7,stroke:#16a34a,stroke-width:2px,color:#14532d
    classDef routine fill:#fce7f3,stroke:#db2777,stroke-width:2px,color:#831843
    classDef storage fill:#f1f5f9,stroke:#475569,stroke-width:1px,color:#0f172a
    classDef external fill:#f5f5f5,stroke:#737373,stroke-width:1px,color:#525252,stroke-dasharray:5 3
    classDef blocked fill:#fee2e2,stroke:#dc2626,stroke-width:2px,color:#7f1d1d
    classDef partial fill:#fef9c3,stroke:#ca8a04,stroke-width:2px,color:#713f12
    classDef live fill:#a7f3d0,stroke:#059669,stroke-width:2px,color:#064e3b
    classDef legacy fill:#e5e5e5,stroke:#a3a3a3,stroke-width:1px,color:#525252,stroke-dasharray:5 3

    %% ── External services ────────────────────────────────
    subgraph EXT["External services"]
        direction LR
        ANTHROPIC[("🧠 Anthropic API<br/>api.anthropic.com<br/>(needs key)")]:::external
        MAX[("🧠 Claude Max<br/>claude.ai<br/>(Steve subscribed)")]:::external
        RSS[("📡 RSS feeds<br/>USCIS · State · CDC · Treasury · Fed · NPR")]:::external
        CF[("☁️ Cloudflare Pages<br/>migukstory project")]:::external
        SLACK[("💬 Slack")]:::external
        INDEXNOW[("📡 IndexNow API<br/>Bing · Yandex · Yep")]:::external
        GOOGLE[("📡 Google Indexing API<br/>(optional)")]:::external
    end

    %% ── GitHub Actions layer ─────────────────────────────
    subgraph GHA["GitHub Actions (zoelumos/migukstory)"]
        direction TB
        W1["⚙️ daily-draft.yml<br/>cron 0 */4 * * *<br/>(every 4h)"]:::blocked
        W2["⚙️ daily-post.yml<br/>workflow_dispatch only"]:::gha
        W3["⚙️ cloudflare-deploy.yml<br/>on push to main"]:::gha
    end

    %% ── claude.ai routines ───────────────────────────────
    subgraph ROUT["claude.ai Routines (5 enabled, runs on Anthropic cloud, billed to Max)"]
        direction TB
        R1["⏰ migukstory-daily-publish<br/>0 12 UTC daily (8am ET)"]:::blocked
        R2["⏰ migukstory-daily-editorial-review<br/>0 13 UTC daily (9am ET)"]:::routine
        R3["⏰ migukstory-daily-health<br/>30 14 UTC daily (10:30am ET)"]:::partial
        R4["⏰ migukstory-weekly-audit<br/>0 15 UTC Mon (11am ET)"]:::routine
        R5["⏰ migukstory-monthly-cf-rotate<br/>0 14 UTC 1st (10am ET)"]:::routine
    end

    %% ── Repo state ──────────────────────────────────────
    subgraph REPO["Repo state (github.com/zoelumos/migukstory)"]
        direction LR
        DRAFTS[(drafts/<br/>AI-drafted, pending review)]:::storage
        QUEUE[(queue/<br/>15 posts pre-staged)]:::storage
        BLOG[(src/content/blog/<br/>23 published posts)]:::storage
        REPORT[(scripts/state/<br/>editor_report.json)]:::storage
        SEEN[(scripts/state/<br/>seen_urls.json)]:::storage
    end

    %% ── Live ────────────────────────────────────────────
    LIVE(["🌐 migukstory.com<br/>Cloudflare Pages edge"]):::live

    %% ── Legacy ──────────────────────────────────────────
    HERMES["📁 ops/hermes/<br/>(local cron via claude -p)<br/>not in use"]:::legacy

    %% ── Connections ─────────────────────────────────────
    RSS --> W1
    W1 -.->|needs ANTHROPIC_API_KEY| ANTHROPIC
    ANTHROPIC -.->|🔴 missing| W1
    W1 -.-> DRAFTS
    W1 -.-> REPORT
    W1 -.-> SEEN

    DRAFTS --> R2
    REPORT --> R2
    R2 -->|read-only brief| MAX

    R1 -.->|needs GitHub MCP| W2
    R1 -.->|🔴 MCP not attached| SLACK
    W2 --> QUEUE
    W2 --> BLOG
    BLOG -->|git push| W3
    W3 --> CF
    CF --> LIVE
    W3 --> INDEXNOW
    W3 -.->|optional| GOOGLE

    QUEUE --> R3
    DRAFTS --> R3
    R3 --> SLACK
    R3 -.->|partial w/o GH MCP| W3

    BLOG --> R4
    R4 --> SLACK

    R5 --> SLACK

    MAX -.->|powers all routines| ROUT

    HERMES -.->|alternative path<br/>not active| W2
```

---

## 2. A day in the life — what fires when (with current state)

```mermaid
sequenceDiagram
    autonumber
    participant Cron as ⏰ Schedulers
    participant Draft as 🤖 daily-draft.yml
    participant Pub as ⚙️ daily-publish (routine)
    participant Editor as 🤖 editorial-review (routine)
    participant Health as 🩺 daily-health (routine)
    participant Site as 🌐 migukstory.com
    participant Slack as 💬 Slack

    Note over Cron: 00:00 UTC (every 4h after)
    Cron->>Draft: GH Actions tick
    Draft-->>Cron: ❌ FAIL — no ANTHROPIC_API_KEY
    Note over Draft: 6× per day this same failure

    Note over Cron: 12:00 UTC (8am ET) — daily-publish
    Cron->>Pub: claude.ai routine fires
    Pub-->>Slack: ❌ "🔴 daily publish FAILED — no GitHub MCP"
    Note over Site: unchanged — no new post today

    Note over Cron: 13:00 UTC (9am ET) — editorial-review
    Cron->>Editor: claude.ai routine fires
    Editor-->>Editor: read editor_report.json (doesn't exist)
    Editor-->>Cron: ✅ "📭 No editor report yet"
    Note over Editor: result visible at routine dashboard URL

    Note over Cron: 14:30 UTC (10:30am ET) — daily-health
    Cron->>Health: claude.ai routine fires
    Health->>Site: curl ✅ 200
    Health->>Health: count queue (15) + drafts (0)
    Health-->>Slack: 🟡 partial status (no workflows section)

    Note over Cron: 16:00 / 20:00 / 00:00 UTC — more daily-draft ticks
    Cron->>Draft: same failure ×3 more

    Note right of Site: End of day:<br/>site unchanged,<br/>queue still at 15,<br/>0 new drafts<br/>6 GH Actions failures<br/>2 Slack messages
```

---

## 3. Decision tree — fixing the 2 blockers

```mermaid
flowchart TB
    classDef option fill:#dbeafe,stroke:#2563eb,stroke-width:2px,color:#1e3a8a
    classDef result fill:#dcfce7,stroke:#16a34a,stroke-width:2px,color:#14532d
    classDef cost fill:#fef9c3,stroke:#ca8a04,color:#713f12

    START([Want full automation working]):::option

    START --> B1{"Blocker 1:<br/>daily-draft.yml<br/>needs ANTHROPIC_API_KEY"}

    B1 --> A1["Option A:<br/>Pay for Anthropic API"]:::option
    B1 --> A2["Option B:<br/>Move drafting to a<br/>claude.ai routine"]:::option

    A1 --> A1c["Cost: ~$30–60/mo<br/>(separate from Max)"]:::cost
    A1 --> A1d["Effort: 5 minutes<br/>(create key, set secret)"]:::cost

    A2 --> A2c["Cost: $0 extra<br/>(uses existing Max quota)"]:::cost
    A2 --> A2d["Effort: ~2 hours<br/>(rewrite ingest as routine)"]:::cost

    START --> B2{"Blocker 2:<br/>daily-publish routine<br/>needs GitHub MCP"}

    B2 --> C1["Option C:<br/>Connect GitHub MCP<br/>(retry the OAuth)"]:::option
    B2 --> C2["Option D:<br/>Add cron back to<br/>daily-post.yml"]:::option

    C1 --> C1c["Cost: $0<br/>Effort: 2 minutes"]:::cost
    C2 --> C2c["Cost: $0<br/>Effort: 5 minutes<br/>Disable daily-publish routine"]:::cost

    A1c --> END1([Full automation, paid API]):::result
    A2c --> END2([Full automation, Max-only]):::result
    C1c --> END3([Routine triggers publish]):::result
    C2c --> END4([GH cron triggers publish]):::result
```

---

## 4. Routines registered on claude.ai

All run in Anthropic's cloud, billed against Steve's Max subscription. Dashboard URLs are bookmarkable.

| Name | ID | Schedule (UTC) | Local approx (ET EDT) | Status | Dashboard |
|---|---|---|---|---|---|
| migukstory-daily-publish | `trig_01VDBqt2KmYvmH3wercFV5os` | `0 12 * * *` | 8:00 AM | 🔴 needs GH MCP | [link](https://claude.ai/code/routines/trig_01VDBqt2KmYvmH3wercFV5os) |
| migukstory-daily-editorial-review | `trig_01TwQNEERU2vYW6yxBPack2F` | `0 13 * * *` | 9:00 AM | 🟢 enabled | [link](https://claude.ai/code/routines/trig_01TwQNEERU2vYW6yxBPack2F) |
| migukstory-daily-health | `trig_01L1Ebbgjf939HNHw5Wze4zf` | `30 14 * * *` | 10:30 AM | 🟡 partial | [link](https://claude.ai/code/routines/trig_01L1Ebbgjf939HNHw5Wze4zf) |
| migukstory-weekly-audit | `trig_01PsRgvyDSmkhzvAbRtyhK3i` | `0 15 * * 1` | Mon 11:00 | 🟢 enabled | [link](https://claude.ai/code/routines/trig_01PsRgvyDSmkhzvAbRtyhK3i) |
| migukstory-monthly-cf-rotate | `trig_01Te7SdsHkTivdYSY2aBLN2q` | `0 14 1 * *` | 1st 10:00 | 🟢 enabled | [link](https://claude.ai/code/routines/trig_01Te7SdsHkTivdYSY2aBLN2q) |

MCPs auto-attached: Adobe-for-creativity, Vercel, Slack. **GitHub MCP NOT attached** (root cause of daily-publish blocker).

---

## 5. GitHub Actions workflows

| File | Trigger | Status | Purpose |
|---|---|---|---|
| `cloudflare-deploy.yml` | push to main (paths filter) | 🟢 working | Build Astro → wrangler deploy → IndexNow ping |
| `daily-draft.yml` | cron `0 */4 * * *` (6×/day) | 🔴 failing | RSS → Claude → drafts → editor grade → auto-PR |
| `daily-post.yml` | workflow_dispatch only | 🟢 working | Move N posts queue → blog → commit → push |

GitHub repo secrets currently set:
- `CLOUDFLARE_API_TOKEN` ✅ (deploy works)
- `CLOUDFLARE_ACCOUNT_ID` ✅
- `ANTHROPIC_API_KEY` ❌ (blocks daily-draft.yml)
- `GOOGLE_SERVICE_ACCOUNT_JSON` ❌ optional (IndexNow alone works)

---

## 6. Cost summary

| Service | Plan | Status | Used for |
|---|---|---|---|
| Claude Max | $200/mo subscription | ✅ active | All 5 claude.ai routines (15 runs/day budget) |
| Anthropic API | pay-as-you-go | ❌ not subscribed | Would unblock daily-draft.yml |
| Cloudflare Pages | Free tier | ✅ active | Hosting + auto-deploy |
| GitHub Actions | Free tier (public repo) | ✅ active | All workflows |
| IndexNow | Free | ✅ active | Bing/Yandex/Yep indexing |
| Google Indexing API | Free | ❌ not set up | Optional faster Google pickup |

**Current marginal monthly cost:** $0 on top of Max (~5 routine runs/day, well under 15/day cap).

---

## 7. Where Hermes / `ops/hermes/` sits

The `ops/hermes/` folder in the repo was created as an alternative path that uses Steve's Mac mini + `claude -p` (local invocation of Claude Code using the Max subscription, no API key). Defined 5 cron jobs in YAML.

**Currently unused.** The claude.ai routines do the same thing remotely, no Mac dependency. The folder remains in the repo as documentation of an alternative path if Steve wants to switch later. Can be safely deleted with one PR.

---

## 8. Repo file conventions

| Path | Purpose | Allowed writers |
|---|---|---|
| `drafts/<date>-<slug>.md` | AI drafts pending review | `draft_from_rss.py` |
| `queue/<topic>-<year>.md` | Approved-or-promoted, ready to publish | `editor_grade.py`, human, `publish_from_queue.py` |
| `src/content/blog/<topic>-<year>.md` | Published posts | `publish_from_queue.py`, human |
| `scripts/state/seen_urls.json` | Dedupe ledger | `draft_from_rss.py` |
| `scripts/state/editor_report.json` | Last grading report | `editor_grade.py` |
| `public/<indexnow-key>.txt` | IndexNow verification | manual |
| `ops/hermes/jobs/*.yml` | Hermes cron defs (unused) | manual |
| `ops/hermes/prompts/*.md` | Hermes prompts (unused) | manual |

---

## 9. Tomorrow morning, what to expect (current state)

🔴 Site unchanged (no new content gets published until 1 of 2 fixes)
🔴 6 failed `daily-draft.yml` runs visible at https://github.com/zoelumos/migukstory/actions
🟢 3 routine dashboards updated with results (editorial-review, daily-health, daily-publish)
🟡 Some Slack messages (depending on if Slack MCP triggers correctly from routines)

**To make tomorrow actually productive:** address Blocker 1 (Option B is recommended — keep everything Max-only). Blocker 2 has a 5-minute fix (Option D — cron in daily-post.yml).

---

*Generated 2026-05-19. Update this file whenever workflows, routines, scripts, or state files change. Mermaid renders inline on GitHub; for static export use [mermaid.live](https://mermaid.live) or the [Mermaid CLI](https://github.com/mermaid-js/mermaid-cli).*
