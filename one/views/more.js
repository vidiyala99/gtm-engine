/* ONE views: Pipeline, Meeting intelligence, Spend & ROI, Strategy & Learning. Synthetic data. */
(function () {
  var cols = [
    { name: 'Matched', n: 24, deals: ['Stackwell', 'Kiln AI', 'Promptwise'] },
    { name: 'Contacted', n: 18, deals: ['Vectorline', 'Cobalt Labs'] },
    { name: 'Meeting', n: 12, deals: ['Agentry', 'Outpost Cloud', 'Lumen Data'] },
    { name: 'Qualified', n: 8, deals: ['RelayOps', 'Northwind ML'] },
    { name: 'Closed', n: 3, deals: ['Brightpath', 'Quanta Logs'] }
  ];

  ONE.view('pipeline', {
    title: 'Pipeline',
    render: function (el, ctx) {
      el.innerHTML = '<div class="page"><h1>Pipeline</h1>' +
        '<p class="lede">Click a deal to move it one stage forward. Synthetic accounts.</p>' +
        '<div id="pl-board" style="display:grid;grid-template-columns:repeat(5,minmax(140px,1fr));overflow-x:auto;border-top:1px solid var(--ink)"></div></div>';
      var board = el.querySelector('#pl-board');
      function draw() {
        board.innerHTML = cols.map(function (c, ci) {
          return '<div style="padding:12px;' + (ci ? 'border-left:1px solid var(--rule)' : '') + '">' +
            '<div style="display:flex;justify-content:space-between;align-items:baseline"><b>' + c.name + '</b>' +
            '<span style="font-family:var(--chart);font-size:26px">' + c.n + '</span></div>' +
            c.deals.map(function (d, di) {
              return '<button class="btn" data-c="' + ci + '" data-d="' + di + '" style="display:block;width:100%;text-align:left;margin-top:8px"' +
                (ci === cols.length - 1 ? ' disabled' : '') + '>' + d + '</button>';
            }).join('') + '</div>';
        }).join('');
        board.querySelectorAll('button[data-c]').forEach(function (b) {
          b.onclick = function () {
            var ci = +b.getAttribute('data-c'), di = +b.getAttribute('data-d');
            var d = cols[ci].deals.splice(di, 1)[0];
            cols[ci].n--; cols[ci + 1].n++; cols[ci + 1].deals.push(d);
            draw();
            ctx.toast(d + ' moved to ' + cols[ci + 1].name);
          };
        });
      }
      draw();
    }
  });

  ONE.view('revenue', {
    title: 'Meeting intelligence',
    render: function (el, ctx) {
      var row = function (k, v) { return '<tr><td class="muted" style="width:220px">' + k + '</td><td>' + v + '</td></tr>'; };
      el.innerHTML = '<div class="page"><h1>Meeting intelligence</h1>' +
        '<p class="lede">What a call changed about one account. Synthetic meeting notes.</p>' +
        '<h2 style="font-size:26px;margin:24px 0 8px">RelayOps <span style="font-family:var(--chart)">$24,000</span></h2>' +
        '<table class="tbl"><tbody>' +
        row('Previous assessment', '<span class="tag good">High intent</span> Strong ICP fit, active tracing pain') +
        row('Meeting outcome', '<span class="tag warn">Not ready</span> Nothing moves until their data migration is done') +
        row('Updated assessment', 'Right account, wrong timing') +
        row('Learning', '<b>High fit does not mean ready now.</b> Timing is scored separately from fit.') +
        '</tbody></table>' +
        '<div style="margin-top:16px;display:flex;gap:8px"><button class="btn go" id="rv-rev">Revisit in 60 days</button>' +
        '<button class="btn" id="rv-acc">Open accounts</button></div></div>';
      el.querySelector('#rv-rev').onclick = function () {
        this.textContent = 'Reminder set'; this.disabled = true;
        ctx.toast('RelayOps scheduled for review in 60 days');
        ctx.feed('Meeting Agent', 'Parked RelayOps until migration ends; reminder in 60 days', 'done');
      };
      el.querySelector('#rv-acc').onclick = function () { ctx.go('accounts'); };
    }
  });

  var spend = [
    ['Paid ads', 40, 12.5], ['Events', 32, 25], ['Cold email', 16, 28.1], ['LinkedIn', 8, 18.8], ['Referrals', 4, 15.6]
  ];
  ONE.view('spend', {
    title: 'Spend & ROI',
    render: function (el, ctx) {
      el.innerHTML = '<div class="page"><h1>Paid ads take 40% of spend and bring 12.5% of qualified opps</h1>' +
        '<p class="lede">Share of spend against share of qualified opportunities, last 90 days. Synthetic data.</p>' +
        '<div style="display:flex;gap:20px;margin:8px 0 16px" class="muted">' +
        '<span><i style="display:inline-block;width:12px;height:12px;background:var(--course)"></i> Share of spend</span>' +
        '<span><i style="display:inline-block;width:12px;height:12px;background:var(--water)"></i> Share of qualified opps</span></div>' +
        spend.map(function (s) {
          return '<div style="display:grid;grid-template-columns:110px 1fr;gap:12px;padding:10px 0;border-bottom:1px solid var(--rule)">' +
            '<b>' + s[0] + '</b><div>' + bar(s[1], 'var(--course)') + bar(s[2], 'var(--water)') + '</div></div>';
        }).join('') +
        '<button class="btn go" id="sp-test" style="margin-top:20px">Test reallocation</button></div>';
      function bar(p, c) {
        return '<div style="display:flex;align-items:center;gap:8px;margin:3px 0"><div style="height:12px;width:' + (p * 2) +
          '%;max-width:80%;background:' + c + '"></div><span style="font-family:var(--chart)">' + p + '%</span></div>';
      }
      el.querySelector('#sp-test').onclick = function () { ctx.toast('Opening the budget simulator'); ctx.go('channels'); };
    }
  });

  ONE.view('strategy', {
    title: 'Strategy & Learning',
    render: function (el, ctx) {
      var weeks = [
        ['Week 1', 'Generic AI-startup list replies at 1.2%', 'Narrowed ICP to teams running agents in production'],
        ['Week 2', 'Platform engineers reply 3x more than CTOs', 'Retargeted outreach to platform leads'],
        ['Week 3', 'Paid ads opps rarely qualify', 'Cut paid ads test budget by half'],
        ['Week 4', 'Dinner attendees refer peers', 'Added referral ask to every event follow-up'],
        ['Week 5', 'High-fit accounts stall on migrations', 'Score timing separately from fit (v3)']
      ];
      var ba = [
        ['Qualified opp rate', '4.5%', '10.8%'], ['Cost per qualified opp', '$310', '$185'],
        ['Qualification time', '5 days', '2 days'], ['Warm intros', '6', '19'], ['Monthly pipeline', '$180k', '$294k']
      ];
      el.innerHTML = '<div class="page"><h1>Strategy & Learning</h1>' +
        '<p class="lede">Each week the system wrote down what it saw and what it changed.</p>' +
        '<table class="tbl"><thead><tr><th>Week</th><th>Observation</th><th>Strategy change</th></tr></thead><tbody>' +
        weeks.map(function (w) { return '<tr><td>' + w[0] + '</td><td>' + w[1] + '</td><td>' + w[2] + '</td></tr>'; }).join('') +
        '</tbody></table>' +
        '<h2 style="font-size:22px;margin:40px 0 8px">Before and after (synthetic)</h2>' +
        '<table class="tbl"><thead><tr><th>Metric</th><th>Week 1</th><th>Week 5</th></tr></thead><tbody>' +
        ba.map(function (r) { return '<tr><td>' + r[0] + '</td><td class="muted">' + r[1] + '</td><td><b>' + r[2] + '</b></td></tr>'; }).join('') +
        '</tbody></table>' +
        '<p class="muted" style="margin-top:12px">Synthetic data for a fictional company. Not real results.</p>' +
        '<p style="margin-top:16px">Running strategy <b id="st-v">v3</b> ' +
        '<button class="btn" id="st-rb" style="margin-left:12px">Roll back to v2</button></p></div>';
      el.querySelector('#st-rb').onclick = function () {
        var v = el.querySelector('#st-v');
        if (v.textContent === 'v3') {
          v.textContent = 'v2'; this.textContent = 'Restore v3';
          ctx.toast('Rolled back to v2: timing no longer scored separately');
          ctx.feed('Strategy Agent', 'Strategy rolled back to v2 by operator', 'warn');
        } else {
          v.textContent = 'v3'; this.textContent = 'Roll back to v2';
          ctx.toast('Restored strategy v3');
        }
      };
    }
  });
})();
