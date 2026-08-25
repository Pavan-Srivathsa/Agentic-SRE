from investigator.connectors.github import GitClient
from paths import CHANGELOG_PATH


def test_payment_commit_diff() -> None:
    diff = GitClient(CHANGELOG_PATH).get_commit_diff("payment-service")
    assert diff.commit_sha == "abc123def456"
    assert "unindexed" in diff.diff_summary.lower() or "join" in diff.diff_summary.lower()
    assert "demo/services/payments/app.py" in diff.files_changed


def test_missing_commit_raises() -> None:
    try:
        GitClient(CHANGELOG_PATH).get_commit_diff("payment-service", commit_sha="nope")
        raise AssertionError("expected KeyError")
    except KeyError:
        pass
