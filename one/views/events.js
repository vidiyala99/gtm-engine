/* ONE view: Events. Synthetic data for fictional customer TraceLayer. */
(function () {
  var attendees = [
    { name: 'Maya Okafor', co: 'Stackwell', role: 'pilot' },
    { name: 'Daniel Reyes', co: 'Kiln AI', role: 'pilot' },
    { name: 'Priya Natarajan', co: 'Northgate Ventures', role: 'investor' },
    { name: 'Tom Albrecht', co: 'Vectorline', role: 'referral' },
    { name: 'Lena Cho', co: 'Promptwise', role: 'partner' },
    { name: 'Sam Whitfield', co: 'Agentry', role: 'pilot' },
    { name: 'Ines Duarte', co: 'Cobalt Labs', role: 'referral' },
    { name: 'Raj Mehta', co: 'Outpost Cloud', role: 'partner' }
  ];
  var sent = {};
  var roleTag = { pilot: 'good', referral: 'info', investor: 'warn', partner: 'info' };

  ONE.view('events', {
    title: 'Events',
    render: function (el, ctx) {
      el.innerHTML =
        '<div class="page">' +
        '<h1>Events build relationships, not just leads</h1>' +
        '<p class="lede">One dinner, read as a relationship map. Synthetic data for TraceLayer.</p>' +
        '<h2 style="font-size:26px;margin:32px 0 4px">AI Infrastructure Founders Dinner</h2>' +
        '<p class="muted">Spend $2,400. Attributed open pipeline <b style="color:var(--ink)">$96,000</b>.</p>' +
        '<div class="grid2" style="gap:40px;margin-top:20px;align-items:start">' +
        '<table class="tbl"><tbody>' +
        '<tr><td>Registrations</td><td style="text-align:right">82</td></tr>' +
        '<tr><td>Attendees</td><td style="text-align:right">64</td></tr>' +
        '<tr><td>Already in CRM</td><td style="text-align:right">21</td></tr>' +
        '<tr><td>New to CRM</td><td style="text-align:right"><b>43</b></td></tr>' +
        '</tbody></table>' +
        '<div style="border-left:1px solid var(--rule);padding-left:24px">' +
        '<div class="muted" style="margin-bottom:8px">What the room produced</div>' +
        line(8, 'pilot conversations') + line(11, 'referral partners') + line(5, 'warm intro paths') +
        line(4, 'partnerships') + line(3, 'follow-ups') +
        '</div></div>' +
        '<h2 style="font-size:22px;margin:40px 0 8px">Who to follow up with</h2>' +
        '<table class="tbl"><thead><tr><th>Person</th><th>Company</th><th>Role</th><th></th></tr></thead>' +
        '<tbody id="ev-att"></tbody></table>' +
        '<div style="margin-top:16px;display:flex;gap:8px">' +
        '<button class="btn go" id="ev-plan">Plan next event</button>' +
        '<button class="btn" id="ev-all">Follow up with all</button></div>' +
        '<h2 style="font-size:22px;margin:40px 0 8px">Earlier events</h2>' +
        '<table class="tbl"><thead><tr><th>Event</th><th>Attendees</th><th>Spend</th><th>Pipeline</th></tr></thead><tbody>' +
        '<tr><td>Observability Meetup, SF</td><td>38</td><td>$1,400</td><td>$54,000</td></tr>' +
        '<tr><td>LLM Ops Breakfast, NYC</td><td>22</td><td>$1,000</td><td>$36,000</td></tr>' +
        '</tbody></table>' +
        '<p class="muted" style="margin-top:12px">All names and companies are fictional.</p>' +
        '</div>';

      function line(n, label) {
        return '<div style="display:flex;gap:12px;align-items:baseline;border-bottom:1px solid var(--rule);padding:6px 0">' +
          '<span style="font-family:var(--chart);font-size:28px;min-width:40px">' + n + '</span><span>' + label + '</span></div>';
      }

      var tb = el.querySelector('#ev-att');
      function draw() {
        tb.innerHTML = attendees.map(function (a, i) {
          var done = sent[a.name];
          return '<tr><td>' + a.name + '</td><td>' + a.co + '</td><td><span class="tag ' + roleTag[a.role] + '">' + a.role +
            '</span></td><td style="text-align:right">' +
            (done ? '<button class="btn ok" disabled>Sent</button>' : '<button class="btn" data-i="' + i + '">Follow up</button>') +
            '</td></tr>';
        }).join('');
        tb.querySelectorAll('button[data-i]').forEach(function (b) {
          b.onclick = function () {
            var a = attendees[+b.getAttribute('data-i')];
            sent[a.name] = true;
            draw();
            ctx.toast('Follow-up sent to ' + a.name);
            ctx.feed('Outreach Agent', 'Sent dinner follow-up to ' + a.name + ' (' + a.role + ')', 'done');
          };
        });
      }
      draw();

      el.querySelector('#ev-all').onclick = function () {
        var n = 0;
        attendees.forEach(function (a) { if (!sent[a.name]) { sent[a.name] = true; n++; } });
        draw();
        ctx.toast(n ? 'Sent ' + n + ' follow-ups' : 'Everyone already has a follow-up');
      };
      el.querySelector('#ev-plan').onclick = function () {
        ctx.toast('Drafted next dinner: 60 seats, 40% referral partners, est. $2,600');
        ctx.feed('Events Agent', 'Proposed next Founders Dinner based on referral yield', 'find');
      };
    }
  });
})();
