-- migukstory.com — newsletter subscribers table
-- Run this in Supabase Dashboard → SQL Editor → New Query → Paste → Run
-- Or via Supabase MCP after install: claude mcp add supabase ...

-- ============================================================================
-- subscribers — anon can INSERT (signup), only service_role can SELECT/UPDATE
-- ============================================================================
create table if not exists public.subscribers (
  id           uuid primary key default gen_random_uuid(),
  email        text not null unique,
  source       text not null default 'newsletter_form',
  created_at   timestamptz not null default now(),
  confirmed_at timestamptz,                 -- set when double opt-in confirmed
  unsubscribed_at timestamptz,              -- set on unsubscribe
  metadata     jsonb                        -- referrer, user-agent, locale, etc.
);

comment on table public.subscribers is
  '미국이야기 위클리 newsletter subscribers. Anon role can INSERT only; SELECT/UPDATE require service_role.';

create index if not exists subscribers_created_at_idx on public.subscribers (created_at desc);
create index if not exists subscribers_email_idx       on public.subscribers (lower(email));

-- ============================================================================
-- Row Level Security
-- ============================================================================
alter table public.subscribers enable row level security;

-- Allow anon (browser w/ publishable key) to INSERT new signups
drop policy if exists "anon can insert subscribers" on public.subscribers;
create policy "anon can insert subscribers"
  on public.subscribers
  for insert
  to anon
  with check (true);

-- Block anon from reading subscriber list (privacy)
-- (no SELECT policy = no anon SELECT access by default with RLS enabled)

-- service_role bypasses RLS automatically — used for admin queries / MCP

-- ============================================================================
-- Optional: track signup source for analytics
-- ============================================================================
-- Common source values to expect:
--   'newsletter_form'         — bottom-of-article NewsletterSignup component
--   'first-30-days-magnet'    — lead magnet PDF download form
--   'manual'                  — added by editor via Supabase dashboard
--   'kakao_open_chat'         — utm tagged
--   'naver_cafe'              — utm tagged
--   'facebook_group'          — utm tagged

-- Verify install:
-- select count(*) from public.subscribers;  -- should return 0
