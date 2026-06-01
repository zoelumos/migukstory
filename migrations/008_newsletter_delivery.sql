-- migukstory.com — newsletter auto-subscribe + delivery ledger
--
-- Purpose:
-- 1. Auth signups automatically become newsletter subscribers.
-- 2. Newsletter sends are recorded per subscriber/post so deploy/publish jobs can
--    email only once and avoid duplicate blasts.
--
-- Run via: node scripts/run_migration.mjs migrations/008_newsletter_delivery.sql

-- Track per-recipient/per-post sends. This table is admin/service-only by RLS.
create table if not exists public.newsletter_sends (
  id             uuid primary key default gen_random_uuid(),
  subscriber_id  uuid references public.subscribers(id) on delete cascade,
  email          text not null,
  post_slug      text not null,
  post_title     text,
  provider       text not null default 'resend',
  provider_id    text,
  status         text not null default 'sent',
  error          text,
  sent_at        timestamptz not null default now(),
  metadata       jsonb,
  unique (email, post_slug)
);

create index if not exists newsletter_sends_sent_at_idx on public.newsletter_sends (sent_at desc);
create index if not exists newsletter_sends_post_slug_idx on public.newsletter_sends (post_slug);

alter table public.newsletter_sends enable row level security;

-- Admins can read send history from admin tools. Service role bypasses RLS for CI.
drop policy if exists "admins read newsletter sends" on public.newsletter_sends;
create policy "admins read newsletter sends"
  on public.newsletter_sends
  for select
  to authenticated
  using (public.current_user_role() = 'admin');

-- Auth/profile signup trigger: create profile + subscribe the member email.
-- This replaces the previous handle_new_user while preserving admin profile logic.
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  v_is_admin boolean := public.is_admin_email(new.email);
begin
  -- Stamp app_metadata.role if admin (server-side, immutable from client).
  -- Preserve migration 006 behavior so current_user_role() policies keep working
  -- for any future admin email added to is_admin_email().
  if v_is_admin then
    update auth.users
      set raw_app_meta_data = coalesce(raw_app_meta_data, '{}'::jsonb)
        || jsonb_build_object('role', 'admin')
      where id = new.id;
  end if;

  insert into public.profiles (id, email, display_name, avatar_url, provider, is_admin, metadata)
  values (
    new.id,
    new.email,
    coalesce(new.raw_user_meta_data->>'full_name', new.raw_user_meta_data->>'name', split_part(new.email, '@', 1)),
    new.raw_user_meta_data->>'avatar_url',
    coalesce(new.raw_app_meta_data->>'provider', 'email'),
    v_is_admin,
    new.raw_user_meta_data
  )
  on conflict (id) do update
    set email = excluded.email,
        display_name = coalesce(public.profiles.display_name, excluded.display_name),
        avatar_url = coalesce(public.profiles.avatar_url, excluded.avatar_url),
        provider = coalesce(public.profiles.provider, excluded.provider),
        is_admin = case when public.is_admin_email(excluded.email) then true else public.profiles.is_admin end;

  -- Login members are intentionally newsletter subscribers by default.
  -- Duplicate public signups are kept indistinguishable by /api/subscribers;
  -- this server-side trigger also does nothing if the email already exists.
  if new.email is not null and length(trim(new.email)) > 4 then
    insert into public.subscribers (email, source, confirmed_at, metadata)
    values (
      lower(trim(new.email)),
      'profile_signup',
      now(),
      jsonb_build_object(
        'auth_user_id', new.id,
        'provider', coalesce(new.raw_app_meta_data->>'provider', 'email'),
        'auto_subscribed', true,
        'ts', now()
      )
    )
    on conflict (email) do update
      set metadata = coalesce(public.subscribers.metadata, '{}'::jsonb) || jsonb_build_object(
            'auth_user_id', new.id,
            'profile_signup_seen_at', now()
          )
      where public.subscribers.unsubscribed_at is null;
  end if;

  return new;
end;
$$;

-- Ensure the trigger exists after replacing the function.
drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- Ensure PostgREST sees the new relation immediately after running through the
-- Supabase Management API. Without this, admin can show PGRST205 schema-cache
-- errors for newsletter_sends until the cache refreshes.
notify pgrst, 'reload schema';
