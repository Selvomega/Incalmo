import json
import hashlib
import textwrap

from incalmo.core.actions.low_level_action import LowLevelAction
from incalmo.core.models.events.http_response_event import HTTPResponseEvent
from incalmo.core.models.events.http_batch_summary_event import HTTPBatchSummaryEvent
from incalmo.models.agent import Agent
from incalmo.models.command_result import CommandResult


class AsyncHTTPBatch(LowLevelAction):
    """Execute multiple HTTP requests in parallel using httpx on the agent.

    Sends a Python script to the agent that batches multiple URLs and executes
    them concurrently, returning results as JSON.
    """

    def __init__(
        self,
        agent: Agent,
        urls: list[str],
        method: str = "GET",
        headers: dict | None = None,
        timeout: int = 10,
    ):
        self.urls = urls
        self.method = method.upper()
        self.headers = headers or {}
        self.timeout = timeout

        # Generate a unique script name based on URL list hash
        url_hash = hashlib.md5("".join(urls).encode()).hexdigest()[:8]
        self.script_path = f"/tmp/async_http_batch_{url_hash}.py"
        self.output_path = f"/tmp/async_http_batch_{url_hash}.json"

        # Generate Python script
        script = self._generate_script()

        # Use echo + python3 pipe (works in non-interactive shells, unlike here-documents)
        script_escaped = script.replace('\\', '\\\\').replace('"', '\\"').replace('$', '\\$').replace('`', '\\`')
        command = f'echo "{script_escaped}" | python3'

        super().__init__(agent, command)

    def _generate_script(self) -> str:
        headers_json = json.dumps(self.headers)
        urls_json = json.dumps(self.urls)

        script = textwrap.dedent(f'''
import asyncio
import json
import httpx
import sys

async def fetch_url(client, url):
    try:
        response = await client.get(url, timeout={self.timeout})
        return {{
            "url": url,
            "status_code": str(response.status_code),
            "body": response.text[:5000],
            "error": None
        }}
    except Exception as e:
        return {{
            "url": url,
            "status_code": "error",
            "body": "",
            "error": str(e)
        }}

async def main():
    urls = {urls_json}
    headers = {headers_json}
    results = []

    try:
        async with httpx.AsyncClient(headers=headers, timeout={self.timeout}, verify=False) as client:
            tasks = [fetch_url(client, url) for url in urls]
            results = await asyncio.gather(*tasks)
    except Exception as e:
        # If httpx fails, fall back to curl wrapper
        import subprocess
        for url in urls:
            try:
                cmd = ['curl', '-s', '-k', '-w', '\\n%{{http_code}}', url]
                output = subprocess.check_output(cmd, timeout={self.timeout}, stderr=subprocess.DEVNULL, text=True)
                lines = output.strip().split('\\n')
                status = lines[-1] if lines else 'error'
                body = '\\n'.join(lines[:-1]) if len(lines) > 1 else ''
                results.append({{"url": url, "status_code": status, "body": body, "error": None}})
            except Exception as curl_err:
                results.append({{"url": url, "status_code": "error", "body": "", "error": str(curl_err)}})

    # Print JSON to stdout - MUST succeed
    sys.stdout.write(json.dumps(results))
    sys.stdout.flush()

asyncio.run(main())
        ''').strip()

        return script

    async def get_result(self, results: CommandResult) -> list:
        responses = []

        try:
            # Parse JSON output from the script
            response_data = json.loads(results.output)

            # Collect response data with bodies for successful responses only
            if isinstance(response_data, list):
                for item in response_data:
                    status = item.get("status_code", "unknown")
                    body = item.get("body", "")

                    # Only keep response body for successful responses (2xx, 3xx)
                    # For error codes (4xx, 5xx) and errors, discard the body to save LLM context
                    if status.startswith(("2", "3")):
                        response_body = body
                    else:
                        response_body = ""

                    responses.append({
                        "url": item.get("url", ""),
                        "method": self.method,
                        "status_code": status,
                        "response_body": response_body
                    })

        except json.JSONDecodeError:
            # If JSON parsing fails, log as errors
            for url in self.urls:
                responses.append({
                    "url": url,
                    "method": self.method,
                    "status_code": "error",
                    "response_body": ""
                })

        # Return a single grouped summary event
        return [HTTPBatchSummaryEvent(responses)]
