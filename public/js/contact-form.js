/**
 * Contact form → mailto handler — external (not inline) to satisfy the strict
 * CSP. Wires the submit listener (the form's inline onsubmit was CSP-blocked).
 */
function openMailto(e) {
	e.preventDefault();
	var f = e.target;
	// Honeypot — bots fill the hidden 'website' field; humans don't see it
	if (f.website && f.website.value) return false;
	var subject = encodeURIComponent('[' + f.type.value + '] ' + f.subject.value);
	var body = encodeURIComponent(
		'보낸 사람: ' + f.name.value + '\n' +
		'답신 이메일: ' + f.email.value + '\n' +
		'문의 유형: ' + f.type.value + '\n\n' +
		'────────\n\n' +
		f.message.value
	);
	window.location.href = 'mailto:editor@migukstory.com?subject=' + subject + '&body=' + body;
	return false;
}

document.addEventListener('DOMContentLoaded', function () {
	var form = document.getElementById('contact-form');
	if (form) form.addEventListener('submit', openMailto);
});
