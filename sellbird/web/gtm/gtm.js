// ── GTM workspace (lane C) ──
//
// One run of the GTM engine, read from /api/gtm/runs/{id} (or the fictional
// fixture), drawn as: intake, ICP, leads, competitors, graph path, the draft
// queue (the human-in-the-loop gate), the pipeline, and the agent feed.
//
// Plain script, no build. It reuses app.js globals: api, escHtml, showToast,
// relTime, currentTab. Every handler is delegated from #gtm via data-act.

const GTM_FIXTURE = 'fixture';
const GTM_POLL_MS = 3000;
const GTM_RUNS_KEY = 'gtm-runs';
const GTM_VIEWS = [
  ['intake', 'Intake'], ['icp', 'ICP'], ['leads', 'Leads'], ['competitors', 'Competitors'],
  ['graph', 'Graph'], ['drafts', 'Drafts'], ['pipeline', 'Pipeline'],
];
const GTM_STAGES = [
  ['matched', 'Matched'], ['contacted', 'Contacted'], ['replied', 'Replied'],
  ['meeting', 'Meeting'], ['closed', 'Closed'],
];
const GTM_STAGE_ORDER = ['matched', 'contacted', 'replied', 'meeting', 'closed_won', 'closed_lost'];
const GTM_EMAIL = {
  verified: ['t-good', 'Verified'], catch_all: ['t-waiting', 'Catch-all'], risky: ['t-waiting', 'Risky'],
  guess: ['t-idle', 'Guess'], invalid: ['t-bad', 'Invalid'], unknown: ['t-idle', 'Unknown'],
};
const GTM_PATHS = [
  ['warm_intro', 'Warm intro'], ['buying_cycle', 'Buying cycle'], ['competitor_displacement', 'Competitor displacement'],
];

const gtm = {
  runId: sessionStorage.getItem('gtm-run') || '',  // '' until the run list says which real run is newest
  run: null,
  error: '',
  view: sessionStorage.getItem('gtm-view') || 'leads',
  intakeMode: 'form',
  leadFilter: 'all',
  draftFilter: 'pending',
  auditActor: 'all',
  pathKind: 'warm_intro',
  path: null,          // {kind, source: 'api'|'local', nodes, edges}
  feed: null,          // band feed, when lane B serves it
  runs: [],
  maskEmails: true,
  editing: null,       // draft id being edited
  rejecting: null,     // draft id waiting for a reason
  adjusting: null,     // expansion index being adjusted
  timer: null,
  updatedAt: null,
  bound: false,
};

// ── Small helpers ──

function gEsc(s) { return escHtml(s); }

function gUrl(u) {
  try {
    const url = new URL(String(u || ''));
    return url.protocol === 'https:' || url.protocol === 'http:' ? url.href : '';
  } catch { return ''; }
}

function gHost(u) {
  try { return new URL(u).hostname.replace(/^www\./, ''); } catch { return ''; }
}

function gIcon(id, cls) {
  return '<svg class="icon' + (cls ? ' ' + cls : '') + '" aria-hidden="true"><use href="#' + id + '"/></svg>';
}

// One toast at a time: a new one replaces the one still showing, so two never overlap.
function gToast(msg, type) {
  document.querySelectorAll('body > .toast').forEach(t => t.remove());
  showToast(msg, type);
}

// An event's own cost: blank when it cost nothing, never rounded down to $0.000.
function gEventCost(n) {
  const v = Number(n) || 0;
  if (v <= 0) return '';
  return v < 0.001 ? '<$0.001' : gMoney(v);
}

function gMoney(n) {
  const v = Number(n) || 0;
  return '$' + (v < 1 ? v.toFixed(3) : v.toFixed(2));
}

function gNum(n) { return (Number(n) || 0).toLocaleString('en-US'); }

function gTime(iso) {
  const d = new Date(iso);
  if (isNaN(d)) return '';
  return d.toLocaleTimeString([], {hour: '2-digit', minute: '2-digit', second: '2-digit'});
}

function gConf(c) {
  const v = Math.max(0, Math.min(1, Number(c) || 0));
  const tone = v >= 0.75 ? 'hi' : v >= 0.5 ? 'mid' : 'lo';
  const word = v >= 0.75 ? 'high' : v >= 0.5 ? 'medium' : 'low';
  return '<span class="gtm-conf ' + tone + '" title="Confidence ' + v.toFixed(2) + ' (' + word + ')">' +
    v.toFixed(2) + '</span>';
}

function gScore(n, label) {
  const v = Math.max(0, Math.min(100, Number(n) || 0));
  return '<span class="gtm-score" title="' + label + ' ' + v + ' of 100"><b>' + v + '</b>' +
    '<i style="--w:' + v + '%"></i></span>';
}

function gTier(t) { return '<span class="gtm-tier t' + gEsc(t) + '" title="Tier ' + gEsc(t) + '">' + gEsc(t) + '</span>'; }

function gEmailBadge(status) {
  const [tone, word] = GTM_EMAIL[status] || GTM_EMAIL.unknown;
  return '<span class="badge ' + tone + '">' + word + '</span>';
}

function gCite(c, opts) {
  if (!c) return '';
  const href = gUrl(c.url);
  const label = c.title || gHost(c.url) || 'source';
  const tip = [c.quote ? '"' + c.quote + '"' : '', c.provider, gHost(c.url)].filter(Boolean).join('\n');
  if (!href) return '<span class="gtm-cite muted">' + gEsc(label) + '</span>';
  return '<a class="gtm-cite" href="' + gEsc(href) + '" target="_blank" rel="noopener noreferrer" title="' + gEsc(tip) + '">' +
    gIcon('i-arrow') + '<span>' + gEsc(label) + '</span>' +
    (opts && opts.host ? '<span class="gtm-cite-host">' + gEsc(gHost(c.url)) + '</span>' : '') + '</a>';
}

function gMaskEmail(e) {
  if (!e || !gtm.maskEmails || gtm.runId === GTM_FIXTURE) return e || '';
  const at = e.indexOf('@');
  return at < 1 ? e : e[0] + '•••' + e.slice(at);
}

function gIsLocal() { return gtm.runId === GTM_FIXTURE; }

function gIndex(run) {
  const companies = Object.create(null), people = Object.create(null), signals = Object.create(null);
  const leadByCompany = Object.create(null), leadByPerson = Object.create(null);
  (run.companies || []).forEach(c => {
    companies[c.id] = c;
    (c.signals || []).forEach(s => { signals[s.id] = Object.assign({company_id: c.id}, s); });
  });
  (run.people || []).forEach(p => { people[p.id] = p; });
  (run.leads || []).forEach(l => {
    leadByCompany[l.company_id] = l;
    if (l.person_id) leadByPerson[l.person_id] = l;
  });
  return {companies, people, signals, leadByCompany, leadByPerson};
}

// ── Loading and polling ──

async function loadGtm() {
  const root = document.getElementById('gtm');
  if (!root) return;
  if (!gtm.bound) { gBind(root); gtm.bound = true; }
  if (!gtm.runId) {  // nothing picked in this tab yet: open the newest real run, else the fixture
    await gLoadRuns();
    gtm.runId = gtm.newestReal || GTM_FIXTURE;
    await gLoadRun();
  } else await Promise.all([gLoadRun(), gLoadRuns()]);
  gRender();
  gSchedule();
}

async function gLoadRun() {
  const path = gtm.runId === GTM_FIXTURE ? '/api/gtm/runs/fixture'
    : '/api/gtm/runs/' + encodeURIComponent(gtm.runId);
  const data = await api(path);
  if (!data || data.success === false || !data.intake) {
    gtm.error = gtm.runId === GTM_FIXTURE
      ? 'The fixture run did not load. Is the gtm extension installed (pip install -e .)?'
      : 'Run ' + gtm.runId + ' did not load. The pipeline routes may not be running on this server yet.';
    if (!gtm.run || gtm.run.id !== gtm.runId) gtm.run = null;
    return;
  }
  gtm.error = '';
  // The fixture is read-only on the server: keep this tab's own decisions on it.
  if (gIsLocal() && gtm.run && gtm.run.id === GTM_FIXTURE) return;
  gtm.run = data;
  gtm.updatedAt = new Date();
  await gLoadFeed();
}

async function gLoadFeed() {
  const feed = await api('/api/gtm/band/feed');
  gtm.feed = feed && !feed.detail ? feed : null;
}

// Lane B lists drafts waiting on the rep as [run_id, draft_id] pairs (or "run/draft").
function gAwaitingRep(draftId) {
  const list = gtm.feed && gtm.feed.awaiting_rep || [];
  return list.some(x => Array.isArray(x) ? x[0] === gtm.runId && x[1] === draftId
    : String(x) === gtm.runId + '/' + draftId || String(x) === draftId);
}

async function gLoadRuns() {
  const saved = (() => { try { return JSON.parse(localStorage.getItem(GTM_RUNS_KEY) || '[]'); } catch { return []; } })();
  const listed = await api('/api/gtm/runs');
  const fromApi = Array.isArray(listed) ? listed
    : (listed && (Array.isArray(listed.ids) ? listed.ids : Array.isArray(listed.runs) ? listed.runs : [])) || [];
  const seen = new Set([GTM_FIXTURE]);
  const runs = [{id: GTM_FIXTURE, label: 'Fixture (fictional)'}];
  fromApi.concat(saved).forEach(r => {
    const id = typeof r === 'string' ? r : r && r.id;
    if (!id || seen.has(id)) return;
    seen.add(id);
    const product = r && r.intake && r.intake.product || r && r.product || r && r.label || '';
    runs.push({id, label: product ? product + ' (' + id + ')' : id});
  });
  if (gtm.runId && !seen.has(gtm.runId)) runs.push({id: gtm.runId, label: gtm.runId});
  gtm.runs = runs;
  // Real run ids start with their UTC start time (run_YYYYmmddHHMMSS_…), so the largest is the newest.
  const real = fromApi.map(r => typeof r === 'string' ? r : r && r.id).filter(id => id && id !== GTM_FIXTURE);
  const stamped = real.filter(id => /^run_\d{14}/.test(id)).sort();
  gtm.newestReal = stamped.length ? stamped[stamped.length - 1] : real[real.length - 1] || '';
}

function gRemember(id, label) {
  try {
    const list = JSON.parse(localStorage.getItem(GTM_RUNS_KEY) || '[]').filter(r => r.id !== id);
    list.unshift({id, label});
    localStorage.setItem(GTM_RUNS_KEY, JSON.stringify(list.slice(0, 20)));
  } catch { /* storage off: the picker still lists the API's runs */ }
}

function gSchedule() {
  clearTimeout(gtm.timer);
  if (gIsLocal()) return;
  gtm.timer = setTimeout(async () => {
    if (typeof currentTab !== 'undefined' && currentTab !== 'gtm') return;
    if (document.hidden) { gSchedule(); return; }
    if (!gtm.editing && !gtm.rejecting && gtm.adjusting === null) {
      const before = JSON.stringify(gtm.run);
      await gLoadRun();
      if (JSON.stringify(gtm.run) !== before) gRender();
      else gRenderLive();
    }
    gSchedule();
  }, gtm.run && gRunStatus(gtm.run) !== 'running' ? GTM_POLL_MS * 4 : GTM_POLL_MS);
}

async function gSwitchRun(id) {
  gtm.runId = id;
  gtm.run = null;
  gtm.path = null;
  sessionStorage.setItem('gtm-run', id);
  gRender();
  await gLoadRun();
  gRender();
  gSchedule();
}

// ── Actions (fixture: local to this tab; real runs: lane A's routes) ──

function gAudit(action, target, detail) {
  gtm.run.audit = gtm.run.audit || [];
  gtm.run.audit.push({at: new Date().toISOString(), actor: 'rep', agent: 'dashboard', action, target,
    detail: detail || '', tokens: 0, cost_usd: 0});
}

async function gPost(path, body, applyLocal, okMsg) {
  if (gIsLocal()) {
    applyLocal();
    gRender();
    gToast(okMsg + ' (fixture: kept in this tab only)', 'success');
    return true;
  }
  const res = await api('/api/gtm/runs/' + encodeURIComponent(gtm.runId) + path, {
    method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body),
  });
  if (!res || res.success === false) {
    gToast(failMsg(res, 'The server did not accept that.') + '', 'error');
    return false;
  }
  gToast(okMsg, 'success');
  if (res.intake && res.id === gtm.runId) { gtm.run = res; gtm.updatedAt = new Date(); }  // lane A answers with the run
  else await gLoadRun();
  gRender();
  return true;
}

async function gAgentReview(draftId) {
  const res = await api('/api/gtm/band/review/' + encodeURIComponent(gtm.runId) + '/' + encodeURIComponent(draftId), {method: 'POST'});
  if (!res || res.success === false) { gToast(failMsg(res, 'The agent review did not start.'), 'error'); return; }
  gToast('Agent review started: planner, builder, reviewer, security', 'success');
  await gLoadFeed();
  gRender();
}

function gDraftAction(id, action, extra) {
  const d = (gtm.run.drafts || []).find(x => x.id === id);
  if (!d) return;
  const body = Object.assign({action}, extra || {});
  const words = {approve: 'Approved', reject: 'Rejected', edit: 'Edit saved'};
  return gPost('/drafts/' + encodeURIComponent(id), body, () => {
    if (action === 'approve') d.status = 'approved';
    if (action === 'reject') {
      d.status = 'rejected';
      d.review_notes = (d.review_notes || []).concat(['rep: ' + (extra && extra.note || 'rejected without a note')]);
    }
    if (action === 'edit') d.body = extra.body;
    gAudit('draft.' + action, id, extra && extra.note || '');
  }, words[action]);
}

function gExpansionAction(i, status, segment) {
  const e = gtm.run.icp && gtm.run.icp.expansions && gtm.run.icp.expansions[i];
  if (!e) return;
  const words = {accepted: 'Segment accepted', adjusted: 'Segment adjusted', dismissed: 'Segment dismissed'};
  const body = {status};
  if (segment) body.segment = segment;
  return gPost('/expansions/' + i, body, () => {
    const before = e.segment;
    e.status = status;
    if (segment) e.segment = segment;
    gAudit('expansion_' + status, 'expansion:' + i, segment && segment !== before ? before + ' -> ' + segment : before);
  }, words[status]);
}

function gLeadAction(companyId, stage) {
  const lead = (gtm.run.leads || []).find(l => l.company_id === companyId);
  return gPost('/leads/' + encodeURIComponent(companyId), {stage}, () => {
    if (lead) { lead.stage = stage; lead.owner = 'rep'; }
    else gtm.run.leads.push({company_id: companyId, person_id: '', stage, owner: 'rep'});
    gAudit('lead.stage', companyId, stage);
  }, 'Moved to ' + stage.replace('closed_', 'closed ').replace('_', ' '));
}

async function gSubmitIntake(form) {
  const err = form.querySelector('.gtm-form-error');
  let intake;
  if (gtm.intakeMode === 'chat') {
    const text = (form.elements.oneliner.value || '').trim();
    if (text.length < 20) { err.textContent = 'Describe the product in a sentence or two (at least 20 characters).'; return; }
    intake = gIntakeFromText(text);
  } else {
    const lines = name => (form.elements[name].value || '').split('\n').map(s => s.trim()).filter(Boolean);
    intake = {
      product: form.elements.product.value.trim(),
      description: form.elements.description.value.trim(),
      features: lines('features'), constraints: lines('constraints'), customers: lines('customers'),
      pricing: form.elements.pricing.value.trim(),
    };
    if (!intake.product || !intake.description) {
      err.textContent = 'Product and description are required.';
      return;
    }
  }
  err.textContent = '';
  const btn = form.querySelector('button[type=submit]');
  btn.disabled = true;
  btn.textContent = 'Starting run…';
  const res = await api('/api/gtm/runs', {
    method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(intake),
  });
  btn.disabled = false;
  btn.textContent = 'Start run';
  const id = res && (res.id || res.run_id);
  if (!id) {
    err.textContent = 'The run did not start: ' + failMsg(res, 'no answer from POST /api/gtm/runs') +
      '. The pipeline routes may not be on this server yet.';
    return;
  }
  gRemember(id, intake.product);
  gtm.view = 'icp';
  sessionStorage.setItem('gtm-view', 'icp');
  gToast('Run ' + id + ' started', 'success');
  await gLoadRuns();
  gSwitchRun(id);
}

// "Name is a ... for ..." or "Name: ..." gives the product name; the rest of
// the text goes to the pipeline as the description, untouched.
function gIntakeFromText(text) {
  const m = text.match(/^\s*([A-Z][\w.\- ]{1,40}?)(?:\s+(?:is|are)\s+|\s*[:,]\s+)/);
  const priced = text.match(/[^.]*(?:\$\s?\d|pricing|per seat|per month|\/mo|\/yr|usage-based)[^.]*\./i);
  return {
    product: m ? m[1].trim() : text.split(/\s+/).slice(0, 3).join(' '),
    description: text, features: [], constraints: [], customers: [],
    pricing: priced ? priced[0].trim() : '',
  };
}

// ── Events ──

function gBind(root) {
  root.addEventListener('click', e => {
    const el = e.target.closest('[data-act]');
    if (!el || !root.contains(el)) return;
    const a = el.dataset.act, v = el.dataset.v;
    if (a === 'view') { gtm.view = v; sessionStorage.setItem('gtm-view', v); gRender(); }
    else if (a === 'intake-mode') { gtm.intakeMode = v; gRender(); }
    else if (a === 'lead-filter') { gtm.leadFilter = v; gRender(); }
    else if (a === 'draft-filter') { gtm.draftFilter = v; gRender(); }
    else if (a === 'audit-actor') { gtm.auditActor = v; gRender(); }
    else if (a === 'mask') { gtm.maskEmails = !gtm.maskEmails; gRender(); }
    else if (a === 'path') { gtm.pathKind = v; gtm.path = null; gRender(); }
    else if (a === 'path-step' && gtm.path) {
      gtm.path.i = Math.max(0, Math.min(gtm.path.paths.length - 1, gtm.path.i + Number(v)));
      gRender();
    }
    else if (a === 'approve') gDraftAction(v, 'approve');
    else if (a === 'edit') { gtm.editing = v; gtm.rejecting = null; gRender(); gFocus('#gtm-edit-' + v); }
    else if (a === 'edit-cancel') { gtm.editing = null; gRender(); }
    else if (a === 'edit-save') {
      const body = document.getElementById('gtm-edit-' + v).value.trim();
      if (!body) { gToast('A draft cannot be empty', 'error'); return; }
      gtm.editing = null;
      gDraftAction(v, 'edit', {body});
    }
    else if (a === 'reject') { gtm.rejecting = v; gtm.editing = null; gRender(); gFocus('#gtm-reject-' + v); }
    else if (a === 'reject-cancel') { gtm.rejecting = null; gRender(); }
    else if (a === 'reject-save') {
      const note = document.getElementById('gtm-reject-' + v).value.trim();
      gtm.rejecting = null;
      gDraftAction(v, 'reject', {note});
    }
    else if (a === 'exp') gExpansionAction(Number(el.dataset.i), v);
    else if (a === 'exp-adjust') { gtm.adjusting = Number(el.dataset.i); gRender(); gFocus('#gtm-adjust-' + el.dataset.i); }
    else if (a === 'exp-adjust-cancel') { gtm.adjusting = null; gRender(); }
    else if (a === 'exp-adjust-save') {
      const i = Number(el.dataset.i);
      const segment = document.getElementById('gtm-adjust-' + i).value.trim();
      if (!segment) { gToast('Write the segment as it should read', 'error'); return; }
      gtm.adjusting = null;
      gExpansionAction(i, 'adjusted', segment);
    }
    else if (a === 'review') gAgentReview(v);
    else if (a === 'refresh') loadGtm();
  });
  root.addEventListener('change', e => {
    const el = e.target;
    if (el.id === 'gtm-run-picker') gSwitchRun(el.value);
    else if (el.dataset.act === 'stage') { if (el.value) gLeadAction(el.dataset.company, el.value); }
  });
  root.addEventListener('submit', e => {
    if (e.target.id === 'gtm-intake-form') { e.preventDefault(); gSubmitIntake(e.target); }
  });
}

function gFocus(sel) {
  const el = document.querySelector(sel);
  if (el) { el.focus(); if (el.setSelectionRange) el.setSelectionRange(el.value.length, el.value.length); }
}

// ── Render ──

function gRender() {
  const root = document.getElementById('gtm');
  if (!root) return;
  const run = gtm.run;
  const head = gHead(run);
  if (!run) {
    root.innerHTML = head + (gtm.error
      ? emptyState('!', 'No run to show', gEsc(gtm.error) + ' Pick another run above, or start one from Intake.')
      : '<div class="gtm-skeleton" aria-busy="true"><i></i><i></i><i></i><i></i></div>');
    return;
  }
  const ix = gIndex(run);
  const views = {intake: gIntake, icp: gIcp, leads: gLeads, competitors: gCompetitors,
    graph: gGraph, drafts: gDrafts, pipeline: gPipeline};
  const body = (views[gtm.view] || gLeads)(run, ix);
  root.innerHTML = head +
    '<div class="gtm-layout">' +
      '<div class="gtm-main" id="gtm-view-' + gEsc(gtm.view) + '">' + body + '</div>' +
      '<aside class="gtm-aside">' + gThinking(run) + '</aside>' +
    '</div>';
  if (gtm.view === 'graph') gGraphLoad(run, ix);
}

function gRenderLive() {
  const el = document.getElementById('gtm-live');
  if (el) el.innerHTML = gLiveText();
}

// Run.status, or, while it still says running, what the pipeline's own audit log
// says: the runner logs run_finished or step_failed even when it leaves status alone.
function gRunStatus(run) {
  const st = run.status || 'running';
  if (st !== 'running') return st;
  const last = (run.audit || []).filter(e => e.actor !== 'rep' &&
    ['run_started', 'run_finished', 'step_failed'].includes(e.action)).pop();
  return !last ? st : last.action === 'run_finished' ? 'done' : last.action === 'step_failed' ? 'failed' : st;
}

function gLiveText() {
  if (gIsLocal()) return '<span class="mini t-idle">Fixture, fictional data</span>';
  if (gtm.error) return '<span class="mini t-bad">Not loading</span>';
  const st = gtm.run && gRunStatus(gtm.run);
  const badge = st === 'failed' ? '<span class="mini t-bad">Run failed</span>'
    : st === 'done' ? '<span class="mini t-good">Run done</span>'
    : '<span class="mini t-active">Running, live</span>';
  return badge + ' <span class="muted">updated ' +
    (gtm.updatedAt ? gtm.updatedAt.toLocaleTimeString([], {hour: '2-digit', minute: '2-digit', second: '2-digit'}) : '') + '</span>';
}

function gHead(run) {
  const opts = gtm.runs.map(r => '<option value="' + gEsc(r.id) + '"' + (r.id === gtm.runId ? ' selected' : '') + '>' +
    gEsc(r.label) + '</option>').join('');
  const title = run ? run.intake.product : 'GTM engine';
  const sub = run ? run.intake.description : 'Intake to cited leads, drafts and pipeline for one product.';
  let facts = '';
  if (run) {
    const cos = run.companies || [], ppl = run.people || [], drafts = run.drafts || [];
    const rejected = cos.filter(c => c.rejected_reason).length;
    const verified = ppl.filter(p => p.email_status === 'verified').length;
    const pending = drafts.filter(d => d.status === 'pending').length;
    const tokens = (run.audit || []).reduce((s, e) => s + (e.tokens || 0), 0);
    const cost = (run.audit || []).reduce((s, e) => s + (e.cost_usd || 0), 0);
    facts = '<div class="facts gtm-facts">' +
      '<span><b>' + cos.length + '</b> companies</span>' +
      '<span><b>' + rejected + '</b> rejected</span>' +
      '<span><b>' + ppl.length + '</b> contacts</span>' +
      '<span><b>' + verified + '</b> verified</span>' +
      '<span><b>' + pending + '</b> drafts waiting</span>' +
      '<span><b>' + gNum(tokens) + '</b> tokens</span>' +
      '<span><b>' + gMoney(cost) + '</b> spent</span>' +
      '<span id="gtm-live">' + gLiveText() + '</span>' +
    '</div>';
  }
  const tabs = GTM_VIEWS.map(([k, label]) => {
    let n = '';
    if (run && k === 'drafts') { const p = (run.drafts || []).filter(d => d.status === 'pending').length; if (p) n = '<span class="n">' + p + '</span>'; }
    if (run && k === 'leads') n = '<span class="n">' + (run.companies || []).length + '</span>';
    return '<button type="button" data-act="view" data-v="' + k + '"' + (gtm.view === k ? ' class="on" aria-current="page"' : '') + '>' + label + n + '</button>';
  }).join('');
  return '<div class="section-head gtm-head">' +
      '<div class="gtm-title"><h2>' + gEsc(title) + '</h2><p>' + gEsc(sub) + '</p></div>' +
      '<div class="page-actions gtm-run-pick">' +
        '<label class="sr-only" for="gtm-run-picker">Run</label>' +
        '<select id="gtm-run-picker" class="form-input gtm-select">' + opts + '</select>' +
        '<button class="btn btn-secondary btn-icon" type="button" data-act="refresh" title="Reload this run" aria-label="Reload this run">' + gIcon('i-refresh') + '</button>' +
      '</div>' +
    '</div>' + facts +
    '<div class="segmented gtm-tabs" role="group" aria-label="GTM views">' + tabs + '</div>';
}

// ── Intake ──

function gIntake(run) {
  const i = run.intake;
  const list = arr => (arr && arr.length) ? '<ul>' + arr.map(x => '<li>' + gEsc(x) + '</li>').join('') + '</ul>' : '<span class="muted">None given</span>';
  const current = '<div class="card gtm-intake-current">' +
    '<div class="card-title">This run\'s intake</div>' +
    '<dl class="gtm-dl">' +
      '<dt>Product</dt><dd>' + gEsc(i.product) + '</dd>' +
      '<dt>Description</dt><dd>' + gEsc(i.description) + '</dd>' +
      '<dt>Features</dt><dd>' + list(i.features) + '</dd>' +
      '<dt>Constraints</dt><dd>' + list(i.constraints) + '</dd>' +
      '<dt>Customers</dt><dd>' + list(i.customers) + '</dd>' +
      '<dt>Pricing</dt><dd>' + (i.pricing ? gEsc(i.pricing) : '<span class="muted">None given</span>') + '</dd>' +
    '</dl></div>';
  const chat = gtm.intakeMode === 'chat';
  const fields = chat
    ? '<div class="form-group"><label class="form-label" for="gtm-oneliner">Describe what you sell</label>' +
        '<textarea class="form-input gtm-oneliner" id="gtm-oneliner" name="oneliner" rows="6" placeholder="PromptQL is a natural-language data agent for enterprise data teams. It plans each query so it can be checked. Contracts start at…"></textarea>' +
        '<div class="form-hint">One box is enough: the pipeline reads features, customers and pricing out of it.</div></div>'
    : '<div class="form-row"><div class="form-group"><label class="form-label" for="gtm-product">Product</label>' +
        '<input class="form-input" id="gtm-product" name="product" autocomplete="off" required></div>' +
        '<div class="form-group"><label class="form-label" for="gtm-pricing">Pricing</label>' +
        '<input class="form-input" id="gtm-pricing" name="pricing" autocomplete="off" placeholder="Usage-based, from $30k a year"></div></div>' +
      '<div class="form-group"><label class="form-label" for="gtm-description">Description</label>' +
        '<textarea class="form-input" id="gtm-description" name="description" rows="3" required></textarea></div>' +
      '<div class="gtm-form-3">' +
        '<div class="form-group"><label class="form-label" for="gtm-features">Features</label>' +
          '<textarea class="form-input" id="gtm-features" name="features" rows="4" placeholder="One per line"></textarea></div>' +
        '<div class="form-group"><label class="form-label" for="gtm-constraints">Constraints</label>' +
          '<textarea class="form-input" id="gtm-constraints" name="constraints" rows="4" placeholder="One per line"></textarea></div>' +
        '<div class="form-group"><label class="form-label" for="gtm-customers">Current customers</label>' +
          '<textarea class="form-input" id="gtm-customers" name="customers" rows="4" placeholder="One per line"></textarea></div>' +
      '</div>';
  const form = '<form class="card" id="gtm-intake-form" novalidate>' +
    '<div class="card-title gtm-split">Start a run' +
      '<span class="segmented" role="group" aria-label="Intake style">' +
        '<button type="button" data-act="intake-mode" data-v="form"' + (chat ? '' : ' class="on" aria-pressed="true"') + '>Form</button>' +
        '<button type="button" data-act="intake-mode" data-v="chat"' + (chat ? ' class="on" aria-pressed="true"' : '') + '>One box</button>' +
      '</span></div>' +
    fields +
    '<p class="gtm-form-error" role="alert"></p>' +
    '<div class="gtm-form-foot"><button class="btn btn-primary" type="submit">Start run</button>' +
      '<span class="muted">Runs ICP, discovery, enrichment and drafts. Nothing is sent without your approval.</span></div>' +
  '</form>';
  return '<div class="gtm-intake">' + form + current + '</div>';
}

// ── ICP ──

function gIcp(run) {
  const icp = run.icp;
  if (!icp) return emptyState('…', 'The ICP is being worked out', 'The pipeline is reading the intake. Rows appear here as soon as it has them.');
  const row = (label, value, conf, why, extra) => '<tr><td class="gtm-k">' + label + '</td>' +
    '<td><div class="cell-main">' + gEsc(value) + (extra ? ' <span class="muted">' + extra + '</span>' : '') + '</div>' +
    (why ? '<div class="cell-sub">' + gEsc(why) + '</div>' : '') + '</td>' +
    '<td class="num">' + gConf(conf) + '</td></tr>';
  const rows = [];
  (icp.industries || []).forEach((x, n) => rows.push(row(n ? '' : 'Industry', x.value, x.confidence, x.why, x.naics ? 'NAICS ' + gEsc(x.naics) : '')));
  (icp.headcount_bands || []).forEach((x, n) => rows.push(row(n ? '' : 'Headcount', x.value, x.confidence, x.why)));
  (icp.revenue_bands || []).forEach((x, n) => rows.push(row(n ? '' : 'Revenue', x.value, x.confidence, x.why)));
  (icp.personas || []).forEach((x, n) => rows.push(row(n ? '' : 'Buyer', x.title, x.confidence, '', gEsc((x.seniority || '').replace('_', ' ')))));
  (icp.triggers || []).forEach((x, n) => rows.push(row(n ? '' : 'Trigger', x.value, x.confidence, x.why)));
  const card = '<div class="table-card gtm-icp"><table><thead><tr><th>Field</th><th>Value and why</th><th class="num">Confidence</th></tr></thead>' +
    '<tbody>' + rows.join('') + '</tbody></table></div>';

  const exps = (icp.expansions || []).map((e, i) => {
    const st = e.status || 'proposed';
    const tone = {proposed: 't-waiting', accepted: 't-good', adjusted: 't-active', dismissed: 't-idle'}[st] || 't-idle';
    const adjusting = gtm.adjusting === i;
    const actions = adjusting
      ? '<div class="gtm-inline-form"><label class="sr-only" for="gtm-adjust-' + i + '">Segment as it should read</label>' +
          '<input class="form-input" id="gtm-adjust-' + i + '" value="' + gEsc(e.segment) + '">' +
          '<button class="btn btn-primary btn-sm" type="button" data-act="exp-adjust-save" data-i="' + i + '">Save adjustment</button>' +
          '<button class="btn btn-ghost btn-sm" type="button" data-act="exp-adjust-cancel">Cancel</button></div>'
      : '<div class="gtm-actions">' +
          '<button class="btn btn-sm btn-secondary" type="button" data-act="exp" data-v="accepted" data-i="' + i + '"' + (st === 'accepted' ? ' disabled' : '') + '>' + gIcon('i-check') + 'Accept</button>' +
          '<button class="btn btn-sm btn-secondary" type="button" data-act="exp-adjust" data-i="' + i + '">' + gIcon('i-pen') + 'Adjust</button>' +
          '<button class="btn btn-sm btn-ghost" type="button" data-act="exp" data-v="dismissed" data-i="' + i + '"' + (st === 'dismissed' ? ' disabled' : '') + '>Dismiss</button>' +
        '</div>';
    return '<article class="gtm-exp' + (st === 'dismissed' ? ' is-dismissed' : '') + '">' +
      '<div class="gtm-split"><h3>' + gEsc(e.segment) + '</h3><span class="badge ' + tone + '">' + gEsc(st[0].toUpperCase() + st.slice(1)) + '</span></div>' +
      '<p>' + gEsc(e.rationale) + '</p>' +
      '<ul class="gtm-evidence">' + (e.evidence || []).map(c => '<li>' + gCite(c, {host: true}) +
        (c.quote ? '<q>' + gEsc(c.quote) + '</q>' : '') + '</li>').join('') + '</ul>' +
      actions + '</article>';
  }).join('');
  return '<div class="subhead">Ideal customer profile <span class="hint">confidence runs 0.00 to 1.00</span></div>' + card +
    '<div class="subhead">Expansion segments <span class="hint">accept, adjust or dismiss each one</span></div>' +
    (exps ? '<div class="gtm-exps">' + exps + '</div>' : '<div class="card"><p class="muted">No expansion segments yet.</p></div>');
}

// ── Leads ──

function gLeads(run, ix) {
  const cos = (run.companies || []).slice().sort((a, b) =>
    (!!a.rejected_reason - !!b.rejected_reason) || (b.fit_score + b.intent_score) - (a.fit_score + a.intent_score));
  const counts = {all: cos.length, A: 0, B: 0, C: 0, rejected: 0};
  cos.forEach(c => { if (c.rejected_reason) counts.rejected++; else counts[c.tier]++; });
  const f = gtm.leadFilter;
  const shown = cos.filter(c => f === 'all' || (f === 'rejected' ? !!c.rejected_reason : !c.rejected_reason && c.tier === f));
  const filters = [['all', 'All'], ['A', 'Tier A'], ['B', 'Tier B'], ['C', 'Tier C'], ['rejected', 'Rejected']].map(([k, l]) =>
    '<button type="button" data-act="lead-filter" data-v="' + k + '"' + (f === k ? ' class="on" aria-pressed="true"' : '') + '>' + l + ' <span class="n">' + counts[k] + '</span></button>').join('');
  const peopleBy = Object.create(null);
  (run.people || []).forEach(p => { (peopleBy[p.company_id] = peopleBy[p.company_id] || []).push(p); });

  const rows = shown.map(c => {
    const sigs = (c.signals || []).map(s => '<li class="' + (s.negative ? 'neg' : '') + '">' +
      '<span class="gtm-sig-kind">' + gEsc(s.kind.replace(/_/g, ' ')) + '</span> ' + gEsc(s.summary) +
      (s.observed_on ? ' <span class="muted">' + gEsc(s.observed_on) + '</span>' : '') + ' ' + gCite(s.citation) + '</li>').join('');
    const ppl = (peopleBy[c.id] || []).map(p => '<li><span class="cell-main">' + gEsc(p.name) + '</span> <span class="muted">' + gEsc(p.title) + '</span> ' +
      gEmailBadge(p.email_status) + '</li>').join('');
    const cites = (c.citations || []).map(x => gCite(x)).join('');
    return '<tr class="' + (c.rejected_reason ? 'is-rejected' : '') + '">' +
      '<td class="gtm-co"><div class="cell-main">' + gEsc(c.name) + '</div><div class="cell-sub">' + gEsc(c.domain) +
        (c.hq ? '<br>' + gEsc(c.hq) : '') + '</div><div class="gtm-cites">' + cites + '</div>' +
        (c.rejected_reason ? '<div class="gtm-reason">' + gIcon('i-alert') + '<span>Rejected: ' + gEsc(c.rejected_reason) + '</span></div>' : '') + '</td>' +
      '<td data-label="Tier">' + gTier(c.tier) + '</td>' +
      '<td data-label="Fit">' + gScore(c.fit_score, 'Fit') + '</td>' +
      '<td data-label="Intent">' + gScore(c.intent_score, 'Intent') + '</td>' +
      '<td class="gtm-wrap gtm-full" data-label="Signals"><div class="cell-sub">' + gEsc(c.industry) + (c.headcount ? ', ' + gEsc(c.headcount) + ' staff' : '') + '</div>' +
        (sigs ? '<ul class="gtm-sigs">' + sigs + '</ul>' : '<span class="muted">No signals</span>') + '</td>' +
      '<td class="gtm-wrap gtm-full" data-label="Contacts">' + (ppl ? '<ul class="gtm-ppl">' + ppl + '</ul>' : '<span class="muted">None yet</span>') + '</td>' +
    '</tr>';
  }).join('');
  const table = shown.length
    ? '<div class="table-card gtm-sheet gtm-cards gtm-leads"><table><thead><tr><th>Company and source</th><th>Tier</th><th>Fit</th><th>Intent</th><th>Signals</th><th>Contacts</th></tr></thead><tbody>' + rows + '</tbody></table></div>'
    : emptyState('0', 'No companies here', cos.length ? 'Nothing matches this filter.' : 'Discovery has not returned companies yet. They appear here as the run finds them.');

  return '<div class="toolbar gtm-split"><div class="segmented" role="group" aria-label="Filter companies">' + filters + '</div></div>' +
    table + gContacts(run, ix);
}

function gContacts(run, ix) {
  const ppl = run.people || [];
  if (!ppl.length) return '';
  const rows = ppl.map(p => {
    const co = ix.companies[p.company_id];
    const li = gUrl(p.linkedin_url);
    // Profile sits under the name and MX under the status, so the sheet fits 1440 px without a sideways scroll.
    return '<tr><td class="gtm-co"><div class="cell-main">' + gEsc(p.name) + '</div><div class="cell-sub">' + gEsc(p.title) + '</div>' +
        (li ? '<a class="gtm-profile" href="' + gEsc(li) + '" target="_blank" rel="noopener noreferrer">LinkedIn profile</a>' : '<div class="cell-sub">No LinkedIn found</div>') + '</td>' +
      '<td data-label="Company">' + gEsc(co ? co.name : p.company_id) + '</td>' +
      '<td class="gtm-email gtm-full" data-label="Email">' + (p.email ? gEsc(gMaskEmail(p.email)) : '<span class="muted">None found</span>') + '</td>' +
      '<td data-label="Status"><div class="gtm-stack">' + gEmailBadge(p.email_status) +
        (p.mx_ok === true ? '<span class="mini t-good">MX ok</span>' : p.mx_ok === false ? '<span class="mini t-bad">No MX</span>' : '<span class="mini t-idle">MX not checked</span>') + '</div></td>' +
      '<td class="num" data-label="Confidence">' + gConf(p.confidence) + '</td>' +
      '<td class="gtm-cites gtm-src" data-label="Source">' + (p.citations || []).map(x => gCite(x)).join('') + '</td></tr>';
  }).join('');
  const mask = gIsLocal() ? '' : '<button class="btn btn-sm btn-ghost" type="button" data-act="mask" aria-pressed="' + gtm.maskEmails + '">' +
    (gtm.maskEmails ? 'Show emails' : 'Mask emails') + '</button>';
  return '<div class="subhead">Contacts <span class="hint">' + mask + '</span></div>' +
    '<div class="table-card gtm-sheet gtm-cards"><table><thead><tr><th>Person and profile</th><th>Company</th><th>Email</th><th>Status and MX</th><th class="num">Confidence</th><th>Source</th></tr></thead><tbody>' + rows + '</tbody></table></div>';
}

// ── Competitors ──

function gCompetitors(run) {
  const comps = run.competitors || [];
  if (!comps.length) return emptyState('0', 'No competitors yet', 'The competitor map fills in after discovery.');
  const cols = [['direct', 'Direct', 'Sells the same thing to the same buyer'],
    ['indirect', 'Indirect', 'Solves the same problem another way'],
    ['alternative', 'Alternative', 'What buyers do instead']];
  return '<div class="gtm-comp-grid">' + cols.map(([k, label, hint]) => {
    const items = comps.filter(c => c.kind === k);
    return '<section class="gtm-comp-col"><div class="subhead">' + label + ' <span class="hint">' + hint + '</span></div>' +
      (items.length ? items.map(c => '<article class="card gtm-comp">' +
        '<div class="gtm-split"><h3>' + gEsc(c.name) + '</h3><span class="muted">' + gEsc(c.domain) + '</span></div>' +
        '<p>' + gEsc(c.positioning) + '</p>' +
        (c.pricing_tiers && c.pricing_tiers.length ? '<div class="gtm-k">Pricing</div><div class="gtm-tags">' + c.pricing_tiers.map(t => '<span class="tag">' + gEsc(t) + '</span>').join('') + '</div>' : '<div class="gtm-k">Pricing</div><p class="muted">Not public</p>') +
        (c.differentiators && c.differentiators.length ? '<div class="gtm-k">Differs on</div><div class="gtm-tags">' + c.differentiators.map(t => '<span class="tag">' + gEsc(t) + '</span>').join('') + '</div>' : '') +
        '<div class="gtm-cites">' + (c.citations || []).map(x => gCite(x, {host: true})).join('') + '</div>' +
      '</article>').join('') : '<p class="muted gtm-none">None found</p>') + '</section>';
  }).join('') + '</div>';
}

// ── Graph path ──

function gGraph() {
  const picker = GTM_PATHS.map(([k, l]) => '<button type="button" data-act="path" data-v="' + k + '"' +
    (gtm.pathKind === k ? ' class="on" aria-pressed="true"' : '') + '>' + l + '</button>').join('');
  const set = gtm.path && gtm.path.kind === gtm.pathKind ? gtm.path : null;
  const p = set && set.paths[set.i];
  let body;
  if (!set) body = '<div class="gtm-skeleton short" aria-busy="true"><i></i></div>';
  else if (!p || !p.nodes.length) body = emptyState('0', 'No path of this kind in this run', gEsc(set.note || 'The graph has no matching multi-hop path yet.'));
  else {
    const pager = set.paths.length > 1
      ? '<div class="gtm-pager"><span class="muted">Path ' + (set.i + 1) + ' of ' + set.paths.length + '</span>' +
        '<button class="btn btn-sm btn-secondary" type="button" data-act="path-step" data-v="-1"' + (set.i ? '' : ' disabled') + '>Previous</button>' +
        '<button class="btn btn-sm btn-secondary" type="button" data-act="path-step" data-v="1"' + (set.i < set.paths.length - 1 ? '' : ' disabled') + '>Next</button></div>' : '';
    const sources = p.nodes.filter(n => gUrl(n.url)).map(n => gCite({url: n.url, title: n.label}, {})).join('');
    body = pager + '<figure class="gtm-path" id="gtm-path">' + gPathSvg(p) +
      '<figcaption>' + gEsc(p.note || '') + ' <span class="muted">' +
        (set.source === 'api' ? 'From the knowledge graph' + (set.engine ? ' (' + gEsc(set.engine) + ')' : '') + '.' : 'Worked out in the browser from this run (graph API not reachable).') + '</span></figcaption></figure>' +
      '<ol class="gtm-path-steps">' + p.nodes.map((n, i) => '<li><b>' + gEsc(n.label) + '</b> <span class="muted">' + gEsc(n.type) + '</span>' +
        (p.edges[i] ? ' <span class="gtm-edge-word">' + gEsc(String(p.edges[i].type).replace(/_/g, ' ')) + '</span>' : '') + '</li>').join('') + '</ol>' +
      (sources ? '<div class="gtm-path-sources"><span class="gtm-k">Sources</span>' + sources + '</div>' : '');
  }
  return '<div class="toolbar"><div class="segmented" role="group" aria-label="Path kind">' + picker + '</div></div>' +
    '<div class="card gtm-graph-card">' + body + '</div>';
}

async function gGraphLoad(run, ix) {
  if (gtm.path && gtm.path.kind === gtm.pathKind) return;
  const kind = gtm.pathKind;
  let set = null;
  const data = await api('/api/gtm/runs/' + encodeURIComponent(run.id) + '/paths/' + kind);
  if (data && !data.detail) {
    const list = Array.isArray(data) ? data : data.paths ? data.paths : [data.path && !Array.isArray(data.path) ? data.path : data];
    const paths = list.map(d => gNormalizePath(d, kind)).filter(Boolean);
    set = {kind, source: 'api', engine: data.engine || '', paths, i: 0,
      note: paths.length ? '' : data.note || 'The knowledge graph found no path of this kind in this run.'};
  }
  if (!set) { const lp = gLocalPath(run, ix, kind); set = {kind, source: 'local', paths: lp.nodes.length ? [lp] : [], i: 0, note: lp.note}; }
  if (gtm.pathKind !== kind || gtm.view !== 'graph') return;
  gtm.path = set;
  gRender();
}

// One path from lane B: {summary, nodes, edges}. Field names vary between
// graph libraries, so read the common ones and order nodes along the edges.
function gNormalizePath(d, kind) {
  if (!d) return null;
  if (Array.isArray(d.path)) d = {nodes: d.path.filter(x => !x.source && !x.from), edges: d.path.filter(x => x.source || x.from)};
  // Lane B: {id, label: <node type>, name, props}. Others: {id, label|name, type}.
  const nodes = (d.nodes || []).map(n => {
    const props = n.props || n.properties || {};
    return {id: String(n.id ?? n.key ?? n.name),
      label: n.name || props.name || (n.type ? n.label : '') || n.title || String(n.id),
      type: n.type || n.kind || (n.name ? n.label : '') || (Array.isArray(n.labels) ? n.labels[0] : n.labels) || '',
      sub: props.title || props.summary || props.domain || props.observed_on || '',
      url: props.source_url || props.url || ''};
  });
  const edges = (d.edges || d.relationships || []).map(e => ({source: String(e.source ?? e.from ?? e.src ?? e.start),
    target: String(e.target ?? e.to ?? e.dst ?? e.end), type: e.type || e.kind || e.rel || e.label || ''}));
  if (!nodes.length) return null;
  // Order: walk from a node no edge points into.
  const byId = Object.fromEntries(nodes.map(n => [n.id, n]));
  const touches = id => edges.filter(e => e.source === id || e.target === id);
  // Lane B lists nodes in path order: start at the first one when it is an end.
  let start = touches(nodes[0].id).length <= 1 ? nodes[0] : nodes.find(n => touches(n.id).length <= 1) || nodes[0];
  const ordered = [start], oEdges = [], used = new Set();
  let cur = start.id;
  while (ordered.length < nodes.length) {
    const e = edges.find((x, i) => !used.has(i) && (x.source === cur || x.target === cur));
    if (!e) break;
    used.add(edges.indexOf(e));
    const next = e.source === cur ? e.target : e.source;
    if (!byId[next]) break;
    oEdges.push(Object.assign({}, e, {reverse: e.target === cur}));
    ordered.push(byId[next]);
    cur = next;
  }
  const note = d.summary || d.note || '';
  if (ordered.length < nodes.length) return {kind, nodes, edges, note};
  return {kind, nodes: ordered, edges: oEdges, note};
}

function gLocalPath(run, ix, kind) {
  const empty = note => ({kind, source: 'local', nodes: [], edges: [], note});
  const ppl = run.people || [];
  const contacted = p => { const l = ix.leadByPerson[p.id]; return l && l.stage !== 'matched'; };
  if (kind === 'warm_intro') {
    // Shared past employer or school first (the real warm intro), then a
    // contacted person's old company that the target works at now.
    const tries = [
      (t) => (t.past_employers || []).map(x => [x, 'previously_employed_at']),
      (t) => (t.schools || []).map(x => [x, 'attended']),
      (t) => { const c = ix.companies[t.company_id]; return c ? [[c.name, 'works_at']] : []; },
    ];
    for (const links of tries) {
      for (const target of ppl.filter(p => !contacted(p))) {
        for (const known of ppl.filter(p => p.id !== target.id && contacted(p))) {
          const hit = links(target).find(([x, rel]) =>
            (rel === 'attended' ? known.schools : known.past_employers || []).includes(x));
          if (!hit) continue;
          const [via, rel] = hit;
          const tco = ix.companies[target.company_id], kco = ix.companies[known.company_id];
          return {kind, source: 'local',
            nodes: [{id: target.id, label: target.name, type: 'Person, target', sub: target.title + (tco ? ', ' + tco.name : '')},
              {id: 'via', label: via, type: rel === 'attended' ? 'School' : 'Company', sub: 'Shared history'},
              {id: known.id, label: known.name, type: 'Person, contacted', sub: known.title + (kco ? ', ' + kco.name : '')}],
            edges: [{type: rel}, {type: rel === 'attended' ? 'attended' : 'previously_employed_at', reverse: true}],
            note: 'Ask ' + known.name + ' for an intro to ' + target.name + ': both have ' + via + ' in common.'};
        }
      }
    }
    return empty('No target shares an employer or school with someone already contacted.');
  }
  if (kind === 'buying_cycle') {
    const personas = (run.icp && run.icp.personas || []).map(p => p.title.toLowerCase());
    for (const c of (run.companies || []).filter(x => !x.rejected_reason)) {
      const s = (c.signals || []).find(x => x.kind === 'job_post' && !x.negative);
      if (!s) continue;
      const buyer = ppl.find(p => p.company_id === c.id && personas.includes(p.title.toLowerCase())) || ppl.find(p => p.company_id === c.id);
      const nodes = [{id: s.id, label: s.summary, type: 'Signal', sub: s.observed_on}, {id: c.id, label: c.name, type: 'Company', sub: 'Tier ' + c.tier}];
      const edges = [{type: 'has_signal', reverse: true}];
      if (buyer) { nodes.push({id: buyer.id, label: buyer.name, type: 'Person', sub: buyer.title}); edges.push({type: 'works_at', reverse: true}); }
      return {kind, source: 'local', nodes, edges,
        note: c.name + ' is hiring for the work the product does' + (buyer ? '; ' + buyer.title + ' owns the budget.' : '.')};
    }
    return empty('No matched company has a job post signal yet.');
  }
  return empty('Competitor displacement needs the graph API (lane B): it joins tech-stack and complaint signals.');
}

function gPathSvg(p) {
  // Up to three nodes a row; a longer path turns down to the next row with an
  // elbow, so the type stays full size instead of shrinking to fit.
  const n = p.nodes.length, PER = 3;
  const W = 230, H = 92, GAP = 190, ROWGAP = 70, PAD = 8, TOP = 20;
  const cols = Math.min(n, PER), rows = Math.ceil(n / PER);
  const width = cols * W + (cols - 1) * GAP + PAD * 2, height = TOP + rows * H + (rows - 1) * ROWGAP + 20;
  const pos = i => ({x: PAD + (i % PER) * (W + GAP), y: TOP + Math.floor(i / PER) * (H + ROWGAP)});
  const typeClass = t => 'k-' + (String(t || 'node').toLowerCase().match(/[a-z]+/) || ['node'])[0];
  let s = '<svg class="gtm-path-svg" viewBox="0 0 ' + width + ' ' + height + '" role="img" aria-label="' +
    gEsc(p.nodes.map(x => x.label).join(' to ')) + '"><defs><marker id="gtm-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0 10 5 0 10z"/></marker></defs>';
  p.nodes.forEach((node, i) => {
    const {x, y} = pos(i);
    if (i < n - 1) {
      const e = p.edges[i] || {type: ''};
      const word = gEsc(String(e.type).replace(/_/g, ' '));
      const mark = (e.reverse ? 'marker-start' : 'marker-end') + '="url(#gtm-arrow)"';
      const nx = pos(i + 1);
      if (nx.y === y) {
        const x1 = x + W, x2 = nx.x;
        s += '<line class="gtm-edge" x1="' + (x1 + 4) + '" y1="' + (y + H / 2) + '" x2="' + (x2 - 4) + '" y2="' + (y + H / 2) + '" ' + mark + '/>' +
          '<text class="gtm-edge-label" x="' + ((x1 + x2) / 2) + '" y="' + (y + H / 2 - 9) + '" text-anchor="middle">' + word + '</text>';
      } else {
        const sx = x + W / 2, sy = y + H + 4, mid = y + H + ROWGAP / 2, ex = nx.x + W / 2, ey = nx.y - 4;
        s += '<path class="gtm-edge" fill="none" d="M' + sx + ' ' + sy + ' V' + mid + ' H' + ex + ' V' + ey + '" ' + mark + '/>' +
          '<text class="gtm-edge-label" x="' + ((sx + ex) / 2) + '" y="' + (mid - 8) + '" text-anchor="middle">' + word + '</text>';
      }
    }
    const label = String(node.label || ''), sub = String(node.sub || '');
    s += '<g class="gtm-node ' + typeClass(node.type) + '"><rect x="' + x + '" y="' + y + '" width="' + W + '" height="' + H + '" rx="10"/>' +
      '<text class="t-type" x="' + (x + 16) + '" y="' + (y + 26) + '">' + gEsc(node.type) + '</text>' +
      '<text class="t-label" x="' + (x + 16) + '" y="' + (y + 54) + '">' + gEsc(label.length > 20 ? label.slice(0, 19) + '…' : label) + '</text>' +
      (sub ? '<text class="t-sub" x="' + (x + 16) + '" y="' + (y + 76) + '">' + gEsc(sub.length > 26 ? sub.slice(0, 25) + '…' : sub) + '</text>' : '') +
      '<title>' + gEsc(label + (sub ? ', ' + sub : '')) + '</title></g>';
  });
  return s + '</svg>';
}

// ── Drafts (the HITL gate) ──

function gDrafts(run, ix) {
  const drafts = run.drafts || [];
  const counts = {pending: 0, approved: 0, rejected: 0, sent: 0, all: drafts.length};
  drafts.forEach(d => { counts[d.status] = (counts[d.status] || 0) + 1; });
  const f = gtm.draftFilter;
  const shown = drafts.filter(d => f === 'all' || d.status === f || (f === 'approved' && d.status === 'sent'));
  const filters = [['pending', 'Waiting'], ['approved', 'Approved'], ['rejected', 'Rejected'], ['all', 'All']].map(([k, l]) =>
    '<button type="button" data-act="draft-filter" data-v="' + k + '"' + (f === k ? ' class="on" aria-pressed="true"' : '') + '>' + l +
    ' <span class="n">' + (k === 'approved' ? counts.approved + counts.sent : counts[k]) + '</span></button>').join('');
  const cards = shown.map(d => gDraftCard(d, ix)).join('');
  return '<div class="toolbar gtm-split"><div class="segmented" role="group" aria-label="Filter drafts">' + filters + '</div>' +
    '<span class="muted gtm-gate-note">' + gIcon('i-flag') + 'Approve is the only way a draft gets sent, and only to the test inbox.</span></div>' +
    (cards || emptyState('0', f === 'pending' ? 'Nothing waiting on you' : 'No drafts here',
      drafts.length ? 'Every draft in this filter has been handled.' : 'Drafts appear after enrichment, each one citing a signal.'));
}

function gDraftCard(d, ix) {
  const p = ix.people[d.person_id] || {name: d.person_id, title: ''};
  const co = ix.companies[p.company_id];
  const tone = {pending: 't-waiting', approved: 't-good', rejected: 't-bad', sent: 't-active'}[d.status] || 't-idle';
  const word = {pending: 'Waiting', approved: 'Approved', rejected: 'Rejected', sent: 'Sent to test inbox'}[d.status] || d.status;
  const sigs = (d.signal_ids || []).map(id => {
    const s = ix.signals[id];
    if (!s) return '<li class="gtm-sig-missing">' + gIcon('i-alert') + 'Signal ' + gEsc(id) + ' is not in this run: the claim has no source.</li>';
    return '<li><div class="gtm-sig-kind">' + gEsc(s.kind.replace(/_/g, ' ')) + (s.observed_on ? ', ' + gEsc(s.observed_on) : '') + '</div>' +
      '<div>' + gEsc(s.summary) + '</div>' +
      (s.citation && s.citation.quote ? '<q>' + gEsc(s.citation.quote) + '</q>' : '') + gCite(s.citation, {host: true}) + '</li>';
  }).join('');
  const editing = gtm.editing === d.id, rejecting = gtm.rejecting === d.id;
  const copy = editing
    ? '<label class="sr-only" for="gtm-edit-' + gEsc(d.id) + '">Draft body</label><textarea class="form-input gtm-edit" id="gtm-edit-' + gEsc(d.id) + '" rows="7">' + gEsc(d.body) + '</textarea>'
    : '<div class="gtm-body">' + gEsc(d.body) + '</div>';
  const notes = (d.review_notes || []).length
    ? '<div class="gtm-notes" role="note"><div class="gtm-k">Review notes</div><ul>' + d.review_notes.map(x => '<li>' + gEsc(x) + '</li>').join('') + '</ul></div>' : '';
  let actions = '';
  if (editing) actions = '<button class="btn btn-primary btn-sm" type="button" data-act="edit-save" data-v="' + gEsc(d.id) + '">Save edit</button>' +
    '<button class="btn btn-ghost btn-sm" type="button" data-act="edit-cancel">Cancel</button><span class="muted">An edit keeps the draft waiting for approval.</span>';
  else if (rejecting) actions = '<label class="sr-only" for="gtm-reject-' + gEsc(d.id) + '">Why reject</label>' +
    '<input class="form-input gtm-reject-input" id="gtm-reject-' + gEsc(d.id) + '" placeholder="Why? For example: the claim about their backlog has no source">' +
    '<button class="btn btn-danger btn-sm" type="button" data-act="reject-save" data-v="' + gEsc(d.id) + '">Reject draft</button>' +
    '<button class="btn btn-ghost btn-sm" type="button" data-act="reject-cancel">Cancel</button>';
  else if (d.status === 'pending') actions = '<button class="btn btn-primary btn-sm" type="button" data-act="approve" data-v="' + gEsc(d.id) + '">' + gIcon('i-check') + 'Approve</button>' +
    '<button class="btn btn-secondary btn-sm" type="button" data-act="edit" data-v="' + gEsc(d.id) + '">' + gIcon('i-pen') + 'Edit</button>' +
    '<button class="btn btn-danger btn-sm" type="button" data-act="reject" data-v="' + gEsc(d.id) + '">' + gIcon('i-close') + 'Reject</button>' +
    (gIsLocal() ? '' : gAwaitingRep(d.id)
      ? '<span class="badge t-waiting gtm-band-wait">Agents passed it: your approval is asked in BAND too</span>'
      : '<button class="btn btn-ghost btn-sm" type="button" data-act="review" data-v="' + gEsc(d.id) + '" title="Planner, builder, reviewer and security check every claim in a BAND room">' + gIcon('i-conversations') + 'Agent review</button>');
  else if (d.status === 'approved') actions = '<span class="muted">' + gIcon('i-check') + 'Approved. It goes to the test inbox only, never to the prospect.</span>';
  else if (d.status === 'rejected') actions = '<span class="muted">Rejected. It cannot be sent.</span>';
  return '<article class="card gtm-draft s-' + gEsc(d.status) + '" id="draft-' + gEsc(d.id) + '">' +
    '<header class="gtm-draft-head"><div><span class="cell-main">' + gEsc(p.name) + '</span> <span class="muted">' + gEsc(p.title) + (co ? ', ' + gEsc(co.name) : '') + '</span></div>' +
      '<div class="gtm-tags"><span class="tag">' + (d.channel === 'linkedin' ? 'LinkedIn' : 'Email') + '</span>' +
      '<span class="tag">Step ' + gEsc(d.step) + '</span><span class="tag accent">Variant ' + gEsc(d.variant) + '</span>' +
      '<span class="badge ' + tone + '">' + gEsc(word) + '</span></div></header>' +
    '<div class="gtm-draft-grid"><div class="gtm-copy">' + (d.subject ? '<div class="gtm-subject">' + gEsc(d.subject) + '</div>' : '') + copy + notes + '</div>' +
      '<aside class="gtm-cited"><div class="gtm-k">Cited signal</div><ul>' + (sigs || '<li class="gtm-sig-missing">No signal cited.</li>') + '</ul></aside></div>' +
    '<footer class="gtm-actions">' + actions + '</footer></article>';
}

// ── Pipeline: Kanban, attribution, conversion, A/B, audit ──

function gPipeline(run, ix) {
  const leads = run.leads || [];
  const cols = GTM_STAGES.map(([k, label]) => {
    const items = leads.filter(l => k === 'closed' ? l.stage.startsWith('closed') : l.stage === k);
    const cards = items.map(l => {
      const c = ix.companies[l.company_id] || {name: l.company_id, tier: '?'};
      const p = ix.people[l.person_id];
      const opts = GTM_STAGE_ORDER.map(s => '<option value="' + s + '"' + (s === l.stage ? ' selected' : '') + '>' +
        s.replace('closed_won', 'Closed won').replace('closed_lost', 'Closed lost').replace(/^./, ch => ch.toUpperCase()) + '</option>').join('');
      return '<li class="gtm-kcard' + (l.stage === 'closed_lost' ? ' lost' : '') + '">' +
        '<div class="gtm-split"><span class="cell-main">' + gEsc(c.name) + '</span>' + gTier(c.tier) + '</div>' +
        '<div class="cell-sub">' + (p ? gEsc(p.name) + ', ' + gEsc(p.title) : 'No contact yet') + '</div>' +
        '<div class="gtm-split"><span class="tag' + (l.owner === 'rep' ? ' accent' : '') + '">' + (l.owner === 'rep' ? 'Rep' : 'AI') + '</span>' +
        (l.stage.startsWith('closed') ? '<span class="mini ' + (l.stage === 'closed_won' ? 't-good">Won' : 't-bad">Lost') + '</span>' : '') +
        '<label class="sr-only" for="gtm-stage-' + gEsc(l.company_id) + '">Move ' + gEsc(c.name) + '</label>' +
        '<select class="gtm-stage" id="gtm-stage-' + gEsc(l.company_id) + '" data-act="stage" data-company="' + gEsc(l.company_id) + '">' + opts + '</select></div></li>';
    }).join('');
    return '<section class="gtm-kcol"><h3>' + label + ' <span class="n">' + items.length + '</span></h3><ul>' + (cards || '<li class="gtm-kempty">Empty</li>') + '</ul></section>';
  }).join('');
  return '<div class="gtm-kanban" role="list">' + cols + '</div>' +
    '<div class="gtm-stats">' + gConversion(run, ix) + gAttribution(run) + gAbStats(run, ix) + '</div>' + gAuditLog(run);
}

function gAttribution(run) {
  const audit = run.audit || [], leads = run.leads || [];
  const ai = audit.filter(e => e.actor === 'ai').length, rep = audit.filter(e => e.actor === 'rep').length;
  const lai = leads.filter(l => l.owner === 'ai').length, lrep = leads.filter(l => l.owner === 'rep').length;
  const bar = (a, b) => {
    const t = a + b || 1;
    return '<div class="bar thick"><span class="c-accent" style="width:' + (a / t * 100) + '%"></span><span class="c-accent-soft" style="width:' + (b / t * 100) + '%"></span></div>';
  };
  return '<div class="card gtm-stat"><div class="card-title">AI vs rep</div>' +
    '<div class="gtm-attr"><div class="gtm-split"><span>Actions</span><span><b>' + ai + '</b> AI, <b>' + rep + '</b> rep</span></div>' + bar(ai, rep) + '</div>' +
    '<div class="gtm-attr"><div class="gtm-split"><span>Leads owned</span><span><b>' + lai + '</b> AI, <b>' + lrep + '</b> rep</span></div>' + bar(lai, lrep) + '</div>' +
    '<div class="funnel-legend gtm-legend"><span class="legend-key"><i class="c-accent"></i>AI</span><span class="legend-key"><i class="c-accent-soft"></i>Rep</span></div></div>';
}

function gConversion(run, ix) {
  // A lost lead is known to have been contacted, not how far it got.
  const reach = (lead, stage) => lead.stage === 'closed_lost' ? stage === 'contacted'
    : GTM_STAGE_ORDER.indexOf(lead.stage) >= GTM_STAGE_ORDER.indexOf(stage);
  const rows = ['A', 'B', 'C'].map(t => {
    const ls = (run.leads || []).filter(l => (ix.companies[l.company_id] || {}).tier === t);
    const n = ls.length;
    const cell = st => {
      const k = ls.filter(l => st === 'closed_won' ? l.stage === 'closed_won' : reach(l, st)).length;
      return '<td class="num">' + k + (n ? ' <span class="muted">' + Math.round(k / n * 100) + '%</span>' : '') + '</td>';
    };
    return '<tr><td>' + gTier(t) + '</td><td class="num">' + n + '</td>' + cell('contacted') + cell('replied') + cell('meeting') + cell('closed_won') + '</tr>';
  }).join('');
  return '<div class="card gtm-stat gtm-conv"><div class="card-title">Conversion by tier</div><div class="table-card"><table class="gtm-mini">' +
    '<thead><tr><th>Tier</th><th class="num">Leads</th><th class="num">Contacted</th><th class="num">Replied</th><th class="num">Meeting</th><th class="num">Won</th></tr></thead>' +
    '<tbody>' + rows + '</tbody></table></div></div>';
}

function gAbStats(run, ix) {
  const groups = Object.create(null);
  (run.drafts || []).forEach(d => {
    const key = d.channel + ' ' + d.variant;
    const g = groups[key] = groups[key] || {channel: d.channel, variant: d.variant, n: 0, approved: 0, rejected: 0, replied: 0};
    g.n++;
    if (d.status === 'approved' || d.status === 'sent') g.approved++;
    if (d.status === 'rejected') g.rejected++;
    const l = ix.leadByPerson[d.person_id];
    if (l && GTM_STAGE_ORDER.indexOf(l.stage) >= GTM_STAGE_ORDER.indexOf('replied') && l.stage !== 'closed_lost') g.replied++;
  });
  const rows = Object.values(groups).sort((a, b) => (a.channel + a.variant).localeCompare(b.channel + b.variant)).map(g =>
    '<tr><td>' + (g.channel === 'linkedin' ? 'LinkedIn' : 'Email') + ' <span class="tag accent">' + gEsc(g.variant) + '</span></td>' +
    '<td class="num">' + g.n + '</td><td class="num">' + g.approved + '</td><td class="num">' + g.rejected + '</td>' +
    '<td class="num">' + g.replied + (g.n ? ' <span class="muted">' + Math.round(g.replied / g.n * 100) + '%</span>' : '') + '</td></tr>').join('');
  return '<div class="card gtm-stat"><div class="card-title">A/B variants</div><div class="table-card"><table class="gtm-mini">' +
    '<thead><tr><th>Variant</th><th class="num">Drafts</th><th class="num">Approved</th><th class="num">Rejected</th><th class="num">Replied</th></tr></thead>' +
    '<tbody>' + (rows || '<tr><td colspan="5" class="muted">No drafts yet</td></tr>') + '</tbody></table></div></div>';
}

function gAuditLog(run) {
  const f = gtm.auditActor;
  const all = (run.audit || []).slice().reverse();
  const shown = all.filter(e => f === 'all' || e.actor === f);
  const filters = [['all', 'All'], ['ai', 'AI'], ['rep', 'Rep']].map(([k, l]) =>
    '<button type="button" data-act="audit-actor" data-v="' + k + '"' + (f === k ? ' class="on" aria-pressed="true"' : '') + '>' + l + '</button>').join('');
  const rows = shown.map(e => '<tr><td class="gtm-ts gtm-full" title="' + gEsc(e.at) + '">' + gEsc(new Date(e.at).toLocaleString([], {month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit'})) + '</td>' +
    '<td data-label="By"><span class="tag' + (e.actor === 'rep' ? ' accent' : '') + '">' + (e.actor === 'rep' ? 'Rep' : 'AI') + '</span></td>' +
    '<td data-label="Agent">' + gEsc(e.agent) + '</td><td class="gtm-action" data-label="Action">' + gEsc(e.action) + '</td><td class="gtm-wrap gtm-full" data-label="Target">' + gEsc(e.target) +
    (e.detail ? '<div class="cell-sub">' + gEsc(e.detail) + '</div>' : '') + '</td>' +
    '<td class="num" data-label="Tokens">' + (e.tokens ? gNum(e.tokens) : '<span class="muted">0</span>') + '</td>' +
    '<td class="num" data-label="Cost">' + (e.cost_usd ? gMoney(e.cost_usd) : '<span class="muted">$0</span>') + '</td></tr>').join('');
  return '<div class="subhead">Audit log <span class="hint"><span class="segmented" role="group" aria-label="Filter audit log">' + filters + '</span></span></div>' +
    '<div class="table-card gtm-sheet gtm-cards gtm-audit"><table><thead><tr><th>When</th><th>By</th><th>Agent</th><th>Action</th><th>Target</th><th class="num">Tokens</th><th class="num">Cost</th></tr></thead>' +
    '<tbody>' + (rows || '<tr><td colspan="7" class="muted">Nothing logged yet</td></tr>') + '</tbody></table></div>';
}

// ── Agent thinking: audit (AI side) plus the BAND room feed ──

function gThinking(run) {
  const items = [];
  (run.audit || []).forEach(e => items.push({t: new Date(e.at).getTime(), who: e.agent || e.actor, what: e.action,
    detail: [e.target, e.detail].filter(Boolean).join(': '), tokens: e.tokens || 0, cost: e.cost_usd || 0, rep: e.actor === 'rep'}));
  // BAND room messages (lane B) carry the words the agents said. Lane B also
  // writes each one to the run's audit log, so the running cost comes from the
  // audit log only and a message's own tokens are shown beside it, not added.
  const msgs = gtm.feed && (Array.isArray(gtm.feed) ? gtm.feed : gtm.feed.items || gtm.feed.messages) || [];
  msgs.filter(m => !m.run_id || m.run_id === run.id).forEach(m => {
    const t = typeof m.t === 'number' ? m.t * (m.t < 1e12 ? 1000 : 1) : new Date(m.at || m.t || m.inserted_at).getTime();
    const to = m.to || m.mentions || [];
    items.push({t: isNaN(t) ? 0 : t, who: m.sender || m.agent || 'band',
      what: (m.kind && m.kind !== 'message' ? m.kind.replace(/_/g, ' ') + ' ' : '') + (to.length ? '@' + to.join(' @') : '') + (m.draft_id ? ' on ' + m.draft_id : ''),
      detail: m.text || m.content || '', tokens: 0, cost: 0, ownTokens: m.tokens || 0, band: true});
  });
  items.sort((a, b) => a.t - b.t);
  let cum = 0, tok = 0;  // cumulative totals go in the header only; each row shows its own cost
  items.forEach(it => { cum += it.cost; tok += it.tokens; if (it.band) it.tokens = it.ownTokens; });
  const rows = items.slice().reverse().slice(0, 80).map(it => '<li class="' + (it.rep ? 'rep' : it.band ? 'band' : '') + '">' +
    '<div class="gtm-feed-meta"><b>' + gEsc(it.who) + '</b>' + (it.band ? ' <span class="tag">BAND</span>' : '') +
    '<span>' + (it.t ? gEsc(gTime(it.t)) : '') + '</span>' +
    '<span class="gtm-feed-cost">' + [it.tokens ? gNum(it.tokens) + ' tok' : '', gEsc(gEventCost(it.cost))].filter(Boolean).join(', ') + '</span></div>' +
    '<div class="gtm-feed-what">' + gEsc(it.what) + '</div>' +
    (it.detail ? '<div class="gtm-feed-detail">' + gEsc(it.detail) + '</div>' : '') + '</li>').join('');
  const open = sessionStorage.getItem('gtm-thinking') !== 'closed';
  return '<details class="card gtm-thinking"' + (open ? ' open' : '') + ' ontoggle="sessionStorage.setItem(\'gtm-thinking\', this.open ? \'open\' : \'closed\')">' +
    '<summary><span class="gtm-split"><span class="card-title">' + gIcon('i-chevron', 'gtm-chev') + 'Agent thinking</span>' +
    '<span class="muted">' + gNum(tok) + ' tok, ' + gMoney(cum) + '</span></span></summary>' +
    '<ol class="gtm-feed" aria-live="polite">' + (rows || '<li class="muted">No agent activity yet.</li>') + '</ol></details>';
}
