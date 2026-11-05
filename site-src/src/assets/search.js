/* Errand Desk site search. Runs only on /search/, which fetches the index
   after the form is submitted. No dependencies. Rank and tokenize stay aligned
   with site-src/searchindex.py (STOP_LIST is checked by tools/test_search.py). */
(function (root, factory) {
  var api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (typeof document !== "undefined") api.attach(document);
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";
  var TITLE = 1, URL = 2, DESC = 4, BODY = 8;
  var STOP_LIST = [
    "a", "about", "above", "after", "again", "all", "also", "am", "an", "and", "any",
    "are", "as", "at", "be", "because", "been", "before", "below", "between", "both",
    "but", "by", "did", "do", "does", "during", "each", "few", "for", "from", "further",
    "had", "has", "have", "having", "he", "her", "here", "hers", "him", "his", "how",
    "i", "if", "in", "into", "is", "it", "its", "itself", "just", "me", "more", "most",
    "my", "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other", "our",
    "out", "over", "own", "per", "same", "she", "so", "some", "such", "than", "that",
    "the", "their", "them", "then", "there", "these", "they", "this", "those", "through",
    "to", "too", "under", "until", "up", "very", "was", "we", "were", "what", "when",
    "where", "which", "while", "who", "whom", "why", "with", "you", "your"
  ];
  var STOP = Object.create(null);
  STOP_LIST.forEach(function (w) { STOP[w] = 1; });

  function tokenize(text) {
    var t = String(text || "").toLowerCase().replace(/['’]/g, "");
    return t.match(/[a-z0-9]+/g) || [];
  }

  function termsOf(query) {
    var seen = Object.create(null), out = [];
    tokenize(query).forEach(function (tok) {
      if (tok.length < 2 || STOP[tok] || seen[tok]) return;
      seen[tok] = 1;
      out.push(tok);
    });
    return out.slice(0, 8);
  }

  function lookupKeys(term) {
    var keys = Object.create(null);
    function add(k) { if (k && k.length > 1) keys[k] = 1; }
    add(term);
    if (term.length > 4 && term.slice(-3) === "ing") {
      var ing = term.slice(0, -3);
      add(ing);
      if (ing.length > 3 && ing.charAt(ing.length - 1) === ing.charAt(ing.length - 2)) add(ing.slice(0, -1));
    }
    if (term.length > 3 && term.slice(-2) === "ed") {
      var ed = term.slice(0, -2);
      add(ed);
      if (ed.length > 3 && ed.charAt(ed.length - 1) === ed.charAt(ed.length - 2)) add(ed.slice(0, -1));
    }
    if (term.length > 4 && term.slice(-3) === "ies") add(term.slice(0, -3) + "y");
    if (term.length > 3 && term.slice(-2) === "es") add(term.slice(0, -2));
    if (term.length > 3 && term.slice(-1) === "s" && term.slice(-2) !== "ss") add(term.slice(0, -1));
    add(term + "s");
    add(term + "es");
    if (term.length > 3 && term.slice(-1) === "y") add(term.slice(0, -1) + "ies");
    add(term + "ed");
    add(term + "ing");
    if (term.length > 2) {
      var last = term.charAt(term.length - 1);
      if ("aeiou".indexOf(last) === -1) {
        add(term + last + "ing");
        add(term + last + "ed");
      }
    }
    return Object.keys(keys);
  }

  function eqLoose(a, b) {
    if (a === b) return "exact";
    var keys = lookupKeys(a);
    for (var i = 0; i < keys.length; i++) if (keys[i] === b) return "stem";
    return "";
  }

  function hitsFor(post, term) {
    var map = new Map();
    lookupKeys(term).forEach(function (key) {
      var list = post[key];
      if (!list) return;
      var exact = key === term;
      for (var i = 0; i < list.length; i++) {
        var n = list[i];
        var id = Math.floor(n / 16);
        var flags = n % 16;
        var cur = map.get(id);
        if (!cur) cur = {flags: 0, exact: 0};
        cur.flags |= flags;
        if (exact) cur.exact |= flags;
        map.set(id, cur);
      }
    });
    return map;
  }

  function scoreFlags(exact, flags) {
    var s = 0;
    if (flags & TITLE) s += (exact & TITLE) ? 40 : 24;
    if (flags & URL) s += (exact & URL) ? 80 : 48;
    if (flags & DESC) s += (exact & DESC) ? 14 : 8;
    if (flags & BODY) s += (exact & BODY) ? 6 : 3;
    return s;
  }

  function matchPhrase(parts, terms) {
    if (!parts.length || parts.length < terms.length) return "";
    var best = "";
    for (var i = 0; i <= parts.length - terms.length; i++) {
      var exact = true, ok = true;
      for (var j = 0; j < terms.length; j++) {
        var eq = eqLoose(terms[j], parts[i + j]);
        if (!eq) { ok = false; break; }
        if (eq !== "exact") exact = false;
      }
      if (ok) {
        if (exact) return "exact";
        best = "stem";
      }
    }
    return best;
  }

  function slugBonus(url, terms) {
    var slug = String(url || "").replace(/^\/+|\/+$/g, "");
    if (!slug || !terms.length) return 0;
    var last = slug.split("/").pop();
    var parts = last.split("-").filter(Boolean);
    var bonus = 0;
    var phrase = matchPhrase(parts, terms);
    if (phrase === "exact") bonus += 45;
    else if (phrase === "stem") bonus += 28;
    // /kansas-city/ outranks /kansas-city-mo/ for "kansas city", and /portland/ outranks /portland-me/.
    if (phrase && parts.length === terms.length) bonus += 22;
    if (terms.length === 1) {
      var term = terms[0];
      if (last === term || last.indexOf(term + "-") === 0) bonus += 24;
      else if (eqLoose(term, last) === "stem") bonus += 14;
    }
    return bonus;
  }

  function findTerm(low, term, from) {
    var keys = lookupKeys(term);
    var best = -1;
    for (var k = 0; k < keys.length; k++) {
      var needle = keys[k];
      var at = from;
      while (at <= low.length) {
        var i = low.indexOf(needle, at);
        if (i < 0) break;
        var before = i === 0 ? "" : low.charAt(i - 1);
        var after = low.charAt(i + needle.length);
        var edge = !/[a-z0-9]/.test(before) && !/[a-z0-9]/.test(after || "");
        if (edge) {
          if (best < 0 || i < best) best = i;
          break;
        }
        at = i + 1;
      }
    }
    return best;
  }

  function phraseIn(text, terms) {
    if (!text || terms.length < 2) return false;
    var low = text.toLowerCase();
    var from = 0;
    var prevEnd = 0;
    for (var i = 0; i < terms.length; i++) {
      var at = findTerm(low, terms[i], from);
      if (at < 0) return false;
      if (i > 0 && at - prevEnd > 24) return false;
      var end = at;
      while (end < low.length && /[a-z0-9]/.test(low.charAt(end))) end++;
      prevEnd = end;
      from = end;
    }
    return true;
  }

  function safeUrl(u) {
    if (typeof u !== "string") return "";
    if (u === "/") return "/";
    if (!/^\/[a-z0-9./-]+$/.test(u)) return "";
    if (u.indexOf("//") !== -1 || u.charAt(u.length - 1) !== "/") return "";
    var parts = u.split("/");
    for (var i = 0; i < parts.length; i++) {
      if (parts[i] === "." || parts[i] === "..") return "";
    }
    return u;
  }

  function highlight(text, terms) {
    var parts = [];
    var re = /[A-Za-z0-9]+|[^A-Za-z0-9]+/g;
    var m;
    while ((m = re.exec(text))) {
      var chunk = m[0];
      var mark = false;
      if (/^[A-Za-z0-9]+$/.test(chunk)) {
        var low = chunk.toLowerCase();
        for (var i = 0; i < terms.length; i++) {
          if (eqLoose(terms[i], low)) { mark = true; break; }
        }
      }
      var prev = parts[parts.length - 1];
      if (prev && prev.m === mark) prev.t += chunk;
      else parts.push({t: chunk, m: mark});
    }
    return parts;
  }

  function snippetParts(doc, terms) {
    var text = [doc.t, doc.d, doc.x].filter(Boolean).join(" \u2014 ");
    text = text.replace(/\s+/g, " ").trim();
    if (!text) return [];
    var windowLen = 180;
    var low = text.toLowerCase();
    var occ = [];
    terms.forEach(function (term) {
      var from = 0;
      while (from < low.length) {
        var at = findTerm(low, term, from);
        if (at < 0) break;
        var end = at;
        while (end < low.length && /[a-z0-9]/.test(low.charAt(end))) end++;
        occ.push({start: at, end: end, term: term});
        from = end;
      }
    });
    var start = 0;
    var end = Math.min(text.length, windowLen);
    if (occ.length) {
      var bestStart = 0, best = -1, bestAt = 1e9;
      for (var s = 0; s < occ.length; s++) {
        var cand = Math.max(0, occ[s].start - 50);
        var candEnd = Math.min(text.length, cand + windowLen);
        var seen = Object.create(null), n = 0, first = 1e9;
        for (var i = 0; i < occ.length; i++) {
          if (occ[i].start >= cand && occ[i].end <= candEnd + 12) {
            if (!seen[occ[i].term]) { seen[occ[i].term] = 1; n++; }
            if (occ[i].start < first) first = occ[i].start;
          }
        }
        if (n > best || (n === best && first < bestAt)) {
          best = n;
          bestAt = first;
          bestStart = cand;
        }
      }
      start = bestStart;
      end = Math.min(text.length, start + windowLen);
    }
    if (start > 0) {
      var sp = text.lastIndexOf(" ", start + 16);
      if (sp >= start - 24 && sp !== -1) start = sp + 1;
    }
    if (end < text.length) {
      var sp2 = text.lastIndexOf(" ", end);
      if (sp2 > start + 40) end = sp2;
    }
    var slice = text.slice(start, end).trim();
    var shown = (start > 0 ? "\u2026" : "") + slice + (end < text.length ? "\u2026" : "");
    return highlight(shown, terms);
  }

  function search(index, query) {
    var trimmed = String(query || "").replace(/\s+/g, " ").trim();
    if (trimmed.length > 200) trimmed = trimmed.slice(0, 200);
    if (!trimmed) return {kind: "empty", query: "", total: 0, results: []};
    var terms = termsOf(trimmed);
    if (!terms.length) return {kind: "vague", query: trimmed, total: 0, results: []};
    if (!index || !index.post || !Array.isArray(index.docs)) {
      return {kind: "error", query: trimmed, total: 0, results: []};
    }
    var perTerm = terms.map(function (term) { return hitsFor(index.post, term); });
    var ids = null;
    for (var t = 0; t < perTerm.length; t++) {
      var keys = new Set(perTerm[t].keys());
      if (ids === null) ids = keys;
      else {
        var next = new Set();
        ids.forEach(function (id) { if (keys.has(id)) next.add(id); });
        ids = next;
      }
    }
    var ranked = [];
    ids.forEach(function (id) {
      var doc = index.docs[id];
      if (!doc) return;
      var url = safeUrl(doc.u);
      if (!url) return;
      var score = slugBonus(url, terms);
      for (var i = 0; i < perTerm.length; i++) {
        var hit = perTerm[i].get(id);
        score += scoreFlags(hit.exact, hit.flags);
      }
      if (phraseIn(doc.t, terms)) score += 18;
      if (phraseIn(doc.d || "", terms)) score += 10;
      ranked.push({
        url: url,
        title: doc.t || url,
        score: score,
        parts: snippetParts(doc, terms)
      });
    });
    ranked.sort(function (a, b) {
      if (b.score !== a.score) return b.score - a.score;
      return a.url < b.url ? -1 : a.url > b.url ? 1 : 0;
    });
    if (!ranked.length) return {kind: "none", query: trimmed, total: 0, results: [], terms: terms};
    return {kind: "hit", query: trimmed, total: ranked.length, results: ranked.slice(0, 30), terms: terms};
  }

  function appendText(doc, parent, text) {
    parent.appendChild(doc.createTextNode(text));
  }

  function addLink(doc, parent, href, label) {
    var a = doc.createElement("a");
    a.setAttribute("href", href);
    a.textContent = label;
    parent.appendChild(a);
  }

  function render(doc, status, list, outcome) {
    list.replaceChildren();
    status.replaceChildren();
    if (outcome.kind === "empty") {
      appendText(doc, status, "Enter a word or phrase, then choose Search.");
      return;
    }
    if (outcome.kind === "vague") {
      appendText(doc, status, "Enter a more specific search, such as a city name or a topic like notary or fax.");
      return;
    }
    if (outcome.kind === "error") {
      appendText(doc, status, "The search index could not be loaded. Check your connection and try again, or browse the ");
      addLink(doc, status, "/guides/", "guides");
      appendText(doc, status, " and the ");
      addLink(doc, status, "/map/", "map");
      appendText(doc, status, ".");
      return;
    }
    if (outcome.kind === "none") {
      appendText(doc, status, "No pages matched \u201c" + outcome.query + "\u201d. Try a city name or a topic such as fax, notary or passport photos.");
      return;
    }
    var shown = outcome.results.length;
    var total = outcome.total;
    var noun = total === 1 ? "page" : "pages";
    var lead = shown < total ? ("Showing " + shown + " of " + total + " " + noun) : (total + " " + noun);
    appendText(doc, status, lead + " for \u201c" + outcome.query + "\u201d.");
    outcome.results.forEach(function (hit) {
      var li = doc.createElement("li");
      var a = doc.createElement("a");
      a.setAttribute("href", hit.url);
      var title = doc.createElement("span");
      title.className = "search-title";
      title.textContent = hit.title;
      var url = doc.createElement("span");
      url.className = "search-url";
      url.textContent = hit.url;
      a.appendChild(title);
      a.appendChild(url);
      var snip = doc.createElement("p");
      snip.className = "search-snip";
      (hit.parts || []).forEach(function (part) {
        if (part.m) {
          var mark = doc.createElement("mark");
          mark.textContent = part.t;
          snip.appendChild(mark);
        } else {
          appendText(doc, snip, part.t);
        }
      });
      li.appendChild(a);
      li.appendChild(snip);
      list.appendChild(li);
    });
  }

  function attach(doc) {
    var status = doc.getElementById("search-status");
    var list = doc.getElementById("search-results");
    if (!status || !list) return;
    var input = doc.getElementById("q");
    var params = new URLSearchParams(location.search);
    var raw = params.get("q");
    if (raw == null) raw = "";
    if (input) input.value = raw;
    var query = raw.replace(/\s+/g, " ").trim();
    if (query.length > 200) query = query.slice(0, 200);
    if (!query || !termsOf(query).length) {
      render(doc, status, list, search({v: 1, docs: [], post: {}}, query));
      return;
    }
    var holder = doc.querySelector("script[data-index]");
    var indexUrl = holder ? holder.getAttribute("data-index") : "";
    if (!indexUrl || indexUrl.charAt(0) !== "/" || indexUrl.indexOf("//") !== -1) {
      render(doc, status, list, {kind: "error", query: query});
      return;
    }
    status.textContent = "Searching\u2026";
    fetch(indexUrl, {headers: {Accept: "application/json"}})
      .then(function (res) {
        if (!res.ok) throw new Error(String(res.status));
        return res.json();
      })
      .then(function (index) {
        if (!index || index.v !== 1 || !Array.isArray(index.docs) || !index.post) throw new Error("bad index");
        if (typeof index.n === "number" && index.n !== index.docs.length) throw new Error("bad index");
        render(doc, status, list, search(index, query));
      })
      .catch(function () {
        render(doc, status, list, {kind: "error", query: query});
      });
  }

  return {
    STOP_LIST: STOP_LIST,
    tokenize: tokenize,
    termsOf: termsOf,
    safeUrl: safeUrl,
    snippetParts: snippetParts,
    highlight: highlight,
    search: search,
    render: render,
    attach: attach
  };
});
