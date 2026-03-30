# Production Deployment

이 문서는 `preguntalo.carroamix.com`으로 `PreguntaLo`를 외부 공개 배포하는 기준 절차입니다.

## 목표 구성

- 외부 도메인: `https://preguntalo.carroamix.com`
- Reverse Proxy / SSL: `Caddy`
- Web: `Next.js`
- API: `FastAPI`
- DB: `Postgres + pgvector`
- Cache: `Redis`
- File Storage: `MinIO`
- Local AI: 호스트 머신의 `Ollama` 또는 동급 로컬 모델 서버

## 1. 사전 조건

배포 대상 머신에서 아래가 준비되어 있어야 합니다.

- Docker / Docker Compose 사용 가능
- `preguntalo.carroamix.com` DNS가 배포 머신의 공인 IP를 가리킴
- 공유기 또는 방화벽에서 `80`, `443` 포트가 배포 머신으로 포워딩됨
- 배포 머신에서 외부로 `80/443` 응답 가능

주의:

- 현재 로컬 맥에서 직접 외부 공개하려면 집/사무실 네트워크의 공인 IP와 포트포워딩이 필요합니다.
- 이게 안 되면 도메인은 연결되어 있어도 외부에서 접속되지 않습니다.

## 2. 환경 파일 준비

루트에서 배포용 env 파일을 만듭니다.

```bash
cp .env.production.example .env.production
```

최소 수정 항목:

- `APP_DOMAIN=preguntalo.carroamix.com`
- `POSTGRES_PASSWORD=강한비밀번호`
- `DATABASE_URL=postgresql+psycopg://app:강한비밀번호@postgres:5432/preguntalo`
- `CORS_ORIGINS=https://preguntalo.carroamix.com,http://localhost:3000,http://127.0.0.1:3000`

로컬 LLM/임베딩 서버를 같은 머신에서 돌린다면:

- `LOCAL_AI_BASE_URL=http://host.docker.internal:11434`

## 3. 배포 실행

```bash
npm run deploy:up
```

직접 명령으로 실행하려면:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build
```

종료:

```bash
npm run deploy:down
```

로그 확인:

```bash
npm run deploy:logs
```

## 4. 공개 경로

- 웹: `https://preguntalo.carroamix.com`
- API Health: `https://preguntalo.carroamix.com/api/v1/health`

## 5. 구성 설명

`docker-compose.prod.yml`은 다음 컨테이너를 올립니다.

- `postgres`
- `redis`
- `minio`
- `createbucket`
- `api`
- `web`
- `caddy`

`Caddy`가 외부 HTTPS를 받고, 아래처럼 라우팅합니다.

- `/` -> `web:3000`
- `/api/proxy/*` -> `api:8000`
- `/api/v1/*` -> `api:8000`

이 구조 덕분에 프런트의 기존 `/api/proxy` 호출을 그대로 유지하면서 외부 도메인에서도 정상 동작합니다.

## 6. 로컬 AI 사용

현재 프로젝트는 OpenAI 없이도 동작할 수 있게 구성되어 있습니다.

추천 방식:

1. 배포 머신 호스트에서 `Ollama` 실행
2. `LOCAL_AI_BASE_URL=http://host.docker.internal:11434` 사용
3. `LOCAL_EMBEDDING_MODEL`, `LOCAL_CHAT_MODEL` 설정
4. 문서 정보화 재실행

예시:

- `LOCAL_EMBEDDING_MODEL=bge-m3`
- `LOCAL_CHAT_MODEL=qwen2.5:7b`

## 7. 배포 후 확인 순서

1. `https://preguntalo.carroamix.com/api/v1/health` 확인
2. 메인 화면 접속 확인
3. `/manuals` 접속 확인
4. 파일 업로드 / 정보화 동작 확인
5. 질문 응답 확인
6. 답변의 근거 pill 클릭 시 원본 PDF 새 창 오픈 확인

## 8. 현재 한계

- 실제 외부 공개 여부는 DNS와 공유기/방화벽 설정에 좌우됩니다.
- 현재 저장소에는 DNS를 자동으로 바꾸는 기능은 없습니다.
- 맥북을 직접 외부 공개 서버로 쓰는 경우, 슬립 모드/네트워크 변경 시 접속이 끊길 수 있습니다.

## 9. 추천 운영 방향

지금 구성으로도 맥에서 바로 공개는 가능하지만, 장기적으로는 아래가 더 안정적입니다.

- 작은 Linux VPS 또는 사내 고정 서버에 배포
- `Postgres + MinIO` 볼륨 백업
- `Ollama` 또는 별도 로컬 모델 서버를 같은 머신에 상주시킴

개발용 맥에서 당장 외부 공개를 유지해야 한다면, 로그인 후 자동 복구는 아래 명령으로 설정할 수 있습니다.

```bash
npm run public:autostart:install
```
