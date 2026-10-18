"""Derived risk fields computed from raw inputs, never extracted as stated
figures where the underlying data exists (BFR 7.1.6). Runs after extract.
Explicitly supplied derived values pass through untouched.
"""
# date: used to parse ISO dates and compute trading years.
from datetime import date

# US territories that are not continental US (excluded from continental flag).
US_NON_CONTINENTAL = {"PR", "GU", "VI", "AS", "MP"}


# _years_between: helper computing years between two ISO date strings.
def _years_between(start_iso: str, end_iso: str) -> float:
    # Parse start date from ISO string.
    s = date.fromisoformat(start_iso)
    # Parse end date from ISO string.
    e = date.fromisoformat(end_iso)
    # Return difference in days converted to years, rounded to 2 decimals.
    return round((e - s).days / 365.25, 2)


# derive: compute derived fields (loss aggregates, continental US, years trading).
def derive(state: dict, as_at: str | None = None) -> dict:
    # Work on a copy of extracted data so we don't mutate input.
    ext = dict(state.get("extracted") or {})
    # as_at defaults to today if not provided.
    today = as_at or date.today().isoformat()
    # Pull loss history list (if any).
    losses = ext.get("losses") or []
    # Only derive loss aggregates if losses exist and not already supplied.
    if losses and ("largest_single_claim_amount" not in ext or ext.get("largest_single_claim_amount") is None):
        # Extract paid/incurred amounts from each loss record.
        amounts = [l.get("paid_incurred_amount", 0) or 0 for l in losses]
        # Largest single claim = max amount.
        ext["largest_single_claim_amount"] = max(amounts) if amounts else 0
        # Total claims amount = sum of amounts.
        ext["total_claims_amount"] = sum(amounts)
        # Count claims in last 3 years.
        ext["claim_count_3_years"] = sum(1 for l in losses if l.get("loss_date", "") >= f"{int(today[:4]) - 3}{today[4:]}")
        # Count claims in last 5 years.
        ext["claim_count_5_years"] = sum(1 for l in losses if l.get("loss_date", "") >= f"{int(today[:4]) - 5}{today[4:]}")
    # Derive years_trading from commencement date if not already supplied.
    if ext.get("business_commencement_date") and ext.get("years_trading") is None:
        try:
            ext["years_trading"] = _years_between(ext["business_commencement_date"], today)
        except ValueError:
            # Invalid date format; leave years_trading unset.
            pass
    # Derive continental US flag from country/state if not supplied.
    if ext.get("insured_in_continental_us") is None and ext.get("insured_country"):
        ext["insured_in_continental_us"] = (
            ext["insured_country"] == "US"
            and (ext.get("insured_state_province") or "") not in US_NON_CONTINENTAL)
    # Derive location_count from locations list if not supplied.
    if isinstance(ext.get("locations"), list) and ext.get("location_count") is None:
        ext["location_count"] = len(ext["locations"])
    # Return merged extracted data.
    return {"extracted": ext}
