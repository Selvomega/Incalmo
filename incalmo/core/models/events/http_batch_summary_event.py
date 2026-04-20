from incalmo.core.models.events.event import Event
from collections import defaultdict


class HTTPBatchSummaryEvent(Event):
    """Groups multiple HTTP responses by status code for compact representation."""

    def __init__(self, responses: list[dict]):
        """
        responses: list of dicts with keys: url, method, status_code, response_body
        """
        self.responses = responses
        self._group_by_status()

    def _group_by_status(self):
        self.grouped = defaultdict(list)
        for resp in self.responses:
            status = resp.get("status_code", "unknown")
            self.grouped[status].append(resp)

    def __str__(self) -> str:
        if not self.grouped:
            return "HTTP Batch: No responses"

        lines = []
        for status in sorted(self.grouped.keys()):
            responses = self.grouped[status]
            count = len(responses)

            if count == 1:
                resp = responses[0]
                url = resp.get("url", "")
                body = resp.get("response_body", "")
                if body:
                    preview = body[:50].replace("\n", " ")
                    lines.append(f"HTTP {resp.get('method', 'GET')} {url} → {status}: {preview}...")
                else:
                    lines.append(f"HTTP {resp.get('method', 'GET')} {url} → {status}")
            else:
                lines.append(f"[{status}] {count} requests:")
                for resp in responses[:3]:
                    url = resp.get("url", "")
                    lines.append(f"  {url}")
                if count > 3:
                    lines.append(f"  ... and {count - 3} more")

        return "\n".join(lines)
