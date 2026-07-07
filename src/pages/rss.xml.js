import { getCollection } from 'astro:content';
import rss from '@astrojs/rss';
import MarkdownIt from 'markdown-it';
import sanitizeHtml from 'sanitize-html';
import { SITE_DESCRIPTION, SITE_TITLE } from '../consts';

const parser = new MarkdownIt();

// Full-content feed, capped to the most recent items.
// - Full `content:encoded` is what AI crawlers (Perplexity/ChatGPT feed
//   ingestion) and Naver's RSS collector actually consume — a summary-only,
//   378-item archive feed was 271KB of near-useless metadata.
// - Mermaid fences are stripped: they render as raw code in feed readers
//   (the site converts them to static lists at build time, but the RSS
//   pipeline bypasses that remark plugin).
const FEED_LIMIT = 50;

function renderBody(body) {
	const withoutMermaid = (body || '').replace(/```mermaid[\s\S]*?```/g, '');
	return sanitizeHtml(parser.render(withoutMermaid), {
		allowedTags: sanitizeHtml.defaults.allowedTags.concat(['img']),
	});
}

export async function GET(context) {
	const posts = (await getCollection('blog', ({ data }) => !data.draft))
		.sort((a, b) => b.data.pubDate.valueOf() - a.data.pubDate.valueOf())
		.slice(0, FEED_LIMIT);
	return rss({
		title: SITE_TITLE,
		description: SITE_DESCRIPTION,
		site: context.site,
		customData: '<language>ko</language>',
		items: posts.map((post) => ({
			...post.data,
			link: `/blog/${post.id}/`,
			content: renderBody(post.body),
		})),
	});
}
