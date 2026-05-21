import type { APIRoute, GetStaticPaths } from 'astro';
import { getCollection } from 'astro:content';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import satori from 'satori';
import { Resvg } from '@resvg/resvg-js';
import { CATEGORIES } from '../../content.config';

/**
 * Per-article Open Graph image generator.
 *
 * Builds one 1200×630 branded share card per blog post at build time:
 *   /og/<slug>.png
 *
 * Why: every article previously shared the same generic placeholder, so
 * pasting a migukstory link into KakaoTalk / Threads / X showed a broken-
 * looking generic image — which kills shares. A real card with the post's
 * Korean headline + category makes every share look intentional.
 *
 * satori (HTML-ish → SVG) + @resvg/resvg-js (SVG → PNG). Korean glyphs come
 * from a subsetted Gowun Batang WOFF bundled in src/assets/og/.
 */

// Read from the project root — process.cwd() is the repo root during
// `astro build`, so this resolves correctly regardless of where the built
// endpoint chunk lands.
const fontGowun = readFileSync(join(process.cwd(), 'src/assets/og/gowun-og.woff'));

export const getStaticPaths: GetStaticPaths = async () => {
	const posts = await getCollection('blog');
	return posts.map((post) => ({
		params: { slug: post.id.replace(/\.(md|mdx)$/, '') },
		props: { post },
	}));
};

export const GET: APIRoute = async ({ props }) => {
	const { post } = props as { post: any };
	const title: string = post.data.title;
	const catKey = post.data.category as keyof typeof CATEGORIES;
	const cat = CATEGORIES[catKey] ?? { label: '미국 스토리', color: '#B91C1C' };

	// satori accepts a hyperscript object tree (no JSX needed in a .ts file).
	const svg = await satori(
		{
			type: 'div',
			props: {
				style: {
					width: '1200px',
					height: '630px',
					display: 'flex',
					flexDirection: 'column',
					justifyContent: 'space-between',
					backgroundColor: '#FAF8F3',
					padding: '64px 72px',
					fontFamily: 'Gowun Batang',
				},
				children: [
					// Top row — category chip + brand
					{
						type: 'div',
						props: {
							style: { display: 'flex', justifyContent: 'space-between', alignItems: 'center' },
							children: [
								{
									type: 'div',
									props: {
										style: {
											display: 'flex',
											backgroundColor: cat.color,
											color: '#FAF8F3',
											fontSize: '30px',
											fontWeight: 700,
											padding: '10px 26px',
											borderRadius: '6px',
										},
										children: cat.label,
									},
								},
								{
									type: 'div',
									props: {
										style: { display: 'flex', fontSize: '30px', color: '#71717A', letterSpacing: '0.16em' },
										children: 'MIGUK STORY',
									},
								},
							],
						},
					},
					// Headline — the post title
					{
						type: 'div',
						props: {
							style: {
								display: 'flex',
								fontSize: title.length > 38 ? '64px' : '78px',
								fontWeight: 700,
								color: '#18181B',
								lineHeight: 1.28,
								letterSpacing: '-0.02em',
								maxWidth: '1056px',
							},
							children: title,
						},
					},
					// Bottom — brick rule + domain
					{
						type: 'div',
						props: {
							style: { display: 'flex', flexDirection: 'column' },
							children: [
								{
									type: 'div',
									props: {
										style: { display: 'flex', width: '120px', height: '8px', backgroundColor: '#B91C1C', marginBottom: '20px' },
										children: [],
									},
								},
								{
									type: 'div',
									props: {
										style: { display: 'flex', fontSize: '32px', color: '#52525B' },
										children: '미국 스토리 · 한국계 미국인을 위한 검증된 가이드',
									},
								},
							],
						},
					},
				],
			},
		},
		{
			width: 1200,
			height: 630,
			fonts: [
				{ name: 'Gowun Batang', data: fontGowun, weight: 700, style: 'normal' },
			],
		}
	);

	const png = new Resvg(svg, { fitTo: { mode: 'width', value: 1200 } }).render().asPng();

	return new Response(new Uint8Array(png), {
		headers: {
			'Content-Type': 'image/png',
			'Cache-Control': 'public, max-age=31536000, immutable',
		},
	});
};
