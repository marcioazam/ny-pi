"""bench-pr gate: only PRs that change the harness's functional behavior spend a benchmark round (fail closed)."""

import subprocess
from pathlib import Path

import pytest

from bench import affects
from bench import run as rb

PUB = (
    "$HOME/.pi/agent/claude-home/CLAUDE.md\tclaude-home/CLAUDE.md\n"
    "$HOME/.pi/agent/x\textensions/x.ts\n"
    "# comment\n"
)


def verdict(*files: str, pub: list[str] | None = None) -> bool:
    return affects.classify(list(files), pub or [], affects.installed_paths(PUB))[0]


@pytest.mark.parametrize(
    "files",
    [
        ("docs/a.md", "README.md", "CHANGELOG.md", "docs/specs/x.txt"),
        ("themes/mono.json",),
        ("bench/run.py", "bench/tests/test_x.py"),
        (
            ".github/workflows/ci.yml",
            "scripts/ci/run-static.sh",
            ".gitignore",
            "LICENSE",
        ),
        (
            "extensions/ui/diff.ts",
            "extensions/ui-visual/tools.ts",
            "claude-home/bin/hud/claude-hud-usage.mjs",
        ),
        (
            "extensions/x.test.ts",
            "bin/test_pi_env.sh",
            "scripts/test_check_refs.py",
            "claude-home/bin/tests/a.sh",
        ),
        ("claude-home/patches/pi-code/statusline-multiline.patch",),
        ("claude-home/bin/evals/harbor/pi_vanilla_api_agent.py",),
    ],
)
def test_non_functional(files: tuple[str, ...]) -> None:
    assert verdict(*files) is False


@pytest.mark.parametrize(
    "files",
    [
        ("docs/a.md", "extensions/x.ts"),
        ("claude-home/CLAUDE.md",),
        ("claude-home/skills/new/SKILL.md",),  # not yet in publish.list, still a prompt
        ("claude-home/hooks/guard.py",),
        ("bin/pi",),
        ("install.sh",),
        ("third-party.json",),
        ("claude-home/patches/pi-code/goal.patch",),
        ("claude-home/bin/evals/harbor/bundle.sh",),
        ("something/unknown.bin",),
        (),  # empty diff: nothing proven
    ],
)
def test_functional(files: tuple[str, ...]) -> None:
    assert verdict(*files) is True


def test_publish_list_only_tests_is_non_functional() -> None:
    assert verdict("publish.list", pub=["extensions/x/index.test.ts"]) is False
    assert verdict("publish.list", pub=["extensions/y.ts"]) is True
    assert verdict("publish.list") is True


def test_render_lists_decision() -> None:
    f, rows = affects.classify(["docs/a.md"], [], set())
    assert affects.render(f, rows).splitlines() == [
        "non-functional",
        "- docs/a.md: docs/tooling",
    ]


def git(repo: Path, *a: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", *a],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def test_cli_against_real_git(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    git(tmp_path, "init", "-q", "-b", "main")
    (tmp_path / "publish.list").write_text(PUB)
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-qm", "base")
    git(tmp_path, "checkout", "-qb", "pr")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/a.md").write_text("x")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-qm", "doc")
    args = ["affects", "--repo", str(tmp_path), "--base", "main", "--head", "pr"]
    assert rb.main(args) == 0
    assert capsys.readouterr().out.splitlines()[0] == "non-functional"
    (tmp_path / "x.ts").write_text("x")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-qm", "code")
    assert rb.main(args) == 0
    assert capsys.readouterr().out.splitlines()[0] == "functional"
    # bad ref: fail closed
    assert (
        rb.main(["affects", "--repo", str(tmp_path), "--base", "nope", "--head", "pr"])
        == 0
    )
    assert capsys.readouterr().out.splitlines()[0] == "functional"
