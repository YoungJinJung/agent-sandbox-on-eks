# agent-sandbox-on-eks

Run untrusted MCP servers and AI agent tools in disposable, isolated sandboxes on Amazon EKS using [kubernetes-sigs/agent-sandbox](https://github.com/kubernetes-sigs/agent-sandbox).

AWS Community Day 발표 데모 레포입니다.

- **CFP 제목:** Agent Sandbox와 Amazon EKS로 만드는 격리형 AI 도구 실행 환경
- **가제(수정안):** Agent Sandbox는 정말 Sandbox인가? Amazon EKS에서 AI 도구 실행 경계 만들기

## 핵심 메시지

> Agent Sandbox는 보안 샌드박스를 제공하지 않는다.
> Kubernetes 수명주기 API 위에 AWS의 격리·IAM·네트워크·감사를 조합해야 비로소 샌드박스가 된다.

## 문서

- [아키텍처](docs/architecture.md): 계층별 선택, 데모 시나리오, 구성도, 런타임 비교
- [구현 계획](docs/plan.md): 단계별 계획, 검증할 가정, 열린 질문

## 데모 코드

`src/mcp_server/server.py`는 Streamable HTTP MCP 서버입니다. `summarize`는 부작용이 없는 예시 도구이고, `check_sandbox_boundary`는 고정된 목적지만 점검합니다. 임의 URL, 셸 명령, 임의 AWS API는 입력받지 않습니다. 외부 HTTPS는 `example.com`만 허용합니다. `example.org`는 DNS는 되지만 Network Firewall이 막고, `evil.example.com`은 DNS Firewall에서 막히도록 분리했습니다.

### 배포 순서

필요 도구: AWS CLI 인증, Terraform, Docker Buildx, `kubectl`, `uv`. 테스트 계정에서만 실행하세요. EKS, 두 NAT Gateway, Network Firewall, CloudWatch Logs는 비용이 발생합니다.

1. `infra/terraform/cluster`에서 `terraform.tfvars.example`을 복사해 현재 공인 IP를 `/32`로 넣고 `terraform init && terraform plan && terraform apply`를 실행합니다.
2. 저장소 루트에서 `./demo/push-image.sh`로 MCP 이미지를 ECR에 빌드·푸시합니다.
3. `infra/terraform/gitops-bridge/terraform.tfvars.example`을 복사하고 클러스터 Terraform outputs와 공개 Git URL을 입력한 뒤 해당 디렉터리에서 `terraform init && terraform plan && terraform apply`를 실행합니다.
4. Argo CD가 생성한 두 Application의 동기화를 확인합니다: `kubectl get applications -n argocd`.
5. `./demo/run.sh`를 실행합니다. 성공하면 허용·차단 관측과 Claim의 TTL 삭제를 기다립니다. 기본 TTL은 2분이며 `SANDBOX_TTL_MINUTES=5 ./demo/run.sh`처럼 바꿀 수 있습니다. Claim이 warm pool에서 할당되면 pool이 교체용 Pod를 하나 띄우므로, 스크립트는 TTL 삭제 확인 후 pool을 제거합니다.
6. 먼저 `infra/terraform/gitops-bridge`에서 `terraform destroy`, 이후 `infra/terraform/cluster`에서 `terraform destroy`를 실행합니다.

Fargate stdout/stderr는 `/aws/eks/<cluster_name>/fargate`, DNS 질의는 `/aws/route53resolver/<cluster_name>`, Network Firewall은 `/aws/network-firewall/<cluster_name>`, VPC Flow Logs는 `/aws/vpc/flow-logs/<cluster_name>` CloudWatch Logs 그룹에서 확인할 수 있습니다. CloudTrail 관리 이벤트는 `terraform -chdir=infra/terraform/cluster output -raw cloudtrail_bucket_name`의 S3 버킷에 전달됩니다.

Terraform state는 두 디렉터리에 각각 local로 저장됩니다. 공유/운영 환경에서는 암호화와 잠금이 설정된 remote backend를 구성하세요. Terraform이 설치하는 Argo CD는 GitOps Bridge 메타데이터를 담은 cluster Secret과 ApplicationSets만 부트스트랩하며, 나머지 Kubernetes 리소스는 Git에서 조정됩니다. 일회성 WarmPool/Claim은 라이브 데모 요청이므로 드라이버가 생성하고 `shutdownTime`으로 종료합니다.

자세한 리소스 경계와 Terraform 형식은 [cluster 인프라 안내](infra/terraform/cluster/README.md), [GitOps Bridge 안내](infra/terraform/gitops-bridge/README.md)를 참고하세요.
