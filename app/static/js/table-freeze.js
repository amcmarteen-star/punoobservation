/*
 * Frozen table columns (Excel-style freeze panes).
 *
 * Opt in from a template:
 *   <div class="um-scroll-wrap table-freeze-wrap">
 *     <table class="um-table" data-freeze="2">
 *
 * data-freeze="1" freezes the first column, "2" the first two.
 *
 * The CSS ("FROZEN TABLE COLUMNS" in style.css) pins the header row and
 * the frozen columns. This script does the two things CSS cannot:
 *   - tells column 2 where column 1 ends (--freeze-col1-width)
 *   - adds .is-scrolled-x so the frozen edge gets a shadow
 *
 * Loaded once in Base.html. A table added after page load (built with
 * innerHTML) needs window.initFrozenTables() once it is on the page.
 */
(function () {
  function setup(table) {
    if (table.dataset.freezeReady) return;
    table.dataset.freezeReady = "1";

    var wrap = table.parentElement;
    var firstTh = table.querySelector("thead th");

    function measure() {
      if (firstTh) {
        table.style.setProperty(
          "--freeze-col1-width",
          firstTh.offsetWidth + "px",
        );
      }
    }

    function onScroll() {
      table.classList.toggle("is-scrolled-x", wrap.scrollLeft > 0);
    }

    measure();
    onScroll();
    wrap.addEventListener("scroll", onScroll, { passive: true });

    // column 1 changes width when rows are filtered or loaded, or the
    // window resizes, so re-measure whenever it does
    if (window.ResizeObserver && firstTh) {
      new ResizeObserver(measure).observe(firstTh);
    } else {
      window.addEventListener("resize", measure);
    }
  }

  function initFrozenTables() {
    document.querySelectorAll("table[data-freeze]").forEach(setup);
  }

  window.initFrozenTables = initFrozenTables;

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initFrozenTables);
  } else {
    initFrozenTables();
  }
})();
