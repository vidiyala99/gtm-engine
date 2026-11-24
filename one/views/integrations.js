/* ONE view: Integrations. Connections are simulated. */
(function () {
  var groups = [
    ['CRM', [
      { name: 'HubSpot', on: true, sync: '12 min ago', records: 4820, dupes: 312, cost: '$0 (existing plan)' },
      { name: 'Salesforce', on: false, sync: 'never', records: 0, dupes: 0, cost: '$0 (existing plan)' }]],
    ['Email', [{ name: 'Gmail', on: true, sync: '4 min ago', records: 12640, dupes: 0, cost: '$0' }]],
    ['Meetings', [
      { name: 'Gong', on: true, sync: '1 hr ago', records: 214, dupes: 6, cost: '$0 (existing plan)' },
      { name: 'Fathom', on: false, sync: 'never', records: 0, dupes: 0, cost: '$0 (free tier)' }]],
    ['Events', [{ name: 'Luma', on: true, sync: '3 hr ago', records: 146, dupes: 21, cost: '$0' }]],
    ['Marketing', [{ name: 'Google Ads', on: true, sync: '30 min ago', records: 38, dupes: 0, cost: '$0 (API)' }]],
    ['Product', [{ name: 'PostHog', on: false, sync: 'never', records: 0, dupes: 0, cost: '~$0 under 1M events' }]]
  ];
  var busy = {};
  function all() { var a = []; groups.forEach(function (g) { a = a.concat(g[1]); }); return a; }
  function find(n) { return all().filter(function (s) { return s.name === n; })[0]; }
  var rot = 0;

  ONE.view('integrations', {
    title: 'Integrations',
    render: function (el, ctx) {
      el.innerHTML =
        '<div class="page">' +
        '<h1>Connect what you already use</h1>' +
        '<p class="lede">ONE reads from the tools the team already pays for. Connections are simulated in this demo.</p>' +
        '<table class="tbl"><thead><tr><th>Source</th><th>Status</th><th>Last sync</th><th>Records</th>' +
        '<th>Duplicates</th><th>Est. provider cost</th><th></th></tr></thead><tbody id="in-body"></tbody></table>' +
        '</div>';
      var body = el.querySelector('#in-body');

      function draw() {
        var h = '';
        groups.forEach(function (g) {
          h += '<tr><td colspan="7" style="padding-top:20px;font-weight:600;border-bottom:1px solid var(--ink)">' + g[0] + '</td></tr>';
          g[1].forEach(function (s) {
            var b = busy[s.name];
            var status = s.on ? '<span class="tag good">Connected</span>' :
              (b === 'connect' ? '<span class="tag warn">Connecting</span>' : '<span class="tag">Not connected</span>');
            var btn = s.on
              ? '<button class="btn" data-a="sync" data-n="' + s.name + '"' + (b ? ' disabled' : '') + '>' +
                (b === 'sync' ? '<span class="in-spin" style="display:inline-block">↻</span> Syncing' : 'Sync') + '</button>'
              : '<button class="btn go" data-a="connect" data-n="' + s.name + '"' + (b ? ' disabled' : '') + '>' +
                (b ? 'Connecting' : 'Connect') + '</button>';
            h += '<tr><td>' + s.name + '</td><td>' + status + '</td><td>' + s.sync + '</td><td>' +
              s.records.toLocaleString('en-US') + '</td><td>' + (s.dupes ? '<span class="tag warn">' + s.dupes + '</span>' : '0') +
              '</td><td class="muted">' + s.cost + '</td><td style="text-align:right">' + btn + '</td></tr>';
          });
        });
        body.innerHTML = h;
        body.querySelectorAll('.in-spin').forEach(function (sp) {
          if (sp.animate) sp.animate([{ transform: 'rotate(0)' }, { transform: 'rotate(360deg)' }], { duration: 800, iterations: Infinity });
        });
        body.querySelectorAll('button[data-a]').forEach(function (bt) {
          bt.onclick = function () {
            var s = find(bt.getAttribute('data-n'));
            if (bt.getAttribute('data-a') === 'connect') connect(s); else sync(s, true);
          };
        });
      }

      function connect(s) {
        busy[s.name] = 'connect'; draw();
        setTimeout(function () {
          busy[s.name] = null;
          s.on = true; s.sync = 'just now';
          s.records = 200 + Math.floor(Math.random() * 1800);
          s.dupes = Math.floor(s.records * 0.04);
          if (el.isConnected) draw();
          ctx.toast(s.name + ' connected');
          ctx.feed('Enrichment Agent', 'Imported ' + s.records.toLocaleString('en-US') + ' records from ' + s.name, 'done');
        }, 1500);
      }
      function sync(s, manual) {
        busy[s.name] = 'sync'; if (el.isConnected) draw();
        setTimeout(function () {
          busy[s.name] = null;
          var n = 1 + Math.floor(Math.random() * 40);
          s.records += n; s.sync = 'just now';
          if (el.isConnected) draw();
          if (manual) ctx.toast(s.name + ' synced, ' + n + ' new records');
          ctx.feed('Enrichment Agent', 'Synced ' + s.name + ': ' + n + ' new records', 'done');
        }, 1200);
      }
      draw();

      ctx.every(7000, function () {
        var on = all().filter(function (s) { return s.on && !busy[s.name]; });
        if (!on.length) return;
        sync(on[rot++ % on.length], false);
      });
    }
  });
})();
