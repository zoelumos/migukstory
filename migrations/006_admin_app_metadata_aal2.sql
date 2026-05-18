-- migukstory.com — Phase 1 OAuth hardening (per 6-agent best-practice synthesis)
--
-- 1. Stamp auth.users.raw_app_meta_data with role='admin' for admin emails.
--    app_metadata is set by service_role only — users CANNOT self-edit.
--    user_metadata is self-editable, so it's unsafe for role claims.
--
-- 2. Restrictive RLS policy on admin write actions requires AAL2 (MFA verified).
--    'restrictive' is critical — without it, Postgres ORs policies and bypasses gate.
--    Will be enforceable once admin enrolls TOTP factor.
--
-- 3. CHECK constraint on comments.post_slug to prevent random slug spam.

-- ============================================================================
-- 1. Stamp app_metadata.role='admin' for admin email(s)
-- ============================================================================
update auth.users
  set raw_app_meta_data = coalesce(raw_app_meta_data, '{}'::jsonb)
    || jsonb_build_object('role', 'admin')
  where lower(email) in ('zoestudiollc@gmail.com');

-- Update the signup trigger so future signins/signups also set app_metadata.role
-- (uses the existing is_admin_email() function from migration 005)
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  v_is_admin boolean := public.is_admin_email(new.email);
begin
  -- Stamp app_metadata.role if admin (server-side, immutable from client)
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
    set is_admin = excluded.is_admin
    where public.is_admin_email(public.profiles.email);
  return new;
end;
$$;

-- ============================================================================
-- 2. Helper functions: check app_metadata.role + AAL from current JWT
-- ============================================================================
create or replace function public.current_user_role() returns text
language sql stable as $$
  select coalesce(auth.jwt() -> 'app_metadata' ->> 'role', 'user');
$$;

create or replace function public.current_user_aal() returns text
language sql stable as $$
  select coalesce(auth.jwt() ->> 'aal', 'aal1');
$$;

-- ============================================================================
-- 3. RESTRICTIVE policies — admin write actions require BOTH role + AAL2
--    Restrictive policies AND with permissive policies (no bypass possible)
-- ============================================================================
-- Comments: restrictive policy that blocks admin destructive ops unless AAL2
drop policy if exists "restrict_admin_writes_to_aal2" on public.comments;
create policy "restrict_admin_writes_to_aal2"
  on public.comments
  as restrictive
  for update
  to authenticated
  using (
    -- Non-admins pass through (this restrictive applies AND with existing perms,
    -- so a non-admin updating own comment is governed by 'authors edit own within 15min')
    public.current_user_role() != 'admin'
    -- Admins must have AAL2 to do destructive ops
    or public.current_user_aal() = 'aal2'
  );

drop policy if exists "restrict_admin_deletes_to_aal2" on public.comments;
create policy "restrict_admin_deletes_to_aal2"
  on public.comments
  as restrictive
  for delete
  to authenticated
  using (
    public.current_user_role() != 'admin'
    or public.current_user_aal() = 'aal2'
  );

-- ============================================================================
-- 4. post_slug shape check (prevents fake-slug comment pollution)
-- ============================================================================
alter table public.comments
  drop constraint if exists comments_post_slug_check;
alter table public.comments
  add constraint comments_post_slug_check
  check (
    length(post_slug) between 2 and 200
    and post_slug ~ '^/[a-z0-9/_\-]+/?$'
  );
