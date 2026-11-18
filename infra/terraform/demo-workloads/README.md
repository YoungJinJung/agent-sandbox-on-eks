# Terraform-managed recording deployment

This optional root installs the pinned Agent Sandbox v1.0.5 controller/CRDs and the repository's MCP chart on the cluster created by `../cluster`. It is an alternative to `../gitops-bridge` for a disposable recording environment. Do not apply both roots to the same cluster: they manage the same Kubernetes resources.

The v20 talk uses the [existing 60-second recording](../../../demo/media/README.md) on slide 20; playback requires no AWS deployment. Use this root only for a new live run or recording. `demo/record.py` captures timestamped terminal output with the original two-minute pacing; it does not render the edited MP4. The [current narration](../../../demo/narration-ko.txt) follows the 60-second presentation edit.

The upstream manifest URL and SHA-256 are pinned in `main.tf`. Terraform uses Helm releases to install access/logging resources, the controller, and then workloads. SecurityGroupPolicy, service accounts, and logging configuration exist before Fargate admits the Router and tool Pods. The existing GitOps chart defaults still install both resource groups.

From the repository root:

```bash
# Confirm the intended account before creating billable AWS resources.
aws sts get-caller-identity
cp infra/terraform/cluster/terraform.tfvars.example infra/terraform/cluster/terraform.tfvars
# Edit the public API CIDR to your current public IPv4 /32. Keep demo = 2 AZ.
python3 demo/with-aws-session.py terraform -chdir=infra/terraform/cluster init
python3 demo/with-aws-session.py terraform -chdir=infra/terraform/cluster plan -out=recording.tfplan
python3 demo/with-aws-session.py terraform -chdir=infra/terraform/cluster apply recording.tfplan

./demo/push-image.sh
python3 demo/with-aws-session.py terraform -chdir=infra/terraform/demo-workloads init
python3 demo/with-aws-session.py terraform -chdir=infra/terraform/demo-workloads plan -out=recording.tfplan
python3 demo/with-aws-session.py terraform -chdir=infra/terraform/demo-workloads apply recording.tfplan

# Keep the user's existing Kubernetes context unchanged.
export KUBECONFIG="$PWD/demo/.runs/kubeconfig"
mkdir -p demo/.runs
aws eks update-kubeconfig --region ap-northeast-2 --name agent-sandbox-demo --alias community-day-recording
./demo/run.sh prepare
./demo/run.sh
```

`with-aws-session.py` bridges AWS CLI login credentials to the pinned AWS provider's SDK. It creates a temporary credential-process profile that reads the original AWS CLI profile. The SDK can renew expiring credentials during long apply/destroy operations; credentials are never printed or written by the helper. The temporary file contains only the process command and is removed when the command exits. If your provider already receives valid credentials, you can invoke Terraform directly.

The stage driver follows Claim → Sandbox UID → actual Pod UID → Pod `spec.nodeName` → live Node `eks.amazonaws.com/compute-type`. It also checks `schedulerName=fargate-scheduler`. Missing or contradictory evidence aborts the run and triggers cleanup. The raw Pod and Node API responses are preserved in `demo/.runs/<claim>.fargate.json`, alongside the network correlation record. A node name prefix or a hard-coded banner is not used as verification.

## Cleanup

Finish the demo and collect its Network Firewall evidence before deleting logs. If preparation was canceled, use `./demo/run.sh cleanup` first. Remove application resources while the controller is still running, then destroy AWS infrastructure:

```bash
python3 demo/with-aws-session.py terraform -chdir=infra/terraform/demo-workloads plan -destroy -out=cleanup.tfplan
python3 demo/with-aws-session.py terraform -chdir=infra/terraform/demo-workloads apply cleanup.tfplan
python3 demo/with-aws-session.py terraform -chdir=infra/terraform/cluster plan -destroy -out=cleanup.tfplan
python3 demo/with-aws-session.py terraform -chdir=infra/terraform/cluster apply cleanup.tfplan
```

Helm-created empty namespaces disappear with the disposable EKS cluster. KMS keys follow AWS scheduled deletion. State, variable values, plans, kubeconfig, and run evidence are ignored by Git; the Terraform source and provider lock files belong in the repository. Production retains the existing minimum-three-AZ policy; this recording explicitly uses two AZs.
