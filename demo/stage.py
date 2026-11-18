"""Prepare off stage, then show allocation, MCP calls and verified release."""

import argparse
import asyncio
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import time
import uuid

from client import run_demo, step

NAMESPACE = "sandbox-demo"
POOL = "mcp-stage"
OWNER_LABEL = "community-day-demo"
RUNS = Path(__file__).parent / ".runs"


def kube(*args: str, payload=None, timeout: int = 75) -> str:
    # Watch/delete commands have their own deadline; don't cut preparation at 15s.
    request_timeout = "0" if args[0] in {"wait", "rollout", "delete"} else "15s"
    result = subprocess.run(
        ["kubectl", f"--request-timeout={request_timeout}", "-n", NAMESPACE, *args],
        input=json.dumps(payload) if payload is not None else None,
        capture_output=True, text=True, timeout=timeout,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result.stdout.strip()


def check_pool() -> dict:
    raw = kube("get", "sandboxwarmpool", POOL, "--ignore-not-found", "-o", "json")
    if not raw:
        raise RuntimeError("준비된 환경이 없습니다. 먼저 ./demo/run.sh prepare 를 실행하세요.")
    pool = json.loads(raw)
    if pool["metadata"].get("labels", {}).get("app.kubernetes.io/managed-by") != OWNER_LABEL:
        raise RuntimeError(f"{POOL}은 이 데모가 만든 풀이 아닙니다. 변경하지 않습니다.")
    return pool


def delete_resource(kind: str, name: str) -> None:
    kube("delete", kind, name, "--ignore-not-found", "--cascade=foreground", "--timeout=60s")


def prepare() -> None:
    print("무대 밖 준비 · Router / Template / Warm Pool")
    kube("get", "sandboxtemplate", "mcp-tools")
    kube("rollout", "status", "deployment/sandbox-router", "-n", "agent-sandbox-system", "--timeout=60s")
    existing = kube("get", "sandboxwarmpool", POOL, "--ignore-not-found", "-o", "name")
    if existing:
        check_pool()
    else:
        kube("create", "-f", "-", payload={
            "apiVersion": "extensions.agents.x-k8s.io/v1beta1", "kind": "SandboxWarmPool",
            "metadata": {"name": POOL, "namespace": NAMESPACE,
                         "labels": {"app.kubernetes.io/managed-by": OWNER_LABEL}},
            "spec": {"replicas": 1, "sandboxTemplateRef": {"name": "mcp-tools"}},
        })
    print("  Fargate 환경 준비를 기다립니다. 무대 시간에는 포함하지 않습니다.", flush=True)
    try:
        kube("wait", "--for=jsonpath={.status.readyReplicas}=1", f"sandboxwarmpool/{POOL}",
             "--timeout=5m", timeout=315)
    except BaseException:
        print("준비 중단 · 재시도하거나 ./demo/run.sh cleanup 으로 남은 대기 풀을 정리하세요.", flush=True)
        raise
    print("  준비 완료 · 무대에서 ./demo/run.sh 실행\n  시연 취소 시 ./demo/run.sh cleanup 으로 대기 환경을 삭제하세요.")


def owned_pod(sandbox: dict, pods: dict) -> dict:
    matches = [pod for pod in pods["items"] if any(
        owner.get("uid") == sandbox["metadata"]["uid"] and owner.get("controller")
        for owner in pod["metadata"].get("ownerReferences", [])
    )]
    if len(matches) != 1:
        raise RuntimeError("할당된 Sandbox 소유의 Pod를 하나로 확인할 수 없습니다.")
    return matches[0]


def verify_fargate(pod: dict, record_path: Path) -> dict:
    print("\n  실제 Kubernetes API 조회 · 이 요청의 Pod → Node · JSON 필드 발췌", flush=True)
    print(f"  $ kubectl -n {NAMESPACE} get pod {pod['metadata']['name']} -o json", flush=True)
    current = json.loads(kube("get", "pod", pod["metadata"]["name"], "-o", "json"))
    if current["metadata"]["uid"] != pod["metadata"]["uid"]:
        raise RuntimeError("검증 중 Pod가 교체됐습니다. 같은 실행 환경으로 확인할 수 없습니다.")
    pod = current
    node_name = pod.get("spec", {}).get("nodeName")
    if not node_name:
        raise RuntimeError("할당된 Pod의 실행 노드를 확인할 수 없습니다.")
    print(f"    spec.nodeName = {node_name}")
    print(f"  $ kubectl get node {node_name} -o json", flush=True)
    node = json.loads(kube("get", "node", node_name, "-o", "json"))
    evidence = {"pod": pod, "node": node,
                "verified_at": datetime.now(timezone.utc).isoformat()}
    evidence_path = record_path.with_suffix(".fargate.json")
    evidence_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2))
    compute_type = node.get("metadata", {}).get("labels", {}).get("eks.amazonaws.com/compute-type")
    scheduler = pod.get("spec", {}).get("schedulerName")
    if node.get("metadata", {}).get("name") != node_name or compute_type != "fargate" or scheduler != "fargate-scheduler":
        raise RuntimeError(f"Fargate 검증 실패 · compute-type={compute_type}, scheduler={scheduler}")
    print(f"    eks.amazonaws.com/compute-type = {compute_type}")
    print(f"    schedulerName = {scheduler}")
    print("  Fargate 확인 · 할당된 Pod와 Node를 연결해 검증했습니다.", flush=True)
    return {"node": node_name, "compute_type": compute_type, "scheduler": scheduler,
            "fargate_evidence": str(evidence_path)}


def release(claim: str, sandbox_id: str, pod_name: str) -> None:
    delete_resource("sandboxclaim", claim)
    # Verify the allocated objects, not the pool's replacement Pod.
    for kind, name in (("sandboxclaim", claim), ("sandbox", sandbox_id), ("pod", pod_name)):
        if name:
            kube("wait", "--for=delete", f"{kind}/{name}", "--timeout=60s")
            print(f"  삭제 확인 · {kind}/{name}", flush=True)


def run(automatic: bool) -> None:
    ttl = int(os.environ.get("SANDBOX_TTL_MINUTES", "5"))
    port = int(os.environ.get("ROUTER_LOCAL_PORT", "18080"))
    if not 1 <= ttl <= 60 or not 1024 <= port <= 65535:
        raise ValueError("TTL은 1~60분, 로컬 포트는 1024~65535 범위여야 합니다.")
    pool = check_pool()
    if pool.get("status", {}).get("readyReplicas", 0) < 1:
        raise RuntimeError("Warm Pool이 아직 준비되지 않았습니다. prepare 를 다시 실행하세요.")
    with socket.socket() as check:
        check.bind(("127.0.0.1", port))
    claim = f"mcp-stage-{uuid.uuid4().hex[:10]}"
    sandbox_id = pod_name = ""
    created = released = False
    forward = None
    started = time.monotonic()
    RUNS.mkdir(exist_ok=True)
    record_path = RUNS / f"{claim}.json"
    record = {"claim": claim, "namespace": NAMESPACE}
    with tempfile.TemporaryFile(mode="w+") as forward_log:
        try:
            step(1, "도구를 실행할 환경 하나를 빌립니다", automatic)
            started = time.monotonic()
            now = datetime.now(timezone.utc)
            record["start_ms"] = int(now.timestamp() * 1000)
            expires = (now + timedelta(minutes=ttl)).isoformat(timespec="seconds").replace("+00:00", "Z")
            # Expiry starts after preparation and the presenter's first pause.
            created = True  # An API timeout may still have created the Claim.
            kube("create", "-f", "-", payload={
                "apiVersion": "extensions.agents.x-k8s.io/v1beta1", "kind": "SandboxClaim",
                "metadata": {"name": claim, "namespace": NAMESPACE},
                "spec": {"warmPoolRef": {"name": POOL},
                         "lifecycle": {"shutdownPolicy": "Delete", "shutdownTime": expires}},
            })
            kube("wait", "--for=condition=Ready", f"sandboxclaim/{claim}", "--timeout=45s")
            sandbox_id = kube("get", "sandboxclaim", claim, "-o", "jsonpath={.status.sandbox.name}")
            if not sandbox_id:
                raise RuntimeError("Claim은 Ready이지만 할당된 Sandbox 이름이 없습니다.")
            sandbox = json.loads(kube("get", "sandbox", sandbox_id, "-o", "json"))
            pod = owned_pod(sandbox, json.loads(kube("get", "pods", "-o", "json")))
            pod_name = pod["metadata"]["name"]
            record.update(sandbox=sandbox_id, pod=pod_name, pod_ip=pod["status"]["podIP"])
            record_path.write_text(json.dumps(record, indent=2))
            print(f"  요청   {claim}\n  환경   {sandbox_id}\n  Pod    {pod_name}\n  상태   Ready · 할당까지 {time.monotonic() - started:.1f}초")
            print(f"  반환 누락 대비 만료 시각 · {expires} ({ttl}분)", flush=True)
            record.update(verify_fargate(pod, record_path))
            record_path.write_text(json.dumps(record, indent=2))
            forward = subprocess.Popen(
                ["kubectl", "-n", "agent-sandbox-system", "port-forward", "--address=127.0.0.1",
                 "service/sandbox-router-svc", f"{port}:8080"],
                stdout=forward_log, stderr=subprocess.STDOUT, text=True,
            )
            for _ in range(100):
                if forward.poll() is not None:
                    forward_log.seek(0)
                    raise RuntimeError("Router 연결 실패\n" + forward_log.read())
                forward_log.seek(0)
                if f"Forwarding from 127.0.0.1:{port}" in forward_log.read():
                    break
                time.sleep(0.1)
            else:
                raise RuntimeError("10초 안에 Router 연결이 준비되지 않았습니다.")
            asyncio.run(run_demo(f"http://127.0.0.1:{port}/mcp", sandbox_id, NAMESPACE, automatic))
            record["end_ms"] = int(time.time() * 1000)
            record_path.write_text(json.dumps(record, indent=2))
            step(4, "작업을 마친 환경을 반환합니다", automatic)
            print("  지금은 Claim을 명시적으로 반환합니다. TTL 만료 시연은 아닙니다.", flush=True)
            release(claim, sandbox_id, pod_name)
            released = True
        finally:
            if forward is not None:
                forward.terminate()
                try:
                    forward.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    forward.kill()
                    forward.wait()
            cleanup_errors = []
            if created and not released:
                print("\n  중단된 실행을 정리합니다.", flush=True)
                try:
                    release(claim, sandbox_id, pod_name)
                except Exception as exc:
                    cleanup_errors.append(f"Claim {claim}: {exc}")
            try:
                delete_resource("sandboxwarmpool", POOL)
            except Exception as exc:
                cleanup_errors.append(f"Warm Pool {POOL}: {exc}")
            if cleanup_errors:
                raise RuntimeError("정리 미완료 · 리소스를 확인하세요.\n" + "\n".join(cleanup_errors))
        print(f"\n  완료 · 요청 환경과 대기 풀 정리 · 총 {time.monotonic() - started:.1f}초")
        print("  Agent Sandbox는 환경의 수명을, AWS 구성은 접근 경계를 관리합니다.")
        print(f"\n  로그 대조용 기록 · {record_path}")
        print(f"  ./demo/run.sh evidence {record_path} --log-group /aws/network-firewall/<cluster_name>")


def blocked_events(events: list, record: dict) -> list:
    matches = []
    for item in events:
        try:
            event = json.loads(item["message"])["event"]
            alert = event.get("alert", {})
            if (event.get("src_ip") == record["pod_ip"]
                    and event.get("tls", {}).get("sni") == "example.org"
                    and alert.get("signature_id") == 1199
                    and alert.get("action") == "blocked"):
                matches.append(event)
        except (KeyError, TypeError, json.JSONDecodeError):
            continue
    return matches


def evidence(record_path: str, log_group: str) -> None:
    import boto3
    record = json.loads(Path(record_path).read_text())
    if "end_ms" not in record:
        raise RuntimeError("도구 점검이 완료되지 않은 실행 기록입니다.")
    logs = boto3.client("logs")
    matches = []
    for page in logs.get_paginator("filter_log_events").paginate(
        logGroupName=log_group, startTime=record["start_ms"], endTime=record["end_ms"] + 1,
        filterPattern=f'{{ $.event.src_ip = "{record["pod_ip"]}" }}',
    ):
        matches.extend(blocked_events(page["events"], record))
    if not matches:
        print("차단 로그 미확인 · 로그 도착 지연 또는 다른 원인일 수 있습니다. 잠시 후 다시 조회하세요.")
        return
    print(f"방화벽 차단 확인 · 실행 {record['claim']}")
    for event in matches:
        print(f"  {event.get('timestamp', '')} | {event['src_ip']} → example.org | 규칙 1199 | blocked")


def main() -> None:
    parser = argparse.ArgumentParser(description="라이브 실행·촬영 데모 · prepare → run → evidence (발표용 60초 영상은 demo/media)")
    parser.add_argument("command", choices=["prepare", "run", "cleanup", "evidence"], nargs="?", default="run")
    parser.add_argument("record", nargs="?")
    parser.add_argument("--auto", action="store_true", help="Enter 대기 없이 실행 (리허설)")
    parser.add_argument("--log-group", help="Network Firewall CloudWatch Logs 그룹")
    args = parser.parse_args()
    if args.command == "evidence" and (not args.record or not args.log_group):
        parser.error("evidence에는 실행 기록 경로와 --log-group이 필요합니다.")
    if args.command == "prepare":
        prepare()
    elif args.command == "cleanup":
        check_pool()
        delete_resource("sandboxwarmpool", POOL)
        print("대기 풀과 그 소유 리소스 삭제 완료")
    elif args.command == "evidence":
        evidence(args.record, args.log_group)
    else:
        run(args.auto)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))
    try:
        main()
    except KeyboardInterrupt:
        print("\n발표자가 실행을 중단했습니다.", file=sys.stderr)
        sys.exit(130)
    except Exception as exc:
        print(f"\n실행 중단 · {exc}", file=sys.stderr)
        sys.exit(1)
