# Amazon EKS의 Agent Sandbox

## 요청 및 egress 흐름

1. AI Agent/Demo Driver의 MCP 도구 호출이 EKS system workload의 router로 들어옵니다.
2. `SandboxClaim`이 AZ-a 또는 AZ-b의 일회성 Fargate Sandbox Pod로 연결됩니다.
3. 외부 HTTPS 트래픽은 Sandbox와 같은 AZ의 AWS Network Firewall endpoint를 지난 뒤 해당 AZ의 NAT Gateway를 거쳐 나갑니다.
4. 두 AZ의 endpoint는 같은 TLS SNI allowlist 정책을 사용합니다. Route 53 DNS Firewall은 승인 도메인의 DNS 질의만 허용합니다.
5. STS, ECR, S3는 VPC endpoint의 private path를 사용합니다. CloudTrail, Resolver Query Logs, Network Firewall logs, VPC Flow Logs가 실행 중 서로 다른 흔적을 남깁니다.

## 주요 서비스

| 서비스 | 역할 |
|---|---|
| Amazon EKS | Kubernetes control plane 및 system workload 관리 |
| AWS Fargate | Sandbox Pod별 compute boundary |
| IRSA | Sandbox에 최소 권한 AWS 자격증명 제공 |
| SecurityGroupPolicy | Sandbox Pod에 전용 security group 연결 |
| AWS Network Firewall | AZ별 endpoint를 통한 HTTPS 도메인 allowlist |
| Route 53 Resolver DNS Firewall | DNS 도메인 allowlist |
| NAT Gateway / Internet Gateway | 방화벽 검사 후 외부 egress 제공 |
| VPC endpoints | STS, ECR, S3 private access |
| CloudTrail / Resolver Query Logs / CloudWatch Logs | AWS API, DNS, firewall, VPC flow 관측 |

## 설계 메모

- AZ-a와 AZ-b는 각각 EKS system private, Sandbox private, firewall 전용, public egress 서브넷을 가집니다.
- 응답 트래픽은 요청과 같은 AZ의 Network Firewall endpoint를 통과하도록 route table을 구성합니다.
- VPC의 `local` route는 인터넷 egress firewall을 지나지 않습니다. 따라서 내부 서비스의 security group도 Sandbox 접근을 허용하지 않도록 별도로 설정해야 합니다.
- HTTPS 도메인 규칙은 TLS SNI를 기준으로 합니다. IP 주소 기반 정책은 별도로 검증합니다.
