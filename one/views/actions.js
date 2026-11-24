/* Action Center: synthetic actions for the fictional customer TraceLayer. */
(function () {
  var ACTIONS = [
    { id: 'a1', role: 'SDR', owner: 'SDR', what: 'Contact 12 newly identified accounts', why: 'High-confidence buying signals across hiring and product launches', conf: 0.82, high: false },
    { id: 'a2', role: 'Marketing', owner: 'Event manager', what: 'Follow up with 8 dinner attendees', why: 'Potential pilots from the agent reliability dinner', conf: 0.74, high: false },
    { id: 'a3', role: 'Marketing', owner: 'Marketing', what: 'Rewrite LinkedIn campaign messaging', why: 'Qualified conversion declining for three weeks', conf: 0.69, high: false },
    { id: 'a4', role: 'AE', owner: 'AE', what: 'Revisit 4 stalled opportunities', why: 'Buying timelines changed in the last two calls', conf: 0.71, high: false },
    { id: 'a5', role: 'Product', owner: 'Product', what: 'Investigate Salesforce integration demand', why: 'Raised on 7 calls, $84k pipeline attached', conf: 0.78, high: false, go: 'signals' },
    { id: 'a6', role: 'GTM', owner: 'GTM manager', what: 'Reallocate $1,500 from paid ads', why: 'Paid CAC rising while events convert better', conf: 0.66, high: true }
  ];
  var state = {}; // id -> 'open' | 'approved' | 'dismissed'
  var filter = 'All';
  var picked = {};
  ACTIONS.forEach(function (a) { state[a.id] = 'open'; });

  function row(a) {
    var s = state[a.id];
    var muted = s === 'dismissed' ? ' class="muted"' : '';
    var ctl;
    if (s === 'approved') ctl = '<button class="btn ok" data-act="undo" data-id="' + a.id + '">Approved</button>';
    else if (s === 'dismissed') ctl = '<button class="btn" data-act="restore" data-id="' + a.id + '">Restore</button>';
    else ctl = '<button class="btn go" data-act="approve" data-id="' + a.id + '">Approve</button> ' +
      '<button class="btn" data-act="dismiss" data-id="' + a.id + '">Dismiss</button>';
    var title = a.go
      ? '<a href="#" data-act="go" data-id="' + a.id + '" style="color:var(--course)">' + a.what + '</a>'
      : a.what;
    return '<tr' + muted + '>' +
      '<td><input type="checkbox" data-pick="' + a.id + '"' + (picked[a.id] ? ' checked' : '') + (s !== 'open' ? ' disabled' : '') + ' aria-label="Select action"></td>' +
      '<td><strong>' + title + '</strong><div class="muted">' + a.why + '</div></td>' +
      '<td>' + a.owner + '</td>' +
      '<td>' + a.conf.toFixed(2) + '</td>' +
      '<td>' + (a.high ? '<span class="tag warn">Needs approval</span>' : '') + '</td>' +
      '<td style="white-space:nowrap">' + ctl + '</td></tr>';
  }

  function render(el, ctx) {
    var roles = ['All', 'SDR', 'Marketing', 'AE', 'Product'];
    var list = ACTIONS.filter(function (a) { return filter === 'All' || a.role === filter; });
    var openCount = ACTIONS.filter(function (a) { return state[a.id] === 'open'; }).length;
    el.innerHTML = '<div class="page">' +
      '<h1>Turn intelligence into action</h1>' +
      '<p class="lede">' + openCount + ' open actions drafted by agents from TraceLayer signals. Synthetic data, fictional company.</p>' +
      '<div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;border-bottom:1px solid var(--rule);padding:12px 0">' +
      roles.map(function (r) {
        return '<button class="btn' + (r === filter ? ' go' : '') + '" data-role="' + r + '">' + r + '</button>';
      }).join('') +
      '<span style="flex:1"></span><button class="btn" data-act="batch">Approve selected</button></div>' +
      '<table class="tbl" style="width:100%"><thead><tr><th></th><th>Action</th><th>Owner</th><th>Confidence</th><th>Impact</th><th></th></tr></thead>' +
      '<tbody>' + (list.length ? list.map(row).join('') : '<tr><td colspan="6" class="muted">No actions for this role.</td></tr>') + '</tbody></table></div>';

    el.querySelectorAll('[data-role]').forEach(function (b) {
      b.onclick = function () { filter = b.dataset.role; render(el, ctx); };
    });
    el.querySelectorAll('[data-pick]').forEach(function (c) {
      c.onchange = function () { picked[c.dataset.pick] = c.checked; };
    });
    el.querySelectorAll('[data-act]').forEach(function (b) {
      b.onclick = function (e) {
        e.preventDefault();
        var act = b.dataset.act, id = b.dataset.id;
        var a = ACTIONS.filter(function (x) { return x.id === id; })[0];
        if (act === 'go') { ctx.go(a.go); return; }
        if (act === 'batch') {
          var ids = Object.keys(picked).filter(function (k) { return picked[k] && state[k] === 'open'; });
          if (!ids.length) { ctx.toast('Select at least one open action first'); return; }
          ids.forEach(function (k) { state[k] = 'approved'; picked[k] = false; });
          ctx.toast('Approved ' + ids.length + ' actions');
          ctx.feed('Strategy Agent', ids.length + ' actions approved in batch, routing to owners', 'done');
        } else if (act === 'approve') {
          state[id] = 'approved';
          ctx.toast('Approved: ' + a.what);
          ctx.feed('Strategy Agent', 'Routed to ' + a.owner + ': ' + a.what, 'done');
        } else if (act === 'dismiss') {
          state[id] = 'dismissed'; picked[id] = false;
          ctx.toast('Dismissed: ' + a.what);
        } else if (act === 'restore' || act === 'undo') {
          state[id] = 'open';
          ctx.toast('Reopened: ' + a.what);
        }
        render(el, ctx);
      };
    });
  }

  ONE.view('actions', { title: 'Action Center', render: render });
})();
