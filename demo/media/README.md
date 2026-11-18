# 발표용 영상 — v20

[60초 MP4](AWS_Community_Day_2026_demo_v18.mp4)와 [SRT 자막](AWS_Community_Day_2026_demo_v18.srt)을 레포에 보관합니다. 파일명의 `v18`은 영상 편집 버전이며, v20 장표의 20장에서도 같은 파일을 사용합니다. 발표 멘트는 [narration-ko.txt](../narration-ko.txt)에 있습니다.

## 재생

- 로컬 PowerPoint: 위 MP4를 파일에서 삽입해 PPTX에 포함합니다. 영상은 무음이며 화면에 자막이 들어 있습니다. SRT는 별도 자막을 지원하는 플레이어용입니다.
- Google Slides: [발표용 Google Slides](https://docs.google.com/presentation/d/1D0ushQ9PlXbvWmQBPe7aMOpbENXl1e8kDcaZwg48RIE/edit?slide=id.p20#slide=id.p20)의 20장에 [Drive MP4](https://drive.google.com/file/d/1HO-FrifvMbZOgdwr3sjAmXa7BohdIWsL/view)가 삽입되어 있습니다. 2026-11-17 슬라이드쇼에서 재생과 종료를 확인한 사본입니다.
- PPTX를 Drive에서 열거나 Google Slides로 변환하면 내장 동영상이 누락될 수 있습니다. 새 사본을 만들 때는 Google Slides 형식으로 변환한 뒤 `삽입 → 동영상 → Google Drive`에서 MP4를 다시 선택합니다. 발표 계정의 영상 접근 권한을 확인하고, 연결된 Drive MP4를 삭제하지 않습니다.

영상 재생에는 AWS 배포가 필요하지 않습니다. Google Slides의 동영상은 Drive 파일을 참조하므로, 로컬 PPTX에 MP4를 포함하는 방식과 다릅니다.

## 실행 기록과 편집 범위

2026-11-16 실제 AWS 촬영 기록을 사용합니다. 할당 Pod의 `spec.nodeName`으로 Node를 조회해 `eks.amazonaws.com/compute-type=fargate`를 확인하고, Pod의 `fargate-scheduler`도 확인한 실행입니다. 데모는 2 AZ이며 운영 설계의 3 AZ 구성과 구분합니다.

v17의 2분 원본 구성에서 발표자 대기를 줄여 v18의 60초 편집본을 만들었습니다. 실제 터미널 출력과 입력 시각을 발표용 화면에 재배치했으며, 선택한 구간 안의 이벤트 순서와 간격을 유지했습니다. 영상 화면의 `총 100.9초`는 편집 전 실행 시간이며, 60초는 성능 측정값이 아닙니다.

편집본 구간 → 원본 기록 구간(초):

- 0–18 → 0–18: 환경 할당·Fargate 확인
- 18–28 → 38.199–48.199: 도구 호출
- 28–48 → 57.124–77.124: 접근 범위
- 48–60 → 92.180–104.180: 반환·삭제 확인

도구는 예시 텍스트의 공백을 정리합니다. PDF 파싱, AI 요약, EFS 초안 저장, S3 보고서 저장은 구현하지 않았습니다. 비허용 HTTPS의 연결 실패만으로 방화벽 차단을 단정하지 않으며, v20의 23장에서 같은 실행의 Pod IP·시각·SNI와 방화벽 로그를 대조합니다.

재촬영은 [데모 가이드](../README.md)와 [Terraform 구성](../../infra/terraform/demo-workloads/README.md)을 따릅니다. `demo/record.py`는 `capture.json`과 `terminal.txt`를 수집하며 MP4를 생성하지 않습니다. 이 폴더에는 최종 배포용 영상과 자막만 보관합니다. 원시 실행 기록은 `demo/.runs/`에 저장하고 Git에서 제외합니다.

## 파일 검증

- MP4: 60.000초, 1920×1080, H.264, yuv420p, 30fps, 오디오 트랙 없음, 1,109,588바이트
- SRT: 9개 구간, 00:00:00.000–00:01:00.000
- SHA-256 MP4: `ac260715b51b9dbc248893cb99e06833670c3cdae08d6ee4c3ef262a3fa4dc47`
- SHA-256 SRT: `eb0a878fb5a8cab633b8e12480c864bcf6fc458d2a64509da7030ded9a9d3b0c`

두 파일은 v20 장표에서 사용한 로컬 최종본과 바이트 단위로 일치합니다. 재촬영하거나 다시 편집하면 자막·발표 멘트·장표의 실행 증거와 이 검증 정보를 함께 갱신합니다.
