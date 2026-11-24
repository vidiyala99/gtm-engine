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
    mk('Halcyon Data', ['Our customer Mira Chen worked 3 years with their current VP Engineering', 'Moved their agent product to general availability last week'], 'Ask Mira to introduce their VP Engineering', 61, 0.30, true)
  ];
  var LABEL = { seq: ['Added to sequence', 'good'], intro: ['Intro requested', 'info'], no: ['Snoozed 30 days', 'warn'] };

  ONE.view('discovery', {
    title: 'Discovery',
    render: function (el, ctx) {
      el.innerHTML =
        '<style>' +
        '.dsc-item{border-top:1px solid var(--rule);padding:12px 0;display:grid;grid-template-columns:minmax(0,1.5fr) minmax(0,1fr) 150px auto;gap:20px;align-items:start;transition:opacity .3s var(--ease)}.dsc-item .btn{padding:4px 10px;font-size:14px}.dsc-why{color:var(--muted);font-size:14px;margin-top:2px}' +
        '.dsc-item.in{animation:dscIn .5s var(--ease)}@keyframes dscIn{from{opacity:0;transform:translateY(-12px)}to{opacity:1;transform:none}}' +
        '.dsc-item.done{opacity:.55}.dsc-item h2{font-size:17px;margin:0}.dsc-item ul{margin:6px 0;padding-left:18px}.dsc-item li{margin:3px 0}' +
        '.dsc-how{font:italic 600 17px var(--chart);color:var(--course)}.dsc-meta{font-size:13px;line-height:1.5;color:var(--muted)}.dsc-acts{display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end}' +
        '.dsc-bar{height:4px;background:var(--rule);margin:2px 0 8px}.dsc-bar i{display:block;height:100%;background:var(--ink)}' +
        '.dsc-acts{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}' +
        '@media(max-width:1000px){.dsc-item{grid-template-columns:1fr 1fr;gap:8px}.dsc-acts{justify-content:flex-start}}@media(max-width:640px){.dsc-item{grid-template-columns:1fr}}' +
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
          '<div class="dsc-why">' + a.why.join('. ') + '.</div></div>' +
          '<span class="dsc-how">' + a.how + '</span>' +
          '<div class="dsc-meta">Enriched ' + a.comp + '%<div class="dsc-bar"><i style="width:' + a.comp + '%"></i></div>' +
          '$' + a.cost.toFixed(2) + ' to enrich' + (a.crm ? ', in CRM' : '') + '</div>' +
          '<div class="dsc-acts"><button class="btn" data-a="seq">Add to sequence</button><button class="btn" data-a="intro">Ask for intro</button><button class="btn" data-a="no">Not now</button></div></div>';
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
