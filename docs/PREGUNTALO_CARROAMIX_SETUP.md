# preguntalo.carroamix.com Setup Checklist

이 문서는 `bunny.carroamix.com` 운영 방식을 기준으로, 같은 맥에서 `preguntalo.carroamix.com`을 외부 공개하는 체크리스트입니다.

핵심 방향:

- 이 맥을 당분간 실제 호스트로 사용
- `web: http://127.0.0.1:3000`
- `api: http://127.0.0.1:8010`
- 외부 공개는 `Cloudflare Tunnel` 사용
- 공유기 포트포워딩 없이 `preguntalo.carroamix.com` 공개

## 1. 현재 로컬 상태 확인

먼저 로컬 서비스가 정상이어야 합니다.

```bash
curl -s --max-time 5 http://127.0.0.1:8010/api/v1/health
```

그리고 웹도 열리는지 확인합니다.

```bash
open http://127.0.0.1:3000
```

## 2. Cloudflare에 carroamix.com 등록

`bunny.carroamix.com`과 같은 방식으로 `carroamix.com` 도메인을 Cloudflare에서 관리해야 합니다.

이미 Bunny가 정상 운영 중이면 이 단계는 이미 끝난 상태일 가능성이 높습니다.

확인할 것:

- `carroamix.com`이 Cloudflare에 등록되어 있는지
- `bunny.carroamix.com`이 같은 계정의 Tunnel로 운영 중인지

## 3. Cloudflare Zero Trust에서 새 Tunnel 생성

Cloudflare 대시보드에서:

1. `Zero Trust`
2. `Networks` -> `Tunnels`
3. 새 tunnel 생성
4. 이름 예시: `preguntalo-mac`

## 4. Published Application 추가

Tunnel 안에서 다음을 설정합니다.

- subdomain: `preguntalo`
- domain: `carroamix.com`
- service type: `HTTP`
- service URL: `http://127.0.0.1:3000`

즉, 외부 접속은 웹 앱으로 먼저 들어오고, 웹이 내부적으로 `/api/proxy`를 통해 API와 통신하게 됩니다.

생성 후 목표 주소:

- `https://preguntalo.carroamix.com`

## 5. Tunnel Token 복사

Tunnel 상세 화면에서:

1. replica 추가 또는 install command 보기
2. `cloudflared tunnel run --token ...` 명령 확인
3. `eyJ...` 형태의 token 값 복사

## 6. 토큰 저장

쉘 히스토리에 남기지 않도록 Keychain 저장을 권장합니다.

```bash
npm run tunnel:store -- "paste-token-here"
```

또는 직접:

```bash
bash scripts/store_cloudflare_tunnel_token.sh "paste-token-here"
```

## 7. Bunny와 같은 방식으로 공개 실행

시작:

```bash
npm run public:start
```

이 스크립트는 아래를 순서대로 수행합니다.

1. API 확인 및 필요 시 시작
2. Web 확인 및 필요 시 시작
3. Cloudflare Tunnel 시작
4. 공개 주소 health 확인

정지:

```bash
npm run public:stop
```

상태 확인:

```bash
npm run public:status
```

## 8. 로그 위치

실행 로그는 루트의 `run/` 아래에 쌓입니다.

- API 로그: `run/api.log`
- 웹 로그: `run/web.log`
- 터널 로그: `run/tunnel.log`

## 9. 외부 확인 주소

- 메인: `https://preguntalo.carroamix.com`
- API health: `https://preguntalo.carroamix.com/api/proxy/api/v1/health`

## 10. 현재 방식의 장점

`bunny.carroamix.com`과 같은 흐름으로 가져가면 장점이 있습니다.

- 공유기 포트포워딩이 없어도 됨
- 맥에서 바로 외부 공개 가능
- DNS/SSL 처리를 Cloudflare가 맡음
- 운영 방식이 기존 Bunny와 동일해서 헷갈림이 적음

## 11. 주의사항

- 맥이 잠들면 서비스가 끊깁니다.
- `cloudflared`가 설치되어 있어야 합니다.
- API와 웹이 모두 이 맥에서 살아 있어야 합니다.
- 로컬 LLM/Ollama를 같이 쓸 경우 해당 프로세스도 계속 살아 있어야 합니다.

## 12. 추천 운영 메모

지금은 Bunny를 벤치마킹해서 같은 맥 공개 방식이 가장 빠릅니다.

장기적으로는:

- PreguntaLo 전용 tunnel 유지
- macOS login 시 자동 실행
- 또는 고정 서버/VPS로 이전

순서가 안정적입니다.

## 13. Mac 로그인 시 자동 실행

`launchd` 기준으로, 로그인할 때마다 공개 서비스를 자동으로 복구할 수 있습니다.

설치:

```bash
npm run public:autostart:install
```

상태 확인:

```bash
npm run public:autostart:status
```

해제:

```bash
npm run public:autostart:uninstall
```

이 자동 실행은 `~/Library/LaunchAgents/com.carroamix.preguntalo.public.plist`를 설치하고, `launchd`가 `preguntalo_public_supervisor.sh`를 계속 실행하도록 등록합니다. Supervisor는 60초 간격으로 API/Web/Tunnel 상태를 확인하면서 필요하면 다시 올립니다.

중요:

- 현재 Tunnel token은 macOS Keychain에서 읽으므로, 사용자 로그인 세션이 있어야 가장 안정적으로 동작합니다.
- 즉, "맥 전원만 켜짐"보다 "맥 전원 켜지고 해당 사용자 로그인 완료"를 기준으로 보는 것이 맞습니다.
- 완전한 부팅 직후 무인 실행이 필요하면 Keychain 대신 별도 비밀값 관리와 `LaunchDaemon` 구성이 추가로 필요합니다.
