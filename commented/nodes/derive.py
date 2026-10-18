# Commented reference copy of nodes/derive.py
# Original code is unchanged; every line below is commented out.
# ======================================================================
# """Derived risk fields computed from raw inputs, never extracted as stated
# figures where the underlying data exists (BFR 7.1.6). Runs after extract.
# Explicitly supplied derived values pass through untouched.
# """
# from datetime import date

# US_NON_CONTINENTAL = {"PR", "GU", "VI", "AS", "MP"}


# def _years_between(start_iso: str, end_iso: str) -> float:
#     s = date.fromisoformat(start_iso)
#     e = date.fromisoformat(end_iso)
#     return round((e - s).days / 365.25, 2)


# def derive(state: dict, as_at: str | None = None) -> dict:
#     ext = dict(state.get("extracted") or {})
#     today = as_at or date.today().isoformat()
#     losses = ext.get("losses") or []
#     if losses and ("largest_single_claim_amount" not in ext or ext.get("largest_single_claim_amount") is None):
#         amounts = [l.get("paid_incurred_amount", 0) or 0 for l in losses]
#         ext["largest_single_claim_amount"] = max(amounts) if amounts else 0
#         ext["total_claims_amount"] = sum(amounts)
#         ext["claim_count_3_years"] = sum(1 for l in losses if l.get("loss_date", "") >= f"{int(today[:4]) - 3}{today[4:]}")
#         ext["claim_count_5_years"] = sum(1 for l in losses if l.get("loss_date", "") >= f"{int(today[:4]) - 5}{today[4:]}")
#     if ext.get("business_commencement_date") and ext.get("years_trading") is None:
#         try:
#             ext["years_trading"] = _years_between(ext["business_commencement_date"], today)
#         except ValueError:
#             pass
#     if ext.get("insured_in_continental_us") is None and ext.get("insured_country"):
#         ext["insured_in_continental_us"] = (
#             ext["insured_country"] == "US"
#             and (ext.get("insured_state_province") or "") not in US_NON_CONTINENTAL)
#     if isinstance(ext.get("locations"), list) and ext.get("location_count") is None:
#         ext["location_count"] = len(ext["locations"])
#     return {"extracted": ext}
