import { makeSupabase, serializeCookie, jsonResponse, type Env } from '../../_supabase';

/**
 * Returns the current user's session summary based on HttpOnly cookies.
 * Used by UserMenu + Comments components to render logged-in/out state.
 */
export const onRequestGet: PagesFunction<Env> = async ({ request, env }) => {
	const cookies: any[] = [];
	const supabase = makeSupabase({ request, env, responseCookies: cookies });
	const { data: { user } } = await supabase.auth.getUser();

	if (!user) {
		return jsonResponse({ authenticated: false });
	}

	const { data: profile } = await supabase
		.from('profiles')
		.select('display_name, avatar_url, is_admin')
		.eq('id', user.id)
		.maybeSingle();

	const role = (user.app_metadata as any)?.role;
	const setCookieHeaders = cookies.map((c) => serializeCookie(c.name, c.value, c.options));

	return jsonResponse(
		{
			authenticated: true,
			user: {
				id: user.id,
				email: user.email,
				name: profile?.display_name || user.email?.split('@')[0] || '독자',
				avatar_url: profile?.avatar_url || null,
				is_admin: profile?.is_admin === true || role === 'admin',
			},
		},
		{},
		setCookieHeaders
	);
};
