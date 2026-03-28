# Infra 프로젝트

## 포인터
- 핸드오프: .claude/handoff.md
- 전역 규칙: ~/.claude/CLAUDE.md (인프라 접속 경로 SSOT 포함)

## 이 프로젝트의 목적
GCP 인프라 관리 (photomon-1, photomon-648d0)

## 현재 활성 GCP 계정
Claude Code 작업: claude-code@photomon-1.iam.gserviceaccount.com (읽기 전용)
운영 작업: siniabi@gmail.com (상윤님 직접)

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
