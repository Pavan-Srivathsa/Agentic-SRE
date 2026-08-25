from investigator.guardrails.redact import redact


def test_redacts_secrets_and_email() -> None:
    text = "token=ghp_example user=sre@example.com"
    out = redact(text)
    assert "ghp_example" not in out
    assert "sre@example.com" not in out
    assert "[REDACTED]" in out
