import type { APIRoute } from 'astro';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import satori from 'satori';
import { Resvg } from '@resvg/resvg-js';

/**
 * Site-wide branded Open Graph card: /og/site.png
 *
 * Used as the default share image for the homepage and hub pages that don't
 * pass their own image. Before this, non-article pages shared a generic Astro
 * placeholder photo — brand-damaging on KakaoTalk/X shares and in AI-search
 * citations. Same satori pipeline as the per-article cards.
 */

const fontGowun = readFileSync(join(process.cwd(), 'src/assets/og/gowun-og.woff'));

export const GET: APIRoute = async () => {
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
					{
						type: 'div',
						props: {
							style: { display: 'flex', fontSize: '30px', color: '#71717A', letterSpacing: '0.16em' },
							children: 'MIGUK STORY',
						},
					},
					{
						type: 'div',
						props: {
							style: {
								display: 'flex',
								flexDirection: 'column',
								gap: '28px',
							},
							children: [
								{
									type: 'div',
									props: {
										style: {
											display: 'flex',
											fontSize: '96px',
											fontWeight: 700,
											color: '#18181B',
											letterSpacing: '-0.02em',
										},
										children: '미국 스토리',
									},
								},
								{
									type: 'div',
									props: {
										style: {
											display: 'flex',
											fontSize: '40px',
											color: '#3F3F46',
											lineHeight: 1.4,
										},
										children: '이민·세금·건강보험·은퇴 — 한국계 미국인을 위한 검증된 가이드',
									},
								},
							],
						},
					},
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
										children: 'migukstory.com',
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
