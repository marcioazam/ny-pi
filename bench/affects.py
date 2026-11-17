"""Does a PR change the harness's FUNCTIONAL behavior? Decides whether bench-pr spends a benchmark round.

Fail closed: any path not proven non-functional is functional. Rules (record: docs/bench/RUNBOOK.md):
non-functional = docs, repo tooling (CI, git hooks, release checks), the benchmark's own infra, eval infra, tests, licence
files, markdown that is not installed, and pure-UI paths (themes, HUD, statusline, visual extensions, render-only patches).
Instruction files installed under claude-home/ are prompts: always functional.
"""

import fnmatch
import subprocess
from pathlib import Path, PurePosixPath

# Pure UI: what the user sees, never what the agent is told or can do.
UI = (
    "themes/*",
    "extensions/ui/*",  # editor, a11y, terminal title, /diff, /btw overlays
    "extensions/ui-visual/*",  # header, icons, tool renderers, working indicator
    "extensions/footer-no-stats.ts",
    "extensions/sticky-prompt/*",
    "claude-home/bin/hud/*",
    "claude-home/plugins/claude-hud/*",
    "claude-home/commands/claude-hud-*.md",  # only configure the HUD
    "claude-home/patches/pi-code/statusline-multiline.patch",
    "claude-home/patches/pi-code/subagent-render.patch",  # call/result drawing only
    "claude-home/patches/pi-code/zzz-panel-column0.patch",  # panel column layout
)
NON_FUNCTIONAL = (
    "docs/*",
    ".github/*",
    ".githooks/*",
    "scripts/ci/*",
    "scripts/check-*",
    "scripts/refs-allow.txt",
    "scripts/fixtures/*",
    "bench/*",  # not installed in the harness (publish.list has no bench/ line)
    "claude-home/bin/evals/*",  # eval infra; bundle.sh is carved out below
    ".gitignore",
    ".gitattributes",
    ".editorconfig",
    ".leak-allow",
    ".gitleaks.toml",
    "LICENSE",
    "NOTICE",
)
FUNCTIONAL_EXCEPTIONS = (
    "claude-home/bin/evals/harbor/bundle.sh",
)  # builds the harness under test
TEST_NAMES = ("*.test.ts", "*.test.mjs", "test_*.py", "*_test.py", "test_*.sh")


def installed_paths(publish_list: str) -> set[str]:
    """Destination column of publish.list lines."""
    out: set[str] = set()
    for ln in publish_list.splitlines():
        if ln.strip() and not ln.startswith("#") and "\t" in ln:
            out.add(ln.split("\t")[1].strip())
    return out


def classify_path(p: str, installed: set[str]) -> tuple[bool, str]:
    """(is_functional, reason)."""
    pp = PurePosixPath(p)
    if p in FUNCTIONAL_EXCEPTIONS:
        return True, "builds the harness under test"
    if any(fnmatch.fnmatchcase(p, g) for g in UI):
        return False, "ui"
    if any(fnmatch.fnmatchcase(pp.name, g) for g in TEST_NAMES) or "tests" in pp.parts:
        return False, "test"
    if any(fnmatch.fnmatchcase(p, g) for g in NON_FUNCTIONAL):
        return False, "docs/tooling"
    if p.endswith(".md"):
        if p in installed or p.startswith("claude-home/"):
            return True, "instruction file installed in the harness"
        return False, "markdown"
    return True, "not proven non-functional"


def classify(
    files: list[str], publish_changes: list[str], installed: set[str]
) -> tuple[bool, list[tuple[str, bool, str]]]:
    """publish_changes: destinations of the publish.list lines the PR added or removed.
    A publish.list change is non-functional only when every touched destination is a test file."""
    rows: list[tuple[str, bool, str]] = []
    for f in files:
        if f == "publish.list":
            tests = bool(publish_changes) and all(
                classify_path(d, set()) == (False, "test") for d in publish_changes
            )
            rows.append(
                (
                    f,
                    not tests,
                    "only test paths" if tests else "installs or removes harness files",
                )
            )
        else:
            fn, why = classify_path(f, installed)
            rows.append((f, fn, why))
    return (any(r[1] for r in rows) or not rows), rows


def _git(*a: str) -> str:
    return subprocess.run(
        ["git", *a], check=True, capture_output=True, text=True
    ).stdout


def evaluate(
    base: str, head: str, repo: Path | None = None
) -> tuple[bool, list[tuple[str, bool, str]]]:
    """Diff merge-base(base, head)..head. Any git failure raises: the caller must treat that as functional."""
    cwd = ["-C", str(repo)] if repo else []
    files = _git(*cwd, "diff", "--name-only", f"{base}...{head}").splitlines()
    pub: list[str] = []
    if "publish.list" in files:
        d = _git(*cwd, "diff", "-U0", f"{base}...{head}", "--", "publish.list")
        pub = sorted(
            installed_paths(
                "\n".join(
                    ln[1:]
                    for ln in d.splitlines()
                    if ln[:1] in "+-" and ln[:3] not in ("+++", "---")
                )
            )
        )
    installed = installed_paths(_git(*cwd, "show", f"{head}:publish.list"))
    return classify(files, pub, installed)


def render(functional: bool, rows: list[tuple[str, bool, str]]) -> str:
    head = "functional" if functional else "non-functional"
    return "\n".join(
        [head, *(f"{'F' if fn else '-'} {p}: {why}" for p, fn, why in rows)]
    )
