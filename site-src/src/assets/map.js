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
  var utb = (svg.getAttribute("data-ut") || "").split(" ").map(Number);
  var mb = (svg.getAttribute("data-metro") || "").split(" ").map(Number);
  var slb = (svg.getAttribute("data-slc") || "").split(" ").map(Number);
  var neb = (svg.getAttribute("data-ne") || "").split(" ").map(Number);
  var omb = (svg.getAttribute("data-omaha") || "").split(" ").map(Number);
  var ksb = (svg.getAttribute("data-ks") || "").split(" ").map(Number);
  var kcb = (svg.getAttribute("data-kc") || "").split(" ").map(Number);
  var nmb = (svg.getAttribute("data-nm") || "").split(" ").map(Number);
  var azb = (svg.getAttribute("data-az") || "").split(" ").map(Number);
  var sdb = (svg.getAttribute("data-sd") || "").split(" ").map(Number);
  var ndb = (svg.getAttribute("data-nd") || "").split(" ").map(Number);
  var mtb = (svg.getAttribute("data-mt") || "").split(" ").map(Number);
  var nvb = (svg.getAttribute("data-nv") || "").split(" ").map(Number);
  var idb = (svg.getAttribute("data-id") || "").split(" ").map(Number);
  var wab = (svg.getAttribute("data-wa") || "").split(" ").map(Number);
  var orb = (svg.getAttribute("data-or") || "").split(" ").map(Number);
  var cab = (svg.getAttribute("data-ca") || "").split(" ").map(Number);
  var okb = (svg.getAttribute("data-ok") || "").split(" ").map(Number);
  var txb = (svg.getAttribute("data-tx") || "").split(" ").map(Number);
  var mnb = (svg.getAttribute("data-mn") || "").split(" ").map(Number);
  var iab = (svg.getAttribute("data-ia") || "").split(" ").map(Number);
  var mob = (svg.getAttribute("data-mo") || "").split(" ").map(Number);
  var arb = (svg.getAttribute("data-ar") || "").split(" ").map(Number);
  var dfb = (svg.getAttribute("data-dfw") || "").split(" ").map(Number);
  var atb = (svg.getAttribute("data-atx") || "").split(" ").map(Number);
  var nwb = (svg.getAttribute("data-nwa") || "").split(" ").map(Number);
  var lab = (svg.getAttribute("data-la") || "").split(" ").map(Number);
  var swb = (svg.getAttribute("data-swla") || "").split(" ").map(Number);
  var wib = (svg.getAttribute("data-wi") || "").split(" ").map(Number);
  var sewb = (svg.getAttribute("data-sewi") || "").split(" ").map(Number);
  var ilb = (svg.getAttribute("data-il") || "").split(" ").map(Number);
  var chib = (svg.getAttribute("data-chi") || "").split(" ").map(Number);
  var msb = (svg.getAttribute("data-ms") || "").split(" ").map(Number);
  var tnb = (svg.getAttribute("data-tn") || "").split(" ").map(Number);
  var memb = (svg.getAttribute("data-mem") || "").split(" ").map(Number);
  var kyb = (svg.getAttribute("data-ky") || "").split(" ").map(Number);
  var alb = (svg.getAttribute("data-al") || "").split(" ").map(Number);
  var inb = (svg.getAttribute("data-ind") || "").split(" ").map(Number);
  var mib = (svg.getAttribute("data-mi") || "").split(" ").map(Number);
  var indyb = (svg.getAttribute("data-indy") || "").split(" ").map(Number);
  var detb = (svg.getAttribute("data-det") || "").split(" ").map(Number);
  var ohb = (svg.getAttribute("data-oh") || "").split(" ").map(Number);
  var phxb = (svg.getAttribute("data-phx") || "").split(" ").map(Number);
  var lvb = (svg.getAttribute("data-lv") || "").split(" ").map(Number);
  var rnb = (svg.getAttribute("data-reno") || "").split(" ").map(Number);
  var bob = (svg.getAttribute("data-boi") || "").split(" ").map(Number);
  var seb = (svg.getAttribute("data-sea") || "").split(" ").map(Number);
  var pdb = (svg.getAttribute("data-pdx") || "").split(" ").map(Number);
  var bab = (svg.getAttribute("data-bay") || "").split(" ").map(Number);
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
    // Labels: show each one only where it fits on screen without overlapping a label already placed
    // or another city's dot, and stays inside the map box. Try the right side of the dot first, then the left; hide it if neither is clear.
    var sr = svg.getBoundingClientRect(), placed = [], dotBoxes = dots.map(function (c) { return { el: c, r: c.getBoundingClientRect() }; });
    function clear(r, own) {
      if (r.left < sr.left || r.right > sr.right || r.top < sr.top || r.bottom > sr.bottom) return false;
      return !placed.some(function (q) {
        return r.left < q.right + 4 && r.right + 4 > q.left && r.top < q.bottom && r.bottom > q.top;
      }) && !dotBoxes.some(function (d) {
        return d.el !== own && r.left < d.r.right && r.right > d.r.left && r.top < d.r.bottom && r.bottom > d.r.top;
      });
    }
    labels.forEach(function (t) {
      t.style.display = "none";
      if (parseFloat(t.getAttribute("data-gap")) * p < MIN_GAP_PX) return;
      var own = t.parentNode.querySelector(".dot"), x = parseFloat(t.getAttribute("data-x")), off = (DOT_PX + 3) * u;
      t.setAttribute("font-size", (FONT_PX * u).toFixed(4));
      t.setAttribute("y", (parseFloat(t.getAttribute("data-y")) + 4 * u).toFixed(4));
      t.style.strokeWidth = (3 * u).toFixed(4);
      t.style.display = "";
      var ok = [1, -1].some(function (side) {
        t.setAttribute("x", (x + side * off).toFixed(4));
        t.setAttribute("text-anchor", side > 0 ? "start" : "end");
        var r = t.getBoundingClientRect();
        if (clear(r, own)) { placed.push(r); return true; }
        return false;
      });
      if (!ok) t.style.display = "none";
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
    else if (a === "ut" && utb.length === 4) fit(utb[0], utb[1], utb[2], utb[3]);
    else if (a === "metro" && mb.length === 4) fit(mb[0], mb[1], mb[2], mb[3]);
    else if (a === "slc" && slb.length === 4) fit(slb[0], slb[1], slb[2], slb[3]);
    else if (a === "ne" && neb.length === 4) fit(neb[0], neb[1], neb[2], neb[3]);
    else if (a === "omaha" && omb.length === 4) fit(omb[0], omb[1], omb[2], omb[3]);
    else if (a === "ks" && ksb.length === 4) fit(ksb[0], ksb[1], ksb[2], ksb[3]);
    else if (a === "kc" && kcb.length === 4) fit(kcb[0], kcb[1], kcb[2], kcb[3]);
    else if (a === "nm" && nmb.length === 4) fit(nmb[0], nmb[1], nmb[2], nmb[3]);
    else if (a === "az" && azb.length === 4) fit(azb[0], azb[1], azb[2], azb[3]);
    else if (a === "sd" && sdb.length === 4) fit(sdb[0], sdb[1], sdb[2], sdb[3]);
    else if (a === "nd" && ndb.length === 4) fit(ndb[0], ndb[1], ndb[2], ndb[3]);
    else if (a === "mt" && mtb.length === 4) fit(mtb[0], mtb[1], mtb[2], mtb[3]);
    else if (a === "nv" && nvb.length === 4) fit(nvb[0], nvb[1], nvb[2], nvb[3]);
    else if (a === "id" && idb.length === 4) fit(idb[0], idb[1], idb[2], idb[3]);
    else if (a === "wa" && wab.length === 4) fit(wab[0], wab[1], wab[2], wab[3]);
    else if (a === "or" && orb.length === 4) fit(orb[0], orb[1], orb[2], orb[3]);
    else if (a === "ca" && cab.length === 4) fit(cab[0], cab[1], cab[2], cab[3]);
    else if (a === "ok" && okb.length === 4) fit(okb[0], okb[1], okb[2], okb[3]);
    else if (a === "tx" && txb.length === 4) fit(txb[0], txb[1], txb[2], txb[3]);
    else if (a === "mn" && mnb.length === 4) fit(mnb[0], mnb[1], mnb[2], mnb[3]);
    else if (a === "ia" && iab.length === 4) fit(iab[0], iab[1], iab[2], iab[3]);
    else if (a === "mo" && mob.length === 4) fit(mob[0], mob[1], mob[2], mob[3]);
    else if (a === "ar" && arb.length === 4) fit(arb[0], arb[1], arb[2], arb[3]);
    else if (a === "dfw" && dfb.length === 4) fit(dfb[0], dfb[1], dfb[2], dfb[3]);
    else if (a === "atx" && atb.length === 4) fit(atb[0], atb[1], atb[2], atb[3]);
    else if (a === "nwa" && nwb.length === 4) fit(nwb[0], nwb[1], nwb[2], nwb[3]);
    else if (a === "la" && lab.length === 4) fit(lab[0], lab[1], lab[2], lab[3]);
    else if (a === "swla" && swb.length === 4) fit(swb[0], swb[1], swb[2], swb[3]);
    else if (a === "wi" && wib.length === 4) fit(wib[0], wib[1], wib[2], wib[3]);
    else if (a === "sewi" && sewb.length === 4) fit(sewb[0], sewb[1], sewb[2], sewb[3]);
    else if (a === "il" && ilb.length === 4) fit(ilb[0], ilb[1], ilb[2], ilb[3]);
    else if (a === "chi" && chib.length === 4) fit(chib[0], chib[1], chib[2], chib[3]);
    else if (a === "ms" && msb.length === 4) fit(msb[0], msb[1], msb[2], msb[3]);
    else if (a === "tn" && tnb.length === 4) fit(tnb[0], tnb[1], tnb[2], tnb[3]);
    else if (a === "mem" && memb.length === 4) fit(memb[0], memb[1], memb[2], memb[3]);
    else if (a === "ky" && kyb.length === 4) fit(kyb[0], kyb[1], kyb[2], kyb[3]);
    else if (a === "al" && alb.length === 4) fit(alb[0], alb[1], alb[2], alb[3]);
    else if (a === "ind" && inb.length === 4) fit(inb[0], inb[1], inb[2], inb[3]);
    else if (a === "mi" && mib.length === 4) fit(mib[0], mib[1], mib[2], mib[3]);
    else if (a === "indy" && indyb.length === 4) fit(indyb[0], indyb[1], indyb[2], indyb[3]);
    else if (a === "det" && detb.length === 4) fit(detb[0], detb[1], detb[2], detb[3]);
    else if (a === "oh" && ohb.length === 4) fit(ohb[0], ohb[1], ohb[2], ohb[3]);
    else if (a === "phx" && phxb.length === 4) fit(phxb[0], phxb[1], phxb[2], phxb[3]);
    else if (a === "lv" && lvb.length === 4) fit(lvb[0], lvb[1], lvb[2], lvb[3]);
    else if (a === "reno" && rnb.length === 4) fit(rnb[0], rnb[1], rnb[2], rnb[3]);
    else if (a === "boi" && bob.length === 4) fit(bob[0], bob[1], bob[2], bob[3]);
    else if (a === "sea" && seb.length === 4) fit(seb[0], seb[1], seb[2], seb[3]);
    else if (a === "pdx" && pdb.length === 4) fit(pdb[0], pdb[1], pdb[2], pdb[3]);
    else if (a === "bay" && bab.length === 4) fit(bab[0], bab[1], bab[2], bab[3]);
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
