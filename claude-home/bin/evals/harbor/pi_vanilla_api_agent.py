"""Harbor's stock pi agent plus the anthropic-workspace-id header (bench API-key mode, pi-vanilla arm).

A user API key without workspace needs the header on every call and Harbor's pi agent injects none.
After the stock install, merge it into models.json of pi's default dir ($HOME/.pi/agent): for a plain
`-m anthropic/<model>` the stock run() sets no PI_CODING_AGENT_DIR (only custom base_url or MCP do).
The workspace id comes from the harbor process env at runtime.
"""

import os
from typing import override

from harbor.agents.installed.pi import Pi  # type: ignore[import-not-found]
from harbor.environments.base import BaseEnvironment  # type: ignore[import-not-found]
from pi_harness_agent import _models_merge


class PiVanillaApiAgent(Pi):  # type: ignore[misc]
    @override
    async def install(self, environment: BaseEnvironment) -> None:
        await super().install(environment)
        ws = os.environ.get("ANTHROPIC_WORKSPACE_ID")
        if ws:
            await self.exec_as_agent(
                environment,
                command=f'set -e; mkdir -p "$HOME/.pi/agent" && cd "$HOME/.pi/agent" && {_models_merge("models.json", ws)}',
            )
