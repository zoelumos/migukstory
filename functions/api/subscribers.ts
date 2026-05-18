import { makeSupabase, jsonResponse, type Env } from '../_supabase';

/**
 * Newsletter signup — POST { email, source, metadata?, website? (honeypot) }.
 * Uses anon role; RLS lets anon INSERT (never SELECT).
 */
export const onRequestPost: PagesFunction<Env> = async ({ request, env }) => {
	const cookies: any[] = [];
	const supabase = makeSupabase({ request, env, responseCookies: cookies });

	let payload: { email?: string; source?: string; metadata?: Record<string, unknown>; website?: string };
	try {
		payload = await request.json();
	} catch {
		return jsonResponse({ error: 'invalid_json' }, { status: 400 });
	}

	// Honeypot
	if (payload.website) return jsonResponse({ ok: true }, { status: 201 });

	const email = String(payload.email || '').trim().toLowerCase();
	const source = String(payload.source || 'newsletter_form').slice(0, 60);
	if (!email.includes('@') || email.length < 5 || email.length > 254) {
		return jsonResponse({ error: 'invalid_email' }, { status: 400 });
	}

	const { error } = await supabase.from('subscribers').insert({
		email,
		source,
		metadata: {
			...payload.metadata,
			ip: request.headers.get('cf-connecting-ip') || null,
			ua: request.headers.get('user-agent') || null,
			referer: request.headers.get('referer') || null,
			ts: new Date().toISOString(),
		},
	});

	if (error) {
		if (error.code === '23505') return jsonResponse({ ok: true, duplicate: true });
		console.error('[/api/subscribers] insert error', error);
		return jsonResponse({ error: error.message }, { status: 400 });
	}

	return jsonResponse({ ok: true }, { status: 201 });
};
