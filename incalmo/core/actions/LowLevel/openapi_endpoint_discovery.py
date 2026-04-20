import shlex

from incalmo.core.actions.low_level_action import LowLevelAction
from incalmo.core.models.events.api_endpoint_discovered_event import APIEndpointDiscovered
from incalmo.core.models.events.bash_output_event import BashOutputEvent
from incalmo.models.agent import Agent
from incalmo.models.command_result import CommandResult

_VALID_METHODS = {"GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"}

# Fetches OpenAPI JSON spec and prints METHOD|PATH for every operation defined in paths
_PY_SCRIPT = (
    "import json,sys;"
    "s=json.load(sys.stdin);"
    "["
    "print(m.upper()+'|'+p)"
    " for p,v in s.get('paths',{}).items()"
    " for m in v"
    " if m.upper() in ('GET','POST','PUT','DELETE','PATCH','OPTIONS','HEAD')"
    "]"
)


class OpenAPIEndpointDiscovery(LowLevelAction):
    """Fetches an OpenAPI/Swagger JSON spec and emits one APIEndpointDiscovered per path+method.

    Parses the `paths` object from the spec and extracts every HTTP method+path pair,
    constructing full URLs from base_url + path. Use this before manual probing to
    enumerate the full attack surface directly from the spec rather than guessing paths.

    Requires python3 on the attacker agent (standard in most environments).
    """

    def __init__(
        self,
        agent: Agent,
        spec_url: str,
        base_url: str,
        token: str | None = None,
    ):
        self.base_url = base_url.rstrip("/")

        auth_flag = f"-H {shlex.quote(f'Authorization: Bearer {token}')} " if token else ""
        command = (
            f"curl -s --max-time 30 -H {shlex.quote('Accept: application/json')} "
            f"{auth_flag}{shlex.quote(spec_url)} "
            f"| python3 -c {shlex.quote(_PY_SCRIPT)}"
        )
        super().__init__(agent, command)

    async def get_result(self, results: CommandResult) -> list:
        events = []
        for line in results.output.splitlines():
            line = line.strip()
            if "|" not in line:
                continue
            method, path = line.split("|", 1)
            if method not in _VALID_METHODS:
                continue
            full_url = self.base_url + path
            events.append(APIEndpointDiscovered(full_url, method, "spec"))

        if not events:
            detail = results.stderr.strip() or results.output.strip() or "no output"
            events.append(
                BashOutputEvent(
                    self.agent,
                    f"OpenAPIEndpointDiscovery failed for {self.base_url} "
                    f"(exit_code={results.exit_code}): {detail}",
                )
            )
        return events
