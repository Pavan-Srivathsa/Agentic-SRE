from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from investigator.models.telemetry import CommitDiff
from paths import CHANGELOG_PATH


class GitClient:
    """Read-only changelog adapter. A live GitHub implementation can replace this later."""

    def __init__(self, changelog_path: Path | None = None) -> None:
        self.changelog_path = changelog_path or CHANGELOG_PATH

    def _load(self) -> list[dict]:
        return json.loads(self.changelog_path.read_text(encoding="utf-8"))

    def get_commit_diff(self, service: str, commit_sha: str | None = None) -> CommitDiff:
        rows = [row for row in self._load() if row["service"] == service]
        if commit_sha:
            rows = [row for row in rows if row["commit_sha"] == commit_sha]
        if not rows:
            raise KeyError(f"no commit for service={service} sha={commit_sha}")
        row = rows[0]
        return CommitDiff(
            commit_sha=row["commit_sha"],
            service=row["service"],
            author=row["author"],
            message=row["message"],
            committed_at=datetime.fromisoformat(row["committed_at"].replace("Z", "+00:00")),
            files_changed=list(row.get("files_changed") or []),
            diff_summary=row.get("diff_summary") or "",
        )
