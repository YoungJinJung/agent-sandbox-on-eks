#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

namespace="sandbox-demo"
router_namespace="agent-sandbox-system"
router_service="sandbox-router-svc"
template="mcp-tools"
claim="mcp-demo-$(date -u +%Y%m%d%H%M%S)"
ttl_minutes="${SANDBOX_TTL_MINUTES:-2}"
if [[ ! "$ttl_minutes" =~ ^[1-9][0-9]*$ ]] || (( ttl_minutes > 60 )); then
  echo "SANDBOX_TTL_MINUTES must be an integer between 1 and 60" >&2
  exit 2
fi
expires="$(TTL_MINUTES="$ttl_minutes" python3 -c 'from datetime import datetime, timedelta, timezone; import os; print((datetime.now(timezone.utc) + timedelta(minutes=int(os.environ["TTL_MINUTES"]))).isoformat(timespec="seconds").replace("+00:00", "Z"))')"
port="${ROUTER_LOCAL_PORT:-18080}"
forward_pid=""
port_forward_log=""
completed=false

cleanup() {
  if [[ -n "$forward_pid" ]]; then
    kill "$forward_pid" 2>/dev/null || true
  fi
  if [[ "$completed" != true ]]; then
    kubectl delete sandboxclaim "$claim" -n "$namespace" --ignore-not-found >/dev/null 2>&1 || true
    kubectl delete sandboxwarmpool "$claim" -n "$namespace" --ignore-not-found >/dev/null 2>&1 || true
  fi
  if [[ -n "$port_forward_log" ]]; then
    rm -f "$port_forward_log"
  fi
}
trap cleanup EXIT
trap 'exit 130' INT TERM

kubectl apply -f - <<EOF
apiVersion: extensions.agents.x-k8s.io/v1beta1
kind: SandboxWarmPool
metadata:
  name: ${claim}
  namespace: ${namespace}
spec:
  replicas: 1
  sandboxTemplateRef:
    name: ${template}
EOF
kubectl wait --for=jsonpath='{.status.readyReplicas}'=1 "sandboxwarmpool/${claim}" -n "$namespace" --timeout=5m

kubectl apply -f - <<EOF
apiVersion: extensions.agents.x-k8s.io/v1beta1
kind: SandboxClaim
metadata:
  name: ${claim}
  namespace: ${namespace}
spec:
  warmPoolRef:
    name: ${claim}
  lifecycle:
    shutdownPolicy: Delete
    shutdownTime: "${expires}"
EOF
kubectl wait --for=condition=Ready "sandboxclaim/${claim}" -n "$namespace" --timeout=5m

sandbox_id="$(kubectl get sandboxclaim "$claim" -n "$namespace" -o jsonpath='{.status.sandbox.name}')"
if [[ -z "$sandbox_id" ]]; then
  echo "SandboxClaim is Ready but has no status.sandbox.name" >&2
  exit 1
fi

port_forward_log="$(mktemp -t agent-sandbox-router.XXXXXX)"
kubectl port-forward -n "$router_namespace" "service/${router_service}" "${port}:8080" >"$port_forward_log" 2>&1 &
forward_pid=$!
for _ in $(seq 1 30); do
  if curl --silent --max-time 1 "http://127.0.0.1:${port}/" >/dev/null; then
    break
  fi
  sleep 1
done

MCP_URL="http://127.0.0.1:${port}/mcp" \
SANDBOX_ID="$sandbox_id" \
SANDBOX_NAMESPACE="$namespace" \
uv run --with-requirements src/mcp_server/requirements.txt demo/client.py

echo "Waiting for claim ${claim} to expire at ${expires} UTC..."
kubectl wait --for=delete "sandboxclaim/${claim}" -n "$namespace" --timeout="$((ttl_minutes * 60 + 60))s"
kubectl delete sandboxwarmpool "$claim" -n "$namespace" --timeout=2m
completed=true
echo "Observed: SandboxClaim ${claim} was deleted after its shutdownTime."
