(() => {
  'use strict';

  const params = new URLSearchParams(window.location.search);
  const rawNext = params.get('next') || '/';
  const next = rawNext.startsWith('/') && !rawNext.startsWith('//') ? rawNext : '/';
  const msgEl = document.querySelector('[data-msg]');

  const setMsg = (text, kind = 'info') => {
    if (!msgEl) return;
    msgEl.textContent = text;
    msgEl.dataset.kind = kind;
  };

  // Remove stale client-side Supabase keys from the old localStorage flow.
  try {
    Object.keys(window.localStorage || {})
      .filter((key) => key.startsWith('sb-'))
      .forEach((key) => window.localStorage.removeItem(key));
  } catch (_) {
    // Safari private mode / locked storage: safe no-op.
  }

  const googleLink = document.getElementById('google-signin');
  if (googleLink instanceof HTMLAnchorElement) {
    googleLink.href = `/api/auth/signin?provider=google&next=${encodeURIComponent(next)}`;
  }

  const errorParam = params.get('error');
  if (errorParam) {
    setMsg(errorParam, 'error');
  }

  fetch('/api/auth/session', { credentials: 'same-origin' })
    .then((response) => response.ok ? response.json() : { authenticated: false })
    .then((data) => {
      if (!data || !data.authenticated || !data.user) return;
      const notice = document.querySelector('[data-logged-in-notice]');
      if (!(notice instanceof HTMLElement)) return;
      const nameEl = notice.querySelector('[data-name]');
      if (nameEl) nameEl.textContent = data.user.name || data.user.email || '회원';
      notice.hidden = false;
    })
    .catch(() => {});

  const form = document.getElementById('email-magic-link');
  if (form instanceof HTMLFormElement) {
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      const submit = form.querySelector('button[type="submit"]');
      const email = String(new FormData(form).get('email') || '').trim().toLowerCase();
      if (!email.includes('@') || email.length < 5) {
        setMsg('올바른 이메일을 입력해 주세요.', 'error');
        return;
      }

      if (submit instanceof HTMLButtonElement) submit.disabled = true;
      setMsg('전송 중…', 'info');
      try {
        const res = await fetch('/api/auth/magic-link', {
          method: 'POST',
          credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, next }),
        });
        const result = await res.json().catch(() => ({}));
        if (!res.ok) {
          setMsg(result.error || '이메일 전송에 실패했습니다. 잠시 후 다시 시도해 주세요.', 'error');
          return;
        }
        setMsg(`${email}으로 로그인 링크를 보내드렸습니다. 메일을 확인해 주세요.`, 'success');
        form.reset();
      } catch (_) {
        setMsg('네트워크 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.', 'error');
      } finally {
        if (submit instanceof HTMLButtonElement) submit.disabled = false;
      }
    });
  }
})();
