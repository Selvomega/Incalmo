import re

from incalmo.core.actions.low_level_action import LowLevelAction
from incalmo.core.models.events.documentation_lookup_event import (
    DocumentationLookup,
)
from incalmo.models.agent import Agent
from incalmo.models.command_result import CommandResult


class LookUpDocument(LowLevelAction):
    """Fetches API documentation from a given URL."""

    def __init__(
        self,
        agent: Agent,
        api_name: str,
        doc_url: str,
    ):
        self.api_name = api_name
        self.doc_url = doc_url

        command = f'curl -s "{self.doc_url}" | head -10000'
        super().__init__(agent, command)

    async def get_result(self, results: CommandResult) -> list:
        content = results.output if results.output else "No documentation found"
        # Clean up excessive whitespace
        content = re.sub(r"\s+", " ", content)[:3000]
        return [
            DocumentationLookup(self.api_name, self.doc_url, content)
        ]
