from incalmo.core.models.events.event import Event


class HTTPResponseEvent(Event):
    def __init__(self, url: str, method: str, status_code: str, response_body: str):
        self.url = url
        self.method = method
        self.status_code = status_code
        self.response_body = response_body

    def __str__(self) -> str:
        preview = self.response_body[:200] if self.response_body else ""
        return f"HTTP {self.method} {self.url} → {self.status_code}: {preview}"
