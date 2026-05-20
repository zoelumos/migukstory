/**
 * Pages Functions root middleware — runs before every request (static + functions).
 *
 * Sole job: canonicalize the host. www.migukstory.com → migukstory.com (301),
 * preserving path + query. Everything else passes straight through to the
 * static asset or matched /api/* function via context.next().
 *
 * Why here and not _redirects: Cloudflare Pages `_redirects` matches on path,
 * not reliably on hostname. A middleware sees the full request URL.
 */
export const onRequest: PagesFunction = async (context) => {
	const url = new URL(context.request.url);
	if (url.hostname === 'www.migukstory.com') {
		url.hostname = 'migukstory.com';
		return Response.redirect(url.toString(), 301);
	}
	return context.next();
};
