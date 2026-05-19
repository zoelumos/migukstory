// Site-wide constants

export const SITE_TITLE = '미국 스토리';
export const SITE_TITLE_EN = 'Miguk Story';
export const SITE_TAGLINE = '한국계 미국인을 위한 검증된 가이드';
export const SITE_DESCRIPTION = '미국에 사는 한국인을 위한 이민·세금·건강·교육 가이드. 매주 정부와 주요 언론의 1차 출처를 바탕으로 정리합니다.';
export const SITE_URL = 'https://migukstory.com';
export const SITE_AUTHOR = '미국 스토리 편집실';
export const ISSUE_NUMBER = '001';

// Named human authors for E-E-A-T (Person schema in JSON-LD).
// Each post can set `author: '<slug>'` in frontmatter; falls back to SITE_AUTHOR (Organization).
// `sameAs` should be real public profile URLs (LinkedIn / X / GitHub) — Google uses these for entity disambiguation.
export const AUTHORS: Record<string, {
	name: string;        // Display name (Korean preferred for KA audience)
	nameEn?: string;     // English transliteration
	jobTitle: string;    // Editorial title
	bio: string;         // Short Korean bio (1-3 sentences) for /authors/<slug>/
	bioFull?: string;    // Longer bio paragraph(s), shown on author page only
	expertise: string[]; // Categories of expertise — informs E-E-A-T 'knowsAbout'
	email?: string;
	sameAs: string[];    // Public profile URLs for Person.sameAs
	image?: string;      // Path under /public/ for author headshot
}> = {
	'steve-song': {
		name: '스티브 송',
		nameEn: 'Steve Song',
		jobTitle: '편집장 · Editor-in-Chief',
		bio: '미국 스토리 편집장. 한국계 미국인 가정의 이민·세무·재정 이슈를 1차 출처 기반으로 풀어 쓰는 데 집중합니다.',
		bioFull: '미국 스토리(Miguk Story)를 창간하고 운영합니다. 매주 USCIS, IRS, 한국 국세청, 주요 외신 등 1차 출처를 교차 확인하여 한국계 미국인 가정 관점에서 의미 있는 분석을 추가한 가이드 콘텐츠를 발행합니다. AI 도구는 자료 수집과 초안 작성 단계에서만 사용하며, 모든 게시 글은 최종적으로 사람이 검토·편집합니다.',
		expertise: ['immigration', 'tax', 'community', 'economy'],
		email: 'editor@migukstory.com',
		sameAs: [
			// Add real profile URLs as available; empty array is acceptable but Person.sameAs improves E-E-A-T.
		],
	},
	'editorial-staff': {
		name: '미국 스토리 편집실',
		nameEn: 'Miguk Story Editorial Staff',
		jobTitle: '편집실 · Editorial',
		bio: '미국 스토리 편집실에서 공동 작업한 글입니다. 사실관계는 명시된 1차 출처를 통해 검증되었습니다.',
		expertise: ['immigration', 'tax', 'health', 'education', 'retirement', 'community', 'real-estate', 'economy'],
		email: 'editor@migukstory.com',
		sameAs: [],
	},
};

// Organization sameAs — public profiles for Organization schema in JSON-LD.
// Add LinkedIn / X / GitHub / Facebook etc. as they become available.
export const ORG_SAME_AS: string[] = [
	// 'https://www.linkedin.com/company/migukstory',
	// 'https://x.com/migukstory',
];

// Default author slug when frontmatter doesn't specify one.
export const DEFAULT_AUTHOR_SLUG = 'editorial-staff';
