# Security Hardening — Manual Cloudflare Steps

This repo now keeps OAuth/Supabase sessions in server-side HttpOnly cookies instead of browser localStorage. The remaining hardening below lives in Cloudflare/Supabase dashboards and should not be committed as secrets.

## Cloudflare WAF

Cloudflare dashboard → Security → WAF:

1. Enable Cloudflare Managed Ruleset and OWASP Core Ruleset.
2. Add a custom rule for private routes:
   - Expression: `(http.request.uri.path contains "/admin") or (http.request.uri.path contains "/auth")`
   - Action: Managed Challenge, or Block if no legitimate external traffic needs those paths.
3. Add rate limiting for API abuse:
   - Expression: `http.request.uri.path contains "/api/"`
   - Suggested start: 60 requests / 1 minute per client IP, then tune from Security Events.
4. Method allow-list for `/api/*`: allow `GET`, `POST`, `OPTIONS`; challenge/block unusual methods.

## Turnstile

Use Turnstile for newsletter and comment abuse protection.

1. Cloudflare dashboard → Turnstile → Add widget.
2. Domain: `migukstory.com`; mode: Managed.
3. Store keys:
   - `PUBLIC_TURNSTILE_SITE_KEY` as public build-time env.
   - `TURNSTILE_SECRET_KEY` as encrypted Cloudflare Pages env.
4. Frontend: render widget on subscriber/comment forms.
5. Backend: verify `cf-turnstile-response` in `functions/api/subscribers.ts` and `functions/api/comments.ts` via `https://challenges.cloudflare.com/turnstile/v0/siteverify`.
6. When enabled, add `https://challenges.cloudflare.com` to `script-src`, `script-src-elem`, and `frame-src` in `public/_headers`.

## Supabase migration

Apply `migrations/007_profiles_subscribers_aal2_hardening.sql` in Supabase:

```bash
node scripts/run_migration.mjs migrations/007_profiles_subscribers_aal2_hardening.sql
```

This removes anon `is_admin` profile exposure, adds AAL2/MFA gating for admin profile writes, and permits authenticated admins to read subscribers via RLS-backed Pages Functions.

## Verification

- `/login` still signs in through `/api/auth/*`.
- DevTools Application → Local Storage has no `sb-*` Supabase session tokens after login.
- Comments can list and post through `/api/comments` while logged in.
- `/admin` loads through `/api/admin` and does not require browser Supabase tokens.
- CSP header no longer allows inline scripts in `script-src`/`script-src-elem`.
