# AWS Community Day 데모 — v20 발표 기준

청중에게 남길 한 문장은 **“도구에 실행 환경을 빌려주고, 접근 범위를 제한한 채 호출하고, 사용한 환경을 정리한다”**입니다. v20의 **19장 사용자 소유권 → 20장 60초 영상 → 21장 관측·정리**로 이어집니다. 기존 1·2·3 흐름과 전체 30분(설명 24분 + 영상 1분 + Q&A 5분)을 유지합니다.

## 발표에서 사용하는 파일

- [60초 MP4](media/AWS_Community_Day_2026_demo_v18.mp4): 실제 AWS 실행 기록을 편집한 무음·자막 영상. `v18` 편집본을 v20에서도 그대로 사용합니다.
- [자막 SRT](media/AWS_Community_Day_2026_demo_v18.srt), [60초 발표 멘트](narration-ko.txt), [영상 출처·재생 안내](media/README.md)
- [발표용 Google Slides](https://docs.google.com/presentation/d/1D0ushQ9PlXbvWmQBPe7aMOpbENXl1e8kDcaZwg48RIE/edit?slide=id.p20#slide=id.p20): 20장에 Drive 영상이 삽입된 사본입니다. 2026-11-17 슬라이드쇼에서 재생과 종료를 확인했습니다.

영상 구간은 **00:00–00:18 할당·Fargate 확인 / 00:18–00:28 도구 호출 / 00:28–00:48 접근 범위 / 00:48–01:00 반환**입니다. 22장에서 연결 실패의 여러 원인을 설명하고, 23장에서 영상과 같은 Pod의 방화벽 로그로 차단을 확인합니다.

발표용 영상만 재생할 때는 AWS를 다시 배포하지 않습니다. 아래 절차는 라이브 실행·리허설·재촬영용입니다. 실제 실행을 60초 안에 끝낸다는 의미가 아니며, 화면의 `총 100.9초`는 편집 전 실행 시간입니다.

## 무대 밖 준비

배포 순서는 루트 README를 따릅니다. 이 변경에는 Network Firewall 규칙 그룹의 `STRICT_ORDER` 수정이 있으므로 Terraform plan을 검토하고 적용한 환경에서 리허설하세요. 로컬 테스트 통과는 AWS 배포 성공을 뜻하지 않습니다.

```bash
# 실행 대상 확인
kubectl config current-context

# Python 의존성 설치, Router/Template 확인, Warm Pool 준비 (최대 5분)
./demo/run.sh prepare

# 무대에서 실행. 각 단계 직전에 Enter를 눌러 설명 속도에 맞춥니다.
./demo/run.sh
```

준비된 Fargate Pod를 사용하므로 무대에서 콜드 스타트를 기다리지 않습니다. 실행 후 대기 풀도 삭제하므로 매 리허설/발표 전에 `prepare`를 다시 실행합니다. `mcp-stage`는 이 데모 전용 이름이며 동일 namespace에서는 한 발표자만 실행합니다. 준비만 해둔 채 발표를 취소하면 `./demo/run.sh cleanup`으로 풀과 소유 리소스를 삭제합니다. 대기 Pod도 과금됩니다.

자동 리허설은 `./demo/run.sh run --auto`입니다. 기본 TTL은 **Claim 생성 시점부터 5분**이며, `SANDBOX_TTL_MINUTES=10 ./demo/run.sh`로 바꿀 수 있습니다. 라이브 시연의 약 2분은 설명을 포함한 목표 시간입니다. API 응답, MCP 호출, 리소스 삭제 속도에 따라 달라지며 실제 소요 시간을 마지막에 출력합니다. `--auto`는 Enter 대기만 생략하며 영상 편집 기능은 아닙니다.

## Fargate 실행 증거를 포함한 재촬영

촬영용 배포·정리는 [Terraform 구성](../infra/terraform/demo-workloads/README.md)을 사용합니다. 첫 단계에서 할당 Pod를 다시 조회해 UID가 유지되는지 확인하고, 그 Pod의 `spec.nodeName`으로 Node를 조회합니다. 실제 Node 라벨 `eks.amazonaws.com/compute-type=fargate`와 Pod의 `schedulerName=fargate-scheduler`가 모두 일치해야 진행합니다. 원본 Pod·Node 응답과 조회 시각은 `demo/.runs/<claim>.fargate.json`에 저장합니다.

[재촬영용 2분 멘트](narration-recording-ko.txt)는 원본 촬영의 환경·Fargate 확인 38초, 도구 호출 19초, 접근 범위 35초, 반환·연결 28초 기준을 보존합니다. 준비 후 `python3 demo/record.py demo/.runs/take-새이름`으로 실제 터미널 출력과 입력 시각을 수집할 수 있습니다. 이 스크립트는 2분 구성의 원시 기록(`capture.json`, `terminal.txt`)을 수집하며 MP4를 생성하지 않습니다. 새 디렉터리를 지정해야 하며, 성공 여부는 기록의 종료 코드로 확인합니다. 60초 발표에는 [현재 발표 멘트](narration-ko.txt)를 사용합니다. 영상 조판은 기록된 값과 순서를 유지하며, 수집되지 않은 결과를 덧붙이지 않습니다.

영상이 끝나면 21장으로 넘겨 “Fargate 실행은 확인했습니다. 이제 연결 실패를 설명하고, 결과를 남긴 뒤 안전하게 끝내는 조건을 보겠습니다”로 이어갑니다. 이 도구는 고정 URL에 GET 요청만 보내며 PDF 본문을 외부로 전송하지 않습니다. S3의 AccessDenied에는 역할 정책과 VPC Endpoint 정책이 함께 영향을 줍니다.

## 로그로 차단 원인 확인

실행 결과는 단계별 한글로 출력합니다. 별도의 `demo/.runs/<실행 ID>.json`은 Pod IP와 조회 시간 범위를 보존하는 내부 기록이며 Git에서 제외합니다. 실행 종료 화면에 나온 경로를 사용합니다.

```bash
AWS_DEFAULT_REGION=ap-northeast-2 python3 demo/with-aws-session.py ./demo/run.sh evidence \
  demo/.runs/<실행 ID>.json \
  --log-group /aws/network-firewall/<cluster_name>
```

이 명령은 발표자 AWS 자격증명으로 `logs:FilterLogEvents`를 호출합니다. Sandbox에 로그 조회 권한을 추가하지 않습니다. 해당 실행 시간 범위와 Pod IP, `example.org` SNI, 규칙 1199, `blocked` 동작이 모두 일치할 때만 **방화벽 차단 확인**을 출력합니다. 로그가 늦게 도착하거나 필요한 필드가 없으면 **차단 로그 미확인**으로 남깁니다. 같은 명령을 나중에 다시 실행할 수 있습니다. AWS 이벤트 형식은 [공식 문서](https://docs.aws.amazon.com/network-firewall/latest/developerguide/firewall-logging-contents.html)를 따릅니다.

라이브 시연에서는 로그 도착을 기다리지 않습니다. 3번 관측 파트에서 조회하거나, 사전 리허설의 실행 ID·시간을 함께 표시한 실제 로그를 준비합니다. v20의 23장 로그는 2026-11-16 촬영과 같은 실행의 기록입니다. 재촬영하면 해당 실행의 로그를 다시 수집해 장표도 교체합니다. 이전 로그를 새 실행의 증거로 소개하지 않습니다.

## 실패했을 때

- Ready가 45초 내에 오지 않거나 Router 연결이 실패하면 중단하고 정리를 시도합니다. 무대에서는 “현재 환경 준비가 지연돼 사전 리허설 화면으로 설명하겠습니다”라고 전환합니다.
- 비허용 HTTPS 연결이나 S3 목록 조회가 성공하면 `확인 필요`를 출력하고 실패로 종료합니다. 정상 차단 시연으로 진행하지 않습니다.
- 삭제 확인이 실패하면 완료 문구를 출력하지 않습니다. 출력된 Claim/Sandbox/Pod 이름으로 리소스를 확인합니다. 강제 프로세스 종료나 제어 영역 장애 시 정리가 보장되지는 않습니다. Claim TTL도 컨트롤러가 동작해야 적용됩니다.
- Warm Pool의 교체용 Pod와 이번 요청의 Pod는 다릅니다. 데모는 Sandbox UID로 소유 Pod를 찾아 삭제를 확인하고, 마지막에 전용 풀을 foreground 삭제합니다.

## 로컬 검증

```bash
uv run --with-requirements src/mcp_server/requirements.txt python -m unittest discover -s src/mcp_server -v
uv run --with-requirements src/mcp_server/requirements.txt python -m unittest discover -s demo -v
bash -n demo/run.sh
terraform -chdir=infra/terraform/cluster validate
```

로컬 테스트는 MCP 도구 경로, 출력 판정, 할당 Pod 식별, 만료 계산, 실패 시 정리, 로그 매칭을 확인합니다. Kubernetes와 AWS는 모의 응답이며, 실제 Fargate 기동·권한 차단·방화벽 차단·삭제 시간은 배포 환경에서 리허설해야 합니다. PDF 업로드·AI 요약·EFS 초안·S3 보고서 저장은 이 데모의 구현 범위에 포함되지 않습니다.

## 실제 AWS 촬영 검증

2026-11-16 v17 재촬영은 서울 리전의 데모 2 AZ, EKS 1.35, Fargate, Agent Sandbox v1.0.5에서 수행했습니다. `cluster`와 `demo-workloads` Terraform root로 인프라와 Helm release를 배포했으며, Argo CD 동기화 과정은 포함하지 않았습니다. 할당된 Pod → 실제 Node → `compute-type=fargate`와 Pod의 `fargate-scheduler`를 Kubernetes API로 확인한 뒤 네 단계를 완료했습니다. STS 성공, S3 `AccessDenied`, 허용 HTTPS 200, 비허용 HTTPS 연결 실패, DNS 이름 해석 실패와 Claim·Sandbox·Pod 삭제를 확인했습니다. 촬영본의 Pod IP·실행 시간·`example.org` SNI와 Network Firewall 규칙 `1199`의 `blocked` 이벤트도 대조했습니다.

배포 과정에서 AZ별 라우팅 테이블, DNS Firewall 규칙 그룹 연결 우선순위, TLS SNI 차단 규칙, Fargate DNS 통신, Router의 kubelet 10250 접근, 이미지 레지스트리의 DNS 별칭과 시스템 서브넷 전용 S3 레이어 읽기를 수정했습니다. v17 원본은 실제 터미널 출력과 입력 시각을 수집한 뒤 발표용 화면으로 재배치한 120초 무음·자막 영상입니다. v18에서 같은 실행 기록의 발표자 대기를 줄여 60초로 편집했고, v20에서도 이 편집본을 사용합니다. v18·v20을 위해 AWS를 재배포하거나 실행 결과를 새로 생성하지 않았습니다.

v17 촬영 후 두 Terraform root를 역순으로 정리하여 Helm release 3개와 AWS 리소스 137개를 삭제했습니다. 당시 두 state의 관리 리소스가 0개임을 확인했고 AWS API에서도 EKS·Network Firewall·VPC·ECR의 부재를 확인했습니다. 당시 KMS 키는 2026-12-16 삭제 예정으로 예약했습니다. 이는 촬영 후 확인 기록이며 현재 AWS 상태를 실시간 조회한 결과는 아닙니다.
