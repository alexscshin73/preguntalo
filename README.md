# preguntalo

`preguntalo`는 복잡한 서비스 매뉴얼을 RAG에 연결해, 사용자가 자연어로 질문하면 답변 초안과 근거 페이지를 함께 보여주는 웹 서비스입니다.

예시:

> "로그인이 안돼. 어떻게 해야 하나?"

응답 목표:

> 로그인을 하기 전에 회원가입이 필요합니다. Citygolf 전용 서비스이므로 관리자에게 사용자 등록을 요청하세요. 관련 페이지: 매뉴얼 2page

## 현재 구현 상태

- `apps/web`: 검색 화면, 다중 매뉴얼 관리 화면, 답변형 결과 UI, 원문 뷰어 placeholder
- `apps/api`: 매뉴얼 등록, 버전 업로드, 동기식 파싱/청킹/임베딩, 검색/섹션 상세 API
- `workers/*`: 향후 비동기 파이프라인용 placeholder
- `docs/`: 아키텍처와 데이터 모델 설계 문서
- `docker-compose.yml`: Postgres, Redis, MinIO 로컬 인프라

## 지금 가능한 것

- 운영자가 여러 매뉴얼을 등록하고 각 매뉴얼에 버전별 파일을 업로드할 수 있습니다.
- 업로드된 문서는 섹션과 청크로 분해되어 검색 가능한 상태로 저장됩니다.
- 사용자는 질문을 보내고 관련 섹션, 답변 초안, 관련 페이지 링크를 확인할 수 있습니다.
- 업로드 형식으로 PDF, DOCX, TXT, MD를 지원합니다.

## 아직 남아 있는 것

- 실제 LLM 기반 답변 합성 고도화
- BM25 + vector 기반 하이브리드 검색 정교화
- PDF.js 기반 원문 뷰어 완성
- 이미지 추출/썸네일/관련 이미지 연결
- 비동기 ingestion workflow 연결

## 실행 방법

1. `.env.example`을 `.env`로 복사합니다.
2. 인프라를 실행합니다.

```bash
docker compose up -d postgres redis minio createbucket
```

3. 개발 환경 점검을 실행합니다.

```bash
npm run doctor
```

`preguntalo`는 Bunny와 충돌하지 않도록 API 포트 `8010`을 기본값으로 사용합니다. `8000`은 Bunny 전용으로 비워둡니다.

4. 가장 간단한 개발 실행은 루트에서 웹과 API를 같이 띄우는 것입니다.

```bash
npm run dev
```

`npm run dev`와 `npm run web:dev`는 동일하게 동작합니다. `apps/api/.venv`를 사용해 API를 먼저 띄우고, 준비되면 `apps/web` 개발 서버를 실행합니다. 기본값은 안정성을 위해 API `reload`를 끈 상태이며, 필요하면 `API_RELOAD=1 npm run api:dev`로 API만 리로드 모드로 실행할 수 있습니다. 웹 기본 포트는 `3000`이지만 이미 사용 중이면 `3001`, `3002`처럼 다음 빈 포트로 자동 우회합니다.

5. API나 웹을 따로 실행하고 싶다면 아래 명령을 사용할 수 있습니다.

```bash
npm run api:dev
```

```bash
npm run web:only
```

## 핵심 경로

- 검색 UI: `http://localhost:3000`
- 매뉴얼 관리 UI: `http://localhost:3000/manuals`
- 관리자 별칭 UI: `http://localhost:3000/admin`
- API health: `http://localhost:8010/api/v1/health`

아키텍처 상세는 [docs/solution-architecture.md](/Users/sclshin/Projects/preguntalo/docs/solution-architecture.md)에서 볼 수 있습니다.

## 외부 배포

`preguntalo.carroamix.com` 같은 외부 도메인으로 공개하려면 배포용 compose와 Caddy 구성을 사용하면 됩니다.

- 배포 가이드: [docs/production-deployment.md](/Users/sclshin/Projects/preguntalo/docs/production-deployment.md)
- 배포 compose: [docker-compose.prod.yml](/Users/sclshin/Projects/preguntalo/docker-compose.prod.yml)
- 배포 env 예시: [.env.production.example](/Users/sclshin/Projects/preguntalo/.env.production.example)

맥에서 `bunny.carroamix.com`과 같은 방식으로 바로 외부 공개하려면 Cloudflare Tunnel 기준 문서를 사용하세요.

- Bunny 벤치마크 방식 가이드: [docs/PREGUNTALO_CARROAMIX_SETUP.md](/Users/sclshin/Projects/preguntalo/docs/PREGUNTALO_CARROAMIX_SETUP.md)
- 공개 시작: `npm run public:start`
- 공개 정지: `npm run public:stop`
- 공개 상태: `npm run public:status`
- 로그인 시 자동 실행 설치: `npm run public:autostart:install`
- 자동 실행 상태: `npm run public:autostart:status`
