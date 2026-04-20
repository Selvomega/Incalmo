import shlex

from incalmo.core.actions.low_level_action import LowLevelAction
from incalmo.core.models.events.api_vulnerability_found_event import APIVulnerabilityFound
from incalmo.models.agent import Agent
from incalmo.models.command_result import CommandResult

# Separator between the failure block header and its body in schemathesis output
_FAILURE_DIVIDER = "_" * 5

# Only installs if the binary is absent — safe to run repeatedly
_ENSURE_SCHEMATHESIS = (
    "command -v schemathesis >/dev/null 2>&1 || pip install -q schemathesis"
)


class SchematesisScan(LowLevelAction):
    """Runs schemathesis against an OpenAPI spec URL using property-based testing.

    Schemathesis auto-generates test cases from the spec and checks for:
    - Server errors: any 5xx response (not_a_server_error)
    - Schema violations: response body not conforming to the declared schema (response_conformance)

    Parses the FAILURES section of schemathesis text output and emits one
    APIVulnerabilityFound per failing endpoint.

    With setup=True (default) the action installs schemathesis via pip if it is not
    already present on the attacker agent — no manual preparation required.
    """

    def __init__(
        self,
        agent: Agent,
        spec_url: str,
        base_url: str | None = None,
        token: str | None = None,
        checks: str = "not_a_server_error,response_conformance",
        setup: bool = True,
    ):
        self.spec_url = spec_url

        parts = ["schemathesis", "run", shlex.quote(spec_url)]
        if base_url:
            parts += ["--base-url", shlex.quote(base_url)]
        if token:
            parts += ["--header", shlex.quote(f"Authorization: Bearer {token}")]
        parts += ["--checks", checks, "--no-color"]
        scan_cmd = " ".join(parts)

        command = f"{_ENSURE_SCHEMATHESIS}; {scan_cmd}" if setup else scan_cmd
        super().__init__(agent, command)

    async def get_result(self, results: CommandResult) -> list:
        output = results.output
        events: list = []

        # Walk the FAILURES section; each block begins with a _____-delimited header
        in_failures = False
        current_method_path: str | None = None
        current_detail_lines: list[str] = []

        def flush_current() -> None:
            if current_method_path:
                detail = " | ".join(current_detail_lines[:5]) if current_detail_lines else "see output"
                events.append(
                    APIVulnerabilityFound(
                        "SchemaViolation",
                        self.spec_url,
                        current_method_path.split()[0] if current_method_path else "UNKNOWN",
                        f"{current_method_path}: {detail}",
                    )
                )

        for line in output.splitlines():
            stripped = line.strip()

            if stripped == "FAILURES":
                in_failures = True
                continue

            if not in_failures:
                continue

            # Section-end marker (====== summary line)
            if stripped.startswith("=") and "passed" in stripped or "failed" in stripped:
                flush_current()
                break

            # Block header: _____ METHOD /path _____
            if stripped.startswith(_FAILURE_DIVIDER) and stripped.endswith(_FAILURE_DIVIDER):
                flush_current()
                current_method_path = stripped.strip("_ ").strip()
                current_detail_lines = []
                continue

            if current_method_path and stripped:
                current_detail_lines.append(stripped)

        # If we never hit the summary line, flush whatever is pending
        if in_failures and current_method_path:
            flush_current()

        # Fallback: schemathesis reported failures but output format was unexpected
        if not events and ("failed" in output.lower() or " F" in output):
            events.append(
                APIVulnerabilityFound(
                    "SchemaViolation",
                    self.spec_url,
                    "UNKNOWN",
                    "Schemathesis reported failures — inspect raw output for details",
                )
            )

        return events
