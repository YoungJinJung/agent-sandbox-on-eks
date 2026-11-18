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
- [v20 발표 데모](demo/README.md): 20장의 60초 영상, 발표 멘트, 실제 Fargate 확인과 재촬영 절차

### 최신 발표본 (v20)

[발표용 Google Slides](https://docs.google.com/presentation/d/1D0ushQ9PlXbvWmQBPe7aMOpbENXl1e8kDcaZwg48RIE/edit?slide=id.p20#slide=id.p20)의 **20장**에서 [60초 MP4](demo/media/AWS_Community_Day_2026_demo_v18.mp4)를 재생합니다. 영상 파일의 `v18`은 편집본 버전이며, v20에서도 같은 영상을 사용합니다. 발표는 설명 24분 + 영상 1분 + Q&A 5분입니다. [60초 발표 멘트](demo/narration-ko.txt)에는 19장과 21장 사이의 연결도 포함돼 있습니다.

PPTX 내장 영상은 Google Slides의 PPTX 호환 편집에서 삭제될 수 있습니다. Google Slides로 발표할 때는 위 발표용 사본을 사용하고, 장표가 참조하는 Drive MP4를 유지합니다. 새 PPTX를 올리는 경우에는 Google Slides 형식으로 저장한 뒤 Drive 영상을 다시 삽입해야 합니다. [재생 점검과 영상 출처](demo/media/README.md)를 참고하세요.

## 데모 코드

`src/mcp_server/server.py`는 Streamable HTTP MCP 서버입니다. `summarize`는 부작용이 없는 예시 도구이고, `check_sandbox_boundary`는 고정된 목적지만 점검합니다. 임의 URL, 셸 명령, 임의 AWS API는 입력받지 않습니다. 외부 HTTPS는 `example.com`만 허용합니다. `example.org`는 DNS는 되지만 Network Firewall이 막고, `evil.example.com`은 DNS Firewall에서 막히도록 분리했습니다.

### 배포 순서

촬영용 일회성 환경은 [Terraform 데모 배포](infra/terraform/demo-workloads/README.md)를 사용하면 AWS 인프라부터 컨트롤러·Router·도구까지 배포하고 역순으로 정리할 수 있습니다. 아래 GitOps Bridge 경로와는 같은 클러스터에 함께 적용하지 않습니다.

필요 도구: AWS CLI 인증, Terraform, Docker Buildx, `kubectl`, `uv`. 테스트 계정에서만 실행하세요. EKS, AZ별 NAT Gateway와 Network Firewall endpoint, CloudWatch Logs는 비용이 발생합니다. Terraform 기본값은 3개 AZ이며, 예제 설정은 데모용 2개 AZ를 명시합니다. 운영은 최소 3개 AZ를 사용합니다.

1. `infra/terraform/cluster`에서 `terraform.tfvars.example`을 복사해 현재 공인 IP를 `/32`로 넣고 `terraform init && terraform plan && terraform apply`를 실행합니다.
2. 저장소 루트에서 `./demo/push-image.sh`로 MCP 이미지를 ECR에 빌드·푸시합니다.
3. `infra/terraform/gitops-bridge/terraform.tfvars.example`을 복사하고 클러스터 Terraform outputs와 공개 Git URL을 입력한 뒤 해당 디렉터리에서 `terraform init && terraform plan && terraform apply`를 실행합니다.
4. Argo CD가 생성한 두 Application의 동기화를 확인합니다: `kubectl get applications -n argocd`.
5. 라이브 실행이나 재촬영 시 `./demo/run.sh prepare`로 환경을 준비한 뒤 `./demo/run.sh`를 실행합니다. Enter로 **환경 할당·Fargate 확인 → 예시 도구 호출 → 접근 결과 → 환경 반환** 네 단계를 진행합니다. Claim·Sandbox·해당 Pod 삭제와 대기 풀 정리까지 확인합니다. 기본 TTL은 Claim 생성 시점부터 5분이며 반환 누락에 대비한 값입니다. 작업 후에는 명시적으로 반환합니다. 실제 실행 시간은 AWS 응답과 발표자 대기에 따라 달라지며, v20에서는 이 실행 기록을 편집한 60초 영상을 사용합니다. [실행·촬영 안내](demo/README.md)를 참고하세요.
6. 먼저 `infra/terraform/gitops-bridge`에서 `terraform destroy`, 이후 `infra/terraform/cluster`에서 `terraform destroy`를 실행합니다.

Fargate stdout/stderr는 `/aws/eks/<cluster_name>/fargate`, DNS 질의는 `/aws/route53resolver/<cluster_name>`, Network Firewall은 `/aws/network-firewall/<cluster_name>`, VPC Flow Logs는 `/aws/vpc/flow-logs/<cluster_name>` CloudWatch Logs 그룹에서 확인할 수 있습니다. CloudTrail 관리 이벤트는 `terraform -chdir=infra/terraform/cluster output -raw cloudtrail_bucket_name`의 S3 버킷에 전달됩니다.

Terraform state는 두 디렉터리에 각각 local로 저장됩니다. 공유/운영 환경에서는 암호화와 잠금이 설정된 remote backend를 구성하세요. Terraform이 설치하는 Argo CD는 GitOps Bridge 메타데이터를 담은 cluster Secret과 ApplicationSets만 부트스트랩하며, 나머지 Kubernetes 리소스는 Git에서 조정됩니다. 일회성 WarmPool/Claim은 드라이버가 생성하고 작업 후 삭제합니다. Claim에는 반환 누락에 대비해 `shutdownTime`도 설정합니다.

자세한 리소스 경계와 Terraform 형식은 [cluster 인프라 안내](infra/terraform/cluster/README.md), [GitOps Bridge 안내](infra/terraform/gitops-bridge/README.md)를 참고하세요.
