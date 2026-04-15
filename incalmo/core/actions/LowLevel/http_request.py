import shlex

from incalmo.core.actions.low_level_action import LowLevelAction
from incalmo.core.models.events.http_response_event import HTTPResponseEvent
from incalmo.models.agent import Agent
from incalmo.models.command_result import CommandResult

_STATUS_SENTINEL = "__INCALMO_STATUS__"


def _build_curl(url: str, method: str, headers: dict | None, body: str | None) -> str:
    parts = ["curl", "-s", "-X", method, shlex.quote(url)]
    if headers:
        for key, value in headers.items():
            parts += ["-H", shlex.quote(f"{key}: {value}")]
    if body:
        parts += ["-d", shlex.quote(body)]
    parts += ["--write-out", shlex.quote(f"\n{_STATUS_SENTINEL}:%{{http_code}}")]
    return " ".join(parts)


def _parse_curl_output(raw: str, url: str, method: str) -> HTTPResponseEvent:
    sentinel = f"\n{_STATUS_SENTINEL}:"
    if sentinel in raw:
        body, status_code = raw.rsplit(sentinel, 1)
        status_code = status_code.strip()
    else:
        body = raw
        status_code = "unknown"
    return HTTPResponseEvent(url, method, status_code, body.strip())


class HTTPRequest(LowLevelAction):
    """Generic HTTP request executed via curl on the agent host."""

    def __init__(
        self,
        agent: Agent,
        url: str,
        method: str = "GET",
        headers: dict | None = None,
        body: str | None = None,
    ):
        self.url = url
        self.method = method.upper()
        self.headers = headers or {}
        self.body = body
        command = _build_curl(url, self.method, headers, body)
        super().__init__(agent, command)

    async def get_result(self, results: CommandResult) -> list:
        return [_parse_curl_output(results.output, self.url, self.method)]
