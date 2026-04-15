import shlex

from incalmo.core.actions.low_level_action import LowLevelAction
from incalmo.core.models.events.http_response_event import HTTPResponseEvent
from incalmo.models.agent import Agent
from incalmo.models.command_result import CommandResult

_STATUS_SENTINEL = "__INCALMO_STATUS__"


class HTTPRequestWithToken(LowLevelAction):
    """HTTP request authenticated with a Bearer token."""

    def __init__(
        self,
        agent: Agent,
        url: str,
        method: str,
        token: str,
        body: str | None = None,
    ):
        self.url = url
        self.method = method.upper()
        self.token = token
        self.body = body

        parts = ["curl", "-s", "-X", self.method, shlex.quote(url)]
        parts += ["-H", shlex.quote(f"Authorization: Bearer {token}")]
        parts += ["-H", shlex.quote("Content-Type: application/json")]
        if body:
            parts += ["-d", shlex.quote(body)]
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
        return [HTTPResponseEvent(self.url, self.method, status_code, body.strip())]
