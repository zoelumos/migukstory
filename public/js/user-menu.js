/**
 * UserMenu hydration — external (not inline) so it passes the strict CSP
 * (script-src 'self', no 'unsafe-inline'). Same pattern as nav-toggle.js /
 * article-toc.js. Swaps the loading skeleton for a login link or the
 * signed-in pill based on /api/auth/session. Never touches tokens.
 */
(function () {
	var root = document.querySelector('.user-menu');
	if (!root) return;

	var skeleton = root.querySelector('.skeleton');
	var loginLink = root.querySelector('.login-link');
	var pill = root.querySelector('.user-pill');
	var avatar = root.querySelector('.avatar');
	var nameEl = root.querySelector('.display-name');
	var adminChip = root.querySelector('.admin-chip');

	function renderLoggedOut() {
		root.dataset.state = 'logged-out';
		if (skeleton) skeleton.hidden = true;
		if (loginLink) loginLink.hidden = false;
		if (pill) pill.hidden = true;
	}

	function renderLoggedIn(user) {
		root.dataset.state = 'logged-in';
		if (skeleton) skeleton.hidden = true;
		if (loginLink) loginLink.hidden = true;
		if (pill) pill.hidden = false;
		if (nameEl) nameEl.textContent = user.name;
		if (avatar) {
			if (user.avatar_url) {
				avatar.src = user.avatar_url;
				avatar.hidden = false;
			} else {
				avatar.hidden = true;
			}
		}
		if (adminChip) adminChip.hidden = !user.is_admin;
	}

	fetch('/api/auth/session', { credentials: 'same-origin' })
		.then(function (r) { return r.json(); })
		.then(function (data) {
			if (data.authenticated && data.user) renderLoggedIn(data.user);
			else renderLoggedOut();
		})
		.catch(renderLoggedOut);
})();
