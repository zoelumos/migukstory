(() => {
  const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

  const setMessage = (form, text, kind) => {
    const msgEl = form.querySelector('[data-msg]');
    if (!msgEl) return;
    msgEl.textContent = text;
    if (kind) msgEl.dataset.kind = kind;
    else delete msgEl.dataset.kind;
  };

  const initNewsletterForm = (form) => {
    if (form.dataset.newsletterReady === 'true') return;
    form.dataset.newsletterReady = 'true';

    form.addEventListener('submit', async (event) => {
      event.preventDefault();

      const fd = new FormData(form);
      const email = String(fd.get('email') || '').trim().toLowerCase();
      const website = String(fd.get('website') || '');
      const source = String(fd.get('source') || form.dataset.source || 'newsletter_form');
      const button = form.querySelector('button[type="submit"]');

      if (website) return; // honeypot: look successful to bots, no UX change needed.

      if (!EMAIL_RE.test(email) || email.length > 254) {
        setMessage(form, '올바른 이메일을 입력해 주세요.', 'error');
        return;
      }

      if (button) {
        button.disabled = true;
        button.dataset.originalText = button.textContent || '구독하기';
        button.textContent = '가입 중…';
      }
      setMessage(form, '', '');

      try {
        const res = await fetch(form.getAttribute('action') || '/api/subscribers', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
          body: JSON.stringify({
            email,
            source,
            metadata: {
              locale: navigator.language || null,
              pathname: window.location.pathname,
              referrer: document.referrer || null,
            },
          }),
        });
        const result = await res.json().catch(() => ({}));

        if (!res.ok && !result.ok) {
          const msg = result.error === 'invalid_email'
            ? '올바른 이메일을 입력해 주세요.'
            : '잠시 후 다시 시도해 주세요. 문제가 계속되면 editor@migukstory.com 으로 알려주세요.';
          setMessage(form, msg, 'error');
        } else {
          setMessage(form, '가입 요청 완료 ✓ 이미 구독 중인 이메일이면 중복 없이 기존 구독을 유지합니다.', 'success');
          form.reset();
        }
      } catch (_err) {
        setMessage(form, '네트워크 오류입니다. 잠시 후 다시 시도해 주세요.', 'error');
      } finally {
        if (button) {
          button.disabled = false;
          button.textContent = button.dataset.originalText || '구독하기';
          delete button.dataset.originalText;
        }
      }
    });
  };

  const init = () => document.querySelectorAll('form.newsletter').forEach(initNewsletterForm);
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, { once: true });
  else init();
})();
