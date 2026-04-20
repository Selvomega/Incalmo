import json
import shlex

from incalmo.core.actions.low_level_action import LowLevelAction
from incalmo.core.models.events.api_vulnerability_found_event import APIVulnerabilityFound
from incalmo.models.agent import Agent
from incalmo.models.command_result import CommandResult

_ZAP_IMAGE = "ghcr.io/zaproxy/zaproxy:stable"
_REPORT_FILE = "incalmo_zap_report.json"

# Sentinels let us extract the JSON report from noisy ZAP scan output
_SENTINEL_START = "__INCALMO_ZAP_START__"
_SENTINEL_END = "__INCALMO_ZAP_END__"

# ZAP Docker image is ~500 MB; only pull if not already cached
_ENSURE_ZAP = (
    f"docker image inspect {_ZAP_IMAGE} >/dev/null 2>&1 "
    f"|| docker pull -q {_ZAP_IMAGE}"
)

# ZAP alert risk codes: 0=informational 1=low 2=medium 3=high
_MIN_RISK_CODE = 2


class ZAPScan(LowLevelAction):
    """Runs OWASP ZAP API scan against an OpenAPI spec using the official Docker image.

    Uses zap-api-scan.py which:
    - Spiders all paths defined in the OpenAPI spec
    - Runs passive analysis on every response
    - Runs active injection attacks (SQLi, XSS, path traversal, etc.) against parameters
    - Reports findings categorised by OWASP risk level

    ZAP writes a JSON report which is extracted via sentinel markers and parsed into
    APIVulnerabilityFound events (medium severity and above only).

    Requires Docker on the attacker agent. First run pulls the image (~500 MB).
    Set setup=False to skip the pull check if the image is already present.
    """

    def __init__(
        self,
        agent: Agent,
        spec_url: str,
        format: str = "openapi",
        token: str | None = None,
        max_scan_mins: int = 60,
        setup: bool = True,
    ):
        self.spec_url = spec_url

        # ZAP writes the JSON report to /zap/wrk/ inside the container.
        # Mounting /tmp as /zap/wrk makes the report appear at /tmp/<file> on the host.
        zap_parts = [
            "docker run --rm",
            "-v /tmp:/zap/wrk:rw",
            _ZAP_IMAGE,
            "zap-api-scan.py",
            f"-t {shlex.quote(spec_url)}",
            f"-f {shlex.quote(format)}",
            f"-J {_REPORT_FILE}",
            f"-m {max_scan_mins}",
        ]

        if token:
            # ZAP replacer script injects a fixed header into every request
            replacer_cfg = (
                "-config replacer.full_list(0).description=incalmo_auth "
                "-config replacer.full_list(0).enabled=true "
                "-config replacer.full_list(0).matchtype=REQ_HEADER "
                "-config replacer.full_list(0).matchstr=Authorization "
                f"-config replacer.full_list(0).replacement=Bearer+{token}"
            )
            zap_parts.append(f"-z {shlex.quote(replacer_cfg)}")

        zap_cmd = " ".join(zap_parts)
        # Print sentinels around the report so we can extract JSON from mixed output
        read_cmd = (
            f"echo {_SENTINEL_START}; "
            f"cat /tmp/{_REPORT_FILE}; "
            f"echo {_SENTINEL_END}"
        )

        scan_and_read = f"{zap_cmd}; {read_cmd}"
        command = f"{_ENSURE_ZAP}; {scan_and_read}" if setup else scan_and_read
        super().__init__(agent, command)

    async def get_result(self, results: CommandResult) -> list:
        output = results.output
        events: list = []

        # Extract JSON between sentinel markers
        if _SENTINEL_START not in output or _SENTINEL_END not in output:
            return events

        start = output.index(_SENTINEL_START) + len(_SENTINEL_START)
        end = output.index(_SENTINEL_END)
        raw_json = output[start:end].strip()

        try:
            report = json.loads(raw_json)
        except json.JSONDecodeError:
            return events

        for site in report.get("site", []):
            for alert in site.get("alerts", []):
                try:
                    risk_code = int(alert.get("riskcode", 0))
                except ValueError:
                    continue
                if risk_code < _MIN_RISK_CODE:
                    continue

                name = alert.get("name", "unknown")
                risk_desc = alert.get("riskdesc", "")
                cweid = alert.get("cweid", "-1")

                # Emit one event per affected URL instance (capped at 5 to avoid noise)
                instances = alert.get("instances", [{}])[:5]
                for instance in instances:
                    url = instance.get("uri", self.spec_url)
                    method = instance.get("method", "GET")
                    details = f"[ZAP/CWE-{cweid}] {name} — {risk_desc}"
                    events.append(APIVulnerabilityFound("ZAPAlert", url, method, details))

        return events
