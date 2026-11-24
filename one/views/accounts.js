/* Accounts view: list + slide-in detail with relationship graph. Synthetic data, fictional companies and people. */
(function () {
  var ACC = [
    { n: 'RelayOps', emp: 42, fit: 91, ready: 'High', sig: 6, rel: 'Warm path via customer' },
    { n: 'Vellum Labs', emp: 65, fit: 86, ready: 'High', sig: 5, rel: 'Investor overlap' },
    { n: 'Quanta AI', emp: 31, fit: 82, ready: 'Medium', sig: 4, rel: 'Event attendee' },
    { n: 'Stackline', emp: 120, fit: 88, ready: 'Customer', sig: 3, rel: 'Existing customer' },
    { n: 'Northpine', emp: 210, fit: 74, ready: 'Medium', sig: 3, rel: 'Cold' },
    { n: 'Glyph Systems', emp: 54, fit: 79, ready: 'Medium', sig: 4, rel: 'Former user' },
    { n: 'Ardent AI', emp: 23, fit: 71, ready: 'Low', sig: 2, rel: 'Cold' },
    { n: 'Kepler Ops', emp: 88, fit: 77, ready: 'High', sig: 5, rel: 'Referral partner' }
  ];
  var merged = false, introAsked = {};
  var tagFor = function (r) { return r === 'High' ? 'good' : r === 'Low' ? 'bad' : r === 'Customer' ? 'info' : 'warn'; };

  function graph() {
    var N = [
      { id: 'tl', x: 60, y: 90, t: 'TraceLayer' },
      { id: 'mira', x: 210, y: 40, t: 'Mira Chen', s: 'Stackline, customer' },
      { id: 'priya', x: 370, y: 90, t: 'Priya Rao', s: 'RelayOps, VP Eng' },
      { id: 'lumen', x: 210, y: 150, t: 'Lumen Ventures', s: 'investor in both' }
    ];
    var P = {}; N.forEach(function (n) { P[n.id] = n; });
    var E = [['tl', 'mira', 1, 'customer'], ['mira', 'priya', 1, 'knows'], ['tl', 'lumen', 0, ''], ['lumen', 'priya', 0, '']];
    var s = '<svg viewBox="0 0 440 190" width="100%" role="img" aria-label="Warm intro path from TraceLayer through Mira Chen to Priya Rao">';
    E.forEach(function (e) {
      var a = P[e[0]], b = P[e[1]];
      s += '<line x1="' + a.x + '" y1="' + a.y + '" x2="' + b.x + '" y2="' + b.y + '" stroke="' + (e[2] ? 'var(--course)' : 'var(--rule)') +
        '" stroke-width="' + (e[2] ? 3 : 1.5) + '"' + (e[2] ? '' : ' stroke-dasharray="4 4"') + '/>';
      if (e[3]) s += '<text x="' + (a.x + b.x) / 2 + '" y="' + ((a.y + b.y) / 2 - 6) + '" text-anchor="middle" style="font:italic 600 12px var(--chart);fill:var(--course)">' + e[3] + '</text>';
    });
    N.forEach(function (n) {
      var hot = n.id !== 'lumen';
      s += '<circle cx="' + n.x + '" cy="' + n.y + '" r="7" fill="' + (hot ? 'var(--course)' : 'var(--paper)') + '" stroke="' + (hot ? 'var(--course)' : 'var(--muted)') + '" stroke-width="1.5"/>' +
        '<text x="' + n.x + '" y="' + (n.y + 22) + '" text-anchor="middle" style="font:600 13px var(--ui);fill:var(--ink)">' + n.t + '</text>' +
        (n.s ? '<text x="' + n.x + '" y="' + (n.y + 36) + '" text-anchor="middle" style="font:italic 12px var(--chart);fill:var(--muted)">' + n.s + '</text>' : '');
    });
    return s + '</svg>';
  }

  function detail(a) {
    var isRelay = a.n === 'RelayOps';
    var people = isRelay
      ? [['Priya Rao', 'VP Engineering', 'buyer'], ['Sam Okafor', 'Staff ML Engineer', 'champion'], ['Lumen Ventures', 'Seed lead', 'investor'], ['Mira Chen', 'Stackline, Head of Platform', 'referral partner']]
      : [['Head of Engineering', 'unnamed', 'buyer'], ['Senior ML Engineer', 'unnamed', 'champion']];
    var hist = isRelay
      ? ['Oct 02 Priya attended TraceLayer webinar (Luma)', 'Oct 19 Sam opened pricing page twice', 'Nov 08 Mira mentioned RelayOps on a QBR call']
      : ['No logged touches yet. Discovery Agent is enriching.'];
    return '<button class="btn acc-x" data-close>Close</button>' +
      '<h2 style="font-size:28px;margin:10px 0 4px">' + a.n + '</h2>' +
      '<p class="muted">' + a.emp + ' employees. ICP fit ' + a.fit + '. Readiness ' + a.ready + '. Synthetic profile.</p>' +
      '<h3>People</h3><table class="tbl">' + people.map(function (p) { return '<tr><td><strong>' + p[0] + '</strong><br><span class="muted">' + p[1] + '</span></td><td><span class="tag info">' + p[2] + '</span></td></tr>'; }).join('') + '</table>' +
      '<h3>Relationship history</h3><ul>' + hist.map(function (h) { return '<li>' + h + '</li>'; }).join('') + '</ul>' +
      (isRelay ? '<h3>Warm intro path</h3>' + graph() : '') +
      '<div class="acc-dup">' + (merged
        ? '<span class="fixmark good">Merged</span> Priya Rao is one record across CRM, Luma and Gmail.'
        : '<span class="fixmark bad">Possible duplicate</span> Priya Rao appears in CRM, Luma and Gmail as 3 records (p.rao@, priya@, priya.rao@relayops.example). <button class="btn" data-merge>Merge</button>') + '</div>' +
      '<p style="margin-top:18px"><button class="btn go" data-intro>' + (introAsked[a.n] ? 'Intro requested' : 'Request warm intro') + '</button></p>';
  }

  ONE.view('accounts', {
    title: 'Accounts',
    render: function (el, ctx) {
      el.innerHTML =
        '<style>' +
        '.acc-row{cursor:pointer}.acc-row:hover td,.acc-row.on td{background:color-mix(in srgb,var(--course) 6%,transparent)}' +
        '.acc-panel{position:fixed;top:0;right:0;bottom:0;width:min(480px,100vw);background:var(--paper);border-left:1px solid var(--rule);padding:24px 20px;overflow:auto;transform:translateX(100%);transition:transform .35s var(--ease);z-index:40}' +
        '.acc-panel.open{transform:translateX(0)}.acc-panel h3{font-size:15px;margin:20px 0 6px;border-top:1px solid var(--rule);padding-top:12px}' +
        '.acc-dup{margin-top:18px;border-top:1px solid var(--rule);padding-top:12px;line-height:1.6}' +
        '</style><div class="page"><h1>Every person can be more than a lead</h1>' +
        '<p class="lede">Buyers, champions, investors and customers are one graph. Click an account to see who can open the door. Fictional companies, synthetic data.</p>' +
        '<table class="tbl"><thead><tr><th>Account</th><th>Fit</th><th>Readiness</th><th>Signals</th><th>Relationship</th></tr></thead><tbody>' +
        ACC.map(function (a, i) {
          return '<tr class="acc-row" data-i="' + i + '" tabindex="0"><td><strong>' + a.n + '</strong> <span class="muted">' + a.emp + ' people</span></td><td>' + a.fit +
            '</td><td><span class="tag ' + tagFor(a.ready) + '">' + a.ready + '</span></td><td>' + a.sig + '</td><td>' + a.rel + '</td></tr>';
        }).join('') + '</tbody></table></div><aside class="acc-panel" aria-label="Account detail"></aside>';

      var panel = el.querySelector('.acc-panel'), open = null;
      function show(i) {
        open = i;
        el.querySelectorAll('.acc-row').forEach(function (r) { r.classList.toggle('on', +r.dataset.i === i); });
        panel.innerHTML = detail(ACC[i]);
        requestAnimationFrame(function () { panel.classList.add('open'); });
      }
      el.querySelectorAll('.acc-row').forEach(function (r) {
        r.onclick = function () { show(+r.dataset.i); };
        r.onkeydown = function (e) { if (e.key === 'Enter') show(+r.dataset.i); };
      });
      panel.onclick = function (e) {
        var t = e.target;
        if (t.closest('[data-close]')) { panel.classList.remove('open'); el.querySelectorAll('.acc-row').forEach(function (r) { r.classList.remove('on'); }); open = null; }
        else if (t.closest('[data-merge]')) { merged = true; show(open); ctx.toast('Merged 3 records into one person'); ctx.feed('Relationship Agent', 'Merged Priya Rao across CRM, Luma and Gmail. History now complete.', 'done'); }
        else if (t.closest('[data-intro]')) {
          var a = ACC[open];
          if (introAsked[a.n]) { ctx.toast('Intro already requested for ' + a.n); return; }
          introAsked[a.n] = true; show(open);
          ctx.toast('Warm intro requested for ' + a.n);
          ctx.feed('Relationship Agent', a.n === 'RelayOps' ? 'Drafted ask to Mira Chen (Stackline) for an intro to Priya Rao. Awaiting your approval.' : 'Looking for a warm path into ' + a.n + '.', 'find');
        }
      };
    }
  });
})();
