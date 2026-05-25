(() => {
	const initComments = (root) => {
		const postSlug = root.dataset.postSlug || window.location.pathname;
		const composeForm = root.querySelector('[data-compose]');
		const loginPrompt = root.querySelector('[data-login-prompt]');
		const list = root.querySelector('[data-comment-list]');
		const countEl = root.querySelector('[data-count]');
		const meAvatar = root.querySelector('[data-me-avatar]');
		const meName = root.querySelector('[data-me-name]');
		const charEl = root.querySelector('[data-char]');
		const textarea = root.querySelector('textarea[name="body"]');
		const loginLink = root.querySelector('#comments-login-link');
		let currentUser = null;

		const escapeHtml = (s) =>
			String(s || '')
				.replace(/&/g, '&amp;')
				.replace(/</g, '&lt;')
				.replace(/>/g, '&gt;')
				.replace(/"/g, '&quot;');

		const formatDate = (iso) => {
			const d = new Date(iso);
			return d.toLocaleDateString('ko-KR', {
				year: 'numeric',
				month: 'short',
				day: 'numeric',
				hour: '2-digit',
				minute: '2-digit',
			});
		};

		const renderList = (comments) => {
			if (!list) return;
			if (countEl) countEl.textContent = comments.length > 0 ? `(${comments.length})` : '';
			if (comments.length === 0) {
				list.innerHTML = '<li class="empty">첫 댓글을 남겨보세요.</li>';
				return;
			}
			list.innerHTML = comments.map((comment) => {
				const author = comment.profiles || {};
				const name = author.display_name || '익명';
				const avatar = author.avatar_url
					? `<img class="c-avatar" src="${escapeHtml(author.avatar_url)}" alt="" />`
					: `<div class="c-avatar-fallback" aria-hidden="true">${escapeHtml(name.charAt(0))}</div>`;
				return `
					<li class="comment" data-id="${escapeHtml(comment.id)}">
						<header class="c-head">
							${avatar}
							<span class="c-name">${escapeHtml(name)}</span>
							<time class="c-time" datetime="${escapeHtml(comment.created_at)}">${formatDate(comment.created_at)}</time>
						</header>
						<p class="c-body">${escapeHtml(comment.body).replace(/\n/g, '<br/>')}</p>
					</li>`;
			}).join('');
		};

		const loadComments = async () => {
			try {
				const res = await fetch(`/api/comments?slug=${encodeURIComponent(postSlug)}`, { credentials: 'same-origin' });
				const data = await res.json().catch(() => ({}));
				if (!res.ok) {
					console.error('load comments', data.error || res.statusText);
					if (list) list.innerHTML = '<li class="empty">댓글을 불러오지 못했습니다.</li>';
					return;
				}
				renderList(data.comments || []);
			} catch (error) {
				console.error('load comments', error);
				if (list) list.innerHTML = '<li class="empty">댓글을 불러오지 못했습니다.</li>';
			}
		};

		const updateAuthUI = (user) => {
			currentUser = user;
			if (user) {
				if (composeForm) composeForm.hidden = false;
				if (loginPrompt) loginPrompt.hidden = true;
				const name = user.name || (user.email || '').split('@')[0] || '독자';
				if (meName) meName.textContent = name;
				if (meAvatar) {
					if (user.avatar_url) {
						meAvatar.src = user.avatar_url;
						meAvatar.hidden = false;
					} else {
						meAvatar.hidden = true;
					}
				}
			} else {
				if (composeForm) composeForm.hidden = true;
				if (loginPrompt) loginPrompt.hidden = false;
				if (loginLink) loginLink.href = `/login/?next=${encodeURIComponent(window.location.pathname)}`;
			}
		};

		const loadSession = async () => {
			try {
				const res = await fetch('/api/auth/session', { credentials: 'same-origin' });
				const data = await res.json();
				updateAuthUI(data.authenticated ? data.user : null);
			} catch {
				updateAuthUI(null);
			}
		};

		textarea?.addEventListener('input', () => {
			if (charEl && textarea) charEl.textContent = `${textarea.value.length} / 5000`;
		});

		composeForm?.addEventListener('submit', async (event) => {
			event.preventDefault();
			if (!currentUser || !textarea) return;
			const body = textarea.value.trim();
			if (body.length < 2) return;

			const submitBtn = composeForm.querySelector('button[type="submit"]');
			if (submitBtn) {
				submitBtn.disabled = true;
				submitBtn.textContent = '게시 중…';
			}

			try {
				const res = await fetch('/api/comments', {
					method: 'POST',
					credentials: 'same-origin',
					headers: { 'Content-Type': 'application/json' },
					body: JSON.stringify({ post_slug: postSlug, body }),
				});
				const data = await res.json().catch(() => ({}));
				if (!res.ok) {
					console.error('post comment', data.error || res.statusText);
					alert('댓글 게시에 실패했습니다. 잠시 후 다시 시도해 주세요.');
				} else {
					textarea.value = '';
					if (charEl) charEl.textContent = '0 / 5000';
					await loadComments();
				}
			} catch (error) {
				console.error('post comment', error);
				alert('댓글 게시에 실패했습니다. 잠시 후 다시 시도해 주세요.');
			} finally {
				if (submitBtn) {
					submitBtn.disabled = false;
					submitBtn.textContent = '댓글 게시';
				}
			}
		});

		Promise.all([loadSession(), loadComments()]);
	};

	document.querySelectorAll('.comments-section').forEach(initComments);
})();
