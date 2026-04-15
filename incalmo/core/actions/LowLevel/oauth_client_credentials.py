import json
import shlex

from incalmo.core.actions.low_level_action import LowLevelAction
from incalmo.core.models.events.api_credential_found_event import APICredentialFound
from incalmo.core.models.events.http_response_event import HTTPResponseEvent
from incalmo.models.agent import Agent
from incalmo.models.command_result import CommandResult

_STATUS_SENTINEL = "__INCALMO_STATUS__"


class OAuthClientCredentials(LowLevelAction):
    """Fetches an OAuth2 access token via the client_credentials grant."""

    def __init__(
        self,
        agent: Agent,
        token_url: str,
        client_id: str,
        client_secret: str,
        scope: str = "",
    ):
        self.token_url = token_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.scope = scope

        form_data = (
            f"grant_type=client_credentials"
            f"&client_id={client_id}"
            f"&client_secret={client_secret}"
        )
        if scope:
            form_data += f"&scope={scope}"

        parts = [
            "curl",
            "-s",
            "-X",
            "POST",
            shlex.quote(token_url),
            "-H",
            shlex.quote("Content-Type: application/x-www-form-urlencoded"),
            "-d",
            shlex.quote(form_data),
            "--write-out",
            shlex.quote(f"\n{_STATUS_SENTINEL}:%{{http_code}}"),
        ]
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

        if status_code == "200":
            try:
                data = json.loads(body)
                token = data.get("access_token", "")
                expires_in = data.get("expires_in")
                scope = data.get("scope", self.scope)
                return [
                    APICredentialFound(
                        "Bearer", token, scope=scope, expires_in=expires_in
                    )
                ]
            except (json.JSONDecodeError, KeyError):
                pass

        return [HTTPResponseEvent(self.token_url, "POST", status_code, body)]
