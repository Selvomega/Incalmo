import json
import shlex

from incalmo.core.actions.low_level_action import LowLevelAction
from incalmo.core.models.events.api_vulnerability_found_event import APIVulnerabilityFound
from incalmo.core.models.events.bash_output_event import BashOutputEvent
from incalmo.models.agent import Agent
from incalmo.models.command_result import CommandResult

# Fetch latest nuclei release tag using curl + python3 (both standard on pentest VMs)
_NUCLEI_VER_CMD = (
    "curl -s https://api.github.com/repos/projectdiscovery/nuclei/releases/latest"
    " | python3 -c \"import sys,json; print(json.load(sys.stdin)['tag_name'])\""
)

# ${_VER#v} strips the leading 'v' from the tag (e.g. v3.3.2 → 3.3.2) for the filename
_NUCLEI_BINARY_INSTALL = (
    f"_VER=$({_NUCLEI_VER_CMD}) && "
    'curl -sL "https://github.com/projectdiscovery/nuclei/releases/download/${_VER}/nuclei_${_VER#v}_linux_amd64.zip"'
    " -o /tmp/_nuclei_install.zip && "
    "mkdir -p ~/.local/bin && "
    "python3 -c \""
    "import zipfile, os; "
    "z = zipfile.ZipFile('/tmp/_nuclei_install.zip'); "
    "z.extract('nuclei', os.path.expanduser('~/.local/bin')); "
    "os.chmod(os.path.expanduser('~/.local/bin/nuclei'), 0o755)"
    "\" && "
    "rm -f /tmp/_nuclei_install.zip"
)

# Ensures nuclei is available:
#   1. Already installed → no-op
#   2. Go present → go install (preferred, handles updates)
#   3. Fallback → download pre-built linux_amd64 binary from GitHub releases
_ENSURE_NUCLEI = (
    "export PATH=$PATH:~/.local/bin:$(go env GOPATH 2>/dev/null)/bin; "
    "command -v nuclei >/dev/null 2>&1 || ("
    "mkdir -p ~/.local/bin && "
    "("
    "command -v go >/dev/null 2>&1 && "
    "go install github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest || "
    f"({_NUCLEI_BINARY_INSTALL})"
    ")"
    ")"
)


class NucleiScan(LowLevelAction):
    """Runs nuclei with microservice/API templates against a target URL.

    Uses community-maintained templates (filtered by tags) to detect:
    - Exposed admin panels and API endpoints
    - Misconfigured authentication and token exposure
    - Known CVEs in microservice frameworks (Spring, Keycloak, etc.)
    - Information disclosure via debug/health endpoints

    Parses nuclei's JSON-per-line output and emits one APIVulnerabilityFound per finding.

    With setup=True (default) the action installs nuclei via `go install` if it is not
    already present on the attacker agent. Requires Go to be installed on the agent;
    set setup=False if nuclei is pre-installed.
    """

    def __init__(
        self,
        agent: Agent,
        target_url: str,
        tags: str = "api,auth,token,exposure,misconfig",
        token: str | None = None,
        severity: str = "medium,high,critical",
        setup: bool = True,
    ):
        self.target_url = target_url

        parts = [
            "nuclei",
            "-u", shlex.quote(target_url),
            "-tags", shlex.quote(tags),
            "-severity", shlex.quote(severity),
            "-jsonl",
            "-silent",
            "-no-interactsh",
            "-timeout", "5",
            "-rate-limit", "20",
        ]
        if token:
            parts += ["-H", shlex.quote(f"Authorization: Bearer {token}")]

        scan_cmd = " ".join(parts)
        command = f"{_ENSURE_NUCLEI}; {scan_cmd}" if setup else scan_cmd
        super().__init__(agent, command)

    async def get_result(self, results: CommandResult) -> list:
        events: list = []
        for line in results.output.splitlines():
            line = line.strip()
            if not line or not line.startswith("{"):
                continue
            try:
                finding = json.loads(line)
                info = finding.get("info", {})
                name = info.get("name", "unknown")
                severity = info.get("severity", "unknown")
                matched_url = finding.get("matched-at", self.target_url)
                template_id = finding.get("template-id", "")
                method = finding.get("type", "http").upper()
                details = f"[{template_id}] {name} (severity={severity})"
                events.append(
                    APIVulnerabilityFound("NucleiTemplate", matched_url, method, details)
                )
            except (json.JSONDecodeError, KeyError):
                continue

        if not events:
            detail = results.stderr.strip() or results.output.strip() or "no output"
            events.append(
                BashOutputEvent(
                    self.agent,
                    f"NucleiScan produced no findings for {self.target_url} "
                    f"(exit_code={results.exit_code}): {detail[:500]}",
                )
            )
        return events
