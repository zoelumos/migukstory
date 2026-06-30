/**
 * Reading progress bar — external (not inline) to satisfy the strict CSP
 * (script-src 'self', no 'unsafe-inline'). Renders a thin top bar that tracks
 * scroll through the <article>. No-op on pages without an article.
 */
document.addEventListener('DOMContentLoaded', function () {
	var article = document.querySelector('article');
	if (!article) return;
	var bar = document.createElement('div');
	bar.className = 'reading-progress';
	document.body.appendChild(bar);
	var onScroll = function () {
		var rect = article.getBoundingClientRect();
		var total = rect.height - window.innerHeight;
		var scrolled = Math.max(0, -rect.top);
		var pct = Math.min(100, Math.max(0, (scrolled / total) * 100));
		bar.style.width = pct + '%';
	};
	window.addEventListener('scroll', onScroll, { passive: true });
	onScroll();
});
