import pytest
import json
from incalmo.core.actions.LowLevel.async_http_batch import AsyncHTTPBatch
from incalmo.models.agent import Agent
from incalmo.models.command_result import CommandResult


@pytest.fixture
def test_agent():
    """Create a mock agent for testing."""
    return Agent(
        paw="test_paw",
        username="attacker",
        privilege="User",
        pid=1234,
        host_ip_addrs=["192.168.122.100"],
        hostname="attacker-vm",
        last_beacon=None
    )


def test_async_http_batch_script_generation(test_agent):
    """Test that AsyncHTTPBatch generates a valid Python script."""
    urls = [
        "https://example.com/api/v1/health",
        "https://example.com/api/v1/users",
        "https://example.com/api/v1/config",
    ]

    action = AsyncHTTPBatch(test_agent, urls)

    # Verify action properties
    assert action.urls == urls
    assert action.method == "GET"
    assert action.timeout == 10
    assert "python3" in action.command.lower()
    assert "asyncio" in action.command
    assert "urllib" in action.command


def test_async_http_batch_with_headers(test_agent):
    """Test AsyncHTTPBatch with custom headers."""
    urls = ["https://example.com/api/v1/protected"]
    headers = {"Authorization": "Bearer token123", "User-Agent": "Incalmo/1.0"}

    action = AsyncHTTPBatch(test_agent, urls, headers=headers)

    # Verify headers are in the script
    assert "Authorization" in action.command
    assert "Bearer token123" in action.command


def test_async_http_batch_result_parsing(test_agent):
    """Test that AsyncHTTPBatch correctly parses JSON results."""
    urls = ["https://example.com/api/v1/health", "https://example.com/api/v1/users"]
    action = AsyncHTTPBatch(test_agent, urls)

    # Mock response from the agent (JSON output from the script)
    mock_response = [
        {
            "url": "https://example.com/api/v1/health",
            "status_code": "200",
            "body": '{"status": "ok"}',
            "error": None
        },
        {
            "url": "https://example.com/api/v1/users",
            "status_code": "401",
            "body": '{"error": "Unauthorized"}',
            "error": None
        }
    ]

    command_result = CommandResult(
        output=json.dumps(mock_response),
        stderr=""
    )

    # Parse results
    import asyncio
    events = asyncio.run(action.get_result(command_result))

    # Verify events
    assert len(events) == 2
    assert events[0].status_code == "200"
    assert events[0].url == "https://example.com/api/v1/health"
    assert events[1].status_code == "401"
    assert events[1].url == "https://example.com/api/v1/users"


def test_async_http_batch_error_handling(test_agent):
    """Test AsyncHTTPBatch error handling for malformed responses."""
    urls = ["https://example.com/api"]
    action = AsyncHTTPBatch(test_agent, urls)

    # Mock malformed response (not JSON)
    command_result = CommandResult(
        output="This is not valid JSON",
        stderr=""
    )

    # Should handle gracefully
    import asyncio
    events = asyncio.run(action.get_result(command_result))

    assert len(events) == 1
    assert events[0].status_code == "error"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
