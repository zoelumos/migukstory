import { makeSupabase, jsonResponse, type Env } from '../_supabase';

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

type SubscriberPayload = {
	email?: string;
	source?: string;
	metadata?: Record<string, unknown>;
	website?: string;
};

async function readPayload(request: Request): Promise<SubscriberPayload | null> {
	const contentType = request.headers.get('content-type') || '';
	try {
		if (contentType.includes('application/json')) {
			return await request.json();
		}
		if (contentType.includes('application/x-www-form-urlencoded') || contentType.includes('multipart/form-data')) {
			const form = await request.formData();
			return {
				email: String(form.get('email') || ''),
				source: String(form.get('source') || ''),
				website: String(form.get('website') || ''),
			};
		}
	} catch {
		return null;
	}
	return null;
}

function safeSource(value: unknown) {
	return String(value || 'newsletter_form')
		.toLowerCase()
		.replace(/[^a-z0-9_-]/g, '_')
		.slice(0, 60) || 'newsletter_form';
}

function safeMetadata(value: unknown): Record<string, string | number | boolean | null> {
	if (!value || typeof value !== 'object' || Array.isArray(value)) return {};
	const entries: Array<[string, string | number | boolean | null]> = [];
	for (const [rawKey, rawValue] of Object.entries(value as Record<string, unknown>).slice(0, 20)) {
		const key = rawKey.replace(/[^a-zA-Z0-9_-]/g, '_').slice(0, 40);
		if (!key) continue;
		if (rawValue == null || typeof rawValue === 'boolean' || typeof rawValue === 'number') {
			entries.push([key, rawValue ?? null]);
		} else if (typeof rawValue === 'string') {
			entries.push([key, rawValue.slice(0, 200)]);
		}
	}
	return Object.fromEntries(entries);
}

function wantsHtmlRedirect(request: Request) {
	const contentType = request.headers.get('content-type') || '';
	const accept = request.headers.get('accept') || '';
	return contentType.includes('application/x-www-form-urlencoded')
		|| contentType.includes('multipart/form-data')
		|| (accept.includes('text/html') && !accept.includes('application/json'));
}

function redirectToSubscribed(request: Request, status: 'ok' | 'invalid' | 'error') {
	const url = new URL('/subscribed/', request.url);
	url.searchParams.set('status', status);
	return Response.redirect(url.toString(), 303);
}

/**
 * Newsletter signup — POST JSON or regular form data.
 * Uses anon Supabase role; RLS permits INSERT while blocking public SELECT.
 * The form-data fallback is intentional: if client JS is blocked, the signup
 * still reaches this endpoint and redirects to an HTML status page.
 */
export const onRequestPost: PagesFunction<Env> = async ({ request, env }) => {
	const cookies: any[] = [];
	const supabase = makeSupabase({ request, env, responseCookies: cookies });
	const htmlRedirect = wantsHtmlRedirect(request);

	const payload = await readPayload(request);
	if (!payload) {
		return htmlRedirect ? redirectToSubscribed(request, 'error') : jsonResponse({ error: 'invalid_payload' }, { status: 400 });
	}

	// Honeypot: pretend success so bots do not learn the filter.
	if (payload.website) {
		return htmlRedirect ? redirectToSubscribed(request, 'ok') : jsonResponse({ ok: true }, { status: 201 });
	}

	const email = String(payload.email || '').trim().toLowerCase();
	const source = safeSource(payload.source);
	if (!EMAIL_RE.test(email) || email.length < 5 || email.length > 254) {
		return htmlRedirect ? redirectToSubscribed(request, 'invalid') : jsonResponse({ error: 'invalid_email' }, { status: 400 });
	}

	const { error } = await supabase.from('subscribers').insert({
		email,
		source,
		metadata: {
			...safeMetadata(payload.metadata),
			ip: request.headers.get('cf-connecting-ip') || null,
			ua: request.headers.get('user-agent') || null,
			referer: request.headers.get('referer') || null,
			ts: new Date().toISOString(),
		},
	});

	if (error && error.code !== '23505') {
		console.error('[/api/subscribers] insert error', { code: error.code, message: error.message });
		return htmlRedirect ? redirectToSubscribed(request, 'error') : jsonResponse({ error: 'subscriber_insert_failed' }, { status: 400 });
	}

	// Return the same public success shape for new and duplicate emails to avoid
	// exposing whether a specific address is already subscribed.
	return htmlRedirect ? redirectToSubscribed(request, 'ok') : jsonResponse({ ok: true }, { status: 201 });
};
