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

	// Prefer the server-stamped JWT app_metadata role. If the profile read is
	// temporarily broken by RLS/migration drift, do not lock out a real admin.
	const hasAdminClaim = (user.app_metadata as any)?.role === 'admin';
	const isAdmin = hasAdminClaim || profile?.is_admin === true;
	if (!isAdmin) {
		return { ok: false as const, response: jsonResponse({ error: profileError?.message || 'forbidden' }, { status: 403 }) };
	}

	return { ok: true as const, supabase, cookies, user, profile, profileError };
}

export const onRequestGet: PagesFunction<Env> = async ({ request, env }) => {
	const auth = await requireAdmin(request, env);
	if (!auth.ok) return auth.response;
	const { supabase, cookies, user, profile, profileError } = auth;

	const safe = async <T>(name: string, promise: PromiseLike<T & { error?: any }>) => {
		try {
			const result = await promise;
			return { name, result, error: result?.error || null };
		} catch (error: any) {
			return { name, result: null as any, error };
		}
	};

	const results = await Promise.all([
		safe('users_count', supabase.from('profiles').select('id', { count: 'exact', head: true })),
		safe('subscribers_count', supabase.from('subscribers').select('id', { count: 'exact', head: true })),
		safe('comments_count', supabase.from('comments').select('id', { count: 'exact', head: true })),
		safe('hidden_comments_count', supabase.from('comments').select('id', { count: 'exact', head: true }).eq('is_hidden', true)),
		safe('comments', supabase
			.from('comments')
			.select('id, post_slug, body, created_at, is_hidden, is_pinned, profiles!comments_author_id_fkey(display_name, email)')
			.order('created_at', { ascending: false })
			.limit(30)),
		safe('subscribers', supabase
			.from('subscribers')
			.select('email, source, created_at, confirmed_at, unsubscribed_at')
			.order('created_at', { ascending: false })
			.limit(20)),
		safe('users', supabase
			.from('profiles')
			.select('id, email, display_name, provider, is_admin, created_at')
			.order('created_at', { ascending: false })
			.limit(100)),
		safe('newsletter_sends', supabase
			.from('newsletter_sends')
			.select('email, post_slug, post_title, status, sent_at')
			.order('sent_at', { ascending: false })
			.limit(20)),
	]);

	const byName = Object.fromEntries(results.map((r) => [r.name, r]));
	const issueList = results
		.filter((r) => r.error)
		.map((r) => ({ name: r.name, message: r.error?.message || String(r.error), code: r.error?.code || null }));
	if (profileError) issueList.unshift({ name: 'profile_self', message: profileError.message, code: profileError.code || null });

	const users = byName.users_count?.result;
	const subs = byName.subscribers_count?.result;
	const allComments = byName.comments_count?.result;
	const hiddenComments = byName.hidden_comments_count?.result;
	const comments = byName.comments?.result;
	const subscribers = byName.subscribers?.result;
	const userRows = byName.users?.result;
	const sendRows = byName.newsletter_sends?.result;

	const setCookieHeaders = cookies.map((c) => serializeCookie(c.name, c.value, c.options));
	return jsonResponse(
		{
			user: {
				id: user.id,
				email: user.email,
				name: profile?.display_name || user.email?.split('@')[0] || '관리자',
			},
			stats: {
				users: users?.count ?? 0,
				subscribers: subs?.error ? null : (subs?.count ?? 0),
				comments: allComments?.count ?? 0,
				hidden: hiddenComments?.count ?? 0,
			},
			comments: comments?.error ? [] : (comments?.data || []),
			subscribers: subscribers?.error ? [] : (subscribers?.data || []),
			users: userRows?.error ? [] : (userRows?.data || []),
			newsletterSends: sendRows?.error ? [] : (sendRows?.data || []),
			issues: issueList,
			subscriberAccess: subscribers?.error ? 'migration_required' : 'ok',
			userAccess: userRows?.error ? 'unavailable' : 'ok',
			newsletterSendAccess: sendRows?.error ? 'migration_required' : 'ok',
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
