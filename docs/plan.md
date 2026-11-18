# 구현 계획

아키텍처는 [architecture.md](architecture.md) 참고.

| 단계 | 내용 | 완료 기준 |
|---|---|---|
| **M0. 결정** | 발표 시간, AWS 계정·리전, IaC 도구 확정 | 아래 "열린 질문" 해소 |
| **M1. 인프라** | 운영 최소 3 AZ VPC (데모 2 AZ), 각 AZ의 system private·sandbox private·Network Firewall·public egress 서브넷, VPC endpoints, EKS Fargate profiles, OIDC provider | `infra/terraform/cluster` plan/apply 및 destroy 가능 |
| **M2. agent-sandbox** | 버전 고정 설치(`sandbox-with-extensions.yaml`), sandbox-router, `SandboxTemplate`(IRSA SA, read-only rootfs, resource limit), Fargate Pod `SecurityGroupPolicy` | WarmPool에서 Claim 할당, 반환 후 Claim·Sandbox·해당 Pod 삭제 확인. 만료 동작은 별도 검증 |
| **M3. MCP 서버** | `summarize`와 경계 점검 도구가 있는 Python MCP 서버(Streamable HTTP), ECR 이미지 | router를 통한 호출이 IAM·DNS·HTTPS 각 관측 결과를 출력 |
| **M4. 네트워크 통제·관측** | AWS Network Firewall의 sandbox 전용 HTTPS SNI allowlist, Route 53 DNS Firewall, AZ별 NAT, CloudTrail, Resolver Query Logs, VPC Flow Logs | `example.com` 성공, `example.org` HTTPS 차단, `evil.example.com` DNS 차단을 각각 확인 |
| **M5. 데모 드라이버** | `demo/run.sh`: 사전 준비와 실행 분리, 실제 Pod·Node의 Fargate 검증, router 경유 MCP 호출, 단계별 관측·삭제 확인 | 약 2분 라이브·촬영 절차와 60초 발표 멘트 구분, 실패 시 정리, 실행 기록 기반 방화벽 로그 대조. 기본 5분 TTL은 반환 누락 대비 |
| **M6. 발표 자료** | v20의 PDF 요약 요청 흐름, 운영 3 AZ draw.io, 20장의 60초 영상과 23장의 로그 대조 | 설명 24분 + 영상 1분 + Q&A 5분. [영상·자막·발표 멘트](../demo/README.md)와 Google Slides 재생본 연결 |

현재 디렉터리 구조:

```
infra/terraform/cluster/       # AWS 기반 인프라와 관측
infra/terraform/gitops-bridge/ # Argo CD 설치와 bridge Secret/ApplicationSet
infra/terraform/demo-workloads/ # 촬영용 Helm 배포·정리 (GitOps Bridge 대체 경로)
gitops/platform/               # Agent Sandbox controller, router
gitops/apps/mcp-sandbox/       # IRSA, Pod SG policy, SandboxTemplate
src/mcp_server/                # 제한된 동작을 가진 MCP 서버와 테스트
demo/                          # 이미지 푸시, 사전 준비·4단계 시연·로그 대조·발표 멘트
demo/media/                    # v20에서 쓰는 60초 MP4·SRT, 출처·재생 안내
docs/                          # 아키텍처, 구현 계획, 발표 노트
```

## M1~M4에서 검증할 가정

- **Fargate + SecurityGroupPolicy:** Fargate Pod에 클러스터 SG를 포함하면 필요한 클러스터 통신 규칙을 재사용할 수 있지만, 필수는 아닙니다([문서](https://docs.aws.amazon.com/eks/latest/best-practices/sgpp.html)). 필요한 DNS, router, control-plane, endpoint 통신만 남긴 전용 SG 규칙을 검증합니다.
- **DNS 출처 추적:** 샌드박스의 DNS 질의는 CoreDNS를 거쳐 VPC resolver로 가므로, Resolver Query Logs의 출발지는 샌드박스 Pod가 아니라 CoreDNS입니다. Pod 단위로 추적하려면 CoreDNS `log` 플러그인이 필요할 수 있습니다.
- **DNS를 통한 유출:** VPC resolver는 인터넷 경로 차단만으로 외부 도메인 질의를 막지 않습니다. Route 53 Resolver DNS Firewall allowlist로 승인 도메인 질의만 허용하고, Pod가 VPC resolver 외 DNS 서버로 직접 질의할 수 없는지 확인합니다.
- **제한된 egress의 Fargate:** AZ별 전용 firewall endpoint → NAT 경로와 return route가 대칭으로 동작하는지, ECR·STS·S3·CloudWatch Logs 등 필요한 AWS VPC endpoint를 통해 Fargate가 동작하는지 확인합니다.
- **도메인 allowlist의 범위:** Network Firewall은 HTTPS에서 TLS SNI, HTTP에서 Host 헤더로 도메인을 판별합니다. 기본 정책은 그 외 트래픽을 거부하고, IP 직접 연결도 차단되는지 확인합니다. VPC 내부 `local` 경로는 인터넷 egress 경로를 통과하지 않으므로 내부 대상 보안 그룹 규칙도 별도로 점검합니다.
- **CloudTrail 전달 지연:** CloudTrail 이벤트는 수 분 늦게 도착합니다. 라이브 데모에서는 발표 초반에 실행해 두거나 사전 실행 결과를 함께 준비합니다.

## 열린 질문

- 발표 시간(데모 구간 길이)
- 사용할 AWS 계정과 리전, 기존 EKS 클러스터 재사용 여부
- Terraform state를 팀 환경에서 사용할 때 remote backend와 lock을 별도로 구성합니다. 데모 root는 local state입니다.
