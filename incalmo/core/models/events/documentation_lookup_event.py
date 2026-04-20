from incalmo.core.models.events.event import Event


class DocumentationLookup(Event):
    def __init__(self, api_name: str, documentation_url: str, content: str):
        self.api_name = api_name
        self.documentation_url = documentation_url
        self.content = content

    def __str__(self) -> str:
        return f"Documentation retrieved for {self.api_name} from {self.documentation_url}"
