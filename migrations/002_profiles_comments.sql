-- migukstory.com — profiles + comments tables (Phase 2 & 3)
--
-- profiles: user metadata after Google OAuth signup
-- comments: per-article threaded comments tied to auth.users
--
-- Run via: node scripts/run_migration.mjs migrations/002_profiles_comments.sql

-- ============================================================================
-- profiles — 1:1 with auth.users, populated on signup via trigger
-- ============================================================================
create table if not exists public.profiles (
  id              uuid primary key references auth.users(id) on delete cascade,
  email           text,
  display_name    text,
  avatar_url      text,
  provider        text,                    -- 'google', 'email', etc.
  is_verified_pro boolean default false,   -- true for /pros directory listings
  banned_at       timestamptz,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now(),
  metadata        jsonb
);

comment on table public.profiles is
  '미국 스토리 user profiles. 1:1 with auth.users. RLS: own row only.';

create index if not exists profiles_email_idx on public.profiles (lower(email));

alter table public.profiles enable row level security;

drop policy if exists "users read own profile" on public.profiles;
create policy "users read own profile" on public.profiles
  for select to authenticated
  using (auth.uid() = id);

drop policy if exists "users update own profile" on public.profiles;
create policy "users update own profile" on public.profiles
  for update to authenticated
  using (auth.uid() = id)
  with check (auth.uid() = id);

-- Auto-create profile row when a new user signs up via OAuth/email
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.profiles (id, email, display_name, avatar_url, provider, metadata)
  values (
    new.id,
    new.email,
    coalesce(new.raw_user_meta_data->>'full_name', new.raw_user_meta_data->>'name', split_part(new.email, '@', 1)),
    new.raw_user_meta_data->>'avatar_url',
    coalesce(new.raw_app_meta_data->>'provider', 'email'),
    new.raw_user_meta_data
  )
  on conflict (id) do nothing;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- ============================================================================
-- comments — per-article threads
-- ============================================================================
create table if not exists public.comments (
  id           uuid primary key default gen_random_uuid(),
  post_slug    text not null,                          -- e.g., 'i130-korean-parents-2026'
  author_id    uuid not null references public.profiles(id) on delete cascade,
  parent_id    uuid references public.comments(id) on delete cascade,  -- for replies
  body         text not null check (length(body) between 2 and 5000),
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now(),
  is_hidden    boolean not null default false,        -- soft delete / moderation
  is_pinned    boolean not null default false,
  reactions    jsonb default '{}'::jsonb              -- {"like": 5, "heart": 2, ...}
);

comment on table public.comments is
  '미국 스토리 article comments. RLS: anyone reads non-hidden; auth.uid() inserts as own author_id.';

create index if not exists comments_post_slug_idx  on public.comments (post_slug, created_at desc);
create index if not exists comments_author_idx     on public.comments (author_id);
create index if not exists comments_parent_idx     on public.comments (parent_id) where parent_id is not null;

alter table public.comments enable row level security;

-- Anyone (including anon) can read non-hidden comments
drop policy if exists "public read non-hidden comments" on public.comments;
create policy "public read non-hidden comments" on public.comments
  for select using (not is_hidden);

-- Authenticated users can insert as themselves
drop policy if exists "authenticated insert own" on public.comments;
create policy "authenticated insert own" on public.comments
  for insert to authenticated
  with check (auth.uid() = author_id);

-- Authors can update their own comment within 15 min
drop policy if exists "authors edit own within 15min" on public.comments;
create policy "authors edit own within 15min" on public.comments
  for update to authenticated
  using (auth.uid() = author_id and (now() - created_at) < interval '15 minutes')
  with check (auth.uid() = author_id);

-- Authors can soft-delete their own (mark hidden)
drop policy if exists "authors soft-delete own" on public.comments;
create policy "authors soft-delete own" on public.comments
  for delete to authenticated
  using (auth.uid() = author_id);

-- service_role bypasses RLS (used for moderation via MCP)
