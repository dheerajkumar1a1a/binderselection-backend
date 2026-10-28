"""Information-request derivation: engine gaps -> named ask items.

The engine already did the deciding here — a rule that couldn't assess said
so ("Cannot assess" with reason `missing:<field>`), and CONTEXT.md forbids
inventing requests. This module only *names* the existing gaps deterministically
and phrases the question to the broker. Field names without a dot map straight
into the answer sheet's structured record (the keyless stub can read them);
nested paths (e.g. `coverage_sections.limit`) go into the sheet's text — live
extractors can read them there, the stub honestly can't.
"""
from __future__ import annotations


def cannot_assess(items_payload: dict) -> list[dict]:
    """Unique missing fields across all binders of one evaluation payload.

    Returns [{field, label, question, raised_by: [[binder_id, rule_id], ...]}] —
    one item per field regardless of how many binders raised it (the broker
    answers the fact, not the binder).
    """
    raised: dict[str, list[list[str]]] = {}
    order: list[str] = []
    for b in items_payload.get("binder_results") or []:
        for o in b.get("rule_outcomes") or []:
            if o.get("outcome") != "Cannot assess":
                continue
            reason = o.get("reason") or ""
            field = reason[len("missing:"):] if reason.startswith("missing:") else reason
            if not field:
                continue
            entry = [b.get("binder_id", "?"), o.get("rule_id", "?")]
            if field not in raised:
                raised[field] = [entry]
                order.append(field)
            else:
                raised[field].append(entry)
    return [{"field": f,
             "label": _label(f),
             "question": _question(f, raised[f]),
             "raised_by": raised[f]} for f in order]


def _label(field: str) -> str:
    """Human-friendly label for a field name."""
    # Split on dots, underscores, and hyphens; title-case each segment
    import re
    parts = re.split(r'[._-]+', field)
    return " ".join(p.capitalize() for p in parts if p)


def _question(field: str, raised_by: list[list[str]]) -> str:
    who = ", ".join(f"{b} ({r})" for b, r in raised_by[:4])
    more = f" and {len(raised_by) - 4} more" if len(raised_by) > 4 else ""
    return (f"Please provide the missing data item '{field}'. "
            f"Without it the following rule(s) could not assess: {who}{more}.")


def flat_field(field: str) -> bool:
    """True if the field can live in the answer sheet's structured record."""
    return "." not in (field or "")


def coerce(field: str, raw: str):
    """Deterministic coercion of a typed answer into a structured-record value.
    No LLM, no discovery — just obvious scalars; anything else stays a string."""
    s = (raw or "").strip()
    low = s.lower()
    if low in ("yes", "true", "y"):
        return True
    if low in ("no", "false", "n"):
        return False
    if low in ("none", "null", "n/a", "na"):
        return None
    for conv in (int, float):
        try:
            return conv(s.replace(",", "").replace("$", ""))
        except ValueError:
            continue
    return s if s else None
