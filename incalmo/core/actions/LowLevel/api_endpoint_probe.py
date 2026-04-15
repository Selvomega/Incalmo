import shlex

from incalmo.core.actions.low_level_action import LowLevelAction
from incalmo.core.models.events.api_endpoint_discovered_event import (
    APIEndpointDiscovered,
)
from incalmo.models.agent import Agent
from incalmo.models.command_result import CommandResult


class APIEndpointProbe(LowLevelAction):
    """Probes a single API path and returns its HTTP status code."""

    def __init__(
        self,
        agent: Agent,
        base_url: str,
        path: str,
        method: str = "GET",
        token: str | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.path = "/" + path.lstrip("/")
        self.full_url = self.base_url + self.path
        self.method = method.upper()
        self.token = token

        parts = [
            "curl",
            "-s",
            "-o",
            "/dev/null",
            "--write-out",
            '"%{http_code}"',
            "-X",
            self.method,
        ]
        if token:
            parts += ["-H", shlex.quote(f"Authorization: Bearer {token}")]
        parts.append(shlex.quote(self.full_url))
        command = " ".join(parts)
        super().__init__(agent, command)

    async def get_result(self, results: CommandResult) -> list:
        status_code = results.output.strip().strip('"')
        return [APIEndpointDiscovered(self.full_url, self.method, status_code)]
