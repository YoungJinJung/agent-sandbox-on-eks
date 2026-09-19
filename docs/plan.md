# 구현 계획

아키텍처는 [architecture.md](architecture.md) 참고.

| 단계 | 내용 | 완료 기준 |
|---|---|---|
| **M0. 결정** | 발표 시간, AWS 계정·리전, IaC 도구 확정 | 아래 "열린 질문" 해소 |
| **M1. 인프라** | VPC(private + isolated 서브넷), VPC endpoints, EKS(EC2 노드그룹 + `sandbox` 네임스페이스 Fargate profile), OIDC provider | `make up` / `make down`으로 생성·삭제 가능 |
| **M2. agent-sandbox** | 버전 고정 설치(`sandbox-with-extensions.yaml`), sandbox-router, `SandboxTemplate`(IRSA SA, read-only rootfs, resource limit, `HTTPS_PROXY`) | `SandboxClaim` 생성 시 Fargate Pod가 뜨고 `shutdownTime` 이후 삭제됨 |
| **M3. 악성 MCP 서버** | `summarize` 도구를 가장한 Python MCP 서버(streamable HTTP), ECR 푸시 | router를 거쳐 도구 호출 시 [데모 시나리오](architecture.md#데모-시나리오)의 1~5 동작 수행 |
| **M4. 네트워크 통제·관측** | egress proxy(allowlist), CloudTrail trail, Resolver Query Logs | 각 시도가 해당 로그에 남는 것을 확인 |
| **M5. 데모 드라이버** | `demo/run.sh`: claim 생성, 도구 호출, 로그 수집, TTL 삭제 확인, `Observed:` 출력 | 한 번의 명령으로 재현 가능 |
| **M6. 발표 자료** | 아키텍처 다이어그램, 런타임 비교, AgentCore vs EKS 선택 기준 | 슬라이드 초안 |

예정 디렉터리 구조:

```
infra/             # VPC, EKS, Fargate profile, IRSA, VPC endpoints, 로그 설정
k8s/
  agent-sandbox/   # 버전 고정 설치 매니페스트, router
  sandbox/         # SandboxTemplate, ServiceAccount(IRSA), (선택) SandboxWarmPool
  egress-proxy/    # deny-by-default proxy + allowlist
mcp/evil-server/   # 악성 MCP 서버 (Dockerfile, server.py)
demo/              # run.sh, 관측 결과 수집
docs/              # 비교표, AgentCore vs EKS, 발표 노트
```

## M1~M4에서 검증할 가정

- **Fargate + SecurityGroupPolicy:** Fargate Pod에 SG를 붙이려면 클러스터 SG를 반드시 포함해야 합니다([문서](https://docs.aws.amazon.com/eks/latest/best-practices/sgpp.html)). 그래서 SG만으로는 VPC 내부 lateral 이동을 좁히기 어려울 수 있습니다. 외부 egress의 1차 경계는 라우팅으로 두고, SG로 어디까지 좁힐 수 있는지 측정합니다.
- **DNS 출처 추적:** 샌드박스의 DNS 질의는 CoreDNS를 거쳐 VPC resolver로 가므로, Resolver Query Logs의 출발지는 샌드박스 Pod가 아니라 CoreDNS입니다. Pod 단위로 추적하려면 CoreDNS `log` 플러그인이 필요할 수 있습니다.
- **DNS를 통한 유출:** NAT가 없어도 VPC resolver는 외부 도메인을 재귀 조회합니다. 따라서 DNS 터널링은 라우팅만으로 막을 수 없습니다. Route 53 Resolver DNS Firewall을 추가할지 M4에서 결정합니다(발표의 "한계" 소재로 좋음).
- **격리 서브넷의 Fargate:** NAT 없이 Fargate Pod가 이미지 pull, IRSA(STS), 로그 전송을 할 수 있는지 확인하고, 필요한 VPC endpoint를 확정합니다.
- **CloudTrail 전달 지연:** CloudTrail 이벤트는 수 분 늦게 도착합니다. 라이브 데모에서는 발표 초반에 실행해 두거나 사전 실행 결과를 함께 준비합니다.

## 열린 질문

- 발표 시간(데모 구간 길이)
- 사용할 AWS 계정과 리전, 기존 EKS 클러스터 재사용 여부
- IaC 도구: Terraform(VPC·로그·EKS를 한 도구로) vs eksctl(EKS는 간단하지만 VPC·로그는 별도)
