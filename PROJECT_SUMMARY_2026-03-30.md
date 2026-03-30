# PreguntaLo 개발 현황 정리

기준일: 2026-03-30

이 문서는 2026-03-27 정리본 이후의 개발 및 공개 배포 상태를 반영한 최신 요약입니다.

## 1. 프로젝트 개요

`PreguntaLo`는 Citygolf 매뉴얼을 등록하고 정보화한 뒤, 사용자의 자연어 질문에 대해 관련 문서를 찾아 답변하는 로컬 기반 QnA 서비스입니다.

현재 기본 흐름은 아래와 같습니다.

1. 운영자가 매뉴얼 파일을 업로드합니다.
2. 서버가 파일과 버전 정보를 저장합니다.
3. 정보화 작업이 문서를 페이지/섹션/청크로 분리하고 검색용 데이터로 저장합니다.
4. 사용자가 질문하면 관련 chunk를 검색합니다.
5. 검색 결과를 바탕으로 답변 문장을 구성합니다.
6. 답변에 붙은 근거 링크를 누르면 원본 매뉴얼 PDF가 해당 페이지로 바로 열립니다.

## 2. 현재 확인된 서비스 상태

2026-03-30 기준 확인 결과:

- 공개 URL: `https://preguntalo.carroamix.com`
- 공개 메인 응답: `HTTP/2 200`
- 공개 API Health: `https://preguntalo.carroamix.com/api/proxy/api/v1/health` -> `{"status":"ok"}`
- 공개 터널 상태: `running`
- 로컬 API 상태: `ok`
- 로컬 웹 상태: `ok`

즉, 현재 PreguntaLo는 외부에서 접속 가능한 상태로 확인되었습니다.

## 3. 이번까지 구현된 핵심 내용

### 3.1 개발 실행 방식 정리

- `npm run web:dev`
  - 웹만 실행
  - 포트 `3000` 고정
- `npm run api:dev`
  - API만 실행
  - 포트 `8010`
- `npm run dev:full`
  - 웹 + API 통합 실행
- `npm run ingest:all`
  - 큐에 있는 문서를 일괄 정보화

관련 파일:

- [package.json](/Users/sclshin/Projects/preguntalo/package.json)
- [scripts/web_dev.sh](/Users/sclshin/Projects/preguntalo/scripts/web_dev.sh)
- [scripts/api_dev.sh](/Users/sclshin/Projects/preguntalo/scripts/api_dev.sh)
- [scripts/dev_up.sh](/Users/sclshin/Projects/preguntalo/scripts/dev_up.sh)
- [scripts/ingest_all.sh](/Users/sclshin/Projects/preguntalo/scripts/ingest_all.sh)

### 3.2 매뉴얼 관리 화면 개편

- 상단 구성:
  - `매뉴얼 관리`
  - `미리보기`
- 하단의 별도 `매뉴얼 정보화` 패널 제거
- 표 컬럼:
  - 파일명
  - 수정일자
  - 크기
  - 정보화
- `형식` 컬럼 제거
- 폴더/파일 우클릭 메뉴를 한국어/스페인어와 연동
- 파일 우클릭 메뉴에 `파일 변경` 추가
- 파일별 `정보화` 버튼 추가
  - 준비: 파란색 `실행`
  - 성공: 초록색 `완료`
  - 실패: 붉은색 `실행`

관련 파일:

- [manuals-shell.tsx](/Users/sclshin/Projects/preguntalo/apps/web/components/manuals/manuals-shell.tsx)
- [manuals-shell.module.css](/Users/sclshin/Projects/preguntalo/apps/web/components/manuals/manuals-shell.module.css)
- [ui-text.ts](/Users/sclshin/Projects/preguntalo/apps/web/components/i18n/ui-text.ts)

### 3.3 매뉴얼 미리보기 개선

- 원본 PDF 중심 미리보기
- 페이지 선택 목록 상단 가로형 배치
- 선택 페이지가 최대한 크게 보이도록 조정
- 상단 패널 높이와 비율 반복 조정

### 3.4 헤더 UI 변경

- 언어변경 버튼을 `language.png` 아이콘으로 교체
- 매뉴얼 등록 버튼을 `manual.png` 아이콘으로 교체
- 별도 보더 박스 제거
- 마우스 오버 툴팁을 언어 상태별로 분기

관련 파일:

- [site-header.tsx](/Users/sclshin/Projects/preguntalo/apps/web/components/site-header.tsx)
- [site-header.module.css](/Users/sclshin/Projects/preguntalo/apps/web/components/site-header.module.css)
- [language.png](/Users/sclshin/Projects/preguntalo/language.png)
- [manual.png](/Users/sclshin/Projects/preguntalo/manual.png)

### 3.5 문서 정보화 / 인덱싱

- 문서 업로드 시 정보화 작업 큐 등록
- 파일별 `실행` 버튼으로 개별 문서 재정보화 가능
- 정보화 시 수행 작업:
  - 페이지 분리
  - 섹션 분리
  - 청크 분리
  - 임베딩 벡터 생성
  - 검색용 저장
- 등록된 7개 문서를 정보화하여 `indexed` 상태로 반영

관련 파일:

- [manuals.py](/Users/sclshin/Projects/preguntalo/apps/api/app/services/manuals.py)
- [ingestion.py](/Users/sclshin/Projects/preguntalo/apps/api/app/services/ingestion.py)
- [ingestion.py](/Users/sclshin/Projects/preguntalo/apps/api/app/workers/ingestion.py)

### 3.6 검색 / 답변 API 개선

- `/api/v1/answer` 구현
- 질문 기반 관련 chunk 검색 및 답변 생성
- 검색 품질 개선:
  - 빈 검색 결과 캐시 방지
  - 정보화/삭제 시 캐시 무효화
  - SQLite fallback 검색 강화
  - 제목/구문/질문 의도 기반 점수 보정
  - README 등 일반 문서 과도한 상위 노출 억제
- 답변 생성 개선:
  - 절차형 질문 인식 강화
  - `마감하기는 어떻게 하나요?` 같은 질문에 직접적인 답변 문장 생성
  - 답변 본문에서 페이지 안내 중심 문장 제거

관련 파일:

- [search.py](/Users/sclshin/Projects/preguntalo/apps/api/app/services/search.py)
- [answer.py](/Users/sclshin/Projects/preguntalo/apps/api/app/services/answer.py)
- [routes.py](/Users/sclshin/Projects/preguntalo/apps/api/app/api/routes.py)
- [search.py](/Users/sclshin/Projects/preguntalo/apps/api/app/schemas/search.py)

### 3.7 Search 화면 개편

- 상단 인기 태그 제거
- `Question` -> `질문하기`
- `Answer` -> `답변받기`
- `Tag + 입력 + 자동생성` 영역 제거
- 질문 입력창:
  - `Enter`로 바로 질문 실행
  - `Shift + Enter`로 줄바꿈
- 답변 표시:
  - 문장 단위 줄바꿈 개선
  - 별도 `근거 문서` 카드 제거
  - `Reference` 영역 전체 제거
- 근거 표시:
  - 답변 문장 뒤에 파란 타원형 근거 pill 표시
  - 최대 15자 표시, 길면 `...`
  - 마우스 오버 시 전체 제목 툴팁 표시
  - 동일 문서 중복 근거는 하나만 남기고 핵심 문장에만 표시
- 근거 pill 클릭 시:
  - 중간 뷰어가 아니라 원본 매뉴얼 PDF의 해당 페이지를 바로 새 창으로 오픈

관련 파일:

- [search-shell.tsx](/Users/sclshin/Projects/preguntalo/apps/web/components/home/search-shell.tsx)
- [search-shell.module.css](/Users/sclshin/Projects/preguntalo/apps/web/components/home/search-shell.module.css)

### 3.8 원문 뷰어 개선

- 기존의 추출 텍스트 중심 내부형 뷰어 제거
- 원본 문서 중심 뷰어로 전환
- 실제 PDF 원본과 이미지가 보이도록 원문 iframe 기반으로 변경

관련 파일:

- [viewer-shell.tsx](/Users/sclshin/Projects/preguntalo/apps/web/components/viewer-shell.tsx)
- [viewer-shell.module.css](/Users/sclshin/Projects/preguntalo/apps/web/components/viewer-shell.module.css)

### 3.9 외부 공개 배포 구성

- `preguntalo.carroamix.com` 공개 구성 완료
- `bunny.carroamix.com`과 같은 운영 방식을 벤치마킹
- Cloudflare Tunnel 기반 공개 스크립트 및 문서 추가

추가된 항목:

- 토큰 저장 스크립트
- tunnel 실행 스크립트
- 공개 시작/정지/상태 확인 스크립트
- Cloudflare 설정 가이드
- production compose / Caddy 구성 문서

관련 파일:

- [PREGUNTALO_CARROAMIX_SETUP.md](/Users/sclshin/Projects/preguntalo/docs/PREGUNTALO_CARROAMIX_SETUP.md)
- [production-deployment.md](/Users/sclshin/Projects/preguntalo/docs/production-deployment.md)
- [preguntalo_public_start.sh](/Users/sclshin/Projects/preguntalo/scripts/preguntalo_public_start.sh)
- [preguntalo_public_stop.sh](/Users/sclshin/Projects/preguntalo/scripts/preguntalo_public_stop.sh)
- [preguntalo_public_status.sh](/Users/sclshin/Projects/preguntalo/scripts/preguntalo_public_status.sh)
- [run_cloudflare_public_tunnel.sh](/Users/sclshin/Projects/preguntalo/scripts/run_cloudflare_public_tunnel.sh)
- [store_cloudflare_tunnel_token.sh](/Users/sclshin/Projects/preguntalo/scripts/store_cloudflare_tunnel_token.sh)
- [docker-compose.prod.yml](/Users/sclshin/Projects/preguntalo/docker-compose.prod.yml)
- [Caddyfile](/Users/sclshin/Projects/preguntalo/infra/caddy/Caddyfile)

## 4. 현재 실행 환경

현재 `.env` 기준 핵심 설정:

- API: `127.0.0.1:8010`
- API Prefix: `/api/v1`
- Database: `sqlite:///./preguntalo-dev.db`
- Storage backend: `local`
- Local storage root: `./data/storage`
- OpenAI key: 비어 있음

관련 파일:

- [apps/api/.env](/Users/sclshin/Projects/preguntalo/apps/api/.env)

## 5. 현재 품질 상태

현재는 질문-검색-답변 흐름이 실제로 동작합니다.

강점:

- 관련 문서를 찾는 기능은 초기보다 크게 개선됨
- 절차형 질문에 대해 직접 답하는 방향으로 개선됨
- 근거 문서를 클릭하면 원본 문서로 바로 이동 가능
- 공개 도메인에서도 실제 접속 가능 상태 확인됨

아직 남아 있는 한계:

- DB가 `SQLite` 기반이라 `pgvector` 기반 벡터 검색이 아님
- 로컬 임베딩 모델이 완전히 붙은 상태가 아니라 fallback 품질 한계가 있음
- 답변 생성이 규칙 기반 fallback 성격이 강해서 문장이 아직 다소 부자연스러울 수 있음
- PDF 추출 텍스트 품질에 따라 답변 자연스러움이 흔들릴 수 있음

## 6. 권장 다음 단계

우선순위는 아래가 좋습니다.

1. 로컬 임베딩 모델 실연결
   - 예: `bge-m3`, `multilingual-e5`
2. `Postgres + pgvector` 전환
   - 실제 벡터 유사도 검색 적용
3. 전체 문서 재정보화
   - 새 임베딩 기준 재인덱싱
4. reranker 추가
   - 상위 후보를 질문 의도 기준으로 재정렬
5. 로컬 LLM 기반 자연어 답변 생성 강화
   - 규칙형 fallback 대신 실제 생성형 응답 강화
6. PDF 텍스트 정제
   - OCR/제어문자/혼합언어 문장 다듬기

## 7. 최종 요약

현재 `PreguntaLo`는 아래 수준까지 정리된 상태입니다.

- 매뉴얼 등록 가능
- 파일별 정보화 실행 가능
- 문서 검색 및 질문 응답 가능
- 답변 내 근거를 원본 문서 페이지와 연결 가능
- 외부 공개 도메인 `preguntalo.carroamix.com`으로 접속 가능
- 관리 화면과 검색 화면 모두 실사용 기준으로 정리 완료

즉, 현재는 “외부 접속 가능한 로컬 문서 기반 QnA 프로토타입” 단계까지 완료되었고, 다음 핵심 과제는 “답변 품질 고도화”입니다.
