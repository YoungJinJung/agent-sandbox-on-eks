"""Local checks only: Kubernetes and AWS are mocked, MCP tools run in process."""

from contextlib import redirect_stdout
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src/mcp_server"))
import server
import client
import stage
from mcp import Client


def observations():
    return {
        "sts_get_caller_identity": {"observation": "success"},
        "s3_list_buckets": {"observation": "error", "error": "AccessDenied"},
        "allowed_https": {"observation": "connected", "status_code": 200},
        "firewall_denied_https": {"observation": "connection_error", "error": "TimeoutError"},
        "dns_firewall_denied_host": {"observation": "not_resolved", "error": "gaierror"},
    }


class DisplayTests(unittest.TestCase):
    def test_timeout_is_not_called_confirmed_block(self):
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertTrue(client.show_observations(observations()))
        self.assertIn("연결 실패", output.getvalue())
        self.assertNotIn("차단 확인", output.getvalue())

    def test_unexpected_access_and_missing_results_are_not_success(self):
        for key in observations():
            with self.subTest(key=key), redirect_stdout(io.StringIO()):
                data = observations()
                data[key] = {"observation": "success" if key != "sts_get_caller_identity" else "error"}
                self.assertFalse(client.show_observations(data))
        with redirect_stdout(io.StringIO()):
            self.assertFalse(client.show_observations({}))


class ToolFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_example_tool_then_boundary_over_mcp(self):
        with patch("client.Client", side_effect=lambda _: Client(server.mcp)), \
             patch("client.streamable_http_client", return_value=None), \
             patch("server._aws_identity", return_value=observations()["sts_get_caller_identity"]), \
             patch("server._s3_list_buckets", return_value=observations()["s3_list_buckets"]), \
             patch("server._resolve", return_value=observations()["dns_firewall_denied_host"]), \
             patch("server._https_get", side_effect=[observations()["allowed_https"], observations()["firewall_denied_https"]]), \
             redirect_stdout(io.StringIO()) as output:
            await client.run_demo("http://localhost/mcp", "sandbox", "sandbox-demo", True)
        text = output.getvalue()
        self.assertLess(text.index("2/4"), text.index("3/4"))
        self.assertIn("출장은 출발 전에", text)
        self.assertIn("PDF 파싱·AI 요약은 하지 않습니다", text)


class StageTests(unittest.TestCase):
    def test_fargate_requires_the_same_pod_and_its_actual_node_label(self):
        pod = {"metadata": {"name": "assigned", "uid": "pod-uid"},
               "spec": {"nodeName": "actual-node", "schedulerName": "fargate-scheduler"}}
        node = {"metadata": {"name": "actual-node", "labels": {"eks.amazonaws.com/compute-type": "fargate"}}}
        with tempfile.TemporaryDirectory() as folder, redirect_stdout(io.StringIO()) as output:
            record = Path(folder) / "run.json"
            with patch("stage.kube", side_effect=[json.dumps(pod), json.dumps(node)]) as kube:
                result = stage.verify_fargate(pod, record)
            self.assertEqual(kube.call_args_list[1].args, ("get", "node", "actual-node", "-o", "json"))
            self.assertEqual(result["compute_type"], "fargate")
            self.assertEqual(json.loads(record.with_suffix(".fargate.json").read_text())["node"], node)
            self.assertIn("Fargate 확인", output.getvalue())
            for label in (None, "ec2"):
                wrong = {"metadata": {"name": "actual-node", "labels": {"eks.amazonaws.com/compute-type": label}}}
                with patch("stage.kube", side_effect=[json.dumps(pod), json.dumps(wrong)]), self.assertRaises(RuntimeError):
                    stage.verify_fargate(pod, record)
            changed = dict(pod, metadata={"name": "assigned", "uid": "replacement"})
            with patch("stage.kube", return_value=json.dumps(changed)), self.assertRaises(RuntimeError):
                stage.verify_fargate(pod, record)

    def test_prepare_watch_keeps_five_minute_deadline(self):
        with patch("stage.subprocess.run", return_value=Mock(returncode=0, stdout="")) as run:
            stage.kube("wait", "--timeout=5m", timeout=315)
        self.assertIn("--request-timeout=0", run.call_args.args[0])
        self.assertEqual(run.call_args.kwargs["timeout"], 315)

    def test_pod_is_selected_by_sandbox_uid_not_pool_label(self):
        sandbox = {"metadata": {"uid": "assigned"}}
        pods = {"items": [{"metadata": {"name": name, "ownerReferences": [{"uid": uid, "controller": True}]}}
                           for name, uid in [("replacement", "pool"), ("actual", "assigned")]]}
        self.assertEqual(stage.owned_pod(sandbox, pods)["metadata"]["name"], "actual")
        with self.assertRaises(RuntimeError):
            stage.owned_pod(sandbox, {"items": []})

    def test_unmanaged_pool_is_rejected(self):
        with patch("stage.kube", return_value='{"metadata": {}}'), self.assertRaises(RuntimeError):
            stage.check_pool()

    def test_release_checks_all_three_objects(self):
        with patch("stage.kube") as kube, redirect_stdout(io.StringIO()):
            stage.release("claim", "sandbox", "actual-pod")
        self.assertIn("--cascade=foreground", kube.call_args_list[0].args)
        self.assertEqual([call.args[2] for call in kube.call_args_list[1:]],
                         ["sandboxclaim/claim", "sandbox/sandbox", "pod/actual-pod"])

    def exercise_run(self, failure=None):
        calls = []
        pause_done = False

        def step(*_):
            nonlocal pause_done
            pause_done = True

        def kube(*args, **kwargs):
            calls.append((args, kwargs))
            if args[0] == "create":
                self.assertTrue(pause_done)
                expiry = datetime.fromisoformat(kwargs["payload"]["spec"]["lifecycle"]["shutdownTime"].replace("Z", "+00:00"))
                self.assertAlmostEqual((expiry - datetime.now(timezone.utc)).total_seconds(), 300, delta=2)
            if args[:2] == ("get", "sandboxclaim"):
                return "allocated"
            if args[:2] == ("get", "sandbox"):
                return '{"metadata":{"uid":"uid"}}'
            if args[:2] == ("get", "pods"):
                return json.dumps({"items": [{"metadata": {"name": "actual-pod", "uid": "pod-uid", "ownerReferences": [{"uid": "uid", "controller": True}]}, "status": {"podIP": "10.0.1.2"}}]})
            if args[:2] == ("get", "pod"):
                return json.dumps({"metadata": {"name": "actual-pod", "uid": "pod-uid"},
                                   "spec": {"nodeName": "actual-node", "schedulerName": "fargate-scheduler"}})
            if args[:2] == ("get", "node"):
                return json.dumps({"metadata": {"name": "actual-node", "labels": {
                    "eks.amazonaws.com/compute-type": "ec2" if failure == "fargate" else "fargate"}}})
            if failure == "ready" and "--for=condition=Ready" in args:
                raise RuntimeError("not ready")
            if failure == "delete" and args[:2] == ("wait", "--for=delete"):
                raise RuntimeError("pod still exists")
            return ""

        process = Mock()
        process.poll.return_value = 1 if failure == "forward" else None

        def popen(*args, **kwargs):
            kwargs["stdout"].write("Forwarding from 127.0.0.1:18080 -> 8080\n")
            kwargs["stdout"].flush()
            return process

        output = io.StringIO()
        with tempfile.TemporaryDirectory() as folder, \
             patch("stage.RUNS", Path(folder)), patch.dict("os.environ", {"SANDBOX_TTL_MINUTES": "5", "ROUTER_LOCAL_PORT": "18080"}), \
             patch("stage.check_pool", return_value={"status": {"readyReplicas": 1}}), \
             patch("stage.socket.socket"), patch("stage.step", side_effect=step), \
             patch("stage.kube", side_effect=kube), patch("stage.subprocess.Popen", side_effect=popen), \
             patch("stage.run_demo", new=AsyncMock(side_effect=RuntimeError("tool error") if failure == "tool" else None)), \
             redirect_stdout(output):
            if failure:
                with self.assertRaises(RuntimeError):
                    stage.run(True)
            else:
                stage.run(True)
                record = json.loads(next(p for p in Path(folder).glob("*.json") if not p.name.endswith(".fargate.json")).read_text())
                self.assertEqual(record["pod"], "actual-pod")
                self.assertEqual(record["compute_type"], "fargate")
                self.assertIn("end_ms", record)
        return calls, output.getvalue(), process

    def test_full_flow_and_expiry_after_presenter_pause(self):
        calls, output, process = self.exercise_run()
        self.assertIn("삭제 확인 · pod/actual-pod", output)
        self.assertIn("완료 · 요청 환경과 대기 풀 정리", output)
        self.assertEqual(calls[-1][0][:3], ("delete", "sandboxwarmpool", stage.POOL))
        process.terminate.assert_called_once()

    def test_failures_clean_up_without_success_banner(self):
        for failure in ("ready", "fargate", "forward", "tool", "delete"):
            with self.subTest(failure=failure):
                calls, output, _ = self.exercise_run(failure)
                self.assertTrue(any(args[:2] == ("delete", "sandboxclaim") for args, _ in calls))
                self.assertTrue(any(args[:2] == ("delete", "sandboxwarmpool") for args, _ in calls))
                self.assertNotIn("완료 · 요청 환경", output)


class EvidenceTests(unittest.TestCase):
    def test_only_correlated_blocked_event_is_evidence(self):
        event = {"src_ip": "10.0.1.2", "tls": {"sni": "example.org"},
                 "alert": {"signature_id": 1199, "action": "blocked"}}
        record = {"pod_ip": "10.0.1.2"}
        self.assertEqual(stage.blocked_events([{"message": json.dumps({"event": event})}], record), [event])
        for field, value in (("src_ip", "10.0.1.3"), ("tls", {"sni": "example.com"}),
                             ("alert", {"signature_id": 1199, "action": "allowed"}),
                             ("alert", {"signature_id": 1200, "action": "blocked"})):
            changed = dict(event, **{field: value})
            self.assertEqual(stage.blocked_events([{"message": json.dumps({"event": changed})}], record), [])
        self.assertEqual(stage.blocked_events([{"message": "not JSON"}], record), [])


if __name__ == "__main__":
    unittest.main()
