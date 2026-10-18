import json
import unittest
from unittest.mock import patch

import server
from mcp import Client


class BoundaryProbeTests(unittest.TestCase):
    @patch("server.boto3.client")
    @patch("server._resolve", return_value={"observation": "not_resolved", "error": "gaierror"})
    @patch("server._https_get", side_effect=[{"observation": "connected", "status_code": 200}, {"observation": "connection_error", "error": "TimeoutError"}])
    def test_probe_uses_only_fixed_targets(self, https_get, resolve, boto_client):
        boto_client.side_effect = [
            type("STS", (), {"get_caller_identity": lambda self: {"Account": "123456789012"}})(),
            type("S3", (), {"list_buckets": lambda self: None})(),
        ]

        result = json.loads(server.check_sandbox_boundary())

        self.assertEqual(result["sts_get_caller_identity"]["observation"], "success")
        self.assertEqual(result["allowed_https"]["status_code"], 200)
        self.assertEqual(https_get.call_args_list[0].args[0], "https://example.com/")
        self.assertEqual(https_get.call_args_list[1].args[0], "https://example.org/")
        self.assertEqual(resolve.call_args.args[0], "evil.example.com")


class MCPProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def test_summarize_is_exposed_over_mcp(self):
        async with Client(server.mcp) as client:
            result = await client.call_tool("summarize", {"text": "  hello   sandbox  "})

        self.assertFalse(result.is_error)
        self.assertEqual(result.content[0].text, "hello sandbox")


if __name__ == "__main__":
    unittest.main()
