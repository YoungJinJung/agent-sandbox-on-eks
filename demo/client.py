"""Audience-facing MCP calls; observations are never treated as proof of safety."""

import asyncio
import json
import os
import sys

import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

SAMPLE_TEXT = """출장은 출발 전에 팀장의 승인을 받아야 합니다.
교통비와 숙박비는 영수증을 첨부해 정산합니다.
출장 종료 후 7일 이내에 출장 보고서를 제출해야 합니다."""


def step(number: int, title: str, automatic: bool = False) -> None:
    if not automatic and sys.stdin.isatty():
        input("\n  [Enter] 다음 단계 ")
    print(f"\n{'━' * 52}\n  {number}/4  {title}\n{'━' * 52}", flush=True)


def text_result(result) -> str:
    if result.is_error:
        raise RuntimeError("MCP 도구 호출이 오류를 반환했습니다.")
    return "\n".join(item.text for item in result.content if item.type == "text")


def show_observations(observations: dict) -> bool:
    checks = [
        ("sts_get_caller_identity", "AWS 역할 확인", "success", None),
        ("s3_list_buckets", "S3 버킷 목록 조회", "error", "AccessDenied"),
        ("allowed_https", "example.com · 허용 대상", "connected", None),
        ("firewall_denied_https", "example.org · 비허용 대상", "connection_error", None),
        ("dns_firewall_denied_host", "evil.example.com · DNS 조회", "not_resolved", None),
    ]
    descriptions = {
        "success": "호출 성공", "error": "호출 거부/오류",
        "connected": "HTTPS 응답 수신", "connection_error": "연결 실패",
        "resolved": "이름 해석 성공", "not_resolved": "이름 해석 실패",
    }
    expected = True
    for key, label, observation, error in checks:
        value = observations.get(key, {})
        matched = value.get("observation") == observation and (error is None or value.get("error") == error)
        expected &= matched
        detail = value.get("error", value.get("status_code", ""))
        message = descriptions.get(value.get("observation"), "결과 없음/알 수 없는 응답")
        print(f"  {'관측' if matched else '확인 필요'} | {label}\n         {message} {detail}")
    print("\n  연결·DNS 실패의 원인은 AWS 로그와 대조해야 합니다.")
    print("  S3 거부에는 역할 정책과 VPC Endpoint 정책이 함께 영향을 줍니다.", flush=True)
    return expected


async def run_demo(url: str, sandbox_id: str, namespace: str, automatic: bool = False) -> None:
    headers = {"X-Sandbox-ID": sandbox_id, "X-Sandbox-Namespace": namespace, "X-Sandbox-Port": "8000"}
    async with httpx2.AsyncClient(headers=headers, timeout=httpx2.Timeout(15, read=60)) as http_client:
        transport = streamable_http_client(url, http_client=http_client)
        async with Client(transport) as client:
            step(2, "빌린 환경에서 도구를 호출합니다", automatic)
            print("  입력 · 출장 규정.pdf에서 추출했다고 가정한 예시 텍스트\n")
            for line in SAMPLE_TEXT.splitlines():
                print(f"    {line}")
            result = await client.call_tool("summarize", {"text": SAMPLE_TEXT})
            print(f"\n  도구 응답\n    {text_result(result)}")
            print("\n  공백 정리·앞 240자 반환 예시입니다. PDF 파싱·AI 요약은 하지 않습니다.")
            step(3, "같은 환경의 접근 범위를 확인합니다", automatic)
            print("  고정된 대상만 점검합니다. PDF 본문을 외부로 전송하지 않습니다.\n", flush=True)
            result = await client.call_tool("check_sandbox_boundary", {})
            if not show_observations(json.loads(text_result(result))):
                raise RuntimeError("예상과 다른 접근 결과가 있습니다. 정상 시연으로 처리하지 않습니다.")


if __name__ == "__main__":
    asyncio.run(run_demo(os.environ["MCP_URL"], os.environ["SANDBOX_ID"],
                         os.environ.get("SANDBOX_NAMESPACE", "sandbox-demo")))
