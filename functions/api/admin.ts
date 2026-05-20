import { makeSupabase, serializeCookie, jsonResponse, type Env } from '../_supabase';

async function requireAdmin(request: Request, env: Env) {
	const cookies: any[] = [];
	const supabase = makeSupabase({ request, env, responseCookies: cookies });
	const { data: { user }, error: userError } = await supabase.auth.getUser();
	if (userError || !user) {
		return { ok: false as const, response: jsonResponse({ error: 'unauthorized' }, { status: 401 }) };
	}

	const { data: profile, error: profileError } = await supabase
		.from('profiles')
		.select('display_name, email, is_admin')
		.eq('id', user.id)
		.maybeSingle();

	const isAdmin = profile?.is_admin === true || (user.app_metadata as any)?.role === 'admin';
	if (profileError || !isAdmin) {
		return { ok: false as const, response: jsonResponse({ error: 'forbidden' }, { status: 403 }) };
	}

	return { ok: true as const, supabase, cookies, user, profile };
}

export const onRequestGet: PagesFunction<Env> = async ({ request, env }) => {
	const auth = await requireAdmin(request, env);
	if (!auth.ok) return auth.response;
	const { supabase, cookies, user, profile } = auth;

	const [users, subs, allComments, hiddenComments, comments, subscribers] = await Promise.all([
		supabase.from('profiles').select('id', { count: 'exact', head: true }),
		supabase.from('subscribers').select('id', { count: 'exact', head: true }),
		supabase.from('comments').select('id', { count: 'exact', head: true }),
		supabase.from('comments').select('id', { count: 'exact', head: true }).eq('is_hidden', true),
		supabase
			.from('comments')
			.select('id, post_slug, body, created_at, is_hidden, is_pinned, profiles!comments_author_id_fkey(display_name, email)')
			.order('created_at', { ascending: false })
			.limit(30),
		supabase
			.from('subscribers')
			.select('email, source, created_at')
			.order('created_at', { ascending: false })
			.limit(20),
	]);

	// Subscriber SELECT is enabled by migration 007. Until that migration is
	// applied in Supabase, keep the rest of the admin dashboard working and show
	// subscribers as unavailable instead of failing the whole endpoint.
	const firstError = [users, allComments, hiddenComments, comments].find((r) => r.error)?.error;
	if (firstError) return jsonResponse({ error: firstError.message }, { status: 400 });

	const setCookieHeaders = cookies.map((c) => serializeCookie(c.name, c.value, c.options));
	return jsonResponse(
		{
			user: {
				id: user.id,
				email: user.email,
				name: profile?.display_name || user.email?.split('@')[0] || '관리자',
			},
			stats: {
				users: users.count ?? 0,
				subscribers: subs.error ? null : (subs.count ?? 0),
				comments: allComments.count ?? 0,
				hidden: hiddenComments.count ?? 0,
			},
			comments: comments.data || [],
			subscribers: subscribers.error ? [] : (subscribers.data || []),
			subscriberAccess: subscribers.error ? 'migration_required' : 'ok',
		},
		{},
		setCookieHeaders
	);
};

export const onRequestPost: PagesFunction<Env> = async ({ request, env }) => {
	const auth = await requireAdmin(request, env);
	if (!auth.ok) return auth.response;
	const { supabase, cookies } = auth;

	let payload: { id?: string; action?: 'toggle-hide' | 'toggle-pin' | 'delete'; state?: boolean };
	try {
		payload = await request.json();
	} catch {
		return jsonResponse({ error: 'invalid_json' }, { status: 400 });
	}

	if (!payload.id || !payload.action) {
		return jsonResponse({ error: 'missing_id_or_action' }, { status: 400 });
	}

	let result;
	if (payload.action === 'toggle-hide') {
		result = await supabase.from('comments').update({ is_hidden: payload.state === true }).eq('id', payload.id);
	} else if (payload.action === 'toggle-pin') {
		result = await supabase.from('comments').update({ is_pinned: payload.state === true }).eq('id', payload.id);
	} else if (payload.action === 'delete') {
		result = await supabase.from('comments').delete().eq('id', payload.id);
	} else {
		return jsonResponse({ error: 'invalid_action' }, { status: 400 });
	}

	if (result.error) return jsonResponse({ error: result.error.message }, { status: 400 });
	const setCookieHeaders = cookies.map((c) => serializeCookie(c.name, c.value, c.options));
	return jsonResponse({ ok: true }, {}, setCookieHeaders);
};
