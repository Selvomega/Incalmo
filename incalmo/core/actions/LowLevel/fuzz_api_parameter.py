import shlex

from incalmo.core.actions.low_level_action import LowLevelAction
from incalmo.core.models.events.http_response_event import HTTPResponseEvent
from incalmo.models.agent import Agent
from incalmo.models.command_result import CommandResult

_SEP = "__INCALMO_FUZZ_SEP__"
_MAX_RESPONSE_LEN = 500


class FuzzAPIParameter(LowLevelAction):
    """Sends a list of parameter payloads to an endpoint to find unexpected behaviour.

    Each payload replaces the value of param_name in a JSON body:
        {"param_name": "<payload>"}

    Useful for discovering injection flaws, missing validation, and error leakage.
    """

    def __init__(
        self,
        agent: Agent,
        url: str,
        method: str,
        param_name: str,
        payloads: list,
        token: str | None = None,
    ):
        self.url = url
        self.method = method.upper()
        self.param_name = param_name
        self.payloads = payloads
        self.token = token

        cmds = []
        for i, payload in enumerate(payloads):
            # Escape payload for embedding in a JSON string
            escaped = payload.replace("\\", "\\\\").replace('"', '\\"')
            body = f'{{"{param_name}": "{escaped}"}}'
            auth_flag = (
                f"-H {shlex.quote(f'Authorization: Bearer {token}')} " if token else ""
            )
            cmd = (
                f'echo -n "{_SEP}{i}:"; '
                f"curl -s -X {self.method} {shlex.quote(url)} "
                f"-H {shlex.quote('Content-Type: application/json')} "
                f"{auth_flag}"
                f"-d {shlex.quote(body)} "
                f'--write-out "\\n__STATUS__:%{{http_code}}"'
            )
            cmds.append(cmd)

        command = "; ".join(cmds)
        super().__init__(agent, command)

    async def get_result(self, results: CommandResult) -> list:
        raw = results.output
        events = []

        for i, payload in enumerate(self.payloads):
            marker = f"{_SEP}{i}:"
            if marker not in raw:
                continue

            start = raw.index(marker) + len(marker)
            # Find end of this segment (start of next marker or end of string)
            next_marker = f"{_SEP}{i + 1}:"
            end = raw.index(next_marker) if next_marker in raw else len(raw)
            segment = raw[start:end]

            status_code = "unknown"
            response_body = segment
            if "\n__STATUS__:" in segment:
                response_body, status_code = segment.rsplit("\n__STATUS__:", 1)
                status_code = status_code.strip()[:3]

            response_body = response_body.strip()[:_MAX_RESPONSE_LEN]
            events.append(
                HTTPResponseEvent(self.url, self.method, status_code, response_body)
            )

        return events
