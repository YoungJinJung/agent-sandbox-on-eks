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
