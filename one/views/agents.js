/* Agents: fourteen synthetic agents sharing one context for the fictional customer TraceLayer. */
(function () {
  var agents = [
    ['Discovery', 'working', 'Scanning launch posts for agent startups', '12 new accounts match the ICP', 0.82],
    ['Enrichment', 'working', 'Filling headcount and stack for 12 accounts', '9 of 12 run LangChain in production', 0.88],
    ['ICP', 'idle', 'Waiting for next enrichment batch', 'Series A, 20 to 80 people fits best', 0.79],
    ['Signal', 'working', 'Watching jobs, launches, pricing pages', 'RelayOps posted 2 GTM engineer roles', 0.81],
    ['Market', 'idle', 'Weekly market digest queued', 'Agent observability searches up 34%', 0.64],
    ['Competitor', 'working', 'Diffing competitor pricing pages', 'Spanwise moved upmarket', 0.72],
    ['Relationship', 'idle', 'Mapping warm paths to target accounts', 'Customer Lumen can introduce RelayOps', 0.76],
    ['Outreach', 'waiting approval', 'Drafts for 12 accounts ready', 'Personalized openers average 61 words', 0.7],
    ['Marketing', 'working', 'Testing new LinkedIn copy', 'Qualified conversion down 18% in 3 weeks', 0.69],
    ['Event', 'waiting approval', 'Follow-ups for 8 dinner attendees', '3 attendees asked about pilots', 0.74],
    ['Revenue', 'working', 'Reforecasting Q1 pipeline', '4 opportunities stalled on timeline', 0.71],
    ['Product Intelligence', 'idle', 'Clustering call transcripts', 'Salesforce sync asked on 7 calls, $84k', 0.78],
    ['Strategy', 'waiting approval', 'Budget shift from paid ads to events', 'Move $1,500, events convert 2.3x', 0.66],
    ['Evaluation', 'working', 'Scoring last week of agent calls', '2 drafts flagged for unsupported claims', 0.9]
  ].map(function (r) { return { name: r[0], status: r[1], task: r[2], finding: r[3], conf: r[4] }; });

  var tasks = [
    'Re-ranking accounts after new signals', 'Reading 3 new call transcripts', 'Checking claims against source pages',
    'Merging duplicate contacts', 'Drafting weekly summary', 'Comparing win rates by channel', 'Watching for reply intent'
  ];
  var statuses = ['working', 'idle', 'working', 'waiting approval'];
  var tick = 0, decided = null;

  function mark(s) { return '<span class="fixmark ' + (s === 'working' ? 'now' : s === 'idle' ? 'good' : 'bad') + '"></span>'; }
  function tag(s) { return '<span class="tag ' + (s === 'working' ? 'info' : s === 'idle' ? 'good' : 'warn') + '">' + s + '</span>'; }

  var thread = [
    ['Discovery Agent', 'RelayOps is a strong ICP match: Series A, 34 people, agents in production.'],
    ['Revenue Agent', 'The last meeting says they are not ready for 60 days. Cold outreach now burns the account.'],
    ['Relationship Agent', 'An existing customer can introduce them when the window opens.'],
    ['Strategy Agent', 'Defer cold outreach. Prepare a warm intro through the customer for day 55.']
  ];

  function render(el, ctx) {
    function draw() {
      el.innerHTML = '<div class="page"><h1>Fourteen agents, one shared context</h1>' +
        '<p class="lede">Every agent reads and writes the same account memory for TraceLayer. Synthetic data, fictional company.</p>' +
        '<table class="tbl" style="width:100%"><thead><tr><th>Agent</th><th>Status</th><th>Current task</th><th>Last finding</th><th>Confidence</th></tr></thead><tbody>' +
        agents.map(function (a) {
          return '<tr><td>' + mark(a.status) + ' <strong>' + a.name + '</strong></td><td>' + tag(a.status) + '</td><td>' + a.task +
            '</td><td>' + a.finding + '</td><td>' + a.conf.toFixed(2) + '</td></tr>';
        }).join('') + '</tbody></table>' +
        '<h2 style="margin-top:40px;border-top:1px solid var(--rule);padding-top:20px">Disagreement on RelayOps</h2>' +
        '<p class="muted">Agents disagree; the human decides. Synthetic account.</p>' +
        thread.map(function (t) {
          return '<div style="border-bottom:1px solid var(--rule);padding:10px 0"><strong>' + t[0] + '</strong><div>' + t[1] + '</div></div>';
        }).join('') +
        '<div style="display:flex;gap:8px;padding-top:14px;align-items:center">' +
        (decided
          ? '<span class="tag ' + (decided === 'accept' ? 'good' : 'warn') + '">' + (decided === 'accept' ? 'Strategy call accepted' : 'Overridden: cold outreach this week') + '</span> <button class="btn" data-d="reset">Reopen</button>'
          : '<button class="btn go" data-d="accept">Accept Strategy\'s call</button><button class="btn" data-d="override">Override</button>') +
        '</div></div>';
      el.querySelectorAll('[data-d]').forEach(function (b) {
        b.onclick = function () {
          var d = b.dataset.d;
          if (d === 'accept') {
            decided = 'accept';
            ctx.toast('Accepted: warm intro to RelayOps scheduled for day 55');
            ctx.feed('Strategy Agent', 'RelayOps: cold outreach deferred, warm intro prepared', 'done');
          } else if (d === 'override') {
            decided = 'override';
            ctx.toast('Overridden: Outreach Agent will contact RelayOps this week');
            ctx.feed('Outreach Agent', 'RelayOps moved to this week by human override', 'warn');
          } else {
            decided = null;
            ctx.toast('Decision reopened');
          }
          draw();
        };
      });
    }
    draw();
    ctx.every(3000, function () {
      tick += 1;
      for (var i = 0; i < 3; i++) {
        var a = agents[(tick * 5 + i * 4) % agents.length];
        a.status = statuses[(tick + i) % statuses.length];
        a.task = tasks[(tick + i * 2) % tasks.length];
      }
      draw();
    });
  }

  ONE.view('agents', { title: 'Agents', render: render });
})();
