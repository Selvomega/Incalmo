import shlex

from incalmo.core.actions.low_level_action import LowLevelAction
from incalmo.core.models.events.http_response_event import HTTPResponseEvent
from incalmo.models.agent import Agent
from incalmo.models.command_result import CommandResult

_METHODS = ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"]
_SEP = "__INCALMO_METHOD_SEP__"


class HTTPMethodFuzz(LowLevelAction):
    """Tries multiple HTTP methods on a URL to discover which are accepted."""

    def __init__(self, agent: Agent, url: str, token: str | None = None):
        self.url = url
        self.token = token

        auth_flag = f'-H "Authorization: Bearer {token}"' if token else ""

        # Build a single shell command that tries each method and prints results
        method_commands = []
        for method in _METHODS:
            # HEAD doesn't return body; use -I for it
            if method == "HEAD":
                cmd = (
                    f'echo -n "{_SEP}{method}:"; '
                    f"curl -s -I -X HEAD {auth_flag} {shlex.quote(url)} "
                    f'--write-out "%{{http_code}}" -o /dev/null'
                )
            else:
                cmd = (
                    f'echo -n "{_SEP}{method}:"; '
                    f"curl -s -o /dev/null -X {method} {auth_flag} {shlex.quote(url)} "
                    f'--write-out "%{{http_code}}"'
                )
            method_commands.append(cmd)

        command = "; ".join(method_commands)
        super().__init__(agent, command)

    async def get_result(self, results: CommandResult) -> list:
        raw = results.output
        events = []
        for method in _METHODS:
            marker = f"{_SEP}{method}:"
            if marker in raw:
                idx = raw.index(marker) + len(marker)
                status_code = raw[idx : idx + 3].strip()
                events.append(HTTPResponseEvent(self.url, method, status_code, ""))
        return events
