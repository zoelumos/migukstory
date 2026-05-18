/**
 * Shared helper for Cloudflare Pages Functions.
 *
 * Creates a Supabase server client that reads/writes HttpOnly cookies via the
 * standard Web Request/Response cookie APIs. @supabase/ssr is bundled at build.
 *
 * Used by /functions/api/auth/* and /functions/api/comments + subscribers.
 */
import { createServerClient, parseCookieHeader } from '@supabase/ssr';

export interface Env {
	PUBLIC_SUPABASE_URL: string;
	PUBLIC_SUPABASE_PUBLISHABLE_KEY: string;
}

export function makeSupabase({
	request,
	env,
	responseCookies,
}: {
	request: Request;
	env: Env;
	responseCookies: Array<{ name: string; value: string; options: any }>;
}) {
	const url = env.PUBLIC_SUPABASE_URL;
	const anon = env.PUBLIC_SUPABASE_PUBLISHABLE_KEY;
	const isProd = url.includes('hoemvraesebfvtkkjbdx');

	return createServerClient(url, anon, {
		cookies: {
			getAll: () =>
				parseCookieHeader(request.headers.get('Cookie') ?? '').map(({ name, value }) => ({
					name,
					value: value ?? '',
				})),
			setAll: (toSet) => {
				toSet.forEach(({ name, value, options }) => {
					responseCookies.push({
						name,
						value,
						options: {
							...options,
							httpOnly: true,
							secure: true,
							sameSite: 'lax',
							path: '/',
							domain: isProd ? '.migukstory.com' : undefined,
						},
					});
				});
			},
		},
		auth: {
			flowType: 'pkce',
			detectSessionInUrl: false,
			autoRefreshToken: true,
			persistSession: true,
		},
	});
}

// Serialize a cookie object into a Set-Cookie header value
export function serializeCookie(name: string, value: string, options: any = {}): string {
	const parts: string[] = [`${name}=${encodeURIComponent(value)}`];
	if (options.maxAge != null) parts.push(`Max-Age=${options.maxAge}`);
	if (options.domain) parts.push(`Domain=${options.domain}`);
	if (options.path) parts.push(`Path=${options.path}`);
	if (options.expires) parts.push(`Expires=${new Date(options.expires).toUTCString()}`);
	if (options.httpOnly) parts.push('HttpOnly');
	if (options.secure) parts.push('Secure');
	if (options.sameSite) parts.push(`SameSite=${options.sameSite[0].toUpperCase() + options.sameSite.slice(1)}`);
	return parts.join('; ');
}

export function jsonResponse(body: unknown, init: ResponseInit = {}, setCookieHeaders: string[] = []) {
	const headers = new Headers({
		'Content-Type': 'application/json',
		'Cache-Control': 'no-store',
		...(init.headers as Record<string, string> | undefined),
	});
	setCookieHeaders.forEach((c) => headers.append('Set-Cookie', c));
	return new Response(JSON.stringify(body), { ...init, headers });
}

export function redirectWithCookies(to: string, setCookieHeaders: string[] = []) {
	const headers = new Headers({ Location: to });
	setCookieHeaders.forEach((c) => headers.append('Set-Cookie', c));
	return new Response(null, { status: 302, headers });
}
