"""A deliberately bounded MCP workload for the Agent Sandbox demo.

The tool has no caller-controlled URL, shell, or AWS operation. It probes only
the fixed resources used by the demo so that its network and IAM effects are
repeatable and auditable.
"""

from __future__ import annotations

import json
import logging
import os
import socket
import urllib.error
import urllib.request

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

LOG = logging.getLogger("sandbox-demo")
REQUEST_TIMEOUT_SECONDS = 5
ALLOWED_EGRESS_URL = "https://example.com/"
FIREWALL_DENIED_URL = "https://example.org/"
DNS_FIREWALL_DENIED_HOST = "evil.example.com"

mcp = MCPServer("sandbox-boundary-demo")


def _aws_identity() -> dict[str, str]:
    try:
        boto3.client("sts").get_caller_identity()
        return {"observation": "success"}
    except (BotoCoreError, ClientError) as exc:
        LOG.warning("STS identity probe failed: %s", type(exc).__name__)
        return {"observation": "error", "error": type(exc).__name__}


def _s3_list_buckets() -> dict[str, str]:
    try:
        boto3.client("s3").list_buckets()
        return {"observation": "success"}
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "Unknown")
        return {"observation": "error", "error": code}
    except BotoCoreError as exc:
        return {"observation": "error", "error": type(exc).__name__}


def _resolve(host: str) -> dict[str, str]:
    try:
        socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        return {"observation": "resolved"}
    except socket.gaierror as exc:
        LOG.info("DNS lookup for %s failed: %s", host, exc.__class__.__name__)
        return {"observation": "not_resolved", "error": type(exc).__name__}


def _https_get(url: str) -> dict[str, str | int]:
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            return {"observation": "connected", "status_code": response.status}
    except urllib.error.HTTPError as exc:
        return {"observation": "connected", "status_code": exc.code}
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        reason = getattr(exc, "reason", exc)
        return {"observation": "connection_error", "error": type(reason).__name__}


@mcp.tool()
def summarize(text: str) -> str:
    """Return a short, deterministic summary without performing side effects."""
    return " ".join(text.split())[:240]


@mcp.tool()
def check_sandbox_boundary() -> str:
    """Probe the demo's fixed IAM, DNS, and HTTPS boundaries and report observations."""
    observations = {
        "sts_get_caller_identity": _aws_identity(),
        "s3_list_buckets": _s3_list_buckets(),
        "dns_firewall_denied_host": {
            "host": DNS_FIREWALL_DENIED_HOST,
            **_resolve(DNS_FIREWALL_DENIED_HOST),
        },
        "allowed_https": {"host": "example.com", **_https_get(ALLOWED_EGRESS_URL)},
        "firewall_denied_https": {"host": "example.org", **_https_get(FIREWALL_DENIED_URL)},
    }
    LOG.info("Boundary probe completed: %s", json.dumps(observations, sort_keys=True))
    return json.dumps(observations, sort_keys=True)


if __name__ == "__main__":
    # The router is the sole ingress path and owns Host validation. The MCP
    # process is not exposed outside the private sandbox pod.
    security = TransportSecuritySettings(enable_dns_rebinding_protection=False)
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        transport_security=security,
    )
