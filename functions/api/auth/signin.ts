import { makeSupabase, serializeCookie, redirectWithCookies, type Env } from '../../_supabase';

/**
 * Server-side OAuth init — generates PKCE verifier, stores in HttpOnly cookie,
 * redirects to Google. The browser never sees the verifier.
 *
 * Fixes "PKCE code verifier not found in storage" by ensuring verifier and
 * exchange both happen server-side.
 *
 * GET /api/auth/signin?provider=google&next=/blog/foo
 */
export const onRequestGet: PagesFunction<Env> = async ({ request, env }) => {
	const url = new URL(request.url);
	const provider = (url.searchParams.get('provider') || 'google').toLowerCase();
	const nextRaw = url.searchParams.get('next') || '/';
	const next = nextRaw.startsWith('/') && !nextRaw.startsWith('//') ? nextRaw : '/';

	if (!['google'].includes(provider)) {
		return Response.redirect(new URL('/login?error=invalid_provider', url.origin).toString(), 302);
	}

	const cookies: any[] = [];
	const supabase = makeSupabase({ request, env, responseCookies: cookies });

	const { data, error } = await supabase.auth.signInWithOAuth({
		provider: 'google',
		options: {
			redirectTo: `${url.origin}/api/auth/callback?next=${encodeURIComponent(next)}`,
			queryParams: { prompt: 'select_account' },
		},
	});

	if (error || !data?.url) {
		console.error('[/api/auth/signin]', error?.message);
		return Response.redirect(
			new URL(`/login?error=${encodeURIComponent(error?.message || 'signin_failed')}`, url.origin).toString(),
			302
		);
	}

	const setCookieHeaders = cookies.map((c) => serializeCookie(c.name, c.value, c.options));
	return redirectWithCookies(data.url, setCookieHeaders);
};
