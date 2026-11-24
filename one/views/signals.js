/* Signals: synthetic market signals for the fictional customer TraceLayer. */
(function () {
  var seq = 0;
  function S(source, what, meaning, rel, conf, flag) {
    seq += 1;
    return { id: 's' + seq, source: source, what: what, meaning: meaning, rel: rel, conf: conf, flag: flag || '', t: Date.now() - seq * 7 * 60000, fresh: false };
  }
  var signals = [
    S('LinkedIn Jobs', 'RelayOps posted 2 GTM engineer roles', 'Buying readiness up: they are staffing the team that would own agent tooling.', 'High', 0.81),
    S('Product Hunt', 'Vellum Labs launched production agents', 'Agents in production need tracing within weeks; strong ICP timing.', 'High', 0.77),
    S('Pricing page change', 'Competitor Spanwise moved upmarket', 'Mid-market teams may be left without a fit; opening for TraceLayer.', 'High', 0.72),
    S('Crunchbase', 'Funding: Quanta AI raised Series A', 'Weak alone. Funding without an agent launch rarely converts.', 'Low', 0.41),
    S('GitHub', 'Northwind AI starred 3 eval frameworks', 'Early evaluation research, likely 1 to 2 quarters out.', 'Medium', 0.58),
    S('Webinar', 'Corvid Systems attended reliability webinar (2 weeks ago)', 'Decaying: no follow-up activity since attendance.', 'Medium', 0.49, 'decaying'),
    S('Call notes', 'Halcyon said "no budget until Q3"', 'Contradictory: same week they posted an MLOps lead role.', 'Medium', 0.52, 'contradictory'),
    S('G2', 'Two reviews cite missing Salesforce sync', 'Matches 7 sales calls asking for Salesforce integration.', 'High', 0.79)
  ];
  var pool = [
    ['Website visit', 'Ferrous Labs viewed pricing 4 times', 'Active evaluation; route to SDR today.', 'High', 0.76],
    ['LinkedIn', 'Pallas AI hired a Head of Platform', 'New leader, new tooling budget in 60 days.', 'Medium', 0.63],
    ['Hacker News', 'Thread on agent outages names 3 target accounts', 'Pain is public; good hook for outreach.', 'Medium', 0.6],
    ['Changelog', 'Competitor Evalkit added cost tracking', 'Parity gap on cost views; flag to Product.', 'High', 0.7],
    ['Crunchbase', 'Orrin Robotics raised seed', 'Too early for TraceLayer; watch only.', 'Low', 0.35],
    ['Event list', 'Kestrel AI registered for the SF dinner', 'Warm touchpoint; pair with AE before the event.', 'High', 0.74]
  ];
  var poolAt = 0, filter = 'All', open = null;

  function ago(t) { var m = Math.max(1, Math.round((Date.now() - t) / 60000)); return m < 60 ? m + 'm ago' : Math.round(m / 60) + 'h ago'; }
  function shown() {
    return signals.filter(function (s) {
      if (filter === 'High') return s.rel === 'High';
      if (filter === 'Contradictory') return s.flag === 'contradictory';
      return true;
    });
  }
  function item(s) {
    var tag = s.flag === 'decaying' ? ' <span class="tag warn">Decaying</span>' :
      s.flag === 'contradictory' ? ' <span class="tag bad">Contradictory</span>' : '';
    var rel = '<span class="tag ' + (s.rel === 'High' ? 'good' : s.rel === 'Low' ? 'bad' : 'info') + '">' + s.rel + '</span>';
    var body = open === s.id
      ? '<div style="padding:8px 0 4px"><p>' + s.meaning + '</p><button class="btn go" data-corr="' + s.id + '">Correlate</button></div>'
      : '';
    return '<li data-sig="' + s.id + '" style="list-style:none;border-bottom:1px solid var(--rule);padding:12px 8px;cursor:pointer;transition:background 1.2s ease;background:' + (s.fresh ? 'color-mix(in srgb, var(--course) 14%, transparent)' : 'transparent') + '">' +
      '<div style="display:flex;gap:12px;align-items:baseline;flex-wrap:wrap"><strong>' + s.what + '</strong>' + tag +
      '<span style="flex:1"></span>' + rel + ' <span class="muted">conf ' + s.conf.toFixed(2) + '</span></div>' +
      '<div class="muted">' + s.source + ' &middot; ' + ago(s.t) + '</div>' + body + '</li>';
  }


  var rivals = [
    { name: 'Spanwise', offers: 'Agent tracing plus a hosted eval suite', targets: 'Enterprise platform teams, annual contracts from $60k', uses: 'Outbound SDR team, analyst reports, a partner program with cloud marketplaces', complaint: 'Smaller teams say setup takes weeks and pricing is opaque (14 public reviews).', opening: 'Lead with "live in an afternoon" and public pricing for teams under 50 engineers.' },
    { name: 'Evalkit', offers: 'Open-source evals with a paid cloud tier', targets: 'Developers at seed-stage AI startups', uses: 'GitHub stars, Discord community, founder posts on X', complaint: 'Users outgrow it when they need production monitoring and alerts (9 forum threads).', opening: 'Offer an import path from Evalkit and target teams that just hit production.' },
    { name: 'Lumenly', offers: 'LLM cost and latency dashboards', targets: 'Finance-minded heads of engineering', uses: 'Paid search on "LLM cost", webinars', complaint: 'No agent-level traces; teams still debug in logs.', opening: 'Show trace-to-cost in one view; bid on their comparison keywords.' }
  ];
  var openRival = null;
  function rivalBlock() {
    return '<h2 style="font-size:17px;font-weight:600;margin:28px 0 4px">Competitor moves</h2>' +
      '<p class="muted" style="margin-bottom:8px">What each competitor offers, who they sell to, how they reach buyers, and where that leaves an opening. Observed activity, not their private metrics.</p>' +
      '<table class="tbl"><thead><tr><th>Competitor</th><th>Offers</th><th>Sells to</th><th>Reaches buyers through</th><th></th></tr></thead><tbody>' +
      rivals.map(function (r, i) {
        var row = '<tr data-rv="' + i + '" style="cursor:pointer"><td><b>' + r.name + '</b></td><td>' + r.offers + '</td><td>' + r.targets + '</td><td>' + r.uses + '</td><td><button class="btn" data-rv="' + i + '">' + (openRival === i ? 'Hide' : 'Opening') + '</button></td></tr>';
        if (openRival === i) row += '<tr><td></td><td colspan="4"><p><span class="tag bad">Customers complain</span> ' + r.complaint + '</p><p style="margin-top:6px"><span class="tag good">Your opening</span> ' + r.opening + '</p><p style="margin-top:8px"><button class="btn go" data-test="' + i + '">Test this messaging</button></p></td></tr>';
        return row;
      }).join('') + '</tbody></table>';
  }

  function render(el, ctx) {
    function draw() {
      el.innerHTML = '<div class="page"><h1>What changed in the market</h1>' +
        '<p class="lede">Signals the Signal Agent is watching for TraceLayer. Synthetic data; all company names, competitors included, are fictional.</p>' +
        '<div style="display:flex;gap:8px;border-bottom:1px solid var(--rule);padding:12px 0">' +
        ['All', 'High', 'Contradictory'].map(function (f) {
          return '<button class="btn' + (f === filter ? ' go' : '') + '" data-f="' + f + '">' + f + '</button>';
        }).join('') + '</div><ul style="margin:0;padding:0">' +
        (shown().map(item).join('') || '<li class="muted" style="list-style:none;padding:12px 8px">Nothing matches.</li>') + '</ul>' + rivalBlock() + '</div>';
      el.querySelectorAll('[data-rv]').forEach(function (b) { b.onclick = function (e) { e.stopPropagation(); var i = +b.dataset.rv; openRival = openRival === i ? null : i; draw(); }; });
      el.querySelectorAll('[data-test]').forEach(function (b) { b.onclick = function (e) { e.stopPropagation(); var r = rivals[+b.dataset.test]; ctx.toast('Experiment drafted against ' + r.name + '. Marketing reviews it before anything runs.'); ctx.feed('Competitor Agent', 'Drafted a messaging test against ' + r.name + ': ' + r.opening, 'find'); }; });
      el.querySelectorAll('[data-f]').forEach(function (b) { b.onclick = function () { filter = b.dataset.f; draw(); }; });
      el.querySelectorAll('[data-sig]').forEach(function (li) {
        li.onclick = function () { open = open === li.dataset.sig ? null : li.dataset.sig; draw(); };
      });
      el.querySelectorAll('[data-corr]').forEach(function (b) {
        b.onclick = function (e) {
          e.stopPropagation();
          var a = signals.filter(function (s) { return s.id === b.dataset.corr; })[0];
          var other = signals.filter(function (s) { return s.id !== a.id && s.rel === 'High'; })[0] || signals[0];
          var text = 'Hypothesis: "' + a.what + '" + "' + other.what + '" point to a window in the next 30 days';
          ctx.toast(text);
          ctx.feed('Signal Agent', text, 'find');
        };
      });
    }
    draw();
    ctx.every(5000, function () {
      var p = pool[poolAt % pool.length]; poolAt += 1;
      var s = S(p[0], p[1], p[2], p[3], p[4]);
      s.t = Date.now(); s.fresh = true;
      signals.unshift(s);
      if (signals.length > 20) signals.pop();
      ctx.feed('Signal Agent', s.what + ' (' + s.source + ')', s.rel === 'Low' ? 'warn' : 'find');
      draw();
      setTimeout(function () {
        s.fresh = false;
        var li = el.querySelector('[data-sig="' + s.id + '"]');
        if (li) li.style.background = 'transparent';
      }, 900);
    });
  }

  ONE.view('signals', { title: 'Signals', render: render });
})();
