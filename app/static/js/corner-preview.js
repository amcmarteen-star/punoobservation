/*
 * Plot preview for corner photographs.
 *
 * While an officer picks corner photos, this reads the GPS location out
 * of each photo in the browser (nothing is uploaded) and draws the plot
 * they make on a map, with the barangay outline and the requester's mark.
 * The officer can see a wrong or missing corner before saving.
 *
 * It follows the server's rules (build_boundary and inspect_photo in
 * app/services/monitoring.py): the boundary is the convex hull of the
 * distinct GPS points, at least minPoints of them, area by the same
 * shoelace formula, and a point outside the barangay outline is flagged.
 * The server still checks everything again when the visit is saved.
 *
 * Markup: an <input type="file" data-corner-preview="#box"> and, inside
 * #box, a map div [data-cp-map], a summary [data-cp-summary] and a list
 * [data-cp-list]. Settings come from <script id="corner-preview-config">.
 * Reads JPEG EXIF only; other formats are listed as "can't preview".
 */
(function () {
  "use strict";

  var CFG = {};
  try {
    CFG = JSON.parse(document.getElementById("corner-preview-config").textContent) || {};
  } catch (e) { CFG = {}; }
  var MIN = CFG.minPoints || 4;

  function esc(s) {
    return String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  // ---- EXIF: GPS and time from a JPEG --------------------------------------

  // Returns {lat, lon, time} | {none: true} (no GPS) | {unsupported: true}.
  function readExif(buffer) {
    var v = new DataView(buffer);
    if (v.byteLength < 4 || v.getUint16(0) !== 0xFFD8) return { unsupported: true };
    var off = 2;
    while (off + 4 <= v.byteLength) {
      if (v.getUint8(off) !== 0xFF) break;
      var marker = v.getUint8(off + 1);
      var size = v.getUint16(off + 2);
      if (marker === 0xE1 && off + 10 <= v.byteLength &&
          v.getUint32(off + 4) === 0x45786966) {          // "Exif"
        return parseTiff(v, off + 10) || { none: true };
      }
      if (marker === 0xDA) break;                          // image data starts
      off += 2 + size;
    }
    return { none: true };
  }

  function parseTiff(v, tiff) {
    try {
      var little = v.getUint16(tiff) === 0x4949;
      var u16 = function (o) { return v.getUint16(o, little); };
      var u32 = function (o) { return v.getUint32(o, little); };
      var entries = function (ifd, fn) {
        var n = u16(ifd);
        for (var i = 0; i < n; i++) fn(ifd + 2 + i * 12);
      };
      var ascii = function (e) {
        var count = u32(e + 4);
        var at = count <= 4 ? e + 8 : tiff + u32(e + 8);
        var s = "";
        for (var i = 0; i < count - 1; i++) s += String.fromCharCode(v.getUint8(at + i));
        return s;
      };
      var rationals = function (e) {
        var at = tiff + u32(e + 8), out = [];
        for (var i = 0; i < 3; i++) {
          var den = u32(at + i * 8 + 4);
          out.push(den ? u32(at + i * 8) / den : 0);
        }
        return out[0] + out[1] / 60 + out[2] / 3600;
      };

      var gpsIfd = null, exifIfd = null, time = null;
      entries(tiff + u32(tiff + 4), function (e) {
        var tag = u16(e);
        if (tag === 0x8825) gpsIfd = tiff + u32(e + 8);
        if (tag === 0x8769) exifIfd = tiff + u32(e + 8);
        if (tag === 0x0132 && !time) time = ascii(e);
      });
      if (exifIfd) {
        entries(exifIfd, function (e) { if (u16(e) === 0x9003) time = ascii(e); });
      }
      if (!gpsIfd) return { none: true, time: time };

      var g = {};
      entries(gpsIfd, function (e) {
        var tag = u16(e);
        if (tag === 1) g.latRef = String.fromCharCode(v.getUint8(e + 8));
        if (tag === 2) g.lat = rationals(e);
        if (tag === 3) g.lonRef = String.fromCharCode(v.getUint8(e + 8));
        if (tag === 4) g.lon = rationals(e);
      });
      if (g.lat == null || g.lon == null || (!g.lat && !g.lon)) return { none: true, time: time };
      var lat = g.latRef === "S" ? -g.lat : g.lat;
      var lon = g.lonRef === "W" ? -g.lon : g.lon;
      // rounded like the server (extract_photo_metadata), so "same spot"
      // means the same thing here and there
      return { lat: Math.round(lat * 1e6) / 1e6, lon: Math.round(lon * 1e6) / 1e6, time: time };
    } catch (err) {
      return null;
    }
  }

  function readPhoto(file) {
    // EXIF sits at the start of the file; no need to read 9 MB
    return file.slice(0, 256 * 1024).arrayBuffer()
      .then(readExif)
      .catch(function () { return { none: true }; });
  }

  function niceTime(t) {
    // "2026:11:07 21:54:03" -> "07 Nov 2026, 21:54"
    var m = /^(\d{4}):(\d{2}):(\d{2}) (\d{2}):(\d{2})/.exec(t || "");
    if (!m) return "";
    var months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
    return m[3] + " " + (months[+m[2] - 1] || m[2]) + " " + m[1] + ", " + m[4] + ":" + m[5];
  }

  // ---- geometry: the server's rules -----------------------------------------

  function inRing(lon, lat, ring) {
    var inside = false;
    for (var i = 0, j = ring.length - 1; i < ring.length; j = i++) {
      var xi = ring[i][0], yi = ring[i][1], xj = ring[j][0], yj = ring[j][1];
      if ((yi > lat) !== (yj > lat) && lon < (xj - xi) * (lat - yi) / (yj - yi) + xi) inside = !inside;
    }
    return inside;
  }

  function inGeometry(lon, lat, geom) {
    if (!geom) return null;
    if (geom.type === "Feature") geom = geom.geometry;
    var polys = geom.type === "Polygon" ? [geom.coordinates]
      : geom.type === "MultiPolygon" ? geom.coordinates : [];
    return polys.some(function (p) { return p && p[0] && inRing(lon, lat, p[0]); });
  }

  function convexHull(points) {       // [[lon, lat], ...], monotone chain
    var pts = points.slice().sort(function (a, b) { return a[0] - b[0] || a[1] - b[1]; });
    if (pts.length < 3) return pts;
    var cross = function (o, a, b) {
      return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);
    };
    var lower = [], upper = [];
    pts.forEach(function (p) {
      while (lower.length >= 2 && cross(lower[lower.length - 2], lower[lower.length - 1], p) <= 0) lower.pop();
      lower.push(p);
    });
    for (var i = pts.length - 1; i >= 0; i--) {
      var p = pts[i];
      while (upper.length >= 2 && cross(upper[upper.length - 2], upper[upper.length - 1], p) <= 0) upper.pop();
      upper.push(p);
    }
    upper.pop(); lower.pop();
    return lower.concat(upper);
  }

  function areaHa(coords) {           // same as polygon_area_ha()
    if (coords.length < 3) return 0;
    var meanLat = coords.reduce(function (s, c) { return s + c[1]; }, 0) / coords.length;
    var mLat = 111132.0, mLon = 111320.0 * Math.cos(meanLat * Math.PI / 180);
    var total = 0;
    for (var i = 0; i < coords.length; i++) {
      var a = coords[i], b = coords[(i + 1) % coords.length];
      total += (a[0] * mLon) * (b[1] * mLat) - (b[0] * mLon) * (a[1] * mLat);
    }
    return Math.abs(total) / 2 / 10000;
  }

  // ---- the preview ------------------------------------------------------------

  function setup(input) {
    var box = document.querySelector(input.dataset.cornerPreview);
    if (!box || !window.L) return;
    var mapEl = box.querySelector("[data-cp-map]");
    var summary = box.querySelector("[data-cp-summary]");
    var list = box.querySelector("[data-cp-list]");
    var brgyName = CFG.barangayName || "the barangay";

    var map = L.map(mapEl, { scrollWheelZoom: false });
    L.tileLayer(MAP_TILES.street.url, {
      maxZoom: 19, attribution: MAP_TILES.street.attribution,
    }).addTo(map);

    var context = L.featureGroup().addTo(map);
    if (CFG.barangay) {
      L.geoJSON(CFG.barangay, {
        interactive: false,
        style: { color: "#64748b", weight: 1.5, dashArray: "6 4", fill: false },
      }).addTo(context);
    }
    var proposed = CFG.proposed || {};
    if (proposed.geometry) {
      L.geoJSON(proposed.geometry, {
        interactive: false,
        style: { color: "#0ea5e9", weight: 2, dashArray: "6 4", fillColor: "#0ea5e9", fillOpacity: 0.08 },
      }).addTo(context);
    }
    if (proposed.pin) {
      L.circleMarker(proposed.pin, { radius: 5, color: "#0ea5e9", weight: 2, fillOpacity: 0.6 })
        .bindTooltip("Requester's pin").addTo(context);
    }
    var plot = L.featureGroup().addTo(map);

    function fitAll() {
      var b = L.latLngBounds([]);
      [plot, context].forEach(function (g) { if (g.getLayers().length) b.extend(g.getBounds()); });
      // the plot first: zoom to the corners when there are any
      if (plot.getLayers().length) b = plot.getBounds();
      else if (proposed.geometry || proposed.pin) {
        b = L.latLngBounds([]);
        context.eachLayer(function (l) {
          if (l.getBounds) b.extend(l.getBounds()); else if (l.getLatLng) b.extend(l.getLatLng());
        });
      }
      if (b.isValid()) map.fitBounds(b, { padding: [30, 30], maxZoom: 18 });
      else map.setView([15.95, 120.6], 10);
    }
    fitAll();

    var token = 0;
    function refresh() {
      var files = Array.prototype.slice.call(input.files || []);
      var mine = ++token;
      if (!files.length) {
        plot.clearLayers();
        list.innerHTML = "";
        summary.className = "cp-summary";
        summary.textContent = "Add corner photos to see the plot they make.";
        fitAll();
        return;
      }
      summary.className = "cp-summary";
      summary.textContent = "Reading photo locations...";
      Promise.all(files.map(readPhoto)).then(function (results) {
        if (mine !== token) return;            // the photos changed meanwhile
        draw(files, results);
      });
    }

    function draw(files, results) {
      plot.clearLayers();
      var seen = {};                          // "lat,lon" -> corner number
      var rows = [], distinct = [];
      results.forEach(function (r, i) {
        var n = i + 1, notes = [], cls = "is-ok";
        if (!r || r.unsupported) {
          notes.push("Can't preview this file. It is still checked when you save.");
          cls = "is-warn";
        } else if (r.none || r.lat == null) {
          notes.push("No location in this photo. Use a GPS camera app.");
          cls = "is-bad";
        } else {
          var key = r.lat + "," + r.lon;
          var inside = inGeometry(r.lon, r.lat, CFG.barangay);
          if (seen[key]) {
            notes.push("Same spot as corner " + seen[key] + ". Take each photo at a different corner.");
            cls = "is-bad";
          } else {
            seen[key] = n;
            distinct.push([r.lon, r.lat]);
          }
          if (inside === false) {
            notes.push("Outside " + brgyName + " on the map.");
            if (cls === "is-ok") cls = "is-warn";
          }
          var icon = L.divIcon({
            className: "cp-pin " + cls, html: String(n), iconSize: [24, 24], iconAnchor: [12, 12],
          });
          L.marker([r.lat, r.lon], { icon: icon, keyboard: false })
            .bindTooltip("Corner " + n + ": " + files[i].name).addTo(plot);
        }
        rows.push(
          '<li class="' + cls + '"><span class="cp-num">' + n + "</span>" +
          '<span class="cp-body"><span class="cp-name">' + esc(files[i].name) + "</span>" +
          '<span class="cp-meta">' +
          (r && r.lat != null ? r.lat.toFixed(5) + ", " + r.lon.toFixed(5) : "") +
          (r && r.time ? (r.lat != null ? " &middot; " : "") + esc(niceTime(r.time)) : "") +
          "</span>" +
          (notes.length ? '<span class="cp-note">' + notes.map(esc).join(" ") + "</span>" : "") +
          "</span></li>");
      });
      list.innerHTML = rows.join("");

      var hull = distinct.length >= 3 ? convexHull(distinct) : [];
      var msg, cls = "cp-summary";
      if (distinct.length < MIN) {
        msg = distinct.length + " different corner" + (distinct.length === 1 ? "" : "s") +
          " so far. At least " + MIN + " are needed to make the boundary.";
        cls += " is-warn";
      } else if (hull.length < 3) {
        msg = "The corners are in a straight line, so they make no area.";
        cls += " is-bad";
      } else {
        var ha = areaHa(hull);
        msg = "Plot: about " + ha.toFixed(2) + " ha from " + hull.length + " corners.";
        if (CFG.plannedHa > 0) {
          var diff = (ha - CFG.plannedHa) / CFG.plannedHa * 100;
          msg += " Planned: " + CFG.plannedHa + " ha (" + (diff >= 0 ? "+" : "") + diff.toFixed(0) + "%).";
          if (Math.abs(diff) > 10) {
            msg += diff > 0 ? " Bigger than planned: check that no corner is outside the site."
              : " Smaller than planned: the corners may not cover the whole site.";
            cls += " is-warn";
          } else {
            cls += " is-ok";
          }
        } else {
          cls += " is-ok";
        }
        if (hull.length < distinct.length) {
          var inner = distinct.length - hull.length;
          msg += " " + inner + " photo" + (inner === 1 ? " is" : "s are") +
            " inside the plot, so not used as a corner.";
        }
      }
      if (hull.length >= 3) {
        L.polygon(hull.map(function (p) { return [p[1], p[0]]; }), {
          color: "#16a34a", weight: 2, fillColor: "#16a34a", fillOpacity: 0.2, interactive: false,
        }).addTo(plot);
      }
      summary.className = cls;
      summary.textContent = msg;
      fitAll();
    }

    // upload.js keeps input.files in step with its own list, without a
    // change event when a file is removed, so watch the list it draws.
    input.addEventListener("change", refresh);
    var zone = input.closest(".up-zone");
    var watched = zone && zone.querySelector(".up-list");
    if (watched) new MutationObserver(refresh).observe(watched, { childList: true });
    refresh();
  }

  function init() {
    if (window.PNOUpload) window.PNOUpload.init();   // so the drop zone exists
    document.querySelectorAll("input[type=file][data-corner-preview]").forEach(setup);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
