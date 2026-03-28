# 인프라 핸드오프 (2026-03-27)

## 레포
- bizprint-serv: /Users/user/COMPANY/Dev/bizprint/bizprint-serv (feature/sprint-1)
- bizprint-web: /Users/user/COMPANY/Dev/bizprint/bizprint-web (develop)
- prepress: /Users/user/COMPANY/Dev/prepress (main)
- infra: /Users/user/COMPANY/Dev/Infra

## 마지막 완료 (2026-03-26~27)

### 장애 대응
- 원인: Claude Code가 WAR 배포 후 pkill -9로 Tomcat 종료 → 3시간 22분 다운
- 재발 방지: settings.json deny 5개 추가, CLAUDE.md 운영서버 금지 규칙 추가
- systemd Restart=on-failure 30초 설정 완료
- GCP Uptime Check + Alert Policy + 이메일 3 + SMS 3 설정 완료

### bizprint1 서버 점검
- catalina.out 6.7GB truncate 완료
- logrotate 설정 (일 500MB, 7일 보관)
- 디스크 73% → 68% (11GB 확보)
- 시스템 저널 3.9GB 삭제
- Swap 4GB 설정 완료

### GCS 최적화
- photo-service-file 수명주기 정책 추가
  - Rule 1: STANDARD/NEARLINE → 90일 후 COLDLINE
  - Rule 2: COLDLINE → 365일 후 ARCHIVE (월 ~$364 절감 예상)
- photomon-db-backup 버킷 생성 (STANDARD, 수명주기 포함)
- 2021년 DB 백업(54.7GB) 삭제

### 보안 강화
- Claude Code 전용 서비스 계정 생성
  - claude-code@photomon-1.iam.gserviceaccount.com
  - 권한: storage.objectViewer, compute.viewer, monitoring.viewer, logging.viewer
  - 현재 활성 계정으로 설정 완료
- ~/.claude/CLAUDE.md 전역 규칙 추가
  - 인프라 접속 경로 SSOT
  - DB/GCS/방화벽 금지 규칙
  - 막혔을 때 원칙

## 지금 하던 것 (중단 상태)
- photomon-tplv SSH 접근 불가 (원인 미확인)
- GCS photo-service-file 파일 접근 패턴 분석 미완료
  - 가설: 포토북 제작 중 집중 접근 → 완료 후 거의 없음
  - clouduploadfile/useruploadfile 15개월 공백 원인 미확인
  - 버킷 기본 클래스 STANDARD 전환 여부 미결정 (코드 확인 필요)

## 다음 할 것
1. photomon-tplv SSH 접근 방법 확인
2. 포토몬 파일 처리 로직 확인 (제작 완료 후 파일 삭제 여부)
3. photo-service-file 버킷 기본 클래스 STANDARD 전환 검토
4. MSSQL 백업 경로 변경 (photo-service-file → photomon-db-backup)
5. photomon-sqlserver-vm 백업 스케줄 확인
6. fail2ban SSH 방어 설정
7. MSSQL VM 디스크/백업 현황 확인

## 주의사항
- bizprint1 (35.216.17.137) = 운영서버 → 직접 SSH 금지 (상윤님 직접 실행)
- Claude Code 현재 계정: claude-code@photomon-1.iam.gserviceaccount.com (읽기 전용)
- 운영 작업 필요 시: gcloud config set account siniabi@gmail.com 으로 전환 후 상윤님 직접 실행
- DB 접근 막히면 우회 탐색 금지 → 즉시 보고
- GCS .bak 파일 읽기/다운로드 절대 금지
- 다음 DB 백업 경로: gs://photomon-db-backup/

## GCP 인프라 현황
### photomon-1 VM (5대)
| VM | 스펙 | 역할 |
|---|---|---|
| bizprint1 | e2-standard-4 | bizprint 운영서버 |
| photomon-sqlserver-vm | n2-standard-8 | MSSQL DB |
| photomon-tpls2b | e2-custom-4-8192 | 포토몬 템플릿 |
| photomon-tplv | e2-custom-4-8192 | 포토몬 템플릿 |
| prepress-1 | e2-medium | 프리프레스 |

### GCS 버킷
| 버킷 | 클래스 | 용량 | 용도 |
|---|---|---|---|
| bizprint_cms | STANDARD | 2.2TB | bizprint 파일 |
| photo-service-file | COLDLINE | 150.9TB | 포토몬 사진 아카이브 |
| photo-web-files | ARCHIVE | 261GB | 포토몬 웹 파일 |
| photomon-db-backup | STANDARD | 신규 | DB 백업 전용 |

### 모니터링
- Uptime Check: biz.photomon.com 5분 간격
- Alert Policy: 다운 감지 시 이메일 3 + SMS 3 발송
