/* Binder Selection Agent — deterministic engine, JavaScript port (static demo).
 *
 * Faithful port of the Python core for GitHub Pages (no backend there):
 *   nodes/extract.py  (stub_extract + money normalisation, conflict detection)
 *   nodes/derive.py   (loss aggregates, years_trading, continental-US)
 *   nodes/completeness.py, capacity.py, appetite.py (incl. logic_group folding
 *     with per-site AND pairing), multibind.py, narrative.py,
 *   review.py (validate), settle reserve/release, persistence.evidence_pack.
 *
 * Deliberately NOT ported: checkpointer persistence, live LLM extraction
 * (needs a secret key — must never ship in a public page), four-eyes admin.
 * Missing data yields Cannot-assess/Refer, never Pass — same as the backend.
 *
 * Usable in browser (window.BinderEngine) and Node (module.exports).
 */
(function (root, factory) {
  const api = factory();
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.BinderEngine = api;
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  function todayISO() { return new Date().toISOString().slice(0, 10); }

  function stableStringify(v) {
    if (v === null || v === undefined) return "null";
    if (Array.isArray(v)) return "[" + v.map(stableStringify).join(",") + "]";
    if (typeof v === "object") {
      return "{" + Object.keys(v).sort().map(k => JSON.stringify(k) + ":" + stableStringify(v[k])).join(",") + "}";
    }
    if (typeof v === "string") return JSON.stringify(v);
    return String(v);
  }

  /* ---------- extract (stub) ---------- */
  function normMoney(raw) {
    if (typeof raw === "number") return [raw, raw];
    if (typeof raw === "string") {
      const orig = raw;
      const n = parseFloat(raw.replace(/\$/g, "").replace(/,/g, "").trim());
      return [Number.isNaN(n) ? null : n, orig];
    }
    return [null, raw];
  }

  function stubExtract(documents) {
    const extracted = {}, meta = {}, seen = {};
    for (const doc of documents || []) {
      const hint = doc.structured_hint || {};
      for (const field of Object.keys(hint)) {
        const raw = hint[field];
        const [val, orig] = field === "total_insured_value" ? normMoney(raw) : [raw, raw];
        (seen[field] = seen[field] || []).push({ value: val, source_document_id: doc.doc_id });
        if (!(field in extracted)) {
          extracted[field] = val;
          meta[field] = { value: val, original_value: orig, present: true, confidence: 1.0, source_document_id: doc.doc_id, source_locator: "structured_hint" };
        }
      }
    }
    for (const field of Object.keys(seen)) {
      const distinct = new Set(seen[field].map(s => stableStringify(s.value)));
      if (distinct.size > 1) { meta[field].contested = true; meta[field].conflict = seen[field]; }
    }
    for (const f of ["total_insured_value", "broker_name", "locations", "commodities"]) {
      if (!(f in extracted)) { extracted[f] = null; meta[f] = { present: false, confidence: 0.0, reason: "absent" }; }
    }
    return [extracted, meta];
  }

  /* ---------- derive ---------- */
  const NON_CONTINENTAL = new Set(["PR", "GU", "VI", "AS", "MP"]);

  function yearsBetween(startISO, endISO) {
    const [sy, sm, sd] = startISO.split("-").map(Number);
    const [ey, em, ed] = endISO.split("-").map(Number);
    const days = (Date.UTC(ey, em - 1, ed) - Date.UTC(sy, sm - 1, sd)) / 86400000;
    return Math.round((days / 365.25) * 100) / 100;
  }

  function derive(extracted, asAt) {
    const ext = Object.assign({}, extracted);
    const today = asAt || todayISO();
    const losses = ext.losses || [];
    if (losses.length && (!("largest_single_claim_amount" in ext) || ext.largest_single_claim_amount == null)) {
      const amounts = losses.map(l => l.paid_incurred_amount || 0);
      ext.largest_single_claim_amount = Math.max.apply(null, amounts);
      ext.total_claims_amount = amounts.reduce((a, b) => a + b, 0);
      const cut3 = (parseInt(today.slice(0, 4), 10) - 3) + today.slice(4);
      const cut5 = (parseInt(today.slice(0, 4), 10) - 5) + today.slice(4);
      ext.claim_count_3_years = losses.filter(l => (l.loss_date || "") >= cut3).length;
      ext.claim_count_5_years = losses.filter(l => (l.loss_date || "") >= cut5).length;
    }
    if (ext.business_commencement_date && ext.years_trading == null) {
      try { ext.years_trading = yearsBetween(ext.business_commencement_date, today); } catch (e) { /* leave absent */ }
    }
    if (ext.insured_in_continental_us == null && ext.insured_country) {
      ext.insured_in_continental_us = ext.insured_country === "US" && !NON_CONTINENTAL.has(ext.insured_state_province || "");
    }
    return ext;
  }

  /* ---------- completeness ---------- */
  const MANDATORY = ["total_insured_value", "broker_name", "locations"];

  function checkCompleteness(extracted, meta) {
    const missing = MANDATORY.filter(f => {
      const v = (extracted || {})[f];
      return v == null || v === "" || (Array.isArray(v) && v.length === 0);
    });
    const contested = Object.keys(meta || {}).filter(f => meta[f] && meta[f].contested);
    return { missing, contested, can_evaluate: missing.length === 0 };
  }

  /* ---------- appetite ---------- */
  function getField(extracted, ref) {
    if (ref.indexOf(".") === -1) return extracted[ref];
    const dot = ref.indexOf(".");
    const head = ref.slice(0, dot), tail = ref.slice(dot + 1);
    const val = extracted[head];
    if (Array.isArray(val)) return val.map(item => (item && typeof item === "object") ? item[tail] : null);
    if (val && typeof val === "object") return val[tail];
    return null;
  }

  function threshold(raw, today) { return raw === "TODAY" ? today : raw; }

  function singleOk(val, op, thr) {
    switch (op) {
      case "lte": return val <= thr;
      case "lt": return val < thr;
      case "gte": return val >= thr;
      case "gt": return val > thr;
      case "eq": return val === thr;
      case "neq": return val !== thr;
      case "in": return thr.includes(val);
      case "not_in": return !thr.map(x => String(x).toUpperCase()).includes(String(val).toUpperCase());
      case "is_true": return val === true;
      case "is_false": return val === false;
      case "is_absent": return val == null;
      case "is_present": return val != null;
      case "before": return String(val) < String(thr);
      case "after": return String(val) > String(thr);
      default: throw new Error("unknown-op:" + op);
    }
  }

  function evaluateRule(extracted, rule, today) {
    today = today || todayISO();
    const val = getField(extracted, rule.field_reference);
    if (val == null || val === "" || (Array.isArray(val) && val.length === 0)) {
      return { rule_id: rule.rule_id, outcome: "Cannot assess", reason: "missing:" + rule.field_reference };
    }
    try {
      const vals = Array.isArray(val) ? val : [val];
      if (vals.some(v => v == null)) {
        return { rule_id: rule.rule_id, outcome: "Cannot assess", reason: "missing:" + rule.field_reference };
      }
      const t = threshold(rule.threshold_value, today);
      const ok = vals.every(v => singleOk(v, rule.operator, t));
      return { rule_id: rule.rule_id, outcome: ok ? "Pass" : "Decline", value: val };
    } catch (e) {
      return { rule_id: rule.rule_id, outcome: "Cannot assess", reason: String((e && e.message) || e) };
    }
  }

  function perSiteAnd(members, extracted, today) {
    const locs = extracted.locations || [];
    let sawUnassessable = false;
    for (let i = 0; i < locs.length; i++) {
      const sub = Object.assign({}, extracted, { locations: [locs[i]] });
      const outs = members.map(([r]) => evaluateRule(sub, r, today).outcome);
      if (outs.every(o => o === "Decline")) return ["Decline", members.map(([r]) => r.rule_id)];
      if (outs.indexOf("Pass") === -1) sawUnassessable = true;
    }
    return sawUnassessable ? ["Cannot assess", []] : ["Pass", []];
  }

  function combineGroups(rules, outcomes, extracted, today) {
    const byId = {};
    rules.forEach((r, i) => { byId[r.rule_id] = [r, outcomes[i]]; });
    const groups = {}, order = [], logicOf = {};
    for (const r of rules) {
      if (r.logic_group) {
        (groups[r.logic_group] = groups[r.logic_group] || []).push(r.rule_id);
        if (order.indexOf(r.logic_group) === -1) order.push(r.logic_group);
        if (!(r.logic_group in logicOf)) logicOf[r.logic_group] = r.logic || "AND";
      }
    }
    if (!order.length) return outcomes;
    const folded = outcomes.filter((o, i) => !rules[i].logic_group);
    for (const g of order) {
      const members = rules.filter(r => r.logic_group === g).map(r => [r, byId[r.rule_id][1]]);
      const logic = logicOf[g] || "AND";
      let combined, bitten;
      if (logic === "AND" && members.every(([r]) => r.scope === "location")) {
        [combined, bitten] = perSiteAnd(members, extracted, today);
      } else {
        const outs = members.map(([, o]) => o.outcome);
        if (logic === "OR") combined = outs.includes("Decline") ? "Decline" : (outs.includes("Cannot assess") ? "Cannot assess" : "Pass");
        else combined = outs.includes("Pass") ? "Pass" : (outs.includes("Cannot assess") ? "Cannot assess" : "Decline");
        bitten = members.filter(([, o]) => o.outcome === "Decline").map(([r]) => r.rule_id);
      }
      folded.push({ rule_id: g, outcome: combined, members: members.map(([r]) => r.rule_id), bitten, value: members.map(([, o]) => o.value) });
    }
    return folded;
  }

  function evaluateRules(extracted, rules, today) {
    const outcomes = combineGroups(rules, rules.map(r => evaluateRule(extracted, r, today)), extracted, today || todayISO());
    const binder = outcomes.some(o => o.outcome === "Decline") ? "Decline"
      : outcomes.some(o => o.outcome === "Cannot assess") ? "Refer" : "Accept";
    return { rule_outcomes: outcomes, binder_outcome: binder };
  }

  /* ---------- capacity ---------- */
  function screen(extracted, line, written, reserved) {
    const available = line - written - reserved;
    const tiv = (extracted || {}).total_insured_value || 0;
    const eligible = available > 0 && available >= tiv;
    return {
      capacity_snapshot: { authorised_line: line, written_to_date: written, reserved, available_capacity: available },
      binder_outcome: eligible ? "eligible" : "excluded:shortfall=" + (tiv - available)
    };
  }

  function isActive(binderId, registry, asAt) {
    asAt = asAt || todayISO();
    for (const b of registry) {
      if (b.binder_id === binderId) {
        const inRange = (b.effective_from || "") <= asAt && (b.effective_to == null || b.effective_to >= asAt);
        return b.status === "active" && inRange;
      }
    }
    return false;
  }

  function screenSafe(extracted, line, written, reserved, binderId, registry, asAt) {
    try {
      if (!isActive(binderId, registry, asAt)) {
        return { capacity_snapshot: {}, binder_outcome: "excluded:suspended-or-retired" };
      }
      return screen(extracted, line, written, reserved);
    } catch (e) {
      return { capacity_snapshot: {}, binder_outcome: "failed:Error:" + String((e && e.message) || e) };
    }
  }

  /* ---------- multibind ---------- */
  function loadEffective(rulesets, binderId, asAt) {
    asAt = asAt || todayISO();
    let best = null;
    for (const data of rulesets) {
      if (data.binder_id !== binderId) continue;
      if ((data.effective_from || "") <= asAt && (data.effective_to == null || data.effective_to >= asAt)) {
        if (!best || (data.version || 0) > (best.version || 0)) best = data;
      }
    }
    if (!best) throw new Error("no effective ruleset for " + binderId);
    return best;
  }

  function evaluateBinders(extracted, DATA, binderIds, asAt, today) {
    binderIds = binderIds || DATA.binders.filter(b => isActive(b.binder_id, DATA.binders, asAt)).map(b => b.binder_id);
    const results = [], rulesets = {};
    for (const bid of binderIds) {
      let capCfg;
      try {
        capCfg = DATA.capacity[bid];
        if (!capCfg) throw new Error("no capacity record for " + bid);
        const cout = screenSafe(extracted, capCfg.authorised_line, capCfg.written_to_date, capCfg.reserved || 0, bid, DATA.binders, asAt);
        if (cout.binder_outcome !== "eligible") {
          results.push({ binder_id: bid, outcome: "excluded", reason: cout.binder_outcome, capacity_snapshot: cout.capacity_snapshot });
          continue;
        }
        const data = loadEffective(DATA.rulesets, bid, asAt);
        rulesets[bid] = data.rules;
        const aout = evaluateRules(extracted, data.rules, today);
        results.push({ binder_id: bid, outcome: aout.binder_outcome, rule_outcomes: aout.rule_outcomes, ruleset_version: data.version, capacity_snapshot: cout.capacity_snapshot });
      } catch (e) {
        results.push({ binder_id: bid, outcome: "failed", reason: "Error:" + String((e && e.message) || e) });
      }
    }
    return { binder_results: results, rulesets };
  }

  function scoreBinders(results, DATA) {
    const w = DATA.scoring.weights;
    const reg = {};
    DATA.binders.forEach(b => { reg[b.binder_id] = b; });
    const scored = [];
    for (const r of results) {
      if (r.outcome !== "Accept") continue;
      const snap = r.capacity_snapshot || {};
      const line = snap.authorised_line || 1.0;
      const avail = snap.available_capacity || 0.0;
      const parts = {
        available_capacity: Math.round(w.available_capacity * avail / line * 1000) / 1000,
        strategic_classification: (DATA.scoring.strategic_points || {})[(reg[r.binder_id] || {}).strategic_classification] || 0,
        appetite_fit: w.appetite_fit
      };
      const total = Math.round((parts.available_capacity + parts.strategic_classification + parts.appetite_fit) * 1000) / 1000;
      scored.push({ binder_id: r.binder_id, parts, total, available_capacity: avail });
    }
    const tie = DATA.scoring.tie_break || [];
    scored.sort((a, b) => {
      const ka = [-a.total].concat(tie.map(k => {
        const v = a[k] !== undefined ? a[k] : a.binder_id;
        return typeof v === "number" ? -v : String(v);
      }));
      const kb = [-b.total].concat(tie.map(k => {
        const v = b[k] !== undefined ? b[k] : b.binder_id;
        return typeof v === "number" ? -v : String(v);
      }));
      for (let i = 0; i < ka.length; i++) {
        if (ka[i] < kb[i]) return -1;
        if (ka[i] > kb[i]) return 1;
      }
      return 0;
    });
    if (!scored.length) return { scores: {}, score_parts: {}, ranking: [], recommendation: "no eligible binder" };
    const scores = {}, parts = {};
    scored.forEach(s => { scores[s.binder_id] = s.total; parts[s.binder_id] = s.parts; });
    return { scores, score_parts: parts, ranking: scored.map(s => s.binder_id), recommendation: scored[0].binder_id };
  }

  /* ---------- narrative ---------- */
  function summarize(state) {
    const ext = state.extracted || {};
    const lines = ["Submission " + (state.submission_reference || "?") + " from " + ext.broker_name +
      " (TIV " + ext.total_insured_value + ") was evaluated against " + (state.binder_results || []).length + " binder(s)."];
    for (const r of state.binder_results || []) {
      if (r.outcome === "Accept") lines.push("- " + r.binder_id + ": eligible for recommendation.");
      else if (r.outcome === "excluded") lines.push("- " + r.binder_id + ": not considered (" + r.reason + ").");
      else if (r.outcome === "failed") lines.push("- " + r.binder_id + ": evaluation failed (" + r.reason + ").");
      else {
        const bites = (r.rule_outcomes || []).filter(o => o.outcome === "Decline").map(o => o.rule_id);
        const gaps = (r.rule_outcomes || []).filter(o => o.outcome === "Cannot assess").map(o => o.rule_id);
        if (bites.length) lines.push("- " + r.binder_id + ": not recommended; rules bitten: " + bites.join(", ") + ".");
        else if (gaps.length) lines.push("- " + r.binder_id + ": needs information (" + gaps.join(", ") + "); referred, not declined.");
      }
    }
    const rec = state.recommendation;
    if (rec && !rec.startsWith("no eligible")) {
      lines.push("Recommended binder: " + rec + " with score " + ((state.scores || {})[rec]) + ". This is advisory; a named underwriter decides.");
    } else lines.push("No binder is recommended; see per-binder reasons above.");
    return lines.join(" ");
  }

  /* ---------- review validate ---------- */
  const OVERRIDE_REASONS = ["PRIOR_RELATIONSHIP", "CAPACITY_PREFERENCE", "TERMS_NEGOTIATED", "BROKER_REQUEST", "OTHER"];

  function hardDeclined(ruleOutcomes, rules) {
    const sev = {};
    (rules || []).forEach(r => { sev[r.rule_id] = r.severity; });
    return (ruleOutcomes || []).filter(o => o.outcome === "Decline" && sev[o.rule_id] === "hard_decline").map(o => o.rule_id);
  }

  function validateDecision(state, human, rules) {
    rules = rules || [];
    const base = { underwriter_id: (human || {}).underwriter_id || "unknown", decided_at: new Date().toISOString() };
    const action = (human || {}).action;
    if (action === "accept") {
      if ((state.recommendation || "").startsWith("no eligible")) return Object.assign({}, base, { valid: false, error: "nothing to accept" });
      return Object.assign({}, base, { valid: true, action: "accept", selected_binder: state.recommendation });
    }
    if (action === "override") {
      if (OVERRIDE_REASONS.indexOf(human.reason_code) === -1) return Object.assign({}, base, { valid: false, error: "reason_code required" });
      if (!human.selected_binder) return Object.assign({}, base, { valid: false, error: "selected_binder required" });
      const hard = hardDeclined(state.rule_outcomes, rules);
      if (hard.length) return Object.assign({}, base, { valid: false, error: "hard-decline blocked: " + JSON.stringify(hard.sort()) });
      return Object.assign({}, base, { valid: true, action: "override", selected_binder: human.selected_binder, reason_code: human.reason_code, commentary: human.commentary || "" });
    }
    if (action === "refer_back") {
      const missing = ((state.completeness || {}).missing || []).slice();
      (state.binder_results || []).forEach(r => (r.rule_outcomes || []).forEach(o => { if (o.outcome === "Cannot assess") missing.push(o.rule_id); }));
      return Object.assign({}, base, { valid: true, action: "refer_back", info_request: Array.from(new Set(missing)).sort() });
    }
    return Object.assign({}, base, { valid: false, error: "action must be accept|override|refer_back" });
  }

  /* ---------- in-memory settle ledger ---------- */
  function newLedger(capacity) {
    const binders = {};
    Object.keys(capacity).forEach(bid => {
      binders[bid] = { authorised_line: capacity[bid].authorised_line, written_to_date: capacity[bid].written_to_date, reservations: {} };
    });
    return { binders };
  }

  function ledgerAvailable(ledger, bid) {
    const b = ledger.binders[bid];
    const reserved = Object.keys(b.reservations).reduce((a, k) => a + b.reservations[k].amount, 0);
    return b.authorised_line - b.written_to_date - reserved;
  }

  function reserve(ledger, binderId, ref, amount) {
    const b = ledger.binders[binderId];
    for (const id of Object.keys(b.reservations)) {
      if (b.reservations[id].submission_ref === ref) {
        return { reservation_id: id, deduped: true, available: ledgerAvailable(ledger, binderId) };
      }
    }
    if (ledgerAvailable(ledger, binderId) < amount) {
      throw new Error("insufficient capacity: available=" + ledgerAvailable(ledger, binderId) + " need=" + amount);
    }
    const id = "res-" + Math.random().toString(16).slice(2, 10);
    b.reservations[id] = { submission_ref: ref, amount };
    return { reservation_id: id, deduped: false, available: ledgerAvailable(ledger, binderId) };
  }

  /* ---------- full run (minus human pause) ---------- */
  function runPipeline(documents, submissionRef, DATA, asAt, today) {
    const [extracted0, meta] = stubExtract(documents);
    const extracted = derive(extracted0, asAt);
    const completeness = checkCompleteness(extracted, meta);
    const state = { submission_reference: submissionRef, extracted, extracted_meta: meta, completeness, halt: null };
    if (!completeness.can_evaluate) { state.halt = "completeness"; return state; }
    Object.assign(state, evaluateBinders(extracted, DATA, null, asAt, today));
    Object.assign(state, scoreBinders(state.binder_results, DATA));
    state.narrative = summarize(state);
    return state;
  }

  return {
    todayISO, stubExtract, normMoney, derive, checkCompleteness,
    evaluateRule, evaluateRules, screen, screenSafe, isActive, loadEffective,
    evaluateBinders, scoreBinders, summarize, validateDecision,
    OVERRIDE_REASONS, newLedger, reserve, runPipeline
  };
});
