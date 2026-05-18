import { makeSupabase, serializeCookie, redirectWithCookies, type Env } from '../../_supabase';

/**
 * Logout — global signOut (revokes refresh-token family on Supabase server),
 * clears HttpOnly cookies, redirects to /.
 */
const handler: PagesFunction<Env> = async ({ request, env }) => {
	const url = new URL(request.url);
	const nextRaw = url.searchParams.get('next') || '/';
	const next = nextRaw.startsWith('/') && !nextRaw.startsWith('//') ? nextRaw : '/';

	const cookies: any[] = [];
	const supabase = makeSupabase({ request, env, responseCookies: cookies });
	try {
		await supabase.auth.signOut({ scope: 'global' });
	} catch (e) {
		console.error('[/api/auth/logout]', e);
	}

	// Belt-and-suspenders: explicit cookie deletion regardless of signOut result
	const ref = env.PUBLIC_SUPABASE_URL.replace(/https:\/\/|\.supabase\.co/g, '');
	const isProd = env.PUBLIC_SUPABASE_URL.includes('hoemvraesebfvtkkjbdx');
	const deleteOpts = { path: '/', domain: isProd ? '.migukstory.com' : undefined, expires: 0, httpOnly: true, secure: true, sameSite: 'lax' };
	const deletes = [
		serializeCookie(`sb-${ref}-auth-token`, '', deleteOpts),
		serializeCookie(`sb-${ref}-auth-token.0`, '', deleteOpts),
		serializeCookie(`sb-${ref}-auth-token.1`, '', deleteOpts),
	];
	const setCookieHeaders = [...cookies.map((c) => serializeCookie(c.name, c.value, c.options)), ...deletes];

	return redirectWithCookies(new URL(next, url.origin).toString(), setCookieHeaders);
};

export const onRequestGet = handler;
export const onRequestPost = handler;
