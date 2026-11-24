/* ICPs view: segment comparison + versioned hypothesis. Synthetic data for fictional TraceLayer. */
(function () {
  var SEGS = [
    { n: 'Funded startups', a: 420, r: 14, q: 4.5, acv: 8000, c: 24 },
    { n: 'Scaling SaaS', a: 280, r: 18, q: 10.8, acv: 18000, c: 38 },
    { n: 'Enterprise teams', a: 95, r: 6, q: 3.2, acv: 65000, c: 112 },
    { n: 'Production AI + GTM hiring', a: 140, r: 21, q: 12.4, acv: 16000, c: 31, isNew: true }
  ];
  var VERS = {
    v1: { h: 'Recently funded startups are high-intent buyers', conf: 0.62, sample: 18,
      why: ['Starting point: founder intuition from the first 18 opportunities.',
            'Funding announcements were the easiest signal to buy and filter on.',
            'No outcome data yet; replies were the only measure.'] },
    v2: { h: 'Funding correlates with replies, not qualified opportunities', conf: 0.71, sample: 41,
      why: ['Funded startups replied at 14% but qualified at only 4.5%.',
            'Scaling SaaS replied less often yet qualified at 10.8%, more than twice as often.',
            'Calls Agent heard "we just raised, not ready to buy tooling" in 9 of 22 discovery calls.'] },
    v3: { h: 'Product launch plus GTM hiring predicts buying readiness', conf: 0.78, sample: 64,
      why: ['Accounts that shipped an AI feature to production and opened GTM roles qualified at 12.4%.',
            'Reply rate rose to 21%: they already feel the pain of debugging agents in production.',
            'Cycle held at 31 days, close to startups, with twice the ACV.',
            'Enterprise stays deprioritized: 112-day cycle does not fit a 90-day runway plan.'] }
  };
  var cur = 'v3';
  var running = false;
  var money = function (v) { return '$' + v.toLocaleString('en-US'); };

  ONE.view('icps', {
    title: 'ICPs',
    render: function (el, ctx) {
      var best = 3;
      var rows = SEGS.map(function (s, i) {
        return '<tr' + (i === best ? ' class="icp-best"' : '') + '><td><strong>' + s.n + '</strong>' +
          (s.isNew ? ' <span class="tag info">new</span>' : '') + '</td><td>' + s.a + '</td><td>' + s.r + '%</td><td>' +
          s.q + '%</td><td>' + money(s.acv) + '</td><td>' + s.c + ' days</td></tr>';
      }).join('');
      el.innerHTML =
        '<style>' +
        '.icp-best td{background:color-mix(in srgb,var(--course) 7%,transparent)}' +
        '.icp-vers{display:flex;gap:8px;margin:28px 0 14px}' +
        '.icp-vers .btn[aria-pressed="true"]{border-color:var(--course);color:var(--course)}' +
        '.icp-hyp{border-top:1px solid var(--rule);border-bottom:1px solid var(--rule);padding:18px 0;transition:background .5s var(--ease)}' +
        '.icp-hyp.flash{background:color-mix(in srgb,var(--course) 10%,transparent)}' +
        '.icp-hyp h2{font-size:26px;line-height:1.2;margin:4px 0 10px;transition:opacity .25s var(--ease),transform .25s var(--ease)}' +
        '.icp-hyp.swap h2,.icp-hyp.swap ul{opacity:0;transform:translateY(6px)}' +
        '.icp-hyp ul{margin:8px 0 0;padding-left:18px;transition:opacity .25s var(--ease),transform .25s var(--ease)}' +
        '.icp-hyp li{margin:6px 0}' +
        '.icp-k{font:italic 600 15px var(--chart);color:var(--muted)}' +
        '.icp-conf{font:italic 700 22px var(--chart);color:var(--course)}' +
        '</style>' +
        '<div class="page"><h1>Your ICP is a hypothesis, not a definition</h1>' +
        '<p class="lede">Each segment is a bet the ICP Agent keeps testing against outcomes, not replies. Synthetic data for a fictional company.</p>' +
        '<table class="tbl"><thead><tr><th>Segment</th><th>Accounts</th><th>Reply rate</th><th>Qualified opp</th><th>ACV</th><th>Cycle</th></tr></thead><tbody>' + rows + '</tbody></table>' +
        '<div class="icp-vers" role="group" aria-label="Hypothesis version">' +
        ['v1', 'v2', 'v3'].map(function (v) { return '<button class="btn" data-v="' + v + '" aria-pressed="' + (v === cur) + '">' + v + '</button>'; }).join('') +
        '</div><div class="icp-hyp" id="icpHyp"></div>' +
        '<p style="margin-top:20px"><button class="btn go" id="icpExp"></button> <button class="btn" id="icpSig">See the signals behind v3</button></p></div>';

      var hyp = el.querySelector('#icpHyp');
      var exp = el.querySelector('#icpExp');
      function fill() {
        var V = VERS[cur];
        hyp.innerHTML = '<span class="icp-k">Current hypothesis, ' + cur + '</span><h2>' + V.h + '</h2>' +
          '<span class="icp-k">Confidence</span> <span class="icp-conf">' + V.conf.toFixed(2) + '</span>' +
          ' <span class="muted">sample ' + V.sample + ' opps</span>' +
          '<p class="icp-k" style="margin-top:14px">What changed and why</p><ul>' +
          V.why.map(function (w) { return '<li>' + w + '</li>'; }).join('') + '</ul>';
      }
      function setExp() {
        exp.textContent = running ? 'Experiment running, day 1 of 14' : 'Start 14-day experiment';
        exp.className = running ? 'btn ok' : 'btn go';
      }
      fill(); setExp();

      el.querySelectorAll('[data-v]').forEach(function (b) {
        b.onclick = function () {
          if (b.dataset.v === cur) return;
          cur = b.dataset.v;
          el.querySelectorAll('[data-v]').forEach(function (x) { x.setAttribute('aria-pressed', String(x === b)); });
          hyp.classList.add('swap', 'flash');
          setTimeout(function () { fill(); hyp.classList.remove('swap'); }, 220);
          setTimeout(function () { hyp.classList.remove('flash'); }, 900);
        };
      });
      exp.onclick = function () {
        if (running) { running = false; setExp(); ctx.toast('Experiment stopped. No budget spent.'); return; }
        running = true; setExp();
        ctx.toast('14-day experiment started on hypothesis ' + cur);
        ctx.feed('ICP Agent', 'Started 14-day test of ' + cur + ': "' + VERS[cur].h + '". Splitting 60 accounts, holdout 20.', 'done');
      };
      el.querySelector('#icpSig').onclick = function () { ctx.go('signals'); };
    }
  });
})();
