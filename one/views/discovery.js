/* Discovery view: accounts with reasons, live discovery from a pool. Synthetic data, fictional companies. */
(function () {
  var mk = function (n, why, how, comp, cost, crm) { return { n: n, why: why, how: how, comp: comp, cost: cost, crm: crm, st: '' }; };
  var LIST = [
    mk('RelayOps', ['Launched an enterprise product 9 days ago', 'Hiring 2 GTM engineers', 'Founder posted about outbound pain', 'Investor intro already in CRM'], 'Warm intro, not cold email', 80, 0.42, true),
    mk('Vellum Labs', ['Shipped agent workflows to production', 'Eval tooling repo starred by 3 engineers', 'Shares investor Lumen Ventures'], 'Investor intro, then technical demo', 74, 0.38, true),
    mk('Quanta AI', ['Attended our Luma event on agent tracing', 'Job post mentions "LLM observability"'], 'Follow up on the event, short note', 66, 0.29, false),
    mk('Kepler Ops', ['Referral partner flagged a pilot budget', 'New Head of Platform started last month'], 'Partner-led intro', 71, 0.33, true),
    mk('Glyph Systems', ['Former trial user, churned before GA', 'Now posting about agent reliability incidents'], 'Re-engage with what changed since trial', 62, 0.25, true),
    mk('Northpine', ['Opened 3 roles for applied AI', 'No production AI feature yet'], 'Nurture, not now', 48, 0.21, false)
  ];
  var POOL = [
    mk('Tessellate', ['Launched an AI copilot last week', 'Hiring a founding GTM lead'], 'Founder-to-founder email', 58, 0.31, false),
    mk('Brightwire', ['CTO spoke on agent failures at a meetup', 'Seed round closed 6 weeks ago'], 'Reference the talk, offer a teardown', 55, 0.27, false),
    mk('Orbit Kernel', ['Docs mention OpenTelemetry for LLM calls', 'Two ML infra roles open'], 'Technical note to the infra lead', 69, 0.36, true),
    mk('Halcyon Data', ['Customer Mira Chen follows their CEO', 'Product launch on Product Hunt'], 'Ask Mira for a light intro', 61, 0.30, true)
  ];
  var LABEL = { seq: ['Added to sequence', 'good'], intro: ['Intro requested', 'info'], no: ['Snoozed 30 days', 'warn'] };

  ONE.view('discovery', {
    title: 'Discovery',
    render: function (el, ctx) {
      el.innerHTML =
        '<style>' +
        '.dsc-item{border-top:1px solid var(--rule);padding:18px 0;display:grid;grid-template-columns:minmax(0,1fr) 220px;gap:24px;transition:opacity .3s var(--ease)}' +
        '.dsc-item.in{animation:dscIn .5s var(--ease)}@keyframes dscIn{from{opacity:0;transform:translateY(-12px)}to{opacity:1;transform:none}}' +
        '.dsc-item.done{opacity:.55}.dsc-item h2{font-size:24px;margin:0 0 6px}.dsc-item ul{margin:6px 0;padding-left:18px}.dsc-item li{margin:3px 0}' +
        '.dsc-how{font:italic 600 17px var(--chart);color:var(--course)}.dsc-meta{font-size:14px;line-height:1.7}' +
        '.dsc-bar{height:4px;background:var(--rule);margin:2px 0 8px}.dsc-bar i{display:block;height:100%;background:var(--ink)}' +
        '.dsc-acts{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}' +
        '@media(max-width:700px){.dsc-item{grid-template-columns:1fr;gap:8px}}' +
        '@media(prefers-reduced-motion:reduce){.dsc-item.in{animation:none}}' +
        '</style><div class="page"><h1>Accounts worth your time this week</h1>' +
        '<p class="lede">Every account comes with the reasons it surfaced, so you judge the evidence, not a score. Fictional companies, synthetic signals.</p>' +
        '<p><button class="btn go" id="dscRun">Run discovery</button> <span class="muted" id="dscCount"></span></p>' +
        '<div id="dscList"></div></div>';

      var listEl = el.querySelector('#dscList'), runBtn = el.querySelector('#dscRun'), busy = false;
      function row(a, fresh) {
        var lab = LABEL[a.st];
        return '<div class="dsc-item' + (fresh ? ' in' : '') + (a.st ? ' done' : '') + '" data-n="' + a.n + '">' +
          '<div><h2>' + a.n + (lab ? ' <span class="tag ' + lab[1] + '">' + lab[0] + '</span>' : '') + '</h2>' +
          '<ul>' + a.why.map(function (w) { return '<li>' + w + '</li>'; }).join('') + '</ul>' +
          '<span class="dsc-how">' + a.how + '</span>' +
          '<div class="dsc-acts"><button class="btn" data-a="seq">Add to sequence</button><button class="btn" data-a="intro">Ask for intro</button><button class="btn" data-a="no">Not now</button></div></div>' +
          '<div class="dsc-meta">Enrichment ' + a.comp + '%<div class="dsc-bar"><i style="width:' + a.comp + '%"></i></div>' +
          'Est. enrichment cost $' + a.cost.toFixed(2) + '<br>Existing CRM relationship: ' + (a.crm ? 'yes' : 'no') + '</div></div>';
      }
      function paint(freshName) {
        listEl.innerHTML = LIST.map(function (a) { return row(a, a.n === freshName); }).join('');
        el.querySelector('#dscCount').textContent = LIST.length + ' accounts, ' + POOL.length + ' candidates left in the pool';
      }
      function discover(src) {
        if (!POOL.length) { if (src === 'manual') ctx.toast('No new accounts match the current ICP'); return false; }
        var a = POOL.shift(); LIST.unshift(a); paint(a.n);
        ctx.feed('Discovery Agent', 'Found ' + a.n + ': ' + a.why[0].toLowerCase() + '. Suggest: ' + a.how.toLowerCase() + '.', 'find');
        return true;
      }
      paint();
      listEl.onclick = function (e) {
        var b = e.target.closest('[data-a]'); if (!b) return;
        var n = b.closest('.dsc-item').dataset.n, a = LIST.filter(function (x) { return x.n === n; })[0];
        a.st = a.st === b.dataset.a ? '' : b.dataset.a; paint();
        ctx.toast(a.st ? n + ': ' + LABEL[a.st][0].toLowerCase() : n + ': action undone');
        if (a.st === 'intro') ctx.feed('Relationship Agent', 'Looking for the warmest path into ' + n + '.', 'find');
      };
      runBtn.onclick = function () {
        if (busy) return; busy = true;
        runBtn.textContent = 'Searching signals...'; runBtn.disabled = true;
        setTimeout(function () {
          busy = false; runBtn.textContent = 'Run discovery'; runBtn.disabled = false;
          if (discover('manual')) ctx.toast('1 new account found');
        }, 1500);
      };
      ctx.every(6000, function () { if (!busy) discover('auto'); });
    }
  });
})();
