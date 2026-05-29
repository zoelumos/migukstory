(() => {
	const statusEl = document.querySelector('[data-status]');
	const locked = document.querySelector('[data-locked]');
	const dashboard = document.querySelector('[data-dashboard]');

	const fmt = (n) => n == null ? '—' : Number(n).toLocaleString('ko-KR');
	const formatDate = (iso) => new Date(iso).toLocaleString('ko-KR');
	const escapeHtml = (s) =>
		String(s || '')
			.replace(/&/g, '&amp;')
			.replace(/</g, '&lt;')
			.replace(/>/g, '&gt;')
			.replace(/"/g, '&quot;');
	const postHref = (slug) => {
		const value = String(slug || '');
		return value.startsWith('/') ? value : `/${value.replace(/^\/+/, '')}`;
	};

	const showLocked = (message, loginHref = '/login?next=/admin') => {
		if (statusEl) statusEl.textContent = message;
		if (locked) {
			locked.hidden = false;
			const link = locked.querySelector('a');
			if (link) link.href = loginHref;
		}
		if (dashboard) dashboard.hidden = true;
	};

	const fetchAdmin = async () => {
		const controller = new AbortController();
		const timer = setTimeout(() => controller.abort(), 15000);
		try {
			const res = await fetch('/api/admin', { credentials: 'same-origin', signal: controller.signal });
			const data = await res.json().catch(() => ({}));
			if (!res.ok) {
				const err = new Error(data.error || res.statusText || 'request_failed');
				err.status = res.status;
				throw err;
			}
			return data;
		} finally {
			clearTimeout(timer);
		}
	};

	const renderStats = (stats) => {
		const set = (sel, n) => {
			const el = document.querySelector(sel);
			if (el) el.textContent = fmt(n);
		};
		set('[data-stat-users]', stats.users);
		set('[data-stat-subs]', stats.subscribers);
		set('[data-stat-comments]', stats.comments);
		set('[data-stat-hidden]', stats.hidden);
	};

	const renderComments = (comments) => {
		const list = document.querySelector('[data-mod-list]');
		if (!list) return;
		if (!comments || comments.length === 0) {
			list.innerHTML = '<li class="loading">아직 댓글이 없습니다.</li>';
			return;
		}
		list.innerHTML = comments.map((c) => `
			<li class="mod-row ${c.is_hidden ? 'is-hidden' : ''} ${c.is_pinned ? 'is-pinned' : ''}" data-id="${escapeHtml(c.id)}">
				<header>
					<a href="${escapeHtml(postHref(c.post_slug))}" target="_blank" rel="noopener noreferrer" class="mod-slug">${escapeHtml(c.post_slug)}</a>
					<span class="mod-author">${escapeHtml(c.profiles?.display_name || '익명')} · ${escapeHtml(c.profiles?.email || '')}</span>
					<time>${formatDate(c.created_at)}</time>
				</header>
				<p class="mod-body">${escapeHtml(c.body)}</p>
				<div class="mod-actions">
					<button data-action="toggle-hide" data-state="${c.is_hidden}">${c.is_hidden ? '복원' : '숨기기'}</button>
					<button data-action="toggle-pin" data-state="${c.is_pinned}">${c.is_pinned ? '고정 해제' : '고정'}</button>
					<button data-action="delete" class="danger">삭제</button>
				</div>
			</li>
		`).join('');

		list.querySelectorAll('button[data-action]').forEach((btn) => {
			btn.addEventListener('click', async (e) => {
				const b = e.currentTarget;
				const row = b.closest('.mod-row');
				const id = row?.dataset.id;
				const action = b.dataset.action;
				if (!id || !action) return;
				if (action === 'delete' && !confirm('정말 삭제할까요? 되돌릴 수 없습니다.')) return;
				b.disabled = true;
				try {
					const state = action === 'toggle-hide' || action === 'toggle-pin' ? b.dataset.state !== 'true' : undefined;
					const res = await fetch('/api/admin', {
						method: 'POST',
						credentials: 'same-origin',
						headers: { 'Content-Type': 'application/json' },
						body: JSON.stringify({ id, action, state }),
					});
					const result = await res.json().catch(() => ({}));
					if (!res.ok) alert('실패: ' + (result.error || res.statusText));
					await loadDashboard();
				} catch (error) {
					alert('실패: ' + (error?.message || 'network_error'));
				} finally {
					b.disabled = false;
				}
			});
		});
	};

	const renderSubscribers = (subscribers) => {
		const tbody = document.querySelector('[data-sub-body]');
		if (!tbody) return;
		if (!subscribers || subscribers.length === 0) {
			tbody.innerHTML = '<tr><td colspan="4">아직 구독자가 없습니다.</td></tr>';
			return;
		}
		tbody.innerHTML = subscribers.map((s) => {
			const status = s.unsubscribed_at ? '해지' : (s.confirmed_at ? '확인됨' : '구독중');
			return `
				<tr><td>${escapeHtml(s.email)}</td><td>${escapeHtml(s.source || '')}</td><td>${escapeHtml(status)}</td><td>${formatDate(s.created_at)}</td></tr>
			`;
		}).join('');
	};

	const renderUsers = (users) => {
		const tbody = document.querySelector('[data-user-body]');
		if (!tbody) return;
		if (!users || users.length === 0) {
			tbody.innerHTML = '<tr><td colspan="5">아직 사용자가 없습니다.</td></tr>';
			return;
		}
		tbody.innerHTML = users.map((u) => `
			<tr>
				<td>${escapeHtml(u.display_name || u.email || u.id)}</td>
				<td>${escapeHtml(u.email || '')}</td>
				<td>${escapeHtml(u.provider || '')}</td>
				<td>${u.is_admin ? '관리자' : '회원'}</td>
				<td>${formatDate(u.created_at)}</td>
			</tr>
		`).join('');
	};

	const renderNewsletterSends = (sends) => {
		const tbody = document.querySelector('[data-send-body]');
		if (!tbody) return;
		if (!sends || sends.length === 0) {
			tbody.innerHTML = '<tr><td colspan="4">아직 이메일 발송 기록이 없습니다.</td></tr>';
			return;
		}
		tbody.innerHTML = sends.map((s) => `
			<tr>
				<td>${escapeHtml(s.email)}</td>
				<td>${escapeHtml(s.post_title || s.post_slug || '')}</td>
				<td>${escapeHtml(s.status || '')}</td>
				<td>${formatDate(s.sent_at)}</td>
			</tr>
		`).join('');
	};

	const renderIssues = (issues) => {
		const box = document.querySelector('[data-admin-issues]');
		const list = document.querySelector('[data-admin-issue-list]');
		if (!box || !list) return;
		if (!issues || issues.length === 0) {
			box.hidden = true;
			list.innerHTML = '';
			return;
		}
		box.hidden = false;
		list.innerHTML = issues.map((issue) => `
			<li><strong>${escapeHtml(issue.name || 'db')}</strong>: ${escapeHtml(issue.message || 'unknown_error')}${issue.code ? ` <code>${escapeHtml(issue.code)}</code>` : ''}</li>
		`).join('');
	};

	const renderFatalError = (message) => {
		['[data-mod-list]', '[data-user-body]', '[data-sub-body]', '[data-send-body]'].forEach((sel) => {
			const el = document.querySelector(sel);
			if (!el) return;
			if (sel === '[data-mod-list]') el.innerHTML = `<li class="loading">${escapeHtml(message)}</li>`;
			else el.innerHTML = `<tr><td colspan="5" class="loading">${escapeHtml(message)}</td></tr>`;
		});
	};

	async function loadDashboard() {
		try {
			const data = await fetchAdmin();
			if (statusEl) statusEl.textContent = `환영합니다, ${data.user.name} (${data.user.email}) — 관리자`;
			if (locked) locked.hidden = true;
			if (dashboard) dashboard.hidden = false;
			renderStats(data.stats || {});
			renderComments(data.comments || []);
			renderUsers(data.users || []);
			renderSubscribers(data.subscribers || []);
			renderNewsletterSends(data.newsletterSends || []);
			renderIssues(data.issues || []);
		} catch (error) {
			const message = error?.name === 'AbortError'
				? 'DB/API 응답이 15초 안에 오지 않았습니다. Supabase 연결을 확인하세요.'
				: `DB/API 로딩 실패: ${error?.message || 'network_error'}`;
			renderFatalError(message);
			if (error?.status === 401 || error?.message === 'unauthorized') {
				showLocked('로그인이 필요합니다.', '/login?next=/admin');
			} else if (error?.status === 403 || error?.message === 'forbidden') {
				showLocked('관리자 권한이 필요합니다.');
			} else {
				if (statusEl) statusEl.textContent = message;
				if (locked) locked.hidden = true;
				if (dashboard) dashboard.hidden = false;
				renderIssues([{ name: 'admin_api', message }]);
			}
		}
	}

	loadDashboard();
})();
