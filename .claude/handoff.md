# 인프라 핸드오프 (2026-03-31)

## 레포
- infra: /Users/user/COMPANY/Dev/Infra

## 마지막 완료 (2026-03-30~31)

### VM 다운그레이드
- photomon-tplv: 4vCPU → 2vCPU/8GB 완료 ✅
- photomon-tpls2b: 롤백 후 현재 4vCPU/8GB → 오늘 밤 2vCPU로 재시도 필요

### GCS 최적화
- photo-service-file 버킷 기본값: COLDLINE → STANDARD 변경 ✅
- 수명주기: 90일 → 30일 변경 ✅ (STANDARD → 30일 → COLDLINE)
- 예상 절감: Write 비용 $309 → ~$15/월

### bizprint1 모니터링
- 매일 03:10 cron 자동 재시작 → systemd Restart=on-failure로 7초 내 자동 복구 확인
- 알림 발송: 이메일 ✅ / SMS ❌ (300초 조건 미충족 — 정상)

### 확인된 사항
- IIS VM(tplv/tpls2b)은 IP 직접 접근 시 404 정상 → 도메인으로만 확인
  - tplv: https://tplv.photomon.com
  - tpls2b: https://tpls.photomon.com

## 지금 하던 것 (중단 상태)
- tpls2b 2vCPU 다운그레이드 미완료 → 오늘 밤 야간 작업

## 다음 할 것
1. tpls2b 2vCPU 다운그레이드 (오늘 밤)
2. bizprint1 + prepress-1 Ops Agent 설치
3. Windows VM (tplv/tpls2b/sqlserver) Ops Agent 설치 (RDP)
4. cron 재시작 스크립트 개선 (shutdown 실패 시 복구 로직)
5. photomon-tplv SSH 접근 방법 확인
6. MSSQL 백업 경로 변경 (photo-service-file → photomon-db-backup)
7. fail2ban SSH 방어 설정
8. Ops Agent 설치 후 JVM Heap 모니터링 추가

## 주의사항
- bizprint1 (35.216.17.137) = 운영서버 → 직접 SSH 금지 (상윤님 직접 실행)
- Claude Code 현재 계정: claude-code@photomon-1.iam.gserviceaccount.com (읽기 전용)
- 운영 작업 필요 시: gcloud config set account siniabi@gmail.com 으로 전환
- IIS VM 서비스 확인은 반드시 도메인으로 (IP 직접 접근 시 404 정상)
- tpls2b 다운그레이드: 오늘 밤 야간 작업 예정
- 다음 DB 백업 경로: gs://photomon-db-backup/
- 성수기(12월) 전 tplv/tpls2b 4vCPU로 원복 필요

## GCP 인프라 현황
### photomon-1 VM (5대)
| VM | 스펙 | 도메인 | 역할 |
|---|---|---|---|
| bizprint1 | e2-standard-4 | biz.photomon.com | bizprint 운영서버 |
| photomon-sqlserver-vm | n2-standard-8 | — (RDP 전용) | MSSQL DB |
| photomon-tplv | custom-2-8192 | tplv.photomon.com | 포토몬 템플릿 |
| photomon-tpls2b | custom-4-8192 | tpls.photomon.com | 포토몬 템플릿 (야간 2vCPU 예정) |
| prepress-1 | e2-medium | — | 프리프레스 (Docker) |

### GCS 현황
| 버킷 | 클래스 | 수명주기 |
|---|---|---|
| photo-service-file | STANDARD (변경됨) | 30일 후 COLDLINE |
| photomon-db-backup | STANDARD | 90일→NEARLINE→365일→COLDLINE |
| bizprint_cms | STANDARD | — |
