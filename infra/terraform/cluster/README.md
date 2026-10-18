# EKS and network foundation

This root provisions the AWS layer only: two-AZ VPC, per-AZ NAT and AWS Network Firewall, DNS Firewall, VPC endpoints, EKS Fargate profiles, pod security groups, IRSA, ECR, and audit logs. It deliberately does not configure a remote Terraform backend; use your team's encrypted, locked remote backend before sharing this demo.

1. Copy `terraform.tfvars.example` to `terraform.tfvars` and replace the example CIDR with your current public IPv4 `/32`.
2. Run `terraform init`, `terraform fmt -check -recursive`, `terraform validate`, `terraform plan`, and `terraform apply` from this directory.
3. Build and push the MCP image with `../../../demo/push-image.sh`.
4. Configure and apply the separate `../gitops-bridge` root.

The primary EKS API endpoint is public but CIDR-restricted, with private endpoint access also enabled. Fargate profiles use the system private subnets for CoreDNS, Argo CD, and the Agent Sandbox controller/router; sandbox pods use the isolated sandbox subnets. All Internet-bound private subnet traffic is routed through the same-AZ Network Firewall endpoint and NAT gateway. NAT return routes send each private subnet's response traffic back through that firewall endpoint.

EKS Fargate does not enforce Kubernetes NetworkPolicy. The sandbox therefore uses a dedicated `SecurityGroupPolicy` and an AWS Network Firewall SNI allowlist. The sandbox SG allows DNS to the cluster service CIDR and TCP/443; the firewall allows only `example.com` HTTPS from sandbox CIDRs. DNS Firewall allows `example.com` and `example.org` (the latter is resolvable but denied by Network Firewall) and blocks unlisted names such as `evil.example.com`. System subnets use a separate source CIDR and pass through the firewall so controllers can retrieve upstream images.

The S3 gateway endpoint policy is limited to ECR's regional image-layer bucket. This avoids turning the ECR layer endpoint into general S3 access for the sandbox. The sandbox IAM role intentionally has no S3 permissions. The GitOps chart configures the EKS Fargate log router to send new pod stdout/stderr to `/aws/eks/<cluster_name>/fargate`; the Fargate execution role has write access only to that log group.

Destroy only after the demo is complete: `terraform destroy`. This is a charged demo environment (two NAT gateways, AWS Network Firewall, EKS control plane, and Fargate workloads).
