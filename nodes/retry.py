"""Transient-failure retries with backoff, bounded (BFR-NFR-016)."""
# time: used for sleep between retries.
import time
# urllib.error: HTTP/URL errors classified as transient or not.
import urllib.error


# is_transient: decide whether an exception is worth retrying.
def is_transient(exc: Exception) -> bool:
    # HTTP errors: retry only 429 (rate limit) or 5xx (server errors).
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code == 429 or 500 <= exc.code < 600
    # URL errors (network) are transient.
    return isinstance(exc, urllib.error.URLError)


# with_retry: call fn with bounded exponential backoff on transient errors.
def with_retry(fn, retries: int = 3, base_delay: float = 0.5, sleep=time.sleep):
    # Track last exception for re-raise after exhaustion.
    last = None
    # Attempt retries+1 times total.
    for attempt in range(retries + 1):
        try:
            # Success: return result immediately.
            return fn()
        except Exception as e:
            # Non-transient or last attempt: re-raise.
            if not is_transient(e) or attempt == retries:
                raise
            # Record and back off exponentially.
            last = e
            sleep(base_delay * (2 ** attempt))
    # Fallback re-raise (unreachable in practice).
    raise last  # pragma: no cover
