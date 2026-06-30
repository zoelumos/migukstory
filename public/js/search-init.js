/**
 * Pagefind search init — external (not inline) to satisfy the strict CSP.
 * Mounts PagefindUI into #search and pre-fills from ?q=.
 */
document.addEventListener('DOMContentLoaded', async function () {
	const { PagefindUI } = await import('/_pagefind/pagefind-ui.js');
	new PagefindUI({
		element: '#search',
		showImages: false,
		excerptLength: 30,
		translations: {
			placeholder: '검색어를 입력하세요 (예: FBAR, I-130, 시민권 시험)',
			clear_search: '지우기',
			load_more: '더 보기',
			search_label: '미국 스토리 검색',
			filters_label: '필터',
			zero_results: '"[SEARCH_TERM]"에 대한 결과가 없습니다.',
			many_results: '"[SEARCH_TERM]"에 대한 결과 [COUNT]개',
			one_result: '"[SEARCH_TERM]"에 대한 결과 1개',
			alt_search: '"[SEARCH_TERM]"에 대한 결과를 찾지 못했습니다. 대신 "[DIFFERENT_TERM]"을 시도해 보세요.',
			search_suggestion: '"[SEARCH_TERM]"에 대한 결과가 없습니다. 다음 검색어를 시도해 보세요:',
			searching: '"[SEARCH_TERM]" 검색 중...',
		},
	});

	// Pre-fill from ?q= query param
	const params = new URLSearchParams(window.location.search);
	const q = params.get('q');
	if (q) {
		setTimeout(function () {
			const input = document.querySelector('#search input[type="text"]');
			if (input) {
				input.value = q;
				input.dispatchEvent(new Event('input', { bubbles: true }));
			}
		}, 200);
	}
});
