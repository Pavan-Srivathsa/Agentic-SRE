from datetime import datetime, timedelta

import pytest

from investigator.connectors.bounds import BoundsError, clamp_window


def test_clamp_window_accepts_30_minutes() -> None:
    start = datetime(2026, 8, 25, 16, 0, 0)
    end = start + timedelta(minutes=30)
    assert clamp_window(start, end) == (start, end)


def test_clamp_window_rejects_inverted_range() -> None:
    start = datetime(2026, 8, 25, 16, 0, 0)
    with pytest.raises(BoundsError):
        clamp_window(start, start - timedelta(minutes=1))


def test_clamp_window_rejects_too_long() -> None:
    start = datetime(2026, 8, 25, 16, 0, 0)
    with pytest.raises(BoundsError, match="time range exceeds"):
        clamp_window(start, start + timedelta(minutes=31))
