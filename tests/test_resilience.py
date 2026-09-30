"""Retries bound the blast radius; logs never leak content."""
import urllib.error
import pytest
from nodes.retry import with_retry, is_transient
from nodes.log import safe_event
import json


def test_retry_then_success():
    calls = []
    def flaky():
        calls.append(1)
        if len(calls) < 3:
            raise urllib.error.HTTPError("u", 429, "busy", {}, None)
        return "ok"
    assert with_retry(flaky, sleep=lambda s: None) == "ok"
    assert len(calls) == 3


def test_non_transient_raises_immediately():
    calls = []
    def bad():
        calls.append(1)
        raise urllib.error.HTTPError("u", 400, "bad", {}, None)
    with pytest.raises(urllib.error.HTTPError):
        with_retry(bad, sleep=lambda s: None)
    assert len(calls) == 1


def test_exhaustion_reraises():
    def down():
        raise urllib.error.URLError("nope")
    with pytest.raises(urllib.error.URLError):
        with_retry(down, retries=1, sleep=lambda s: None)


def test_logs_redact_content():
    line = safe_event("extracted", submission_reference="S",
                      text="secret", value=123, outcome="Accept")
    assert "secret" not in line and "123" not in line.replace("Accept", "")
    assert json.loads(line)["outcome"] == "Accept"
