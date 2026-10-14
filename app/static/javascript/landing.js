/* Landing page behaviour: sticky-nav state, scroll reveals, and the
   coverage marquee. Everything here is progressive enhancement, so the
   page is complete and readable with this file blocked. */
(function () {
    "use strict";

    var reduced = window.matchMedia("(prefers-reduced-motion: reduce)");

    /* ---------- Sticky nav ----------
       A sentinel at the top of the document tells us when the bar has
       left the hero, which avoids listening to every scroll frame. */
    function initNav() {
        var wrap = document.querySelector(".landing-nav-wrap");
        var sentinel = document.querySelector(".landing-nav-sentinel");
        if (!wrap || !sentinel || !("IntersectionObserver" in window)) return;

        new IntersectionObserver(function (entries) {
            wrap.classList.toggle("is-stuck", !entries[0].isIntersecting);
        }).observe(sentinel);

        /* The bar stays on screen the whole way down the page; it no longer
           slides away while scrolling down. */
    }

    /* ---------- Current section in the nav ----------
       Underlines the link for the part of the page being read: Home over
       the hero, then About, Coverage and Features as each reaches the top
       third of the screen. Checked once per frame while scrolling. */
    function initNavSpy() {
        var links = Array.prototype.slice.call(
            document.querySelectorAll('.landing-nav-links a[href^="#"]'));
        var items = links.map(function (a) {
            var id = a.getAttribute("href").slice(1);
            return { link: a, target: document.getElementById(id) };
        }).filter(function (it) { return it.target; });
        if (!items.length) return;

        var bar = document.querySelector(".landing-nav-wrap");
        var current = null;

        function setCurrent(it) {
            if (it === current) return;
            current = it;
            items.forEach(function (x) {
                if (x === it) x.link.setAttribute("aria-current", "page");
                else x.link.removeAttribute("aria-current");
            });
        }

        function update() {
            var line = (bar ? bar.offsetHeight : 0) + window.innerHeight * 0.3;
            var active = items[0];   // Home: the hero, before any section
            items.forEach(function (it, i) {
                if (i === 0) return;
                if (it.target.getBoundingClientRect().top <= line) active = it;
            });
            setCurrent(active);
        }

        var ticking = false;
        window.addEventListener("scroll", function () {
            if (ticking) return;
            ticking = true;
            window.requestAnimationFrame(function () { update(); ticking = false; });
        }, { passive: true });
        // once more when scrolling stops, so the final section is always
        // right even if a frame was skipped (or after a jump from a link)
        window.addEventListener("scrollend", update);
        window.addEventListener("resize", update);
        update();
    }

    /* ---------- Scroll reveal ----------
       Reveals replay. An element that has been scrolled past is put back
       to its hidden state once it is fully clear of the screen, so coming
       back to it animates again rather than finding it already settled.
       Two thresholds make that safe: 0.15 brings an element in, and only
       a ratio of exactly 0 -- completely off screen -- resets it, so an
       element sitting on the edge never flickers between the two.

       Under reduced motion the CSS never hides anything, so this is a
       no-op. */
    function initReveals() {
        var items = document.querySelectorAll(".landing-reveal");
        if (!items.length) return;

        if (reduced.matches || !("IntersectionObserver" in window)) {
            items.forEach(function (el) { el.classList.add("is-in"); });
            return;
        }

        var io = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                var el = entry.target;

                if (entry.isIntersecting) {
                    el.classList.add("is-in");
                    return;
                }
                if (entry.intersectionRatio !== 0) return;

                /* Which side it left by decides which side it returns
                   from, so the motion always follows the scroll rather
                   than fighting it. */
                el.classList.toggle("is-above", entry.boundingClientRect.bottom <= 0);
                el.classList.remove("is-in");
            });
        }, { rootMargin: "0px 0px -12% 0px", threshold: [0, 0.15] });

        items.forEach(function (el) { io.observe(el); });
    }

    /* ---------- Coverage marquee ----------
       The strip scrolls continuously. Pointing at it eases the speed down
       rather than stopping dead, and it can be dragged, because a strip you
       cannot steer is a strip you cannot actually read. */
    function initMarquee() {
        document.querySelectorAll("[data-marquee]").forEach(setupMarquee);
    }

    function setupMarquee(root) {
        var track = root.querySelector(".landing-track");
        if (!track || !track.children.length) return;

        /* Under reduced motion the CSS leaves the strip as a plain
           horizontal scroller, which needs no script at all. */
        if (reduced.matches) return;

        var NORMAL = 42;   /* pixels per second */
        var SLOW = 9;
        var EASE = 3.5;    /* how fast the speed reaches its target */

        var originalCount = track.children.length;

        /* One duplicate set is all it takes to hide the seam on wrap. */
        Array.prototype.slice.call(track.children).forEach(function (node) {
            var clone = node.cloneNode(true);
            clone.setAttribute("aria-hidden", "true");
            track.appendChild(clone);
        });

        var loopWidth = 0;
        var offset = 0;
        var speed = NORMAL;
        var target = NORMAL;
        var last = 0;
        var raf = null;
        var onScreen = true;
        var dragging = false;
        var dragX = 0;
        var dragOffset = 0;

        function measure() {
            /* The original set is half the track, so it is the loop length. */
            loopWidth = track.scrollWidth / 2;
        }

        /* Keeps the offset inside one loop in both directions, so dragging
           backwards past zero wraps instead of running off the start. */
        function normalize() {
            if (loopWidth > 0) {
                offset = ((offset % loopWidth) + loopWidth) % loopWidth;
            }
        }

        function paint() {
            track.style.transform = "translate3d(" + (-offset).toFixed(2) + "px, 0, 0)";
        }

        function frame(now) {
            var dt = last ? Math.min((now - last) / 1000, 0.05) : 0;
            last = now;

            if (!dragging) {
                speed += (target - speed) * Math.min(dt * EASE, 1);
                offset += speed * dt;

                normalize();
                paint();
            }

            raf = window.requestAnimationFrame(frame);
        }

        function start() {
            if (raf !== null) return;
            last = 0;
            raf = window.requestAnimationFrame(frame);
        }

        function stop() {
            if (raf === null) return;
            window.cancelAnimationFrame(raf);
            raf = null;
        }

        function slow() { target = SLOW; }
        function resume() { target = NORMAL; }

        root.addEventListener("mouseenter", slow);
        root.addEventListener("mouseleave", resume);
        root.addEventListener("focusin", slow);
        root.addEventListener("focusout", resume);


        /* Drag to steer. The offset follows the pointer exactly, and the
           drift picks back up from wherever it was let go. */
        function onDown(e) {
            if (e.button !== undefined && e.button !== 0) return;
            dragging = true;
            dragX = e.clientX;
            dragOffset = offset;
            root.classList.add("is-dragging");
            if (track.setPointerCapture && e.pointerId !== undefined) {
                try { track.setPointerCapture(e.pointerId); } catch (err) { /* not captured */ }
            }
        }
        function onMove(e) {
            if (!dragging) return;
            offset = dragOffset - (e.clientX - dragX);
            normalize();
            paint();
        }
        function onUp() {
            if (!dragging) return;
            dragging = false;
            last = 0;
            root.classList.remove("is-dragging");
        }

        track.addEventListener("pointerdown", onDown);
        track.addEventListener("pointermove", onMove);
        track.addEventListener("pointerup", onUp);
        track.addEventListener("pointercancel", onUp);
        track.addEventListener("lostpointercapture", onUp);
        track.addEventListener("dragstart", function (e) { e.preventDefault(); });

        document.addEventListener("visibilitychange", function () {
            if (document.hidden || !onScreen) { stop(); } else { start(); }
        });

        if ("IntersectionObserver" in window) {
            onScreen = false;
            new IntersectionObserver(function (entries) {
                onScreen = entries[0].isIntersecting;
                if (onScreen && !document.hidden) { start(); } else { stop(); }
            }, { threshold: 0 }).observe(root);
        }

        /* The track grows as the lazy images arrive, so remeasure on change. */
        if ("ResizeObserver" in window) {
            new ResizeObserver(measure).observe(track);
        } else {
            window.addEventListener("resize", measure);
            window.addEventListener("load", measure);
        }

        root.classList.add("is-running");
        measure();
        if (onScreen) { start(); }
    }

    /* ---------- About-section photograph carousel ----------
       Three photographs on screen at once, the middle one largest. Every
       tick they move round one slot: the middle goes left, the right
       comes to the middle, and the left wraps round to the right.

       There are more photographs than slots, so position is worked out
       from the distance to whichever card is currently in the middle
       rather than kept on the elements. A card two steps out is placed
       just past the visible three and left invisible, which is what
       makes a card arrive by sliding in rather than fading up out of
       nothing. Everything further round waits parked off to the right. */
    function initPlates() {
        var root = document.querySelector("[data-plates]");
        if (!root) return;

        var slides = Array.prototype.slice.call(root.querySelectorAll(".landing-plate"));
        if (slides.length < 3) return;

        var CLASSES = ["is-center", "is-right", "is-far-right", "is-far-left", "is-left"];
        var HOLD = 2500;
        var count = slides.length;
        var centre = 1;
        var timer = null;

        /* Clicking any photograph opens it in the viewer, and also brings
           it to the middle, so closing the viewer leaves the set on the
           picture that was being looked at. Each card is a keyboard target
           too (Enter or Space). */
        var viewer = createViewer(slides, function (i) {
            centre = i;
            paint();
        }, stop, restart);

        slides.forEach(function (slide, i) {
            var img = slide.querySelector("img");
            slide.setAttribute("tabindex", "0");
            slide.setAttribute("role", "button");
            slide.setAttribute("aria-label", "View photo: " + (img ? img.alt : "photograph"));
            slide.addEventListener("click", function () { viewer.open(i); });
            slide.addEventListener("keydown", function (e) {
                if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    viewer.open(i);
                }
            });
        });

        /* Steps forward from the middle card, so the one before it comes
           out as count - 1 and lands in the left-hand slot. */
        function slotFor(i) {
            var step = (i - centre + count) % count;
            if (step === 0) return "is-center";
            if (step === 1) return "is-right";
            if (step === 2) return "is-far-right";
            if (step === count - 1) return "is-left";
            if (step === count - 2) return "is-far-left";
            return null;
        }

        function paint() {
            slides.forEach(function (el, i) {
                var slot = slotFor(i);
                CLASSES.forEach(function (name) {
                    el.classList.toggle(name, name === slot);
                });
            });
        }

        /* middle -> left, right -> middle, left -> right */
        function advance() {
            centre = (centre + 1) % count;
            paint();
        }

        function stop() { if (timer) { clearInterval(timer); timer = null; } }
        function restart() {
            stop();
            if (reduced.matches) return;
            timer = setInterval(advance, HOLD);
        }

        /* Hovering holds the set still on whichever picture is being
           looked at, and the tab going to the background stops it
           entirely rather than racing through it unseen. */
        root.addEventListener("mouseenter", stop);
        root.addEventListener("mouseleave", restart);
        root.addEventListener("focusin", stop);
        root.addEventListener("focusout", restart);
        document.addEventListener("visibilitychange", function () {
            if (document.hidden) { stop(); } else { restart(); }
        });

        paint();
        restart();
    }

    /* ---------- Photo viewer ----------
       One photograph at a time, large but not full-screen, over a blurred
       and dimmed page. A native <dialog> shown with showModal() brings
       Escape-to-close, a focus trap and an inert page for free; the blur
       is its ::backdrop. Arrows (and the arrow keys) step through the set,
       and clicking anywhere outside the photograph closes it. */
    function createViewer(slides, onShow, pause, resume) {
        var dialog = document.createElement("dialog");
        dialog.className = "landing-viewer";
        // focus lands on the dialog itself when it opens, not on the close
        // button, so no focus ring shows until someone presses Tab
        dialog.setAttribute("tabindex", "-1");
        dialog.setAttribute("aria-label", "Photograph");
        dialog.innerHTML =
            '<figure class="landing-viewer-frame">' +
            '  <img alt="">' +
            '</figure>' +
            '<button type="button" class="landing-viewer-btn is-close" aria-label="Close">' +
            '  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>' +
            '</button>' +
            '<button type="button" class="landing-viewer-btn is-prev" aria-label="Previous photograph">' +
            '  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m15 18-6-6 6-6"/></svg>' +
            '</button>' +
            '<button type="button" class="landing-viewer-btn is-next" aria-label="Next photograph">' +
            '  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m9 18 6-6-6-6"/></svg>' +
            '</button>';
        document.body.appendChild(dialog);

        var img = dialog.querySelector("img");
        var current = 0;

        function show(i) {
            current = (i + slides.length) % slides.length;
            var src = slides[current].querySelector("img");
            img.src = src.currentSrc || src.src;
            img.alt = src.alt;
            onShow(current);
        }

        function open(i) {
            pause();
            show(i);
            if (typeof dialog.showModal === "function") {
                dialog.showModal();
            } else {
                dialog.setAttribute("open", "");
            }
            dialog.focus();
        }

        function close() {
            if (typeof dialog.close === "function") dialog.close();
            else dialog.removeAttribute("open");
        }

        dialog.querySelector(".is-close").addEventListener("click", close);
        dialog.querySelector(".is-prev").addEventListener("click", function () { show(current - 1); });
        dialog.querySelector(".is-next").addEventListener("click", function () { show(current + 1); });

        // a click on the dialog itself (the blurred margin), not on the
        // photograph or a button, closes it
        dialog.addEventListener("click", function (e) {
            if (e.target === dialog) close();
        });

        dialog.addEventListener("keydown", function (e) {
            if (e.key === "ArrowLeft") { e.preventDefault(); show(current - 1); }
            if (e.key === "ArrowRight") { e.preventDefault(); show(current + 1); }
        });

        dialog.addEventListener("close", function () {
            resume();
            var back = slides[current];
            if (back) back.focus({ preventScroll: true });
        });

        return { open: open };
    }

    /* ---------- Hero map ----------
       Each municipality in the two surveyed districts is its own path.
       Pointing at one asks /api/municipality/<name> - a public route, so
       the landing page needs no session - for its site count.

       The map is fully readable without any of this; the tip is an extra. */
    function initMapHover() {
        var figure = document.querySelector(".landing-hero-map");
        var tip = document.getElementById("mapTip");
        if (!figure || !tip) return;

        var name = tip.querySelector(".map-tip-name");
        var stats = tip.querySelector(".map-tip-stats");
        var cache = {};
        var active = null;

        /* Site count only. The API's tree_total is the CONTRACTED target, not
           what survived or was even planted, so showing it beside a site count
           read as an achievement it is not. */
        function describe(data) {
            if (!data || !data.found) return "No recorded sites";
            var sites = data.site_count || 0;
            if (!sites) return "No recorded sites";
            return sites + " " + (sites === 1 ? "site" : "sites");
        }

        function place(path) {
            var box = path.getBoundingClientRect();
            var frame = figure.getBoundingClientRect();
            var x = box.left + box.width / 2 - frame.left;
            var y = box.top - frame.top;

            /* Near the top of the map there is no room above the shape, so
               the tip flips underneath it rather than escaping the figure. */
            var below = y < tip.offsetHeight + 12;
            tip.classList.toggle("is-below", below);
            tip.style.top = (below ? box.bottom - frame.top + 8 : y - 8) + "px";
            tip.style.left = Math.max(
                tip.offsetWidth / 2,
                Math.min(x, frame.width - tip.offsetWidth / 2)
            ) + "px";
        }

        function show(path) {
            var muni = path.getAttribute("data-municipality");
            if (!muni) return;
            active = muni;

            name.textContent = muni;
            stats.textContent = cache[muni] ? describe(cache[muni]) : "Loading…";
            tip.hidden = false;
            place(path);

            if (cache[muni]) return;

            /* Two spellings are in play. GADM writes "UrdanetaCity", the DENR
               spreadsheet writes "Urdaneta City", and scripts/fixnames.py
               rewrites the database from the first to the second. A checkout
               that has not run it still holds the run-together form, and
               /api/municipality matches case-insensitively but not
               space-insensitively - so ask for both rather than reporting no
               sites on a database that has them. */
            var candidates = [muni];
            var squashed = muni.replace(/\s+/g, "");
            if (squashed !== muni) candidates.push(squashed);

            (function attempt(i) {
                if (i >= candidates.length) {
                    cache[muni] = null;
                    if (active === muni) { stats.textContent = describe(null); }
                    return;
                }
                fetch("/api/municipality/" + encodeURIComponent(candidates[i]))
                    .then(function (r) { return r.ok ? r.json() : null; })
                    .catch(function () { return null; })
                    .then(function (data) {
                        if (!data || !data.found) return attempt(i + 1);
                        cache[muni] = data;
                        /* The pointer may have moved on while this was in
                           flight - only the shape still under it may write. */
                        if (active !== muni) return;
                        stats.textContent = describe(data);
                        place(path);
                    });
            })(0);
        }

        function hide() {
            active = null;
            tip.hidden = true;
        }

        figure.addEventListener("mouseover", function (e) {
            var path = e.target.closest(".map-muni");
            if (path) show(path);
        });
        figure.addEventListener("mouseout", function (e) {
            var path = e.target.closest(".map-muni");
            if (path && !path.contains(e.relatedTarget)) hide();
        });
        figure.addEventListener("focusin", function (e) {
            var path = e.target.closest(".map-muni");
            if (path) show(path);
        });
        figure.addEventListener("focusout", hide);
        window.addEventListener("blur", hide);
    }

    function init() {
        initNav();
        initNavSpy();
        initReveals();
        initMarquee();
        initPlates();
        initMapHover();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
