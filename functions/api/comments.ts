import { makeSupabase, serializeCookie, jsonResponse, type Env } from '../_supabase';

/**
 * Comments API
 *  - GET ?slug=/blog/foo/   → list non-hidden comments for that post
 *  - POST { post_slug, body } → insert as auth.uid()
 */
export const onRequestGet: PagesFunction<Env> = async ({ request, env }) => {
	const url = new URL(request.url);
	const slug = url.searchParams.get('slug');
	if (!slug) return jsonResponse({ error: 'missing slug' }, { status: 400 });

	const cookies: any[] = [];
	const supabase = makeSupabase({ request, env, responseCookies: cookies });
	const { data, error } = await supabase
		.from('comments')
		.select('id, body, created_at, is_pinned, profiles!comments_author_id_fkey(display_name, avatar_url)')
		.eq('post_slug', slug)
		.eq('is_hidden', false)
		.order('is_pinned', { ascending: false })
		.order('created_at', { ascending: true });

	if (error) return jsonResponse({ error: error.message }, { status: 400 });
	return jsonResponse({ comments: data || [] });
};

export const onRequestPost: PagesFunction<Env> = async ({ request, env }) => {
	const cookies: any[] = [];
	const supabase = makeSupabase({ request, env, responseCookies: cookies });
	const { data: { user } } = await supabase.auth.getUser();
	if (!user) return jsonResponse({ error: 'unauthorized' }, { status: 401 });

	let payload: { post_slug?: string; body?: string };
	try {
		payload = await request.json();
	} catch {
		return jsonResponse({ error: 'invalid_json' }, { status: 400 });
	}

	const post_slug = String(payload.post_slug || '').trim();
	const body = String(payload.body || '').trim();

	if (!/^\/[a-z0-9\/_\-]+\/?$/.test(post_slug) || post_slug.length > 200) {
		return jsonResponse({ error: 'invalid_slug' }, { status: 400 });
	}
	if (body.length < 2 || body.length > 5000) {
		return jsonResponse({ error: 'invalid_body_length' }, { status: 400 });
	}

	const { data, error } = await supabase
		.from('comments')
		.insert({ post_slug, body, author_id: user.id })
		.select('id')
		.single();

	if (error) {
		console.error('[/api/comments] insert error', error);
		return jsonResponse({ error: error.message }, { status: 400 });
	}

	const setCookieHeaders = cookies.map((c) => serializeCookie(c.name, c.value, c.options));
	return jsonResponse({ ok: true, id: data.id }, { status: 201 }, setCookieHeaders);
};
