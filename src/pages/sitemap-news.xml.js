import { getCollection } from 'astro:content';
import { SITE_TITLE, SITE_URL } from '../consts';

const escapeXml = (value) => String(value)
	.replaceAll('&', '&amp;')
	.replaceAll('<', '&lt;')
	.replaceAll('>', '&gt;')
	.replaceAll('"', '&quot;')
	.replaceAll("'", '&apos;');

export async function GET() {
	const now = Date.now();
	const twoDays = 48 * 60 * 60 * 1000;
	const posts = (await getCollection('blog', ({ data }) => !data.draft))
		.filter((post) => now - post.data.pubDate.valueOf() <= twoDays)
		.sort((a, b) => b.data.pubDate.valueOf() - a.data.pubDate.valueOf())
		.slice(0, 100);

	const urls = posts.map((post) => `
	<url>
		<loc>${SITE_URL}/blog/${escapeXml(post.id)}/</loc>
		<news:news>
			<news:publication>
				<news:name>${escapeXml(SITE_TITLE)}</news:name>
				<news:language>ko</news:language>
			</news:publication>
			<news:publication_date>${post.data.pubDate.toISOString()}</news:publication_date>
			<news:title>${escapeXml(post.data.title)}</news:title>
		</news:news>
	</url>`).join('\n');

	return new Response(`<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:news="http://www.google.com/schemas/sitemap-news/0.9">
${urls}
</urlset>
`, {
		headers: { 'Content-Type': 'application/xml; charset=utf-8' },
	});
}
