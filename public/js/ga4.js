(() => {
	const current = document.currentScript;
	const measurementId = current?.dataset?.measurementId || '';

	if (!/^G-[A-Z0-9]+$/.test(measurementId)) return;

	window.dataLayer = window.dataLayer || [];
	window.gtag = function gtag() {
		window.dataLayer.push(arguments);
	};

	window.gtag('js', new Date());
	window.gtag('config', measurementId, {
		anonymize_ip: true,
		send_page_view: true,
	});
})();
