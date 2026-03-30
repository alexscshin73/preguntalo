# Manual RAG Official Solution Architecture

작성일: 2026-03-13

이 문서는 기존 MVP를 대체할 정식 솔루션의 아키텍처, 기술 스택, 데이터 모델, API, 구현 순서를 정의한다.

## 1. 목표

이 솔루션은 대량의 매뉴얼을 업로드하고, 한국어/스페인어/영어 질문에 대해 가장 관련성 높은 내용을 찾고, 사용자가 클릭한 결과를 구조적으로 요약해 주며, 최종적으로 매뉴얼 원본까지 연결하는 것을 목표로 한다.

핵심 요구사항:

- 대량 매뉴얼 업로드 지원
- 한국어, 스페인어, 영어 질의 지원
- RAG 기반 검색 및 근거 제시
- 매뉴얼 관련 이미지의 구조적 저장
- 검색 결과 목록 제공
- 클릭 후 상세 요약과 출처 URL 표시
- 원문 매뉴얼 뷰어 연결

## 2. 제품 구조

권장 구조는 다음과 같다.

```text
Frontend (Next.js)
  -> API Gateway / App Backend (FastAPI)
    -> PostgreSQL + pgvector
    -> Redis
    -> Object Storage (S3 or MinIO)
    -> Workflow Engine (Temporal)
      -> Ingestion Worker
      -> OCR / Parsing Worker
      -> Embedding Worker
      -> Summarization Worker
```

역할은 아래처럼 나눈다.

- Frontend: 업로드 UI, 검색 UI, 상세 요약 UI, 원문 뷰어
- Backend API: 인증, 문서 조회, 검색, 결과 상세, URL 발급
- Ingestion Worker: 업로드 후 텍스트 추출, 청킹, 메타데이터 생성
- Search Layer: 하이브리드 검색과 재정렬
- Storage Layer: 원본 파일, 추출 이미지, 썸네일, 변환본 저장

## 3. 권장 기술 스택

### 3.1 Frontend

- Next.js
- TypeScript
- Tailwind CSS
- TanStack Query
- PDF.js

선정 이유:

- 관리자 화면과 사용자 검색 화면을 하나의 웹앱으로 통합하기 쉽다.
- 서버 컴포넌트와 클라이언트 UI를 적절히 분리할 수 있다.
- PDF.js로 페이지 앵커 기반 원문 뷰어를 쉽게 붙일 수 있다.

### 3.2 Backend

- FastAPI
- Pydantic
- SQLAlchemy
- Alembic

선정 이유:

- API 설계와 문서화가 빠르다.
- 비동기 처리와 Python 기반 문서 파싱 생태계를 함께 활용하기 좋다.

### 3.3 Data / Search

- PostgreSQL 16
- pgvector
- Redis

선정 이유:

- 메타데이터와 벡터 검색을 분리하지 않고 함께 관리할 수 있다.
- 언어, 버전, 문서 타입, 조직, 권한 기반 필터링이 필요할 때 유리하다.
- Redis는 캐시와 백그라운드 작업 보조 용도로 충분하다.

### 3.4 File / Asset Storage

- Amazon S3
- 또는 MinIO

저장 대상:

- 원본 PDF, DOCX, PPTX
- OCR 변환본
- 추출 이미지
- 썸네일
- 미리보기용 PDF/HTML

### 3.5 Workflow / Jobs

- Temporal

선정 이유:

- 긴 문서 처리, 재시도, 부분 실패 복구, 재색인, 배치 파이프라인을 안정적으로 운영할 수 있다.

### 3.6 Parsing / OCR

- Unstructured
- 필요 시 Tesseract 또는 클라우드 OCR 보강

선정 이유:

- PDF, 이미지 기반 문서, OCR, 레이아웃 기반 분해를 통합하기 쉽다.

### 3.7 LLM / Embeddings

- Embeddings: `text-embedding-3-large`
- Query rewriting / answer drafting / detail summary: `gpt-5-mini`
- 고정밀 운영 검수 또는 오프라인 평가: `gpt-4.1` 또는 상위 모델

선정 이유:

- 다국어 검색 품질과 응답 비용의 균형이 좋다.

## 4. 왜 기존 MVP를 버려야 하는가

기존 MVP는 아래 한계가 있다.

- 단일 `docx` 전제
- 언어 판별이 규칙 기반 단순 추정
- Chroma 로컬 저장
- UI와 인덱싱 코드 혼재
- 이미지 자산 처리 부재
- 문서 버전 관리 부재
- 결과 클릭 후 상세 요약 흐름 부재
- 원문 링크 구조 부재

따라서 이번 정식 솔루션은 처음부터 아래 구조를 전제로 설계한다.

- 업로드와 검색 API 분리
- 파이프라인 비동기화
- 문서 버전 관리
- 이미지 메타데이터 관리
- 페이지/섹션 단위 원문 연결

## 5. 문서 처리 파이프라인

### 5.1 업로드 단계

1. 관리자가 파일 업로드
2. 시스템이 `manual`, `manual_version`, `file_asset` 레코드 생성
3. 원본 파일을 S3 또는 MinIO에 저장
4. Temporal 워크플로우 시작

### 5.2 파싱 단계

1. 파일 타입 감지
2. PDF/DOCX/PPTX별 파서 라우팅
3. OCR 필요 여부 판정
4. 페이지, 섹션, 블록, 테이블, 이미지 추출
5. 언어 감지
6. 정규화 및 메타데이터 생성

### 5.3 청킹 단계

청킹 단위는 단순 문단이 아니라 의미 단위 섹션이어야 한다.

권장 계층:

- manual
- manual_version
- source_page
- section
- chunk

청킹 규칙:

- 제목과 본문을 분리
- 리스트와 표는 가급적 하나의 의미 단위로 보존
- chunk는 300~800 토큰 내외에서 시작
- 이전/다음 chunk 연결 정보 유지
- 페이지 번호와 섹션 경로 유지

### 5.4 임베딩 / 인덱싱 단계

저장 내용:

- chunk 본문
- 정규화 본문
- 언어 코드
- 제목 경로
- 페이지 범위
- 원문 파일 링크 정보
- 이미지 참조 정보
- embedding vector

### 5.5 요약 캐시 단계

검색 결과를 사용자가 클릭했을 때마다 즉석 생성만 하면 비용이 커질 수 있다.

따라서 아래 2계층을 둔다.

- 검색 시: 짧은 snippet만 즉시 반환
- 상세 클릭 시: section summary 생성 후 캐시

## 6. 검색 아키텍처

정식 서비스는 벡터 검색만으로 가지 않는다.

권장 검색 순서:

1. Query normalization
2. Query language detection
3. Query expansion 또는 multilingual rewrite
4. BM25 keyword retrieval
5. Vector retrieval
6. Reciprocal Rank Fusion 또는 weighted merge
7. Reranking
8. Top-N 결과 반환

이유:

- 매뉴얼 질의는 UI 용어, 모델명, 숫자, 버튼 문구가 중요하다.
- 이런 케이스는 키워드 검색이 벡터 검색보다 강할 때가 많다.
- 다국어 질의에서는 벡터 검색이 큰 이점을 준다.

## 7. 다국어 처리 원칙

지원 언어는 `ko`, `es`, `en`으로 고정한다.

원칙:

- 원문 언어는 문서 단위와 chunk 단위 모두 저장
- 질문 언어와 문서 언어가 달라도 검색 가능해야 함
- 응답 요약 언어는 사용자 질문 언어를 기본으로 함
- 원문 발췌는 가능한 한 원본 언어 그대로 유지

실무 전략:

- 모든 chunk를 원문 기준으로 인덱싱
- 필요한 경우 질의를 영어 중간 표현으로 확장하지 말고 다국어 임베딩을 그대로 활용
- FAQ성 강한 제품명, 메뉴명, 버튼명은 별도 synonym 사전을 둠

## 8. 이미지 처리 설계

이미지는 단순 첨부파일이 아니라 검색 결과의 중요한 맥락이 될 수 있다.

저장해야 할 항목:

- 원본 이미지 파일 경로
- 추출 위치 페이지 번호
- 소속 섹션 ID
- bounding box
- caption 또는 주변 문맥
- OCR 텍스트
- 썸네일 경로

활용 방식:

- 검색 결과 상세 화면에서 관련 이미지 카드 노출
- 원문 뷰어에서 해당 페이지 하이라이트
- 추후 이미지 기반 질의응답 확장 가능

## 9. 원문 뷰어 설계

원문 접근은 공개 파일 링크보다 내부 뷰어 경유 방식이 좋다.

권장 방식:

- Frontend route: `/viewer/[manualId]/[versionId]?page=12&section=abc`
- Backend가 signed URL 또는 proxy stream 발급
- PDF는 PDF.js로 뷰어 제공
- DOCX/PPTX는 업로드 시 PDF 미리보기본 생성

사용자 경험:

- 검색 결과 클릭
- 요약과 함께 관련 페이지 번호 노출
- "원문 보기" 클릭 시 해당 페이지로 바로 이동

## 10. 추천 폴더 구조

```text
preguntalo/
├── apps/
│   ├── web/                      # Next.js frontend
│   └── api/                      # FastAPI backend
├── packages/
│   ├── ui/                       # shared UI components
│   ├── config/                   # env/config schemas
│   └── types/                    # shared contracts
├── workers/
│   ├── ingestion/
│   ├── parsing/
│   ├── embedding/
│   └── summarization/
├── infra/
│   ├── docker/
│   ├── terraform/
│   └── scripts/
├── docs/
│   ├── solution-architecture.md
│   ├── db-schema.md
│   └── api-contracts.md
├── tests/
│   ├── e2e/
│   ├── integration/
│   └── fixtures/
├── .env.example
├── docker-compose.yml
└── README.md
```

## 11. 데이터베이스 스키마 초안

### 11.1 `organizations`

- `id`
- `name`
- `created_at`

### 11.2 `users`

- `id`
- `organization_id`
- `email`
- `role`
- `created_at`

### 11.3 `manuals`

- `id`
- `organization_id`
- `title`
- `manual_code`
- `category`
- `default_language`
- `status`
- `created_at`
- `updated_at`

### 11.4 `manual_versions`

- `id`
- `manual_id`
- `version_label`
- `source_file_asset_id`
- `preview_file_asset_id`
- `status`
- `indexed_at`
- `created_at`

### 11.5 `file_assets`

- `id`
- `organization_id`
- `storage_provider`
- `bucket`
- `object_key`
- `mime_type`
- `size_bytes`
- `sha256`
- `original_filename`
- `created_at`

### 11.6 `source_pages`

- `id`
- `manual_version_id`
- `page_number`
- `width`
- `height`
- `image_asset_id`
- `ocr_text`

### 11.7 `sections`

- `id`
- `manual_version_id`
- `parent_section_id`
- `page_start`
- `page_end`
- `heading`
- `heading_path`
- `language`
- `sort_order`

### 11.8 `chunks`

- `id`
- `section_id`
- `manual_version_id`
- `page_start`
- `page_end`
- `language`
- `chunk_text`
- `normalized_text`
- `token_count`
- `prev_chunk_id`
- `next_chunk_id`
- `embedding vector`
- `tsv` or keyword index field
- `created_at`

### 11.9 `images`

- `id`
- `manual_version_id`
- `section_id`
- `source_page_id`
- `file_asset_id`
- `thumbnail_asset_id`
- `caption`
- `ocr_text`
- `bbox_x`
- `bbox_y`
- `bbox_w`
- `bbox_h`
- `created_at`

### 11.10 `search_logs`

- `id`
- `user_id`
- `query_text`
- `query_language`
- `manual_id`
- `result_count`
- `created_at`

### 11.11 `search_results_cache`

- `id`
- `query_hash`
- `summary_language`
- `section_id`
- `summary_text`
- `citations_json`
- `created_at`
- `expires_at`

## 12. 검색 API 초안

### 12.1 관리자 API

- `POST /api/v1/manuals`
  설명: 매뉴얼 메타데이터 생성

- `POST /api/v1/manuals/{manualId}/upload`
  설명: 원본 파일 업로드 및 인제스트 시작

- `GET /api/v1/manuals`
  설명: 매뉴얼 목록 조회

- `GET /api/v1/manuals/{manualId}/versions`
  설명: 버전 목록 조회

- `POST /api/v1/manuals/{manualId}/reindex`
  설명: 재색인 요청

### 12.2 사용자 검색 API

- `POST /api/v1/search`
  설명: 질문 기반 검색 결과 목록 반환

요청 예시:

```json
{
  "query": "개점 시재 입력은 어디서 하나요?",
  "language": "ko",
  "manualIds": ["man_123"],
  "topK": 10
}
```

응답 예시:

```json
{
  "queryLanguage": "ko",
  "results": [
    {
      "sectionId": "sec_1",
      "manualId": "man_123",
      "manualTitle": "POS Opening Manual",
      "heading": "개점 시재 입력",
      "snippet": "개점 전 POS에서 시재 금액을 입력합니다.",
      "score": 0.92,
      "pageStart": 4,
      "pageEnd": 5,
      "detailUrl": "/manuals/man_123/sections/sec_1"
    }
  ]
}
```

### 12.3 상세 요약 API

- `GET /api/v1/sections/{sectionId}`
  설명: 사용자가 클릭한 결과의 상세 요약과 출처 반환

응답 예시:

```json
{
  "sectionId": "sec_1",
  "summaryLanguage": "ko",
  "summary": "이 절은 개점 시재 입력 절차를 설명합니다...",
  "citations": [
    {
      "page": 4,
      "label": "원문 보기",
      "viewerUrl": "/viewer/man_123/ver_2?page=4&section=sec_1"
    }
  ],
  "relatedImages": [
    {
      "imageId": "img_9",
      "thumbnailUrl": "/api/v1/images/img_9/thumbnail",
      "viewerUrl": "/viewer/man_123/ver_2?page=4&section=sec_1"
    }
  ]
}
```

### 12.4 원문 URL API

- `GET /api/v1/manuals/{manualId}/versions/{versionId}/viewer-url?page=4`
  설명: signed URL 또는 viewer proxy URL 반환

## 13. 상세 요약 생성 규칙

상세 요약은 전체 문서를 요약하지 않는다.

입력 컨텍스트:

- 사용자가 클릭한 section
- 인접 section 일부
- 관련 이미지 caption / OCR

출력 규칙:

- 질문 언어로 응답
- 원문에 없는 내용 추론 금지
- 절차형 문서는 단계별 리스트 유지
- 숫자, 경고, 버튼명은 원문 기준 유지
- 항상 citation URL 포함

## 14. 보안 / 운영 고려사항

- 조직 단위 매뉴얼 접근 제어
- signed URL 만료 시간 적용
- 업로드 파일 바이러스 검사
- OCR 실패, 파싱 실패, 임베딩 실패 상태 관리
- 검색 로그 수집 및 품질 측정
- 문서 버전 간 diff 추적 가능성 확보

## 15. 품질 평가 체계

정식 운영 전 반드시 평가셋이 필요하다.

최소 평가 항목:

- 질의 언어별 검색 정확도
- top-3, top-5 recall
- 요약 정확도
- 출처 연결 정확도
- 원문 뷰어 페이지 점프 정확도

권장 데이터셋:

- 한국어 질문 50개
- 스페인어 질문 50개
- 영어 질문 50개
- 오답 유도 질문 20개

## 16. 단계별 구현 로드맵

### Phase 1: Foundation

목표:

- 모노레포 생성
- Next.js, FastAPI, PostgreSQL, pgvector, S3/MinIO, Redis 부트스트랩
- 기본 인증 및 환경변수 체계 확립

완료 조건:

- 웹앱과 API가 분리 구동됨
- DB 마이그레이션 가능
- 파일 업로드가 저장소에 정상 적재됨

### Phase 2: Ingestion MVP 2.0

목표:

- PDF/DOCX 업로드
- 파싱/OCR
- section/chunk 생성
- 임베딩 생성
- pgvector 색인

완료 조건:

- 한 개 매뉴얼 업로드 후 검색 가능
- 페이지 정보와 원문 링크가 남음

### Phase 3: Search Experience

목표:

- 검색 API
- 결과 목록 UI
- 상세 요약 API
- citation 링크 노출

완료 조건:

- 질문 -> 결과 목록 -> 상세 요약 -> 원문 보기까지 연결

### Phase 4: Asset Intelligence

목표:

- 이미지 추출
- related images 노출
- 이미지 메타데이터 저장

완료 조건:

- 결과 상세 화면에서 관련 이미지 확인 가능

### Phase 5: Production Readiness

목표:

- 조직/권한 관리
- 평가셋 운영
- 재색인
- 장애 대응/모니터링

완료 조건:

- 운영 환경 배포 가능
- 검색 품질 기준선 확보

## 17. 추천 우선순위

처음부터 모든 걸 다 만들지 않는다.

가장 먼저 구현할 것:

1. 업로드 + 저장소 + DB 스키마
2. 파서 + chunk 생성
3. 벡터 검색 + BM25 검색
4. 결과 목록 UI
5. 상세 요약 + citation
6. 원문 viewer
7. 이미지 추출과 연결

## 18. 이번 프로젝트의 기준 결론

이번 솔루션은 아래 조합을 기준선으로 삼는다.

- Frontend: Next.js
- Backend: FastAPI
- Workflow: Temporal
- Database: PostgreSQL + pgvector
- Storage: S3 or MinIO
- Parsing: Unstructured
- LLM: OpenAI

즉, 기존의 `단일 스크립트 MVP`에서 `업로드 파이프라인 + 검색 서비스 + 상세 뷰어`로 구조를 재편하는 것이 정답이다.
