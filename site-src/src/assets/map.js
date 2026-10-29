/* Errand Desk /map/: pan and zoom for the inline SVG map by changing its viewBox. No dependencies. */
(function () {
  "use strict";
  var root = document.getElementById("usmap");
  if (!root) return;
  var svg = root.querySelector("svg");
  var tools = root.querySelector(".usmap-tools");
  var status = root.querySelector(".usmap-status");
  var W = 975, H = 610, MAXK = 60, DOT_PX = 5, HIT_PX = 14, FONT_PX = 13, MIN_GAP_PX = 22;
  var cob = (svg.getAttribute("data-co") || "").split(" ").map(Number);
  var wyb = (svg.getAttribute("data-wy") || "").split(" ").map(Number);
  var mb = (svg.getAttribute("data-metro") || "").split(" ").map(Number);
  var dots = [].slice.call(svg.querySelectorAll(".dot"));
  var hits = [].slice.call(svg.querySelectorAll(".hit"));
  var labels = [].slice.call(svg.querySelectorAll(".lbl")).sort(function (a, b) {
    return a.getAttribute("data-pri") - b.getAttribute("data-pri");
  });
  var vb = { x: 0, y: 0, w: W, h: H };

  function clamp(v, a, b) { return Math.max(a, Math.min(b, v)); }
  function ppu() { // screen pixels per viewBox unit (preserveAspectRatio "meet")
    var r = svg.getBoundingClientRect();
    return Math.min(r.width / vb.w, r.height / vb.h) || 1;
  }
  function render() {
    var k = W / vb.w;
    vb.w = W / k; vb.h = H / k;
    vb.x = clamp(vb.x, -vb.w / 2, W - vb.w / 2);
    vb.y = clamp(vb.y, -vb.h / 2, H - vb.h / 2);
    if (k <= 1.0001) { vb.x = 0; vb.y = 0; }
    svg.setAttribute("viewBox", [vb.x, vb.y, vb.w, vb.h].map(function (n) { return +n.toFixed(3); }).join(" "));
    var p = ppu(), u = 1 / p;
    dots.forEach(function (c) { c.setAttribute("r", (DOT_PX * u).toFixed(4)); c.style.strokeWidth = (1.5 * u).toFixed(4); });
    hits.forEach(function (c) { c.setAttribute("r", (HIT_PX * u).toFixed(4)); });
    // Labels: show each one only where it fits on screen without overlapping a label already placed.
    var placed = [];
    labels.forEach(function (t) {
      t.style.display = "none";
      if (parseFloat(t.getAttribute("data-gap")) * p < MIN_GAP_PX) return;
      t.setAttribute("font-size", (FONT_PX * u).toFixed(4));
      t.setAttribute("x", (parseFloat(t.getAttribute("data-x")) + (DOT_PX + 3) * u).toFixed(4));
      t.setAttribute("y", (parseFloat(t.getAttribute("data-y")) + 4 * u).toFixed(4));
      t.style.strokeWidth = (3 * u).toFixed(4);
      t.style.display = "";
      var r = t.getBoundingClientRect(), hit = placed.some(function (q) {
        return r.left < q.right + 4 && r.right + 4 > q.left && r.top < q.bottom && r.bottom > q.top;
      });
      if (hit) t.style.display = "none"; else placed.push(r);
    });
    svg.style.setProperty("--u", u);
    root.classList.toggle("is-zoomed", k > 1.0001);
  }
  function toSvg(cx, cy) { // client px -> viewBox coordinates
    var r = svg.getBoundingClientRect(), p = ppu();
    var ox = (r.width - vb.w * p) / 2, oy = (r.height - vb.h * p) / 2;
    return { x: vb.x + (cx - r.left - ox) / p, y: vb.y + (cy - r.top - oy) / p };
  }
  function zoomAt(f, sx, sy) { // f > 1 zooms in, keeping viewBox point (sx, sy) fixed on screen
    var k = clamp((W / vb.w) * f, 1, MAXK), nw = W / k, nh = H / k;
    vb.x = sx - (sx - vb.x) * (nw / vb.w); vb.y = sy - (sy - vb.y) * (nh / vb.h);
    vb.w = nw; vb.h = nh; render();
  }
  function zoomCenter(f) { zoomAt(f, vb.x + vb.w / 2, vb.y + vb.h / 2); }
  function fit(x0, y0, x1, y1) {
    var pad = 0.08, w = (x1 - x0) * (1 + 2 * pad), h = (y1 - y0) * (1 + 2 * pad);
    var k = clamp(Math.min(W / w, H / h), 1, MAXK);
    vb.w = W / k; vb.h = H / k; vb.x = (x0 + x1) / 2 - vb.w / 2; vb.y = (y0 + y1) / 2 - vb.h / 2; render();
  }
  function say(msg) { if (status) status.textContent = msg; }

  tools.hidden = false;
  tools.addEventListener("click", function (e) {
    var b = e.target.closest("button"); if (!b) return;
    var a = b.getAttribute("data-act");
    if (a === "in") zoomCenter(1.6);
    else if (a === "out") zoomCenter(1 / 1.6);
    else if (a === "reset") { vb = { x: 0, y: 0, w: W, h: H }; render(); }
    else if (a === "co" && cob.length === 4) fit(cob[0], cob[1], cob[2], cob[3]);
    else if (a === "wy" && wyb.length === 4) fit(wyb[0], wyb[1], wyb[2], wyb[3]);
    else if (a === "metro" && mb.length === 4) fit(mb[0], mb[1], mb[2], mb[3]);
    say("Zoom " + (W / vb.w).toFixed(1) + "x");
  });

  svg.addEventListener("wheel", function (e) {
    e.preventDefault();
    var d = e.deltaMode === 1 ? e.deltaY * 16 : e.deltaY;
    var pt = toSvg(e.clientX, e.clientY);
    zoomAt(Math.exp(-clamp(d, -100, 100) * 0.0025), pt.x, pt.y);
  }, { passive: false });

  // Pointer pan (one finger or mouse) and pinch zoom (two fingers).
  var ptrs = {}, moved = false, startX = 0, startY = 0, last = null, captured = false;
  function count() { return Object.keys(ptrs).length; }
  function pinchState() {
    var ids = Object.keys(ptrs), a = ptrs[ids[0]], b = ptrs[ids[1]];
    return { d: Math.hypot(a.x - b.x, a.y - b.y), cx: (a.x + b.x) / 2, cy: (a.y + b.y) / 2 };
  }
  svg.addEventListener("pointerdown", function (e) {
    if (e.pointerType === "mouse" && e.button !== 0) return;
    ptrs[e.pointerId] = { x: e.clientX, y: e.clientY };
    if (count() === 1) { moved = false; startX = e.clientX; startY = e.clientY; captured = false; }
    last = count() === 2 ? pinchState() : null;
  });
  svg.addEventListener("pointermove", function (e) {
    var p = ptrs[e.pointerId]; if (!p) return;
    var px = p.x, py = p.y; p.x = e.clientX; p.y = e.clientY;
    if (!moved && Math.hypot(e.clientX - startX, e.clientY - startY) > 6) moved = true;
    if (!moved) return;
    if (!captured) { try { svg.setPointerCapture(e.pointerId); } catch (_) {} captured = true; }
    if (count() >= 2) {
      var s = pinchState();
      if (last && last.d > 0) {
        var a = toSvg(last.cx, last.cy);
        zoomAt(s.d / last.d, a.x, a.y);
        var u = 1 / ppu();
        vb.x -= (s.cx - last.cx) * u; vb.y -= (s.cy - last.cy) * u; render();
      }
      last = s;
    } else {
      var k = 1 / ppu();
      vb.x -= (e.clientX - px) * k; vb.y -= (e.clientY - py) * k; render();
    }
  });
  function up(e) {
    delete ptrs[e.pointerId];
    last = count() === 2 ? pinchState() : null;
  }
  svg.addEventListener("pointerup", up);
  svg.addEventListener("pointercancel", up);
  // A drag or pinch should not also follow a dot link.
  svg.addEventListener("click", function (e) { if (moved) { e.preventDefault(); e.stopPropagation(); moved = false; } }, true);
  window.addEventListener("resize", render);
  render();
})();
