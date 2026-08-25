from __future__ import annotations

import re

_SECRET = re.compile(r"(api[_-]?key|token|password|secret)\s*[:=]\s*\S+", re.I)
_EMAIL = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)


def redact(text: str) -> str:
    text = _SECRET.sub("[REDACTED]", text)
    return _EMAIL.sub("[REDACTED_EMAIL]", text)
