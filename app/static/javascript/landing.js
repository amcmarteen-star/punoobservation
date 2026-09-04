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

    function init() {
        initNav();
        initReveals();
        initMarquee();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
