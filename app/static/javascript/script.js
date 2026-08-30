/* Auth pages: password visibility toggles + confirm-password validation.
   Loaded by Log_in.html and Register.html. */
(function () {
    'use strict';

    /* ---- show / hide password ------------------------------------- */
    document.querySelectorAll('[data-toggle-password]').forEach(function (btn) {
        btn.addEventListener('click', function () {
            var input = document.getElementById(btn.getAttribute('data-toggle-password'));
            if (!input) { return; }

            var showing = input.type === 'text';
            input.type = showing ? 'password' : 'text';

            btn.setAttribute('aria-pressed', String(!showing));
            btn.setAttribute('aria-label', showing ? 'Show password' : 'Hide password');

            // Typing position is lost when the type changes, so put it back.
            var end = input.value.length;
            input.focus();
            try { input.setSelectionRange(end, end); } catch (e) { /* not all types support it */ }
        });
    });

    /* ---- confirm password ------------------------------------------ */
    // The previous version relied on `register_form` resolving through the
    // browser's id-as-global behaviour, and only checked on submit.
    var registerForm = document.getElementById('register_form');
    if (!registerForm) { return; }

    var password = document.getElementById('password');
    var confirmPassword = document.getElementById('confirmPassword');
    var errorMessage = document.getElementById('error-message');

    if (!password || !confirmPassword || !errorMessage) { return; }

    function mismatch() {
        return confirmPassword.value !== '' && password.value !== confirmPassword.value;
    }

    function showError(show) {
        errorMessage.hidden = !show;
        confirmPassword.classList.toggle('has-error', show);
        confirmPassword.setAttribute('aria-invalid', show ? 'true' : 'false');
    }

    // Checked on blur rather than on every keystroke: flagging a mismatch
    // while someone is still halfway through typing is just noise.
    confirmPassword.addEventListener('blur', function () {
        showError(mismatch());
    });

    // Once the error is up, clear it as soon as it stops being true.
    confirmPassword.addEventListener('input', function () {
        if (!errorMessage.hidden && !mismatch()) { showError(false); }
    });

    password.addEventListener('input', function () {
        if (!errorMessage.hidden && !mismatch()) { showError(false); }
    });

    registerForm.addEventListener('submit', function (event) {
        if (password.value !== confirmPassword.value) {
            event.preventDefault();
            showError(true);
            confirmPassword.focus();
        }
    });
}());
