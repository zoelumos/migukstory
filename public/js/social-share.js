/**
 * Social-share "copy link" button — external (not inline) to satisfy the strict
 * CSP. Reads the URL from the button's data-url attribute.
 */
document.querySelectorAll('.btn.copy').forEach(function (btn) {
	btn.addEventListener('click', function () {
		var url = btn.getAttribute('data-url');
		var label = btn.querySelector('.btn-label');
		if (!label) return;
		navigator.clipboard.writeText(url).then(function () {
			var orig = label.textContent;
			label.textContent = '복사됨 ✓';
			btn.classList.add('copied');
			setTimeout(function () {
				label.textContent = orig;
				btn.classList.remove('copied');
			}, 1500);
		}).catch(function () { /* noop */ });
	});
});
