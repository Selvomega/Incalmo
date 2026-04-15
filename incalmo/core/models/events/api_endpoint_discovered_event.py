from incalmo.core.models.events.event import Event


class APIEndpointDiscovered(Event):
    def __init__(self, url: str, method: str, status_code: str):
        self.url = url
        self.method = method
        self.status_code = status_code

    def __str__(self) -> str:
        return (
            f"Endpoint discovered: {self.method} {self.url} (HTTP {self.status_code})"
        )
