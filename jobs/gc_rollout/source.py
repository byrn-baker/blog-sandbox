"""Validate source while permitting reviewed backup artifacts in a shared repo."""
import subprocess
from pathlib import Path, PurePosixPath


def git(root, *args):
    result = subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, timeout=30)
    return result.stdout.decode("utf-8")


def relative_backup_path(rendered):
    path = PurePosixPath(rendered)
    if path.is_absolute() or ".." in path.parts or not path.parts or str(path) == ".":
        raise ValueError("Backup path must be a concrete relative file path")
    # Never let a bad mapping exempt executable source or Git metadata.
    if path.suffix not in {".cfg", ".conf"}:
        raise ValueError("NTP profile backup artifacts must be .cfg or .conf files")
    if path.parts[0] in {".git", "jobs", "templates", "config_contexts", "graphql_queries", "integrations"}:
        raise ValueError("Backup output mapping overlaps protected source")
    return str(path)


def validate_source(repo, approved):
    if str(repo.pk) != approved["id"] or repo.name != approved["name"]:
        raise ValueError("Source repository identity changed")
    root = Path(repo.filesystem_path)
    allowed = set(approved.get("backup_paths", []))
    baseline = approved["commit"]
    head = git(root, "rev-parse", "HEAD").strip()
    for revision in {head, repo.current_head}:
        if revision == baseline:
            continue
        try:
            git(root, "merge-base", "--is-ancestor", baseline, revision)
            changed = set(filter(None, git(root, "diff", "--name-only", "-z", baseline, revision, "--").split("\0")))
        except subprocess.CalledProcessError as exc:
            raise ValueError("Source HEAD changed or approved history is unavailable") from exc
        if not changed <= allowed:
            raise ValueError("Source HEAD changed outside approved backup paths; prepare a new rollout")
    dirty = set(filter(None, git(root, "diff", "--name-only", "-z", "HEAD", "--").split("\0")))
    dirty.update(filter(None, git(root, "ls-files", "--others", "--exclude-standard", "-z").split("\0")))
    if not dirty <= allowed:
        raise ValueError("Uncommitted source changes invalidate approval")
