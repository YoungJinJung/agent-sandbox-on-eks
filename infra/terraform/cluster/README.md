# EKS and network foundation

This root provisions the AWS layer only: a multi-AZ VPC, per-AZ NAT and AWS Network Firewall, DNS Firewall, VPC endpoints, EKS Fargate profiles, pod security groups, IRSA, ECR, and audit logs. It deliberately does not configure a remote Terraform backend; use your team's encrypted, locked remote backend before sharing this demo.

`availability_zone_count` defaults to **3**. Our production design requires **at least three AZs**; every environment except `demo` enforces this minimum. The example explicitly selects two AZs for the presentation demo. For production, set `environment = "production"` and `availability_zone_count = 3` or more. This is our design policy, not an EKS minimum requirement. Each selected AZ receives all four subnet types, its own NAT gateway, and a firewall endpoint with same-AZ return routes. Three AZs alone do not provide application failover: verify workload placement, surviving capacity, and interrupted-job recovery separately.

Use the three-AZ setting when creating the production cluster. EKS requires updated cluster subnets to remain within the original AZ set ([AWS networking requirements](https://docs.aws.amazon.com/eks/latest/userguide/network-reqs.html)); changing an existing two-AZ cluster to three through this root is not an in-place migration. Plan a new cluster and workload migration, including Fargate profiles and added network cost. Existing two-AZ demos must explicitly retain `availability_zone_count = 2`.

1. Copy `terraform.tfvars.example` to `terraform.tfvars` and replace the example CIDR with your current public IPv4 `/32`.
2. Run `terraform init`, `terraform fmt -check -recursive`, `terraform validate`, `terraform plan`, and `terraform apply` from this directory.
3. Build and push the MCP image with `../../../demo/push-image.sh`.
4. Configure and apply the separate `../gitops-bridge` root.

The primary EKS API endpoint is public but CIDR-restricted, with private endpoint access also enabled. Fargate profiles use the system private subnets for CoreDNS, Argo CD, and the Agent Sandbox controller/router; sandbox pods use the isolated sandbox subnets. All Internet-bound private subnet traffic is routed through the same-AZ Network Firewall endpoint and NAT gateway. NAT return routes send each private subnet's response traffic back through that firewall endpoint.

EKS Fargate does not enforce Kubernetes NetworkPolicy. The sandbox therefore uses a dedicated `SecurityGroupPolicy` and an AWS Network Firewall SNI allowlist. The sandbox SG allows DNS to the cluster service CIDR and TCP/443; the firewall allows only `example.com` HTTPS from sandbox CIDRs. DNS Firewall allows `example.com` and `example.org` (the latter is resolvable but denied by Network Firewall) and blocks unlisted names such as `evil.example.com`. System subnets use a separate source CIDR and pass through the firewall so controllers can retrieve upstream images.

The S3 gateway endpoint policy allows ECR's regional image-layer bucket. System subnets also receive read-only access to the regional public Kubernetes registry image-layer bucket, because `registry.k8s.io` redirects layer downloads there. That additional allowance does not apply to sandbox subnets. Neither statement grants general S3 access or bucket listing. The DNS allowlist includes the registry's regional `pkg.dev` redirect and its `googlecode.l.googleusercontent.com` CNAME target. The sandbox IAM role intentionally has no S3 permissions. The GitOps chart configures the EKS Fargate log router to send new pod stdout/stderr to `/aws/eks/<cluster_name>/fargate`; the Fargate execution role has write access only to that log group.

Destroy only after the demo is complete: `terraform destroy`. This is a charged environment (one NAT gateway and firewall endpoint per selected AZ, EKS control plane, and Fargate workloads).
