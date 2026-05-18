-- migukstory.com — admin role
--
-- Designate zoestudiollc@gmail.com as the site admin.
-- Adds is_admin column on profiles, updates the auto-create trigger,
-- adds RLS policies that let admins moderate any comment.

-- ============================================================================
-- profiles.is_admin column
-- ============================================================================
alter table public.profiles
  add column if not exists is_admin boolean not null default false;

create index if not exists profiles_is_admin_idx on public.profiles (is_admin) where is_admin = true;

-- ============================================================================
-- Auto-grant admin to known admin emails on signup (and reset on update)
-- ============================================================================
-- Whitelist of admin emails (case-insensitive). Keep small + grep-able.
create or replace function public.is_admin_email(em text) returns boolean
language sql immutable as $$
  select lower(em) in ('zoestudiollc@gmail.com');
$$;

-- Update the existing signup trigger to set is_admin if email matches
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.profiles (id, email, display_name, avatar_url, provider, is_admin, metadata)
  values (
    new.id,
    new.email,
    coalesce(new.raw_user_meta_data->>'full_name', new.raw_user_meta_data->>'name', split_part(new.email, '@', 1)),
    new.raw_user_meta_data->>'avatar_url',
    coalesce(new.raw_app_meta_data->>'provider', 'email'),
    public.is_admin_email(new.email),
    new.raw_user_meta_data
  )
  on conflict (id) do update
    set is_admin = excluded.is_admin
    where public.is_admin_email(public.profiles.email);
  return new;
end;
$$;

-- If profile row already exists for the admin email, flip the flag now
update public.profiles set is_admin = true where public.is_admin_email(email);

-- ============================================================================
-- Helper to check current request's admin status (used by RLS policies)
-- ============================================================================
create or replace function public.current_user_is_admin() returns boolean
language sql stable security definer set search_path = public as $$
  select coalesce(
    (select is_admin from public.profiles where id = auth.uid()),
    false
  );
$$;

-- ============================================================================
-- Admin RLS policies on comments
-- ============================================================================
-- Admins can SELECT hidden comments (regular anon can't)
drop policy if exists "admins read hidden comments" on public.comments;
create policy "admins read hidden comments" on public.comments
  for select to authenticated
  using (public.current_user_is_admin());

-- Admins can UPDATE any comment (hide, pin, edit body for moderation)
drop policy if exists "admins moderate any comment" on public.comments;
create policy "admins moderate any comment" on public.comments
  for update to authenticated
  using (public.current_user_is_admin())
  with check (public.current_user_is_admin());

-- Admins can DELETE any comment
drop policy if exists "admins delete any comment" on public.comments;
create policy "admins delete any comment" on public.comments
  for delete to authenticated
  using (public.current_user_is_admin());

-- ============================================================================
-- Admin RLS policies on profiles (so admin can see banned users, etc.)
-- ============================================================================
drop policy if exists "admins read all profiles" on public.profiles;
create policy "admins read all profiles" on public.profiles
  for select to authenticated
  using (public.current_user_is_admin());

drop policy if exists "admins update any profile" on public.profiles;
create policy "admins update any profile" on public.profiles
  for update to authenticated
  using (public.current_user_is_admin())
  with check (public.current_user_is_admin());

-- ============================================================================
-- Grant authenticated role permission to read is_admin column on own profile
-- (so client UI can check)
-- ============================================================================
grant select (id, display_name, avatar_url, is_admin) on public.profiles to anon;
grant select (id, display_name, avatar_url, is_admin, email, provider) on public.profiles to authenticated;
