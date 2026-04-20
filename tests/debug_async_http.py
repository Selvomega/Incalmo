#!/usr/bin/env python3
"""
Debug script to see what command is being sent to the agent
and what output is actually returned.
"""

from incalmo.core.actions.LowLevel.async_http_batch import AsyncHTTPBatch
from incalmo.models.agent import Agent
from datetime import datetime

# Create test agent
agent = Agent(
    paw="test",
    username="attacker",
    privilege="User",
    pid=1234,
    host_ip_addrs=["192.168.122.100"],
    hostname="attacker-vm",
    last_beacon=datetime.now()
)

# Create action with a few test URLs
urls = [
    "http://192.168.122.20:8080/health",
    "http://192.168.122.20:8080/api",
]

action = AsyncHTTPBatch(agent, urls, timeout=5)

print("=" * 80)
print("DEBUG: AsyncHTTPBatch Command Generation")
print("=" * 80)
print()
print("URLs being probed:")
for url in urls:
    print(f"  - {url}")
print()
print("Generated command to send to agent:")
print("-" * 80)
print(action.command)
print("-" * 80)
print()
print("Command length:", len(action.command))
print()
print("=" * 80)
print("TEST: Try running this script manually on the VM")
print("=" * 80)
print()
print("Run this on the attacker VM:")
print()
print("ssh -i ~/.ssh/incalmo attacker@192.168.122.100 << 'EOFTEST'")
print(action.command)
print("EOFTEST")
print()
print("=" * 80)
print("Expected output: JSON array with results")
print("=" * 80)
