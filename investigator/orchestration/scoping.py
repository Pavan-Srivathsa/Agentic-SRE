from __future__ import annotations

from datetime import datetime, timedelta

from investigator.connectors.bounds import MAX_RANGE, clamp_window
from investigator.connectors.dependencies import list_dependencies
from investigator.models.incident import AlertIngest, Scope, TimeWindow


def incident_window(starts_at: datetime) -> TimeWindow:
    start = starts_at - timedelta(minutes=5)
    end = starts_at + timedelta(minutes=10)
    start, end = clamp_window(start, end, MAX_RANGE)
    return TimeWindow(start=start, end=end)


def baseline_window(incident: TimeWindow) -> TimeWindow:
    end = incident.start
    start = end - timedelta(minutes=25)
    start, end = clamp_window(start, end, MAX_RANGE)
    return TimeWindow(start=start, end=end)


def combined_window(incident: TimeWindow, baseline: TimeWindow) -> TimeWindow:
    end = incident.end
    start = max(baseline.start, end - MAX_RANGE)
    start, end = clamp_window(start, end, MAX_RANGE)
    return TimeWindow(start=start, end=end)


def build_scope(alert: AlertIngest, depth: int = 2) -> Scope:
    incident = incident_window(alert.starts_at)
    baseline = baseline_window(incident)
    by_depth = list_dependencies(alert.service, depth=depth)
    services: list[str] = []
    seen: set[str] = set()
    for key in sorted(by_depth):
        for service in by_depth[key]:
            if service not in seen:
                seen.add(service)
                services.append(service)
    return Scope(
        primary_service=alert.service,
        services=services,
        incident=incident,
        baseline=baseline,
        by_depth=by_depth,
    )
