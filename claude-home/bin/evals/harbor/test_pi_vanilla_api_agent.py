"""pi_vanilla_api_agent without Harbor: after the stock install it merges the workspace header into the default pi dir."""

import asyncio
import json
import subprocess
import sys
import types
from pathlib import Path
from typing import Any

import pytest


class _Pi:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def install(self, environment: Any) -> None:
        self.calls.append(("base", "install"))

    async def exec_as_agent(self, environment: Any, command: str, env: Any = None, cwd: Any = None, timeout_sec: Any = None) -> None:  # fmt: skip
        self.calls.append(("agent", command))


def _stub(name: str, **attrs: Any) -> None:
    m = types.ModuleType(name)
    m.__dict__.update(attrs)
    sys.modules[name] = m


for _n in ("harbor", "harbor.agents", "harbor.agents.installed", "harbor.environments"):
    _stub(_n)
_stub("harbor.agents.installed.pi", Pi=_Pi)
_stub("harbor.agents.installed.node_install", nvm_node_install_snippet=lambda: "NVM")
_stub("harbor.environments.base", BaseEnvironment=object)
sys.path.insert(0, str(Path(__file__).parent))
import pi_vanilla_api_agent


def _install() -> list[tuple[str, str]]:
    agent = pi_vanilla_api_agent.PiVanillaApiAgent()
    asyncio.run(agent.install(object()))
    calls: list[tuple[str, str]] = agent.calls
    return calls


def test_install_runs_stock_install_then_merges(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ANTHROPIC_WORKSPACE_ID", "wrkspc_x'; rm -rf /")
    calls = _install()
    assert calls[0] == ("base", "install")
    cmd = calls[1][1]
    assert "anthropic-workspace-id" in cmd and "models.json" in cmd
    assert "'wrkspc_x'\"'\"'; rm -rf /'" in cmd  # shlex-quoted, never bare
    assert (
        '"$HOME/.pi/agent"' in cmd
    )  # pi's default dir: no PI_CODING_AGENT_DIR for plain -m anthropic/<model>


def test_no_workspace_skips_merge(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_WORKSPACE_ID", raising=False)
    assert _install() == [("base", "install")]


def test_merge_writes_header_under_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:  # fmt: skip
    monkeypatch.setenv("ANTHROPIC_WORKSPACE_ID", "w1")
    cmd = _install()[1][1]
    assert subprocess.run(["bash", "-c", cmd], env={"HOME": str(tmp_path), "PATH": "/usr/bin:/bin"}, check=False).returncode == 0  # fmt: skip
    d = json.loads((tmp_path / ".pi/agent/models.json").read_text())
    assert d["providers"]["anthropic"]["headers"] == {"anthropic-workspace-id": "w1"}
