import { makeSupabase, serializeCookie, jsonResponse, type Env } from '../../_supabase';

/**
 * Server-side magic-link request — server-generated PKCE flow.
 * Body: { email: string, next?: string }
 */
export const onRequestPost: PagesFunction<Env> = async ({ request, env }) => {
	const url = new URL(request.url);
	let payload: { email?: string; next?: string };
	try {
		payload = await request.json();
	} catch {
		return jsonResponse({ error: 'invalid_json' }, { status: 400 });
	}
	const email = String(payload.email || '').trim().toLowerCase();
	const nextRaw = String(payload.next || '/');
	const next = nextRaw.startsWith('/') && !nextRaw.startsWith('//') ? nextRaw : '/';
	if (!email.includes('@') || email.length < 5 || email.length > 254) {
		return jsonResponse({ error: '이메일 형식을 확인해 주세요.' }, { status: 400 });
	}

	const cookies: any[] = [];
	const supabase = makeSupabase({ request, env, responseCookies: cookies });
	const { error } = await supabase.auth.signInWithOtp({
		email,
		options: {
			emailRedirectTo: `${url.origin}/api/auth/callback?next=${encodeURIComponent(next)}`,
		},
	});

	if (error) {
		console.error('[/api/auth/magic-link]', error.message);
		return jsonResponse({ error: error.message }, { status: 400 });
	}

	const setCookieHeaders = cookies.map((c) => serializeCookie(c.name, c.value, c.options));
	return jsonResponse({ ok: true }, { status: 200 }, setCookieHeaders);
};
