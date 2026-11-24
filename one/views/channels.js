/* ONE view: Channels. Synthetic data for fictional customer TraceLayer. */
(function () {
  var rows = [
    { name: 'Cold email', spend: 2400, leads: 410, opps: 18, pipe: 216000, why: 'Works when the email cites a launch or a hiring signal; generic intros reply under 2%.' },
    { name: 'LinkedIn', spend: 1200, leads: 260, opps: 12, pipe: 144000, why: 'Heads of Data read implementation posts; founder storytelling gets likes, not meetings.' },
    { name: 'Hosted dinners', spend: 4800, leads: 64, opps: 16, pipe: 288000, why: 'Founders of AI infra companies come for the room; 5 warm intro paths per dinner.' },
    { name: 'Cold caking', spend: 900, leads: 30, opps: 6, pipe: 96000, why: 'A cake to the eng team on launch day; 1 in 5 books a call. Only worth it for tier A accounts.' },
    { name: 'Launch parties', spend: 3200, leads: 120, opps: 4, pipe: 48000, why: 'Big room, weak buyers: mostly engineers without budget. Fun, not pipeline.' },
    { name: 'Paid ads', spend: 6000, leads: 540, opps: 8, pipe: 96000, why: 'Clicks come from students and tool shoppers; ICP companies rarely search this way.' },
    { name: 'Referrals', spend: 600, leads: 22, opps: 10, pipe: 180000, why: 'Customers vouch to peers at similar stage; the warmest and cheapest channel.' }
  ];
  rows.forEach(function (r) { r.cpo = Math.round(r.spend / r.opps); r.conv = Math.round(r.opps / r.leads * 1000) / 10; r.roi = Math.round(r.pipe / r.spend); });
  function verdict(r) {
    if (r.cpo <= 110) return ['Scale', 'good'];
    if (r.cpo <= 300) return ['Keep', 'info'];
    return ['Cut', 'bad'];
  }
  var money = function (n) { return '$' + Math.round(n).toLocaleString('en-US'); };
  var sortKey = 'cpo', sortDir = 1;
  var cols = [
    ['name', 'Channel'], ['spend', 'Spend'], ['leads', 'Leads'], ['conv', 'Lead to opp'], ['opps', 'Qualified opps'],
    ['pipe', 'Pipeline'], ['roi', 'Pipeline per $1'], ['cpo', 'Cost per opp']
  ];


  var plays = [
    { name: 'Gift GTA 6 to 12 tier A Heads of Data', cost: 840, why: 'It launched last week and every engineer wants it. A copy plus a note tied to their launch earns a reply.', ask: 'Book a 20 minute call', expect: '3 to 4 calls' },
    { name: 'GTA 6 night at the office', cost: 1200, why: 'Engineers at target accounts come for the game; their Heads of Data come because their team does.', ask: 'Invite 40 engineers from matched accounts', expect: '2 warm intros, 1 pilot' },
    { name: 'Thanksgiving lunch at the office', cost: 650, why: 'Local founders who are away from family on Thursday show up; small table, real conversations.', ask: 'Invite 15 local ICP founders', expect: '2 to 3 qualified opps' }
  ];
  var proposed = {};
  function playsBlock() {
    return '<h2 style="margin-top:44px;font-size:22px">This week\'s plays</h2>' +
      '<p class="muted">Ideas the Marketing and Event agents drafted for this week. Not run yet; each needs approval.</p>' +
      '<table class="tbl"><thead><tr><th>Play</th><th>Cost</th><th>Why it fits TraceLayer</th><th>Ask</th><th>Expected</th><th></th></tr></thead><tbody>' +
      plays.map(function (p, i) {
        return '<tr><td><b>' + p.name + '</b></td><td>' + money(p.cost) + '</td><td class="muted" style="max-width:36ch">' + p.why + '</td><td>' + p.ask + '</td><td>' + p.expect + '</td><td><button class="btn ' + (proposed[i] ? 'ok' : 'go') + '" data-play="' + i + '">' + (proposed[i] ? 'Proposed' : 'Propose') + '</button></td></tr>';
      }).join('') + '</tbody></table>';
  }

  ONE.view('channels', {
    title: 'Channels',
    render: function (el, ctx) {
      var sim = { 'Paid ads': 6000, 'Hosted dinners': 4800, 'Referrals': 600 };
      el.innerHTML =
        '<div class="page">' +
        '<h1>Where qualified pipeline actually comes from</h1>' +
        '<p class="lede">Every channel TraceLayer spent on in the last 90 days, from email to cakes, with the reason it works or fails for this customer. Synthetic data. Click a header to sort.</p>' +
        '<table class="tbl" id="ch-tbl"><thead><tr></tr></thead><tbody></tbody></table>' +
        '<div id="ch-plays"></div>' +
        '<h2 style="margin-top:48px;font-size:22px">Budget simulator</h2>' +
        '<p class="muted">Move the three budgets. Cold email and LinkedIn stay fixed.</p>' +
        '<div class="grid2" style="align-items:start;gap:32px">' +
        '<div id="ch-sliders"></div>' +
        '<div id="ch-out" style="border-left:1px solid var(--rule);padding-left:24px"></div>' +
        '</div>' +
        '<p class="muted" style="margin-top:12px">Linear estimate from the last 90 days. Not a forecast.</p>' +
        '<div style="margin-top:16px;display:flex;gap:8px">' +
        '<button class="btn go" id="ch-apply">Propose this budget</button>' +
        '<button class="btn" id="ch-reset">Reset</button></div>' +
        '</div>';

      var playsEl = el.querySelector('#ch-plays');
      function drawPlays() {
        playsEl.innerHTML = playsBlock();
        playsEl.querySelectorAll('[data-play]').forEach(function (b) { b.onclick = function () {
          var i = +b.dataset.play; proposed[i] = !proposed[i]; drawPlays();
          if (proposed[i]) { ctx.feed('Event Agent', 'Proposed: ' + plays[i].name + ' (' + money(plays[i].cost) + '). Waiting on owner approval.', 'find'); ctx.toast('Proposed. It runs only after the owner approves.', function () { proposed[i] = false; drawPlays(); }); }
        }; });
      }
      drawPlays();
      var thead = el.querySelector('#ch-tbl thead tr');
      var tbody = el.querySelector('#ch-tbl tbody');
      function drawTable() {
        thead.innerHTML = cols.map(function (c) {
          var mark = c[0] === sortKey ? (sortDir === 1 ? ' ↑' : ' ↓') : '';
          return '<th data-k="' + c[0] + '" style="cursor:pointer;user-select:none">' + c[1] + mark + '</th>';
        }).join('') + '<th>Verdict</th>';
        var sorted = rows.slice().sort(function (a, b) {
          var x = a[sortKey], y = b[sortKey];
          if (typeof x === 'string') return x.localeCompare(y) * sortDir;
          return (x - y) * sortDir;
        });
        tbody.innerHTML = sorted.map(function (r) {
          var v = verdict(r);
          return '<tr><td><b>' + r.name + '</b><div class="muted" style="font-size:14px;max-width:34ch">' + r.why + '</div></td><td>' + money(r.spend) + '</td><td>' + r.leads + '</td><td>' + r.conv + '%</td><td>' + r.opps +
            '</td><td>' + money(r.pipe) + '</td><td>' + money(r.roi) + '</td><td>' + money(r.cpo) +
            '</td><td><span class="tag ' + v[1] + '">' + v[0] + '</span></td></tr>';
        }).join('');
        thead.querySelectorAll('th[data-k]').forEach(function (th) {
          th.onclick = function () {
            var k = th.getAttribute('data-k');
            if (k === sortKey) sortDir = -sortDir; else { sortKey = k; sortDir = 1; }
            drawTable();
          };
        });
      }
      drawTable();

      var sliders = el.querySelector('#ch-sliders');
      var out = el.querySelector('#ch-out');
      var max = { 'Paid ads': 10000, 'Hosted dinners': 10000, 'Referrals': 3000 };
      sliders.innerHTML = Object.keys(sim).map(function (k) {
        return '<label style="display:block;margin-bottom:18px">' +
          '<span style="display:flex;justify-content:space-between"><b>' + k + '</b>' +
          '<span data-v="' + k + '" style="font-family:var(--chart)"></span></span>' +
          '<input type="range" min="0" max="' + max[k] + '" step="100" value="' + sim[k] +
          '" data-k="' + k + '" style="width:100%"></label>';
      }).join('');

      function estimate() {
        var spend = 0, opps = 0;
        rows.forEach(function (r) {
          var s = sim.hasOwnProperty(r.name) ? sim[r.name] : r.spend;
          spend += s;
          opps += s * (r.opps / r.spend);
        });
        return { spend: spend, opps: opps, cpo: opps ? spend / opps : 0 };
      }
      var base = estimate();
      function drawOut() {
        Object.keys(sim).forEach(function (k) { el.querySelector('[data-v="' + k + '"]').textContent = money(sim[k]); });
        var e = estimate();
        var d = Math.round(e.opps) - Math.round(base.opps);
        out.innerHTML =
          '<div class="muted">Estimated qualified opps</div>' +
          '<div style="font-size:44px;font-family:var(--chart)">' + Math.round(e.opps) +
          ' <span class="fixmark ' + (d >= 0 ? 'good' : 'bad') + '" style="font-size:18px">' + (d >= 0 ? '+' : '') + d + '</span></div>' +
          '<div class="muted" style="margin-top:12px">Cost per opp</div>' +
          '<div style="font-size:32px;font-family:var(--chart)">' + money(e.cpo) + '</div>' +
          '<div class="muted" style="margin-top:12px">Total spend ' + money(e.spend) + ' (was ' + money(base.spend) + ')</div>';
      }
      sliders.querySelectorAll('input').forEach(function (inp) {
        inp.oninput = function () { sim[inp.getAttribute('data-k')] = +inp.value; drawOut(); };
      });
      drawOut();

      el.querySelector('#ch-apply').onclick = function () {
        var e = estimate();
        ctx.toast('Budget proposal saved: ' + Math.round(e.opps) + ' opps at ' + money(e.cpo) + ' each (synthetic)');
        ctx.feed('Strategy Agent', 'Drafted reallocation: Paid ads ' + money(sim['Paid ads']) + ', Events ' + money(sim['Hosted dinners']) + ', Referrals ' + money(sim['Referrals']), 'done');
      };
      el.querySelector('#ch-reset').onclick = function () {
        sim = { 'Paid ads': 6000, 'Hosted dinners': 4800, 'Referrals': 600 };
        sliders.querySelectorAll('input').forEach(function (inp) { inp.value = sim[inp.getAttribute('data-k')]; });
        drawOut();
        ctx.toast('Budgets reset to the last 90 days');
      };
    }
  });
})();
