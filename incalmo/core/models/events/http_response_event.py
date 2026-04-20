from incalmo.core.models.events.event import Event


class HTTPResponseEvent(Event):
    def __init__(self, url: str, method: str, status_code: str, response_body: str):
        self.url = url
        self.method = method
        self.status_code = status_code
        self.response_body = response_body

    def __str__(self) -> str:
        if not self.response_body:
            return f"HTTP {self.method} {self.url} → {self.status_code}"

        if self.status_code in ("404", "403", "401"):
            return f"HTTP {self.method} {self.url} → {self.status_code}"

        preview = self.response_body[:100] if self.response_body else ""
        preview = preview.replace("\n", " ").replace("\r", "")
        if len(self.response_body) > 100:
            preview += "..."
        return f"HTTP {self.method} {self.url} → {self.status_code}: {preview}"
