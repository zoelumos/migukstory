import { makeSupabase, serializeCookie, redirectWithCookies, type Env } from '../../_supabase';

/**
 * OAuth callback — exchanges Google's code for a Supabase session, sets HttpOnly
 * cookies, redirects to ?next= or /.
 *
 * Per IETF draft-ietf-oauth-browser-based-apps-26 §6.1.4: token stays out of JS.
 */
export const onRequestGet: PagesFunction<Env> = async ({ request, env }) => {
	const url = new URL(request.url);
	const code = url.searchParams.get('code');
	const oauthErr = url.searchParams.get('error');
	const nextRaw = url.searchParams.get('next') || '/';
	const next = nextRaw.startsWith('/') && !nextRaw.startsWith('//') ? nextRaw : '/';

	if (oauthErr) {
		const desc = url.searchParams.get('error_description') || oauthErr;
		return Response.redirect(new URL(`/login?error=${encodeURIComponent(desc)}`, url.origin).toString(), 302);
	}
	if (!code) {
		return Response.redirect(new URL('/login?error=missing_code', url.origin).toString(), 302);
	}

	const cookies: any[] = [];
	const supabase = makeSupabase({ request, env, responseCookies: cookies });
	const { error } = await supabase.auth.exchangeCodeForSession(code);
	if (error) {
		console.error('[/api/auth/callback]', error.message);
		return Response.redirect(new URL(`/login?error=${encodeURIComponent(error.message)}`, url.origin).toString(), 302);
	}

	const setCookieHeaders = cookies.map((c) => serializeCookie(c.name, c.value, c.options));
	return redirectWithCookies(new URL(next, url.origin).toString(), setCookieHeaders);
};
