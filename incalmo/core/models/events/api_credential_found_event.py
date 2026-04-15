from incalmo.core.models.events.event import Event


class APICredentialFound(Event):
    def __init__(
        self,
        token_type: str,
        token_value: str,
        scope: str | None = None,
        expires_in: int | None = None,
    ):
        self.token_type = token_type
        self.token_value = token_value
        self.scope = scope
        self.expires_in = expires_in

    def __str__(self) -> str:
        return (
            f"API credential found: {self.token_type} token "
            f"(scope={self.scope}, expires_in={self.expires_in})"
        )
