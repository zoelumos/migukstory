import { makeSupabase, serializeCookie, jsonResponse, type Env } from '../_supabase';

/**
 * Comments API
 *  - GET ?slug=/blog/foo/   → list non-hidden comments for that post
 *  - POST { post_slug, body } → insert as auth.uid()
 */
const normalizePostSlug = (value: string) => {
	const path = String(value || '').split('?')[0].split('#')[0].trim();
	if (!path) return '';
	const withLead = path.startsWith('/') ? path : `/${path}`;
	return withLead.endsWith('/') ? withLead : `${withLead}/`;
};

const slugVariants = (slug: string) => {
	const canonical = normalizePostSlug(slug);
	const noTrailing = canonical.length > 1 ? canonical.replace(/\/$/, '') : canonical;
	return [...new Set([canonical, noTrailing])];
};

const commentSelect = 'id, post_slug, body, created_at, is_pinned, profiles!comments_author_id_fkey(display_name, avatar_url)';
const bareCommentSelect = 'id, post_slug, body, created_at, is_pinned';

export const onRequestGet: PagesFunction<Env> = async ({ request, env }) => {
	const url = new URL(request.url);
	const slug = normalizePostSlug(url.searchParams.get('slug') || '');
	if (!slug) return jsonResponse({ error: 'missing slug' }, { status: 400 });

	const cookies: any[] = [];
	const supabase = makeSupabase({ request, env, responseCookies: cookies });
	const variants = slugVariants(slug);
	const query = (select: string) => supabase
		.from('comments')
		.select(select)
		.in('post_slug', variants)
		.eq('is_hidden', false)
		.order('is_pinned', { ascending: false })
		.order('created_at', { ascending: true });

	let { data, error } = await query(commentSelect);

	// If the public profile display-field migration is missing/drifted, PostgREST
	// can fail the embedded profiles join and make real comments disappear. Keep
	// the discussion visible with anonymous authors, and surface the schema issue
	// to the console/admin instead of returning an empty thread to readers.
	if (error && /profiles|permission|relationship|schema cache/i.test(error.message || '')) {
		console.error('[/api/comments] profile join failed; falling back to bare comments', error);
		const fallback = await query(bareCommentSelect);
		data = (fallback.data || []).map((comment: any) => ({ ...comment, profiles: null }));
		error = fallback.error;
	}

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

	const post_slug = normalizePostSlug(payload.post_slug || '');
	const body = String(payload.body || '').trim();

	if (!/^\/[a-z0-9\/_\-]+\/$/.test(post_slug) || post_slug.length > 200) {
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
