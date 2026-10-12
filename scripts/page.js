(function () {
  var FIELDS = [
    { id: 'all', label: 'All fields' },
    { id: 'humanities', label: 'Humanities and social sciences' },
    { id: 'health', label: 'Health and biological sciences' },
    { id: 'physical', label: 'Physical sciences and engineering' },
    { id: 'environment', label: 'Environment, climate and agriculture' },
    { id: 'any', label: 'Open to any discipline' }
  ];
  var FIELD_NAME = {};
  FIELDS.forEach(function (f) { FIELD_NAME[f.id] = f.label; });
  var SCOPE_NAME = { kenya: 'Kenya', international: 'International' };

  var G = [];
  var TODAY = new Date();
  var MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

  function endOf(d) { return new Date(d + 'T23:59:00+03:00'); }
  function fmt(d) { var p = d.split('-'); return parseInt(p[2], 10) + ' ' + MONTHS[parseInt(p[1], 10) - 1] + ' ' + p[0]; }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }

  var field = 'all';
  var fieldsEl = document.getElementById('fields');
  var ledger = document.getElementById('ledger');
  var qEl = document.getElementById('q');
  var statusEl = document.getElementById('status');
  var scopeEl = document.getElementById('scope');
  var summaryEl = document.getElementById('summary');

  function prepare() {
    G.forEach(function (g) {
      g.cats = g.cats && g.cats.length ? g.cats : ['any'];
      if (!g.deadline) { g.state = 'check'; g.days = null; return; }
      var end = endOf(g.deadline);
      var days = Math.ceil((end - TODAY) / 86400000);
      g.days = days;
      g.state = end < TODAY ? 'closed' : (days <= 14 ? 'soon' : 'open');
    });
    var ORDER = { soon: 0, open: 0, check: 1, closed: 2 };
    G.sort(function (a, b) {
      if (ORDER[a.state] !== ORDER[b.state]) return ORDER[a.state] - ORDER[b.state];
      if (a.state === 'closed') return b.deadline < a.deadline ? -1 : 1;
      if (a.state === 'check') return a.title < b.title ? -1 : 1;
      return a.deadline < b.deadline ? -1 : 1;
    });
  }

  function inField(g, f) {
    if (f === 'all') return true;
    if (f === 'any') return g.cats.indexOf('any') > -1;
    return g.cats.indexOf(f) > -1 || g.cats.indexOf('any') > -1;
  }
  function inScope(g) { return scopeEl.value === 'all' || g.scope === scopeEl.value; }

  function buildIndex() {
    fieldsEl.innerHTML = '';
    FIELDS.forEach(function (f) {
      var n = G.filter(function (g) { return inScope(g) && inField(g, f.id) && g.state !== 'closed'; }).length;
      var li = document.createElement('li');
      var b = document.createElement('button');
      b.type = 'button';
      b.setAttribute('aria-pressed', f.id === field ? 'true' : 'false');
      b.innerHTML = '<span>' + esc(f.label) + '</span><span class="n" title="Not yet closed">' + n + '</span>';
      b.addEventListener('click', function () { field = f.id; buildIndex(); render(); });
      li.appendChild(b);
      fieldsEl.appendChild(li);
    });
    document.getElementById('field-hint').textContent = (field === 'any' || field === 'all' ? '' : 'Includes grants open to any discipline. ') + 'Numbers count grants that have not closed yet.';
  }

  function whenBlock(g) {
    var label = { open: 'Open', soon: 'Closing soon', closed: 'Closed', check: 'Date not published' }[g.state];
    var date = g.deadline ? fmt(g.deadline) : 'Check funder';
    var rel = '';
    if (g.state === 'open' || g.state === 'soon') rel = g.days <= 0 ? 'Closes today' : (g.days === 1 ? '1 day left' : g.days + ' days left');
    if (g.state === 'closed') rel = 'Deadline passed';
    return '<div class="when"><span class="pill ' + g.state + '">' + label + '</span><span class="date">' + esc(date) + '</span>' + (rel ? '<span class="rel">' + rel + '</span>' : '') + '</div>';
  }

  function safeUrl(u) { return /^https?:\/\//i.test(u || '') ? u : '#'; }

  function rowHtml(g) {
    var tags = '<span class="w">' + esc(SCOPE_NAME[g.scope] || 'International') + '</span><span>' + esc(g.type) + '</span>' +
      g.cats.map(function (c) { return '<span class="c">' + esc(FIELD_NAME[c] || c) + '</span>'; }).join('') +
      (g.auto ? '<span class="auto">Auto-found, unchecked</span>' : '');
    return '<li class="row' + (g.state === 'closed' ? ' is-closed' : '') + '">' +
      whenBlock(g) +
      '<div class="body">' +
        '<div class="tags">' + tags + '</div>' +
        '<h3>' + esc(g.title) + '</h3>' +
        '<p class="funder">' + esc(g.funder) + '</p>' +
        '<p class="sum">' + esc(g.summary) + '</p>' +
        '<dl class="facts"><div><dt>Award</dt><dd>' + esc(g.amount) + '</dd></div><div><dt>Who can apply</dt><dd>' + esc(g.who) + '</dd></div></dl>' +
        '<p class="note"><b>Before you apply</b>' + esc(g.note) + '</p>' +
        '<div class="foot"><a class="go" href="' + esc(safeUrl(g.url)) + '" target="_blank" rel="noopener noreferrer">Funder page</a><span class="src">Read from: ' + esc(g.src) + '</span></div>' +
      '</div></li>';
  }

  function render() {
    var q = qEl.value.trim().toLowerCase();
    var st = statusEl.value;
    var list = G.filter(function (g) {
      if (!inField(g, field) || !inScope(g)) return false;
      if (st === 'live' && !(g.state === 'open' || g.state === 'soon')) return false;
      if (st === 'soon' && g.state !== 'soon') return false;
      if (st === 'check' && g.state !== 'check') return false;
      if (st === 'closed' && g.state !== 'closed') return false;
      if (q) {
        var hay = (g.title + ' ' + g.funder + ' ' + g.summary + ' ' + g.who + ' ' + g.type + ' ' + (SCOPE_NAME[g.scope] || '')).toLowerCase();
        return q.split(/\s+/).every(function (w) { return hay.indexOf(w) > -1; });
      }
      return true;
    });
    ledger.innerHTML = list.length ? list.map(rowHtml).join('') : '<li class="empty">No grants match. Clear the search or change the filters.</li>';
    var open = list.filter(function (g) { return g.state === 'open' || g.state === 'soon'; }).length;
    var soon = list.filter(function (g) { return g.state === 'soon'; }).length;
    var chk = list.filter(function (g) { return g.state === 'check'; }).length;
    var cl = list.filter(function (g) { return g.state === 'closed'; }).length;
    summaryEl.innerHTML = '<span><b>' + list.length + '</b> shown</span><span><b>' + open + '</b> open</span><span><b>' + soon + '</b> closing within 14 days</span><span><b>' + chk + '</b> date not published</span><span><b>' + cl + '</b> closed</span>';
  }

  function init(data) {
    G = (data && data.grants) || [];
    prepare();
    var totalOpen = G.filter(function (g) { return g.state === 'open' || g.state === 'soon'; }).length;
    var autoN = G.filter(function (g) { return g.auto; }).length;
    var upd = '';
    try { upd = new Date(data.updated).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'Africa/Nairobi' }); } catch (e) { upd = ''; }
    document.getElementById('checked').textContent = upd || 'recently';
    document.getElementById('count-line').textContent = G.length + ' entries, ' + totalOpen + ' open' + (autoN ? ', ' + autoN + ' auto-found' : '');
    qEl.addEventListener('input', render);
    statusEl.addEventListener('change', render);
    scopeEl.addEventListener('change', function () { buildIndex(); render(); });
    buildIndex();
    render();
  }

  function fail() {
    ledger.innerHTML = '<li class="empty">The grants list could not be loaded. If you opened this file directly from your computer, publish it on GitHub Pages or run <code>python -m http.server</code> in this folder and open the address it prints.</li>';
    summaryEl.textContent = '';
  }

  fetch('data/grants.json', { cache: 'no-cache' })
    .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
    .then(init)
    .catch(fail);
})();
