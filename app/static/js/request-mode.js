/* Request mode for the GIS map: /gis-map?request=1
 *
 * The user finds the place on the real map, drops a pin or draws the
 * plot, or picks an existing site to adopt. "Continue" then opens the
 * request form with all of it filled in.
 *
 * Loaded after the GIS map script, so `map` already exists. Settings come
 * from the #req-mode-config JSON block in GIS_map.html.
 */
(function () {
  "use strict";

  const cfgEl = document.getElementById("req-mode-config");
  if (!cfgEl || typeof map === "undefined") return;
  const CFG = JSON.parse(cfgEl.textContent);

  const panel = document.getElementById("rq-panel");
  const typeSelect = document.getElementById("rq-type");
  const typeNote = document.getElementById("rq-type-note");
  const tools = document.getElementById("rq-tools");
  const toolBtns = tools.querySelectorAll("[data-mode]");
  const undoBtn = document.getElementById("rq-undo");
  const clearBtn = document.getElementById("rq-clear");
  const statusEl = document.getElementById("rq-status");
  const summaryEl = document.getElementById("rq-summary");
  const continueBtn = document.getElementById("rq-continue");
  const collapseBtn = document.getElementById("rq-collapse");

  const GREEN = "#16a34a";

  let features = [];       // barangay outlines, each with a bbox
  let mode = "explore";    // explore | pin | draw
  let pinMarker = null;
  let corners = [];        // [lat, lng] in click order
  let cornerDots = [];
  let shape = null;
  let site = null;         // the site to adopt
  let outline = null;      // the barangay the pin or plot is in

  // Drawn below the pin and the plot.
  map.createPane("rqArea");
  map.getPane("rqArea").style.zIndex = 440;
  map.getPane("rqArea").style.pointerEvents = "none";
  const drawLayer = L.layerGroup().addTo(map);

  // ---- names --------------------------------------------------------------

  function esc(value) {
    return String(value === null || value === undefined ? "" : value)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  // Same folding as normalize_municipality() in app/utils/jurisdiction.py.
  // barangay.geojson writes "UrdanetaCity" and misspells "Pozzorubio".
  const ALIASES = { pozzorubio: "pozorrubio" };
  function norm(name) {
    const key = String(name || "").toLowerCase().replace(/[\s.\-']/g, "");
    return ALIASES[key] || key;
  }

  const allowed = new Set(CFG.municipalities.map(norm));

  function isAdoption() { return typeSelect.value === CFG.adoption; }
  function needsMap() { return CFG.siteTypes.indexOf(typeSelect.value) !== -1; }

  // ---- geometry -----------------------------------------------------------

  // Ray casting on the outer ring, the same test as point_in_ring() on
  // the server, so the browser and the server agree about the pin.
  function ringContains(ring, x, y) {
    let inside = false;
    for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
      const xi = ring[i][0], yi = ring[i][1];
      const xj = ring[j][0], yj = ring[j][1];
      if ((yi > y) !== (yj > y) &&
          x < (xj - xi) * (y - yi) / (yj - yi + 1e-300) + xi) {
        inside = !inside;
      }
    }
    return inside;
  }

  function polygonsOf(geometry) {
    if (!geometry) return [];
    if (geometry.type === "Polygon") return [geometry.coordinates];
    if (geometry.type === "MultiPolygon") return geometry.coordinates;
    return [];
  }

  function bboxOf(feature) {
    const b = [180, 90, -180, -90];
    polygonsOf(feature.geometry).forEach(function (p) {
      (p[0] || []).forEach(function (c) {
        b[0] = Math.min(b[0], c[0]); b[1] = Math.min(b[1], c[1]);
        b[2] = Math.max(b[2], c[0]); b[3] = Math.max(b[3], c[1]);
      });
    });
    return b;
  }

  function featureContains(feature, lat, lng) {
    const b = feature.bbox;
    if (lng < b[0] || lng > b[2] || lat < b[1] || lat > b[3]) return false;
    return polygonsOf(feature.geometry).some(function (p) {
      return p[0] && ringContains(p[0], lng, lat);
    });
  }

  function featureAt(lat, lng) {
    return features.find(function (f) { return featureContains(f, lat, lng); }) || null;
  }

  // polygon_area_ha() from app/services/monitoring.py, so the area shown
  // here matches what the server stores.
  function areaHa(latlngs) {
    if (latlngs.length < 3) return 0;
    const meanLat = latlngs.reduce(function (s, c) { return s + c[0]; }, 0) / latlngs.length;
    const mLat = 111132.0;
    const mLon = 111320.0 * Math.cos(meanLat * Math.PI / 180);
    let total = 0;
    for (let i = 0; i < latlngs.length; i++) {
      const a = latlngs[i], b = latlngs[(i + 1) % latlngs.length];
      total += (a[1] * mLon) * (b[0] * mLat) - (b[1] * mLon) * (a[0] * mLat);
    }
    return Math.abs(total) / 2 / 10000;
  }

  // The average of the corners, as the server's boundary_centre() does.
  function cornersCentre() {
    const n = corners.length;
    return [
      corners.reduce(function (s, c) { return s + c[0]; }, 0) / n,
      corners.reduce(function (s, c) { return s + c[1]; }, 0) / n,
    ];
  }

  function round7(n) { return Math.round(n * 1e7) / 1e7; }

  // ---- what was marked, and what is wrong with it --------------------------

  // The barangay that decides the request: the pin's, else the plot centre's.
  function placeFeature() {
    if (pinMarker) {
      const ll = pinMarker.getLatLng();
      return featureAt(ll.lat, ll.lng);
    }
    if (corners.length >= 3) {
      const c = cornersCentre();
      return featureAt(c[0], c[1]);
    }
    return null;
  }

  function hasMark() { return !!pinMarker || corners.length >= 3; }

  // Returns { errors: [...], warnings: [...] }. Errors stop Continue.
  function problems() {
    const errors = [];
    const warnings = [];

    if (isAdoption()) {
      if (site && !allowed.has(norm(site.municipality))) {
        errors.push(site.municipality + " is outside your jurisdiction. Pick a site in a municipality you cover.");
      }
      return { errors: errors, warnings: warnings };
    }

    if (corners.length > 0 && corners.length < 3) {
      errors.push("A plot needs at least 3 corners. Add more, or use Clear.");
    }

    // A pin and a plot must describe the same place. The server refuses
    // the request otherwise, so it is stopped here first.
    if (pinMarker && corners.length >= 3) {
      const ll = pinMarker.getLatLng();
      const ring = corners.map(function (c) { return [c[1], c[0]]; });
      if (!ringContains(ring, ll.lng, ll.lat)) {
        errors.push("The pin is outside the plot. Drag the pin inside the plot, or redraw the plot around the pin.");
      }
    }

    if (hasMark() && features.length) {
      const f = placeFeature();
      const what = pinMarker ? "The pin" : "The plot";
      if (!f) {
        errors.push(what + " is outside the area this system covers (Districts 5 and 6). Move it inside Eastern Pangasinan.");
      } else if (!allowed.has(norm(f.properties.NAME_2))) {
        errors.push(what + " is in " + f.properties.NAME_2 + ", outside your jurisdiction.");
      } else if (corners.length >= 3) {
        const outside = corners.filter(function (c) { return !featureContains(f, c[0], c[1]); }).length;
        if (outside) {
          warnings.push(outside + " corner(s) of the plot fall outside " + f.properties.NAME_3
            + ". Barangay outlines are approximate, so you may still continue.");
        }
      }
    }
    return { errors: errors, warnings: warnings };
  }

  // ---- panel --------------------------------------------------------------

  function render() {
    const adoption = isAdoption();
    typeNote.textContent = !typeSelect.value
      ? "Choose a type to start."
      : adoption
        ? "Click a tree marker or a town, open its sites, then press “Adopt this site”."
        : needsMap()
          ? "Drop a pin on the site, or draw the plot by clicking its corners."
          : "Marking the place is optional for this type.";
    tools.hidden = !typeSelect.value || adoption;
    if (adoption && mode !== "explore") setMode("explore");

    undoBtn.disabled = corners.length === 0;
    clearBtn.disabled = corners.length === 0 && !pinMarker;

    // what was marked
    const lines = [];
    if (adoption) {
      if (site) {
        lines.push("<strong>Site to adopt:</strong> " + esc(site.name));
        lines.push(esc(site.barangay) + ", " + esc(site.municipality)
          + (site.area ? " · " + esc(site.area) + " ha" : ""));
      }
    } else {
      const f = features.length ? placeFeature() : null;
      if (f) lines.push("<strong>" + esc(f.properties.NAME_3) + "</strong>, " + esc(f.properties.NAME_2));
      if (pinMarker) {
        const ll = pinMarker.getLatLng();
        lines.push("Pin: " + ll.lat.toFixed(5) + ", " + ll.lng.toFixed(5));
      }
      if (corners.length >= 3) lines.push("Plot: " + areaHa(corners).toFixed(2) + " ha, " + corners.length + " corners");
    }
    summaryEl.innerHTML = lines.join("<br>");
    summaryEl.hidden = !lines.length;

    // errors first, then warnings, then the next step
    const p = problems();
    let text = "", kind = "";
    if (p.errors.length) { text = p.errors.join(" "); kind = "error"; }
    else if (p.warnings.length) { text = p.warnings.join(" "); kind = "warn"; }
    else if (mode === "pin") text = pinMarker ? "Click again or drag the pin to move it." : "Click the map where the site is.";
    else if (mode === "draw") text = corners.length < 3 ? "Click each corner of the plot, in order around the edge." : "Keep clicking to add corners.";
    else if (!adoption && typeSelect.value && !hasMark()) text = "Use Explore to look around. Pick Drop pin or Draw plot when you find the place.";
    statusEl.textContent = text;
    statusEl.className = "rq-status" + (kind ? " is-" + kind : "");

    // Continue
    let ready = !!typeSelect.value && !p.errors.length;
    if (adoption) ready = ready && !!site;
    else if (needsMap()) ready = ready && hasMark();
    continueBtn.disabled = !ready;

    drawOutline();
  }

  // Green dashed outline of the barangay the request falls in.
  function drawOutline() {
    if (outline) { drawLayer.removeLayer(outline); outline = null; }
    if (isAdoption() || !features.length) return;
    const f = placeFeature();
    if (!f) return;
    outline = L.geoJSON(f, {
      pane: "rqArea", interactive: false,
      style: { color: GREEN, weight: 2.5, dashArray: "6 4", fillOpacity: 0.04, fillColor: GREEN },
    }).addTo(drawLayer);
  }

  function setMode(next) {
    mode = next;
    toolBtns.forEach(function (b) { b.setAttribute("aria-pressed", String(b.dataset.mode === mode)); });
    // While placing, the GIS layers let clicks through to the map.
    map.getContainer().classList.toggle("req-placing", mode !== "explore");
    render();
  }

  // ---- pin and plot -------------------------------------------------------

  function placePin(latlng) {
    if (!pinMarker) {
      pinMarker = L.marker(latlng, { draggable: true, zIndexOffset: 1000 }).addTo(drawLayer);
      pinMarker.getElement().classList.add("rq-pin");
      pinMarker.on("dragend", render);
    } else {
      pinMarker.setLatLng(latlng);
    }
    render();
  }

  function addCorner(latlng) {
    corners.push([latlng.lat, latlng.lng]);
    cornerDots.push(L.circleMarker(latlng, {
      pane: "rqArea", radius: 4, color: GREEN, weight: 2,
      fillColor: "#ffffff", fillOpacity: 1, interactive: false,
    }).addTo(drawLayer));
    redrawShape();
  }

  function redrawShape() {
    if (shape) { drawLayer.removeLayer(shape); shape = null; }
    if (corners.length >= 3) {
      shape = L.polygon(corners, {
        pane: "rqArea", color: GREEN, weight: 2, fillColor: GREEN, fillOpacity: 0.2, interactive: false,
      }).addTo(drawLayer);
    } else if (corners.length === 2) {
      shape = L.polyline(corners, {
        pane: "rqArea", color: GREEN, weight: 2, dashArray: "4 4", interactive: false,
      }).addTo(drawLayer);
    }
    render();
  }

  function clearMarks() {
    if (pinMarker) { drawLayer.removeLayer(pinMarker); pinMarker = null; }
    cornerDots.forEach(function (d) { drawLayer.removeLayer(d); });
    cornerDots = [];
    corners = [];
    redrawShape();
  }

  map.on("click", function (e) {
    if (mode === "pin") placePin(e.latlng);
    else if (mode === "draw") addCorner(e.latlng);
  });

  toolBtns.forEach(function (btn) {
    btn.addEventListener("click", function () { setMode(btn.dataset.mode); });
  });
  undoBtn.addEventListener("click", function () {
    corners.pop();
    const dot = cornerDots.pop();
    if (dot) drawLayer.removeLayer(dot);
    redrawShape();
  });
  clearBtn.addEventListener("click", clearMarks);

  typeSelect.addEventListener("change", function () {
    // A pin or plot has no use for an adoption, and a chosen site has
    // none for anything else.
    if (isAdoption()) clearMarks();
    else site = null;
    if (needsMap() && mode === "explore" && !hasMark()) setMode("pin");
    else render();
  });

  collapseBtn.addEventListener("click", function () {
    const collapsed = panel.classList.toggle("is-collapsed");
    collapseBtn.setAttribute("aria-expanded", String(!collapsed));
  });

  // ---- adoption: buttons inside the GIS site cards --------------------------

  window.reqMode = {
    // HTML for an "Adopt this site" button, or "" when not adopting.
    adoptButton: function (s, municipality, barangay) {
      if (!isAdoption()) return "";
      return '<button type="button" class="rq-adopt-btn"'
        + ' data-id="' + esc(s.site_id) + '" data-name="' + esc(s.site_name) + '"'
        + ' data-muni="' + esc(municipality) + '" data-brgy="' + esc(barangay) + '"'
        + ' data-area="' + esc(s.area_size_ha || "") + '"'
        + ' onclick="event.stopPropagation(); reqMode.adopt(this)">Adopt this site</button>';
    },
    adopt: function (btn) {
      site = {
        id: btn.dataset.id, name: btn.dataset.name,
        municipality: btn.dataset.muni, barangay: btn.dataset.brgy,
        area: btn.dataset.area,
      };
      panel.classList.remove("is-collapsed");
      render();
    },
  };

  // ---- continue to the form -----------------------------------------------

  continueBtn.addEventListener("click", function () {
    const q = new URLSearchParams({ "new": "1", type: typeSelect.value });
    if (isAdoption() && site) {
      q.set("site", site.id);
      q.set("site_name", site.name);
      q.set("muni", site.municipality);
      q.set("brgy", site.barangay);
      if (site.area) q.set("area", site.area);
    } else {
      const f = placeFeature();
      if (f) {
        q.set("muni", f.properties.NAME_2);
        q.set("brgy", f.properties.NAME_3);
      }
      if (pinMarker) {
        const ll = pinMarker.getLatLng();
        q.set("lat", ll.lat.toFixed(6));
        q.set("lng", ll.lng.toFixed(6));
      }
      if (corners.length >= 3) {
        const ring = corners.map(function (c) { return [round7(c[1]), round7(c[0])]; });
        ring.push(ring[0]);
        q.set("boundary", JSON.stringify({ type: "Polygon", coordinates: [ring] }));
        q.set("area", areaHa(corners).toFixed(2));
      }
    }
    window.location.href = CFG.formUrl + "?" + q.toString();
  });

  // ---- coming back from the form ("Change on map") ------------------------

  function restore() {
    const q = new URLSearchParams(window.location.search);
    const type = q.get("type");
    if (type && CFG.requestTypes.indexOf(type) !== -1) typeSelect.value = type;

    const bounds = [];
    const lat = parseFloat(q.get("lat")), lng = parseFloat(q.get("lng"));
    if (isFinite(lat) && isFinite(lng)) {
      placePin(L.latLng(lat, lng));
      bounds.push([lat, lng]);
    }
    try {
      const ring = JSON.parse(q.get("boundary") || "null").coordinates[0];
      ring.slice(0, -1).forEach(function (c) {
        addCorner(L.latLng(c[1], c[0]));
        bounds.push([c[1], c[0]]);
      });
    } catch (e) { /* no plot, or not readable: start without one */ }

    if (q.get("site")) {
      site = {
        id: q.get("site"), name: q.get("site_name") || "Chosen site",
        municipality: q.get("muni") || "", barangay: q.get("brgy") || "",
        area: q.get("area") || "",
      };
    }
    if (bounds.length) map.fitBounds(bounds, { maxZoom: 16, padding: [40, 40] });
    render();
  }

  // One barangay file per CENRO the user's map covers (CENRO_GEOJSON).
  Promise.all((CFG.geojsonUrls || []).map(function (url) {
    return fetch(url).then(function (res) {
      if (!res.ok) throw new Error(url + " " + res.status);
      return res.json();
    });
  }))
    .then(function (files) {
      if (!files.length) throw new Error("no barangay outlines for this CENRO");
      features = [].concat.apply([], files.map(function (d) { return d.features; }));
      features.forEach(function (f) { f.bbox = bboxOf(f); });
      restore();
    })
    .catch(function () {
      statusEl.textContent = "Barangay outlines could not load, so the location cannot be checked. Reload the page to try again.";
      statusEl.className = "rq-status is-error";
    });

  render();
})();
