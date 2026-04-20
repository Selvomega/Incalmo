from dataclasses import dataclass


@dataclass
class HTTPRequestRecord:
    """A lightweight record of a single HTTP request made during testing.

    Stored in EnvironmentStateService.request_history. Both HTTPResponseEvent
    and APIEndpointDiscovered are mapped into this type so the LLM has a single
    consistent list to query.
    """

    url: str
    method: str
    status_code: str
    response_body: str | None = None

    def __str__(self) -> str:
        body_preview = f": {self.response_body[:200]}" if self.response_body else ""
        return f"{self.method} {self.url} → {self.status_code}{body_preview}"
