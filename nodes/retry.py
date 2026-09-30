"""Transient-failure retries with backoff, bounded (BFR-NFR-016)."""
import time
import urllib.error


def is_transient(exc: Exception) -> bool:
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code == 429 or 500 <= exc.code < 600
    return isinstance(exc, urllib.error.URLError)


def with_retry(fn, retries: int = 3, base_delay: float = 0.5, sleep=time.sleep):
    last = None
    for attempt in range(retries + 1):
        try:
            return fn()
        except Exception as e:
            if not is_transient(e) or attempt == retries:
                raise
            last = e
            sleep(base_delay * (2 ** attempt))
    raise last  # pragma: no cover
