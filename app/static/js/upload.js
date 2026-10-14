/*
 * File uploads: drop zones and an upload progress card.
 *
 * 1. Any <input type="file" data-upload-zone> becomes a drop zone. Files
 *    can be dropped on it or browsed for; chosen files are listed with
 *    their size and a remove button. Files over data-max-mb, or not
 *    matching the input's accept list, are refused with a warning and
 *    never sent. The input itself stays in the form (visually hidden) and
 *    holds exactly the files listed, so the form posts them as before.
 *
 * 2. A <form data-upload-form> that has files chosen is sent with
 *    XMLHttpRequest instead of a plain submit, behind a progress card: the
 *    percentage, a segmented bar, bytes sent, time left, speed and Cancel.
 *    When the server answers, the page it returns (usually the redirect
 *    target with its flash messages) replaces this one, exactly as a normal
 *    submit would. Other submit handlers on the form still run first; if
 *    one of them stops the submit, nothing is sent.
 *
 * 3. window.PNOUpload.send(form, opts) does (2) on demand, for forms that
 *    submit themselves from script (the species photo control).
 *
 * The limits here are checked in the browser only.
 */
(function () {
    "use strict";

    var SEGMENTS = 24;
    var ICON = {
        up: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3v12"/><path d="m17 8-5-5-5 5"/><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/></svg>',
        clip: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l8.57-8.57A4 4 0 1 1 18 8.84l-8.59 8.57a2 2 0 0 1-2.83-2.83l8.49-8.48"/></svg>',
        x: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>',
        warn: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/></svg>'
    };

    function esc(s) {
        return String(s).replace(/[&<>"']/g, function (c) {
            return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
        });
    }

    function fmtBytes(n) {
        if (n < 1024) return n + " B";
        if (n < 1024 * 1024) return (n / 1024).toFixed(1) + " KB";
        return (n / 1024 / 1024).toFixed(1) + " MB";
    }

    // does a file match an accept list such as "image/*,.pdf"?
    function accepted(file, accept) {
        if (!accept) return true;
        var name = file.name.toLowerCase(), type = (file.type || "").toLowerCase();
        return accept.split(",").some(function (rule) {
            rule = rule.trim().toLowerCase();
            if (!rule) return false;
            if (rule.charAt(0) === ".") return name.slice(-rule.length) === rule;
            if (rule.slice(-2) === "/*") return type.indexOf(rule.slice(0, -1)) === 0;
            return type === rule;
        });
    }

    // a short human list of what the field takes, from its accept list
    function acceptLabel(accept) {
        if (!accept) return "Any file";
        return accept.split(",").map(function (r) {
            r = r.trim().toLowerCase();
            if (r === "image/*") return "images";
            if (r.indexOf("image/") === 0) return "." + r.slice(6).replace("jpeg", "jpg");
            return r;
        }).filter(function (v, i, a) { return a.indexOf(v) === i; }).join(" ");
    }

    function checkFile(file, accept, maxBytes, maxMb) {
        if (!accepted(file, accept)) {
            return file.name + " is not an accepted type (" + acceptLabel(accept) + ").";
        }
        if (maxBytes && file.size > maxBytes) {
            return file.name + " is " + fmtBytes(file.size) + ", over the " + maxMb + " MB limit.";
        }
        return null;
    }

    /* ------------------------------------------------------------------
       1. drop zones
       ------------------------------------------------------------------ */
    function makeZone(input) {
        if (input.dataset.uploadReady) return;
        input.dataset.uploadReady = "1";

        var maxMb = parseFloat(input.dataset.maxMb || "10");
        var maxBytes = maxMb * 1024 * 1024;
        var accept = input.getAttribute("accept") || "";
        var multiple = input.multiple;
        var kept = [];   // the files currently chosen

        var zone = document.createElement("div");
        zone.className = "up-zone";
        zone.innerHTML =
            '<div class="up-drop" tabindex="0" role="button">' +
            '  <span class="up-drop-icon">' + ICON.up + '</span>' +
            '  <span class="up-drop-text">Drop ' + (multiple ? "files" : "a file") +
            ' here or <span class="up-browse">browse</span></span>' +
            '  <span class="up-drop-hint">Up to ' + maxMb + ' MB' + (multiple ? " each" : "") +
            ' &middot; ' + esc(acceptLabel(accept)) + '</span>' +
            '</div>' +
            '<ul class="up-list" hidden></ul>' +
            '<div class="up-error" role="alert" hidden>' +
            '  <span class="up-error-icon">' + ICON.warn + '</span>' +
            '  <div><strong></strong><ul></ul></div>' +
            '  <button type="button" class="up-btn up-btn-sm">Dismiss</button>' +
            '</div>';
        input.classList.add("up-input");
        input.parentNode.insertBefore(zone, input.nextSibling);
        zone.appendChild(input);       // keep the input inside, out of sight

        var drop = zone.querySelector(".up-drop");
        var list = zone.querySelector(".up-list");
        var errBox = zone.querySelector(".up-error");

        function sync() {
            var dt = new DataTransfer();
            kept.forEach(function (f) { dt.items.add(f); });
            input.files = dt.files;
            list.hidden = kept.length === 0;
            list.innerHTML = kept.map(function (f, i) {
                return '<li>' + ICON.clip +
                    '<span class="up-li-name">' + esc(f.name) + '</span>' +
                    '<span class="up-li-size">' + fmtBytes(f.size) + '</span>' +
                    '<button type="button" class="up-remove" data-i="' + i + '" aria-label="Remove ' +
                    esc(f.name) + '" title="Remove">' + ICON.x + '</button></li>';
            }).join("");
            // a single-file field hides the drop zone once it has its file
            drop.hidden = !multiple && kept.length > 0;
        }

        function showErrors(problems) {
            if (!problems.length) { errBox.hidden = true; return; }
            errBox.querySelector("strong").textContent =
                problems.length === 1 ? "This file was not added" : problems.length + " files were not added";
            errBox.querySelector("ul").innerHTML = problems.map(function (p) {
                return "<li>" + esc(p) + "</li>";
            }).join("");
            errBox.hidden = false;
        }

        function add(files) {
            var problems = [];
            Array.prototype.forEach.call(files, function (f) {
                var why = checkFile(f, accept, maxBytes, maxMb);
                if (why) { problems.push(why); return; }
                if (!multiple) kept = [];
                var dup = kept.some(function (k) {
                    return k.name === f.name && k.size === f.size && k.lastModified === f.lastModified;
                });
                if (!dup) kept.push(f);
            });
            sync();
            showErrors(problems);
        }

        // the browser's own picker writes to input.files; take them from there
        input.addEventListener("change", function () {
            var picked = Array.prototype.slice.call(input.files);
            if (input.dataset.uploadSyncing) return;
            input.dataset.uploadSyncing = "1";
            add(picked);
            delete input.dataset.uploadSyncing;
        });

        drop.addEventListener("click", function () { input.click(); });
        drop.addEventListener("keydown", function (e) {
            if (e.key === "Enter" || e.key === " ") { e.preventDefault(); input.click(); }
        });
        ["dragenter", "dragover"].forEach(function (t) {
            drop.addEventListener(t, function (e) { e.preventDefault(); drop.classList.add("is-over"); });
        });
        ["dragleave", "drop"].forEach(function (t) {
            drop.addEventListener(t, function () { drop.classList.remove("is-over"); });
        });
        drop.addEventListener("drop", function (e) {
            e.preventDefault();
            add(e.dataTransfer.files);
        });
        list.addEventListener("click", function (e) {
            var btn = e.target.closest(".up-remove");
            if (!btn) return;
            kept.splice(parseInt(btn.dataset.i, 10), 1);
            sync();
        });
        errBox.querySelector(".up-btn").addEventListener("click", function () { errBox.hidden = true; });

        // a form reset empties the zone too
        if (input.form) {
            input.form.addEventListener("reset", function () { kept = []; sync(); showErrors([]); });
        }
    }

    /* ------------------------------------------------------------------
       2/3. sending a form behind the progress card
       ------------------------------------------------------------------ */
    function buildCard(title) {
        var overlay = document.createElement("div");
        overlay.className = "up-overlay";
        overlay.innerHTML =
            '<div class="up-card" data-state="uploading" role="dialog" aria-modal="true" aria-label="' + esc(title) + '">' +
            '  <div class="up-head">' +
            '    <span class="up-title">' + ICON.up + ' ' + esc(title) + '</span>' +
            '    <span class="up-status" aria-live="polite"><i></i><span>Uploading</span></span>' +
            '  </div>' +
            '  <div class="up-body">' +
            '    <div class="up-file">' +
            '      <div class="up-file-row">' +
            '        <span class="up-file-name">' + ICON.clip + '<span class="up-o-name"></span></span>' +
            '        <span class="up-pct">0%</span>' +
            '      </div>' +
            '      <div class="up-bar" aria-hidden="true">' + new Array(SEGMENTS + 1).join("<span></span>") + '</div>' +
            '      <div class="up-meta">' +
            '        <span class="up-bytes"></span>' +
            '        <span class="up-rate"><span class="up-left"></span> <span class="up-speed"></span></span>' +
            '      </div>' +
            '      <div class="up-actions"><button type="button" class="up-btn up-o-cancel">Cancel</button></div>' +
            '    </div>' +
            '    <div class="up-error" role="alert" hidden>' +
            '      <span class="up-error-icon">' + ICON.warn + '</span>' +
            '      <div><strong>Upload failed</strong><p class="up-o-err"></p></div>' +
            '      <button type="button" class="up-btn up-btn-sm up-o-close">Close</button>' +
            '    </div>' +
            '  </div>' +
            '</div>';
        document.body.appendChild(overlay);
        return overlay;
    }

    function filesIn(form) {
        var list = [];
        Array.prototype.forEach.call(form.querySelectorAll('input[type="file"]'), function (inp) {
            Array.prototype.forEach.call(inp.files || [], function (f) { list.push(f); });
        });
        return list;
    }

    function send(form, opts) {
        opts = opts || {};
        var files = filesIn(form);
        var overlay = buildCard(opts.title || "Uploading files");
        var card = overlay.querySelector(".up-card");
        var q = function (sel) { return overlay.querySelector(sel); };
        var status = q(".up-status span");
        var started = performance.now();

        q(".up-o-name").textContent = files.length === 1
            ? files[0].name
            : files.length + " files";

        function progress(sent, total) {
            var pct = total ? sent / total : 0;
            q(".up-pct").textContent = Math.floor(pct * 100) + "%";
            var exact = pct * SEGMENTS;
            Array.prototype.forEach.call(q(".up-bar").children, function (seg, i) {
                seg.classList.toggle("is-on", i < Math.floor(exact));
                seg.classList.toggle("is-part", i === Math.floor(exact) && exact % 1 > 0.05);
            });
            q(".up-bytes").textContent = fmtBytes(sent) + " / " + fmtBytes(total);
            var secs = (performance.now() - started) / 1000;
            if (secs > 0.15 && sent > 0) {
                var rate = sent / secs;
                q(".up-left").textContent = Math.max(0, Math.ceil((total - sent) / rate)) + "s left";
                q(".up-speed").textContent = (rate * 8 / 1e6).toFixed(1) + "Mbps";
            }
        }

        function close() { overlay.remove(); }

        function fail(message) {
            card.dataset.state = "error";
            status.textContent = "Failed";
            q(".up-file").hidden = true;
            q(".up-error").hidden = false;
            q(".up-o-err").textContent = message;
            q(".up-o-close").focus();
        }

        var data = new FormData(form);
        if (opts.submitter && opts.submitter.name) data.append(opts.submitter.name, opts.submitter.value);

        var xhr = new XMLHttpRequest();
        xhr.upload.onprogress = function (e) {
            if (e.lengthComputable) progress(e.loaded, e.total);
        };
        xhr.upload.onload = function () {
            card.dataset.state = "processing";
            status.textContent = "Processing";
            q(".up-left").textContent = opts.processing || "Saving...";
            q(".up-speed").textContent = "";
            q(".up-o-cancel").disabled = true;   // the server has it now
        };
        xhr.onload = function () {
            // the page the server answered with -- usually the redirect
            // target with its messages -- replaces this one
            if (xhr.responseURL) history.replaceState(null, "", xhr.responseURL);
            document.open();
            document.write(xhr.responseText);
            document.close();
        };
        xhr.onerror = function () { fail("The connection failed. Nothing was saved; try again."); };
        xhr.onabort = close;
        q(".up-o-cancel").addEventListener("click", function () { xhr.abort(); });
        q(".up-o-close").addEventListener("click", close);

        xhr.open((form.getAttribute("method") || "POST").toUpperCase(), form.action);
        xhr.send(data);
        progress(0, files.reduce(function (n, f) { return n + f.size; }, 0) || 1);
        q(".up-o-cancel").focus();
    }

    // forms marked data-upload-form go through send() when they carry files.
    // Listening on document, the form's own submit handlers have already run.
    document.addEventListener("submit", function (e) {
        var form = e.target;
        if (!form.matches || !form.matches("form[data-upload-form]")) return;
        if (e.defaultPrevented) return;
        if (!filesIn(form).length) return;      // no files: an ordinary submit is fine
        e.preventDefault();
        send(form, {
            title: form.dataset.uploadTitle,
            processing: form.dataset.uploadProcessing,
            submitter: e.submitter
        });
    });

    function init() {
        document.querySelectorAll('input[type="file"][data-upload-zone]').forEach(makeZone);
    }

    window.PNOUpload = {
        send: send,
        check: checkFile,
        fmtBytes: fmtBytes,
        init: init
    };

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
