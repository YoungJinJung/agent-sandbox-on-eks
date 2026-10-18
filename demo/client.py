"""Call one sandbox MCP endpoint through the cluster's sandbox-router."""

import asyncio
import json
import os

import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client


async def main() -> None:
    headers = {
        "X-Sandbox-ID": os.environ["SANDBOX_ID"],
        "X-Sandbox-Namespace": os.environ.get("SANDBOX_NAMESPACE", "sandbox-demo"),
        "X-Sandbox-Port": "8000",
    }
    async with httpx2.AsyncClient(headers=headers, timeout=httpx2.Timeout(15, read=60)) as http_client:
        transport = streamable_http_client(os.environ["MCP_URL"], http_client=http_client)
        async with Client(transport) as client:
            result = await client.call_tool("check_sandbox_boundary", {})
            if result.is_error:
                raise RuntimeError("MCP boundary probe returned an error")
            if result.structured_content:
                print(json.dumps(result.structured_content, indent=2, sort_keys=True))
            else:
                for item in result.content:
                    if item.type == "text":
                        print(item.text)


if __name__ == "__main__":
    asyncio.run(main())
