/* The shared place picker: type-to-search municipality and barangay boxes.
 *
 * The standard is the Species Recommendation page's picker. Every page that
 * asks for a municipality and barangay uses this file and the macro in
 * templates/partials/_place_picker.html. Nothing here is copied elsewhere.
 *
 * Two layers:
 *
 *   PlacePicker.makeCombo(opts)   one search box over a list of names
 *       opts: input, list, items, noun ("municipality"), onPick(name),
 *             onType() (optional, after every keystroke)
 *       Typing filters the names: names that start with the text come first,
 *       then names that contain it. Spaces, dots and dashes are ignored, so
 *       "sanman" finds "San Manuel". Arrow keys move, Enter picks, Escape
 *       puts back the last choice. Leaving the box with text that names
 *       exactly one place picks it.
 *
 *   PlacePicker.get(root)         a municipality box and a barangay box,
 *       joined, for a [data-place-picker] element the macro wrote. The
 *       barangay list follows the municipality. A hidden location id is
 *       kept in step when the page asks for one. Events on root:
 *         place:municipality  {municipality}
 *         place:barangay      {municipality, barangay, id}
 *       Returns {municipality(), barangay(), id(), setByName(m, b), clear()}.
 *       setByName fires no events; it returns {municipality: bool,
 *       barangay: bool} for what it found.
 */
(function () {
  "use strict";

  function fold(s) { return String(s).toLowerCase().replace(/[\s.\-']/g, ""); }
  function esc(s) {
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  // Bold the typed text inside the name, when it appears as typed.
  function highlight(name, q) {
    const i = q ? name.toLowerCase().indexOf(q.toLowerCase()) : -1;
    if (i < 0) return esc(name);
    return esc(name.slice(0, i)) + "<mark>" + esc(name.slice(i, i + q.length))
      + "</mark>" + esc(name.slice(i + q.length));
  }

  function makeCombo(opts) {
    const input = opts.input;
    const list = opts.list;
    let items = opts.items;
    let chosen = input.value;   // the last name picked from the list
    let shown = [];
    let active = -1;

    function matches(q) {
      const key = fold(q);
      if (!key) return items.slice();
      const starts = [], contains = [];
      items.forEach(function (t) {
        const f = fold(t);
        if (f.startsWith(key)) starts.push(t);
        else if (f.indexOf(key) !== -1) contains.push(t);
      });
      return starts.concat(contains);
    }

    function open() {
      if (input.disabled) return;
      const q = input.value.trim();
      // Right after a pick the box holds the full name; show every name
      // then, so clicking it again works like a dropdown.
      const all = q === chosen;
      shown = all ? items.slice() : matches(q);
      active = shown.length ? Math.max(0, all ? shown.indexOf(chosen) : 0) : -1;
      list.innerHTML = shown.length
        ? shown.map(function (t, i) {
            return '<li role="option" id="' + list.id + '-opt-' + i + '" data-i="' + i + '">'
              + highlight(t, all ? "" : q) + "</li>";
          }).join("")
        : '<li class="place-combo-empty">No ' + opts.noun + ' matches “' + esc(q) + '”.</li>';
      list.hidden = false;
      input.setAttribute("aria-expanded", "true");
      syncActive();
    }

    function close() {
      list.hidden = true;
      input.setAttribute("aria-expanded", "false");
      input.removeAttribute("aria-activedescendant");
    }

    function syncActive() {
      list.querySelectorAll("li[data-i]").forEach(function (li) {
        const on = Number(li.dataset.i) === active;
        li.classList.toggle("is-active", on);
        li.setAttribute("aria-selected", on ? "true" : "false");
        if (on) li.scrollIntoView({ block: "nearest" });
      });
      if (active >= 0) input.setAttribute("aria-activedescendant", list.id + "-opt-" + active);
    }

    function pick(name) {
      input.value = name;
      close();
      if (name !== chosen) {
        chosen = name;
        opts.onPick(name);
      }
    }

    input.addEventListener("focus", function () { input.select(); open(); });
    input.addEventListener("click", open);
    input.addEventListener("input", function () {
      open();
      if (opts.onType) opts.onType();
    });

    input.addEventListener("keydown", function (e) {
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        if (list.hidden) { open(); return; }
        if (!shown.length) return;
        active = (active + (e.key === "ArrowDown" ? 1 : -1) + shown.length) % shown.length;
        syncActive();
      } else if (e.key === "Enter") {
        // Enter picks the highlighted name instead of submitting the form.
        if (!list.hidden && active >= 0) {
          e.preventDefault();
          pick(shown[active]);
        } else if (input.value.trim() !== chosen) {
          e.preventDefault();
        }
      } else if (e.key === "Escape") {
        input.value = chosen;
        close();
        if (opts.onType) opts.onType();
      }
    });

    // mousedown, not click: it fires before the input loses focus
    list.addEventListener("mousedown", function (e) {
      const li = e.target.closest("li[data-i]");
      e.preventDefault();
      if (li) pick(shown[Number(li.dataset.i)]);
    });

    // Leaving the box with half-typed text: take the name if the text
    // names exactly one, else put back the name already chosen.
    input.addEventListener("blur", function () {
      close();
      const q = input.value.trim();
      if (q === chosen) return;
      const exact = items.find(function (t) { return fold(t) === fold(q); });
      const only = matches(q);
      if (exact) pick(exact);
      else if (q && only.length === 1) pick(only[0]);
      else {
        input.value = chosen;
        if (opts.onType) opts.onType();
      }
    });

    return {
      chosen: function () { return chosen; },
      setChosen: function (name) { chosen = name; input.value = name; },
      // a new list of names (e.g. another town's barangays) and its value
      reset: function (newItems, value) {
        items = newItems;
        chosen = value || "";
        input.value = chosen;
        close();
      },
    };
  }

  // ---- a municipality box and a barangay box, joined ---------------------
  function attach(root) {
    const places = JSON.parse(root.querySelector('[data-role="places"]').textContent);
    const muniInput = root.querySelector('[data-role="municipality"]');
    const brgyInput = root.querySelector('[data-role="barangay"]');
    const idInput = root.querySelector('[data-role="location-id"]');
    const muniOnly = !brgyInput;

    const municipalities = [];
    places.forEach(function (p) {
      if (municipalities.indexOf(p.municipality) === -1) municipalities.push(p.municipality);
    });
    municipalities.sort();

    function barangaysOf(m) {
      return places.filter(function (p) { return p.municipality === m; })
        .map(function (p) { return p.barangay; }).sort();
    }
    function placeOf(m, b) {
      return places.find(function (p) { return p.municipality === m && p.barangay === b; });
    }
    function fire(name, detail) {
      root.dispatchEvent(new CustomEvent(name, { detail: detail, bubbles: true }));
    }
    function setBrgyEnabled(on) {
      if (muniOnly) return;
      brgyInput.disabled = !on;
      brgyInput.placeholder = on ? "Search a barangay…" : "Pick a municipality first";
    }

    let brgyCombo = null;
    const muniCombo = makeCombo({
      input: muniInput,
      list: root.querySelector('[data-role="municipality-list"]'),
      items: municipalities,
      noun: "municipality",
      onPick: function (m) {
        if (brgyCombo) brgyCombo.reset(barangaysOf(m), "");
        setBrgyEnabled(true);
        if (idInput) idInput.value = "";
        fire("place:municipality", { municipality: m });
      },
    });
    if (!muniOnly) {
      brgyCombo = makeCombo({
        input: brgyInput,
        list: root.querySelector('[data-role="barangay-list"]'),
        items: barangaysOf(muniInput.value),
        noun: "barangay",
        onPick: function (b) {
          const p = placeOf(muniCombo.chosen(), b);
          if (idInput) idInput.value = p ? p.id : "";
          brgyInput.setCustomValidity("");
          fire("place:barangay", { municipality: muniCombo.chosen(), barangay: b,
                                   id: p ? p.id : null });
        },
      });
      setBrgyEnabled(!!muniInput.value);
    }

    // A required picker needs a real place, not half-typed text.
    const form = root.closest("form");
    if (form && root.hasAttribute("data-required")) {
      form.addEventListener("submit", function (e) {
        const ok = muniOnly ? !!muniCombo.chosen()
                            : !!(muniCombo.chosen() && brgyCombo.chosen());
        if (!ok) {
          e.preventDefault();
          const box = muniOnly || !muniCombo.chosen() ? muniInput : brgyInput;
          box.setCustomValidity("Choose a " + (box === muniInput ? "municipality" : "barangay") + " from the list.");
          box.reportValidity();
          box.addEventListener("input", function clear() {
            box.setCustomValidity("");
            box.removeEventListener("input", clear);
          });
        }
      });
    }

    return {
      municipality: function () { return muniCombo.chosen(); },
      barangay: function () { return brgyCombo ? brgyCombo.chosen() : ""; },
      id: function () { return idInput ? idInput.value : ""; },
      // Choose by name, ignoring spacing and case: the map spells
      // "SanManuel" where the database has "San Manuel". No events.
      setByName: function (m, b) {
        const muni = municipalities.find(function (x) { return fold(x) === fold(m || ""); });
        if (!muni) return { municipality: false, barangay: false };
        muniCombo.setChosen(muni);
        let brgy = null;
        if (brgyCombo) {
          const names = barangaysOf(muni);
          brgy = names.find(function (x) { return fold(x) === fold(b || ""); }) || null;
          brgyCombo.reset(names, brgy || "");
          setBrgyEnabled(true);
          const p = brgy ? placeOf(muni, brgy) : null;
          if (idInput) idInput.value = p ? p.id : "";
        }
        return { municipality: true, barangay: !!brgy };
      },
      clear: function () {
        muniCombo.setChosen("");
        if (brgyCombo) brgyCombo.reset([], "");
        setBrgyEnabled(false);
        if (idInput) idInput.value = "";
      },
    };
  }

  function get(root) {
    if (!root) return null;
    if (!root.placePicker) root.placePicker = attach(root);
    return root.placePicker;
  }

  function attachAll() {
    document.querySelectorAll("[data-place-picker]").forEach(get);
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", attachAll);
  } else {
    attachAll();
  }

  window.PlacePicker = { makeCombo: makeCombo, get: get, fold: fold };
})();
