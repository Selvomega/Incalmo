import shlex

from incalmo.core.actions.low_level_action import LowLevelAction
from incalmo.core.models.events.api_vulnerability_found_event import (
    APIVulnerabilityFound,
)
from incalmo.core.models.events.http_response_event import HTTPResponseEvent
from incalmo.models.agent import Agent
from incalmo.models.command_result import CommandResult

_SEP = "__INCALMO_BOLA_SEP__"


class BrokenObjectLevelAuth(LowLevelAction):
    """Tests for BOLA/IDOR by requesting the same resource with different object IDs.

    url_template should contain {id} as a placeholder, e.g.:
        "https://api.example.com/v1/users/{id}/profile"
    """

    def __init__(
        self,
        agent: Agent,
        url_template: str,
        object_ids: list,
        token: str,
    ):
        self.url_template = url_template
        self.object_ids = object_ids
        self.token = token

        cmds = []
        for obj_id in object_ids:
            url = url_template.replace("{id}", str(obj_id))
            cmd = (
                f'echo -n "{_SEP}{obj_id}:"; '
                f"curl -s -o /dev/null "
                f"-H {shlex.quote(f'Authorization: Bearer {token}')} "
                f"-X GET {shlex.quote(url)} "
                f'--write-out "%{{http_code}}"'
            )
            cmds.append(cmd)

        command = "; ".join(cmds)
        super().__init__(agent, command)

    async def get_result(self, results: CommandResult) -> list:
        raw = results.output
        events = []
        success_ids = []

        for obj_id in self.object_ids:
            marker = f"{_SEP}{obj_id}:"
            if marker in raw:
                idx = raw.index(marker) + len(marker)
                status_code = raw[idx : idx + 3].strip()
                url = self.url_template.replace("{id}", str(obj_id))
                events.append(HTTPResponseEvent(url, "GET", status_code, ""))
                if status_code in ("200", "201"):
                    success_ids.append(obj_id)

        if len(success_ids) > 1:
            details = f"IDs {success_ids} all returned 200 — potential unauthorized cross-object access"
            vuln_url = self.url_template
            events.append(APIVulnerabilityFound("BOLA", vuln_url, "GET", details))

        return events
