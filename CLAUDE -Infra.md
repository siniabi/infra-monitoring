# Infra 프로젝트

## 포인터
- 핸드오프: .claude/handoff.md
- 전역 규칙: ~/.claude/CLAUDE.md (인프라 접속 경로 SSOT 포함)

## 이 프로젝트의 목적
GCP 인프라 관리 (photomon-1, photomon-648d0)

## 현재 활성 GCP 계정
Claude Code 작업: claude-code@photomon-1.iam.gserviceaccount.com (읽기 전용)
운영 작업: siniabi@gmail.com (상윤님 직접)

---

## GCS 버킷 현황 및 접속 방법

### 인증
- Claude Code 계정: claude-code@photomon-1.iam.gserviceaccount.com (읽기 전용)
- 키 파일: /Users/user/.config/gcloud/claude-code-sa-key.json
- 전환 명령: gcloud config set account claude-code@photomon-1.iam.gserviceaccount.com

### 버킷 목록 (photomon-1)

| 버킷 | 클래스 | 용량 | 사용 서비스 | 접근 규칙 |
|---|---|---|---|---|
| bizprint_cms | STANDARD | 2.2TB | bizprint 운영서버 (파일 서빙) | ls만 허용 |
| photo-service-file | COLDLINE | 150.9TB | 포토몬 사진 인쇄 서비스 전체 | ls만 허용, 파일 읽기 금지 |
| photo-web-files | ARCHIVE | 261GB | 포토몬 웹 파일 | ls만 허용 |
| photomon-db-backup | STANDARD | 신규 | FOTOMON DB 백업 전용 | ls만 허용, .bak 읽기 절대 금지 |
| photomon-images | STANDARD | 0GB | 미사용 | — |
| photomon-1.appspot.com | STANDARD | 0GB | App Engine | — |

### photo-service-file 상세 구조
```
gs://photo-service-file/
├── tplv/                    ← 포토몬 tplv 서버 파일
│   ├── clouduploadfile/YYMMDD/사용자ID/   ← 제작 중 업로드 사진
│   ├── useruploadfile/YYMMDD/사용자ID/    ← 사용자 업로드
│   ├── orderfile/YYMMDD/                  ← 주문 처리 파일 (매일 생성)
│   ├── orderfile_tmp/                     ← 임시 주문 파일
│   ├── webuploadfile/                     ← 웹 업로드
│   ├── simplebasket/                      ← 간편 장바구니
│   ├── sscard/                            ← SS카드
│   └── gallery/                           ← 갤러리
├── tplw/ ~ tplz/            ← 비어있음 (미사용)
├── photomon-db/             ← FOTOMON DB 백업 (.bak) — 읽기 금지
├── file4/orderfile/         ← 레거시 (2021년)
├── dev1_photomon/           ← 개발 잔존 파일
└── dev2_biz/                ← 개발 잔존 파일
```

### 수명주기 정책 현황
| 버킷 | 정책 |
|---|---|
| photo-service-file | STANDARD/NEARLINE → 90일 → COLDLINE → 365일 → ARCHIVE |
| photomon-db-backup | STANDARD → 90일 → NEARLINE → 365일 → COLDLINE |

### 접속 명령어 예시
```bash
# 버킷 목록
gcloud storage buckets list --project=photomon-1

# 폴더 구조 조회 (허용)
gcloud storage ls gs://photo-service-file/tplv/ --project=photomon-1

# 용량 확인 (허용, 단 대용량 버킷은 시간 소요)
gsutil du -s gs://bizprint_cms

# 파일 읽기/다운로드 (금지)
# gsutil cp gs://photo-service-file/... → 절대 금지
# gsutil cat gs://photo-service-file/... → 절대 금지
```

### 비용 현황 (2026-03 기준)
| 항목 | 월 비용 |
|---|---|
| photo-service-file 스토리지 (150TB COLDLINE) | ~$604 |
| photo-service-file Write 요청 | ~$309 |
| bizprint_cms (2.2TB STANDARD) | ~$46 |
| 합계 | ~$959+ |

### 주의사항
- photo-service-file에 직접 Write 시 COLDLINE Class A 요청 비용 발생 (STANDARD 대비 20배)
- DB 백업은 반드시 gs://photomon-db-backup/ 에 업로드
- .bak 파일 다운로드 시 COLDLINE retrieval 비용 ($0.01/GB) 발생

---

## DB 접속 경로 SSOT

### 접속 방법 (bizprint1 경유)
모든 DB는 bizprint1 서버를 경유하여 접속한다.
sqlcmd 경로: /opt/mssql-tools18/bin/sqlcmd
서버: 34.64.217.66:1433

```bash
# 접속 패턴 (비밀번호 파일 방식 — zsh ! 문자 이슈 우회)
gcloud compute ssh bizprint1 --zone=asia-northeast3-b --project=photomon-1 \
  --command="printf 'qlwmvmflsxm\x210(iL1#\$' > /tmp/pw && \
  /opt/mssql-tools18/bin/sqlcmd -S 34.64.217.66 -U bizprint \
  -P \"\$(cat /tmp/pw)\" -d [DB명] -Q \"[쿼리]\" -s',' -W -C 2>&1 && rm /tmp/pw"
```

### DB 목록
| DB | 용도 | 접속 계정 | 비고 |
|---|---|---|---|
| bizprint | bizprint 운영 | bizprint / qlwmvmflsxm!0(iL1#$ | 운영 DB |
| bizprint_new | bizprint 개발 | bizprint_new / qlwmvmflsxm!2 | 개발 DB |
| FOTOMON | 포토몬 운영 | bizprint 계정으로 접속 가능 | SELECT만 허용 |
| bizprint_prepress | prepress 전용 | prepress / PrepressDb!2026# | prepress-1 경유 권장 |
| ARTMON / DOCUMON / DPLUSBI | 기타 서비스 | bizprint 계정 | 조회만 |

### bizprint1 SSH 접근 규칙
- 허용: 읽기 전용 작업 (로그 조회, DB SELECT, 파일 목록 조회)
- 금지: 파일 수정/삭제, 서비스 재시작, WAR 배포, pkill, systemd 변경, shutdown/startup

---

## VM 현황 (photomon-1)

| VM | 외부 IP | 내부 IP | 스펙 | 역할 |
|---|---|---|---|---|
| bizprint1 | 35.216.17.137 | 10.178.0.25 | e2-standard-4 (4vCPU/16GB) | bizprint 운영서버 |
| photomon-sqlserver-vm | 34.64.217.66 | 10.178.0.15 | n2-standard-8 (8vCPU/32GB) | MSSQL DB (RDP 전용) |
| photomon-tpls2b | 35.216.47.203 | — | e2-custom-4-8192 | 포토몬 템플릿 |
| photomon-tplv | 35.216.46.157 | — | e2-custom-4-8192 | 포토몬 템플릿 |
| prepress-1 | 34.64.151.213 | 10.178.0.28 | e2-medium (2vCPU/4GB) | 프리프레스 (Docker) |

---

## 모니터링 현황

| 항목 | 내용 |
|---|---|
| Uptime Check | biz.photomon.com 5분 간격 HTTP 체크 |
| Alert Policy | bizprint 운영서버 다운 알림 |
| 이메일 알림 | hsy@maybeone.co.kr, mdw@maybeone.co.kr, ljb@maybeone.co.kr |
| SMS 알림 | +821037491995, +821042740669, +821053236231 |
| Tomcat 자동복구 | systemd Restart=on-failure, RestartSec=30s |

---

## 절대 금지 규칙

- 방화벽 규칙 변경으로 DB 접근 시도 금지
- GCS 백업 파일(.bak, .sql, .dump) 읽기/다운로드 금지
- 접근이 막히면 우회 경로 탐색 금지 → 즉시 상윤님께 보고 후 대기
- 운영 DB(bizprint, FOTOMON) 외부 직접 접속 시도 금지
- photomon-sqlserver-vm 방화벽 규칙 수정 금지
- DB 접근 실패 시 GCS 백업 파일로 우회 시도 금지
- bizprint1에서 pkill, kill -9, shutdown.sh, startup.sh 실행 금지
- WAR 배포, systemd 변경은 상윤님 직접 실행

## 막혔을 때 원칙
1. 즉시 중단
2. 상윤님께 상황 보고
3. 대안 제시 후 승인 대기
4. 절대 우회 경로 탐색 금지
