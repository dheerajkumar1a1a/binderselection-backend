/* Cross-verify the JS engine against Python expectations.
 *
 * Run from repo root:  node scripts/verify_engine_js.mjs
 * 1. Asserts docs/data/*.json are byte-identical to the source of truth
 *    (rules/, samples/) — the public snapshot cannot drift silently.
 * 2. Replicates tests/test_dataset.py::run_case in JS for every sample
 *    case and asserts halt, binder outcome, recommendation, per-rule cells.
 */
const fs = require("fs");
const path = require("path");
const E = require("../docs/engine.js");

const ROOT = path.resolve(__dirname, "..");
let failures = 0;
const fail = (msg) => { failures++; console.error("FAIL:", msg); };

function read(p) { return fs.readFileSync(path.join(ROOT, p, ), "utf-8"); }

// ---- 1. freshness: docs/data mirrors source ----
const pairs = [
  ["rules/binders.json", "docs/data/rules/binders.json"],
  ["rules/scoring.json", "docs/data/rules/scoring.json"],
  ["rules/capacity.json", "docs/data/rules/capacity.json"],
  ["rules/binder_A_v1.json", "docs/data/rules/binder_A_v1.json"],
  ["rules/binder_A_v2.json", "docs/data/rules/binder_A_v2.json"],
  ["rules/binder_B_v1.json", "docs/data/rules/binder_B_v1.json"],
  ["rules/override_reason_codes.json", "docs/data/rules/override_reason_codes.json"],
  ["samples/manifest.json", "docs/data/samples/manifest.json"],
];
for (const [a, b] of pairs) {
  if (read(a) !== read(b)) fail(`stale copy: ${b} differs from ${a}`);
}
const manifest = JSON.parse(read("samples/manifest.json"));
const diskCases = fs.readdirSync(path.join(ROOT, "samples/cases")).filter(f => f.endsWith(".json")).sort();
const listed = manifest.cases.map(c => c.file).sort();
if (JSON.stringify(diskCases) !== JSON.stringify(listed)) fail("manifest does not match samples/cases");
for (const f of diskCases) {
  if (read("samples/cases/" + f) !== read("docs/data/samples/cases/" + f)) fail(`stale case copy: ${f}`);
}

// ---- 2. replicate run_case (tests/test_dataset.py) ----
const V1 = JSON.parse(read("rules/binder_A_v1.json")).rules;
const A2 = JSON.parse(read("rules/binder_A_v2.json"));
const B1 = JSON.parse(read("rules/binder_B_v1.json"));
const RULESETS = [A2, B1];

function effective(binderId) {
  const cands = RULESETS.filter(d => d.binder_id === binderId);
  return cands.reduce((a, b) => ((b.version || 0) > (a.version || 0) ? b : a));
}

function runCase(kase) {
  const state = { submission_reference: kase.case_id };
  const [ext0, meta] = E.stubExtract(kase.documents);
  const extracted = E.derive(ext0);
  const completeness = E.checkCompleteness(extracted, meta);
  state.extracted = extracted; state.completeness = completeness;
  if (!completeness.can_evaluate) return { halt: "completeness", state };
  const c = kase.capacity || {};
  const cout = E.screen(extracted, c.line ?? 15000000, c.written ?? 5000000, c.reserved ?? 0);
  state.capacity_snapshot = cout.capacity_snapshot;
  state.binder_outcome = cout.binder_outcome;
  if (cout.binder_outcome !== "eligible") return { halt: "capacity", state };
  let rules;
  if (kase.ruleset) {
    const data = effective(kase.ruleset.binder_id);
    rules = data.rules;
    state.ruleset_version = data.version;
  } else rules = V1;
  Object.assign(state, E.evaluateRules(extracted, rules));
  // single-binder placeholder rank (nodes/rank.py)
  if (state.binder_outcome === "Accept") {
    state.scores = { binder_A: 7.0 }; state.ranking = ["binder_A"]; state.recommendation = "binder_A";
  } else { state.scores = {}; state.ranking = []; state.recommendation = "no eligible binder"; }
  return { halt: null, state };
}

for (const f of diskCases) {
  const kase = JSON.parse(read("samples/cases/" + f));
  const res = runCase(kase);
  const exp = kase.expected;
  const id = kase.case_id;
  if (res.halt !== exp.halt) { fail(`${id}: halt ${res.halt} != expected ${exp.halt}`); continue; }
  const st = res.state;
  if (exp.halt === "completeness") {
    if (JSON.stringify(st.completeness.missing) !== JSON.stringify(exp.missing)) {
      fail(`${id}: missing ${JSON.stringify(st.completeness.missing)} != ${JSON.stringify(exp.missing)}`);
    }
  } else if (exp.halt === "capacity") {
    if (!String(st.binder_outcome).startsWith("excluded")) fail(`${id}: not excluded: ${st.binder_outcome}`);
    if ("shortfall" in exp) {
      const got = st.extracted.total_insured_value - st.capacity_snapshot.available_capacity;
      if (got !== exp.shortfall) fail(`${id}: shortfall ${got} != ${exp.shortfall}`);
    }
  } else {
    if (st.binder_outcome !== kase.binder_outcome) fail(`${id}: outcome ${st.binder_outcome} != ${kase.binder_outcome}`);
    if (st.recommendation !== exp.recommendation) fail(`${id}: reco ${st.recommendation} != ${exp.recommendation}`);
    const got = {};
    st.rule_outcomes.forEach(o => { got[o.rule_id] = o.outcome; });
    for (const [rid, oc] of Object.entries(exp.rules || {})) {
      if (got[rid] !== oc) fail(`${id}/${rid}: ${got[rid]} != ${oc}`);
    }
  }
}

if (failures) { console.error(`${failures} FAILURE(S)`); process.exit(1); }
console.log(`engine.js verified: ${diskCases.length} cases + data freshness, all match Python expectations`);
