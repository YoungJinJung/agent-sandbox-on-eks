# 아키텍처

## 계층별 선택

Agent Sandbox가 주는 것은 `Sandbox` / `SandboxTemplate` / `SandboxClaim` / `SandboxWarmPool` 같은 **수명주기 API**입니다. 격리 런타임은 사용자가 따로 골라야 합니다([위협 모델](https://github.com/kubernetes-sigs/agent-sandbox/blob/main/docs/security/threat_model.md)). 이 레포는 EKS에서 그 빈칸을 다음 계층으로 채웁니다.

| 계층 | 이 레포의 선택 | 대안 (비교만 함) |
|---|---|---|
| 수명주기 | agent-sandbox `SandboxClaim` + `shutdownTime` | Job + `ttlSecondsAfterFinished` |
| 런타임 격리 | **EKS Fargate** (Pod마다 전용 microVM·커널) | EC2 + gVisor, EC2 + Kata |
| AWS 권한 | **IRSA** (최소 권한 role) | EKS Pod Identity (Fargate 미지원) |
| 네트워크 | **NAT 없는 격리 서브넷** + deny-by-default egress proxy | NetworkPolicy (Fargate 미지원) |
| 관측 | CloudTrail, Route 53 Resolver Query Logs, proxy 로그 | eBPF 기반 syscall 관측 (Fargate·gVisor에서 전제가 약함) |

## 데모 시나리오

> 악성 MCP 서버가 제한된 AWS 역할을 쓰고 외부로 데이터를 보내려 한다
> → AWS 호출은 CloudTrail에 남고, 외부 전송은 egress 정책이 막는다
> → Sandbox는 TTL 이후 삭제된다.

악성 MCP 서버는 평범한 도구(`summarize`)처럼 보이지만, 호출되면 다음을 시도합니다.

1. `sts:GetCallerIdentity`: 권한이 없어도 성공하는 호출이며 CloudTrail에 남습니다.
2. `s3:ListBuckets`: 최소 권한 role이라 `AccessDenied`가 나고, 이 역시 CloudTrail에 남습니다.
3. proxy를 거쳐 `https://evil.example.com` 호출: allowlist에 없어 proxy가 거부하고 로그를 남깁니다.
4. proxy를 무시한 직접 연결: 라우팅 경로가 없어 timeout이 납니다.
5. `evil.example.com` DNS 조회: Resolver Query Logs에 남습니다.

데모 결과는 `PASS/SAFE` 대신 **관측한 사실**로 출력합니다.

```
Observed:
- sts:GetCallerIdentity 호출
- s3:ListBuckets AccessDenied
- evil.example.com DNS 조회
- 443/tcp 외부 연결 차단 (proxy deny)
- Sandbox TTL 삭제 완료

Not observed != safe
```

**의도적으로 다루지 않는 것:** 미끼 파일 읽기 검출은 제외합니다. `readOnlyRootFilesystem`은 쓰기만 막고 읽기 증거는 남기지 않습니다. 읽기를 검출하려면 fanotify/audit, 파일 접근 중개 API, syscall 관측 같은 별도 계층이 필요하고, 이는 별도 연구 주제입니다.

## 구성도

```
┌──────────────────────────── VPC ─────────────────────────────────────┐
│                                                                      │
│  private subnet (NAT 있음)             isolated subnet (NAT·IGW 없음)│
│  ┌──────────── EKS EC2 node ───────┐   ┌──── EKS Fargate ──────────┐ │
│  │ agent-sandbox controller        │   │ ns: sandbox               │ │
│  │ sandbox-router ─────────────────┼──▶│  MCP server Pod (microVM) │ │
│  │ egress proxy (deny-by-default)◀─┼───┤   ├─ IRSA: 최소 권한 role │ │
│  │ CoreDNS                         │   │   ├─ read-only rootfs     │ │
│  └───────────────┬─────────────────┘   │   ├─ CPU/memory limit     │ │
│                  │ allowlist만         │   ├─ HTTPS_PROXY=proxy    │ │
│                  ▼                     │   └─ shutdownTime (TTL)   │ │
│              NAT → Internet            └──────────┬────────────────┘ │
│                                                   │                  │
│                          VPC endpoints: sts, ecr.api, ecr.dkr, s3    │
└──────────────────────────────────────────────────────────────────────┘
   관측: CloudTrail (AWS API) · Route 53 Resolver Query Logs (DNS) · proxy access log (egress)

Agent / Test Driver ──▶ sandbox-router ──▶ SandboxClaim ──▶ MCP server (Fargate)
```

설계 원칙:

- **통제와 관측을 분리합니다.** 외부 egress를 실제로 막는 것은 격리 서브넷의 라우팅(NAT 없음)입니다. proxy는 허용된 목적지로 가는 유일한 경로이자 관측 지점입니다. 악성 코드가 `HTTPS_PROXY`를 무시해도 나갈 경로가 없습니다.
- **Fargate 하나만 끝까지 구현합니다.** gVisor와 Kata는 비교표와 후속 실험으로 남깁니다.
- **Warm Pool은 선택 사항입니다.** Fargate에서도 쓸 수 있지만, 대기 중인 Pod도 microVM 비용이 계속 나갑니다. 콜드 스타트 시간을 측정한 뒤 켤지 정합니다.

### Fargate의 트레이드오프

| 항목 | 영향 |
|---|---|
| Pod마다 전용 커널·compute boundary | 첫 구현의 격리 경계로 가장 단순함 |
| IMDS 접근 불가 | 노드 자격증명 탈취 경로가 없음 |
| DaemonSet 불가 | 노드 기반 관측 에이전트를 쓸 수 없고 sidecar나 AWS 측 로그에 의존 |
| RuntimeClass 선택 불가 | gVisor/Kata와 겹쳐 쓸 수 없음 |
| privileged, hostNetwork 불가 | 샌드박스 입장에서는 장점 |
| NetworkPolicy 미적용 | egress 통제를 서브넷 라우팅, SG, proxy로 해결해야 함 |
| Pod Identity 미지원 | IRSA 사용 |
| 유휴 Warm Pool Pod도 과금 | 콜드 스타트 지연과 유휴 비용 중 하나를 골라야 함 |

### 런타임 비교 (발표용, 구현 범위 밖)

| | Fargate | EC2 + gVisor | EC2 + Kata |
|---|---|---|---|
| 격리 경계 | microVM (AWS 관리) | 사용자 공간 커널 | 경량 VM |
| 노드 관리 | 없음 | 노드 이미지·containerd 설정 | 노드 이미지·containerd 설정, KVM 필요 |
| 하드웨어 요건 | 없음 | 없음 | metal, 또는 nested virtualization 지원 인스턴스(C/M/R 7i·8i 등) |
| 노드 레벨 관측 (eBPF) | 불가 | 샌드박스 내부 syscall 관측 전제가 약함 | 게스트 커널 안은 보이지 않음 |
| 기동 속도 | 느림 (수십 초) | 빠름 | 중간 |

## 참고

- [kubernetes-sigs/agent-sandbox](https://github.com/kubernetes-sigs/agent-sandbox)
- [Agent Sandbox 위협 모델](https://github.com/kubernetes-sigs/agent-sandbox/blob/main/docs/security/threat_model.md)
- [EKS Fargate considerations](https://docs.aws.amazon.com/eks/latest/userguide/fargate.html)
- [Security Groups for Pods with Fargate](https://docs.aws.amazon.com/eks/latest/best-practices/sgpp.html)
- [VPC CNI network policy considerations](https://docs.aws.amazon.com/eks/latest/userguide/cni-network-policy.html)
- [EKS Pod Identity restrictions](https://docs.aws.amazon.com/eks/latest/userguide/pod-identities.html)
- [EC2 nested virtualization](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/amazon-ec2-nested-virtualization.html)
