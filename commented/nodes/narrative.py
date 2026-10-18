# Commented reference copy of nodes/narrative.py
# Original code is unchanged; every line below is commented out.
# ======================================================================
# """Narrative summary: describes already-determined outcomes, decides nothing
# (BFR-REC-007/008/011). Deterministic template; an LLM may rephrase it later
# but must not add conclusions. Never describes risk as bound/placed (REC-010).
# """


# def summarize(state: dict) -> dict:
#     ref = state.get("submission_reference", "?")
#     ext = state.get("extracted") or {}
#     tiv = ext.get("total_insured_value")
#     broker = ext.get("broker_name")
#     lines = [f"Submission {ref} from {broker} (TIV {tiv}) was evaluated "
#              f"against {len(state.get('binder_results', []))} binder(s)."]
#     for r in state.get("binder_results", []):
#         if r.get("outcome") == "Accept":
#             lines.append(f"- {r['binder_id']}: eligible for recommendation.")
#         elif r.get("outcome") == "excluded":
#             lines.append(f"- {r['binder_id']}: not considered ({r.get('reason')}).")
#         elif r.get("outcome") == "failed":
#             lines.append(f"- {r['binder_id']}: evaluation failed ({r.get('reason')}).")
#         else:
#             bites = [o.get("rule_id") for o in r.get("rule_outcomes", [])
#                      if o.get("outcome") == "Decline"]
#             gaps = [o.get("rule_id") for o in r.get("rule_outcomes", [])
#                     if o.get("outcome") == "Cannot assess"]
#             if bites:
#                 lines.append(f"- {r['binder_id']}: not recommended; rules bitten: {', '.join(bites)}.")
#             elif gaps:
#                 lines.append(f"- {r['binder_id']}: needs information ({', '.join(gaps)}); referred, not declined.")
#     rec = state.get("recommendation")
#     if rec and not rec.startswith("no eligible"):
#         lines.append(f"Recommended binder: {rec} with score {state.get('scores', {}).get(rec)}. "
#                      f"This is advisory; a named underwriter decides.")
#     else:
#         lines.append("No binder is recommended; see per-binder reasons above.")
#     return {"narrative": " ".join(lines)}
