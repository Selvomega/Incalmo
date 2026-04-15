import shlex

from incalmo.core.actions.low_level_action import LowLevelAction
from incalmo.core.models.events.api_vulnerability_found_event import (
    APIVulnerabilityFound,
)
from incalmo.core.models.events.http_response_event import HTTPResponseEvent
from incalmo.models.agent import Agent
from incalmo.models.command_result import CommandResult

_STATUS_SENTINEL = "__INCALMO_STATUS__"


class MissingFunctionLevelAuth(LowLevelAction):
    """Tests whether an endpoint is accessible without any authentication."""

    def __init__(
        self,
        agent: Agent,
        url: str,
        method: str = "GET",
        body: str | None = None,
    ):
        self.url = url
        self.method = method.upper()
        self.body = body

        parts = ["curl", "-s", "-X", self.method, shlex.quote(url)]
        if body:
            parts += [
                "-H",
                shlex.quote("Content-Type: application/json"),
                "-d",
                shlex.quote(body),
            ]
        parts += ["--write-out", shlex.quote(f"\n{_STATUS_SENTINEL}:%{{http_code}}")]
        command = " ".join(parts)
        super().__init__(agent, command)

    async def get_result(self, results: CommandResult) -> list:
        raw = results.output
        sentinel = f"\n{_STATUS_SENTINEL}:"
        if sentinel in raw:
            body, status_code = raw.rsplit(sentinel, 1)
            status_code = status_code.strip()
        else:
            body = raw
            status_code = "unknown"

        body = body.strip()
        events = [HTTPResponseEvent(self.url, self.method, status_code, body)]

        if status_code in ("200", "201"):
            details = (
                f"{self.method} {self.url} returned {status_code} without any "
                f"authentication headers"
            )
            events.append(
                APIVulnerabilityFound("MissingAuth", self.url, self.method, details)
            )

        return events
