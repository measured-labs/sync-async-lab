# ADR-008: WebSocket 동시 연결 (B3)

- 상태: 끝남 — 2026-04-11 측정 · 결과 커밋 342ecff
- 원문: [hypotheses-extended.md](../archive/report/hypotheses-extended.md) "B3", [results-extended.md](../archive/report/results-extended.md) "B3", [future-work.md](../archive/report/future-work.md) "B3"(측정 전 계획) — 2026-11-18 이 형식으로 옮김. 원문 줄을 그대로 옮기고 제목 깊이와 절 순서만 맞췄다. 바꾼 낱말 · 표기: "JVM 힙 메모리가 지배적이며" → "JVM 힙 메모리가 대부분을 차지하며"; 내부 IP를 "k6 서버(별도 PC) · 앱 서버"로. 2026-11-18에 덧붙인 확인 내용은 "한계"(와 각주)에 날짜를 달아 따로 적었다.
- 원문 판정(원문 절 제목): "B3: WebSocket 장기 커넥션 테스트 — ✅ 가설 입증 (이벤트 루프/goroutine 모델이 우수)"
- 줄임 이름: B3은 확장 실험 목록 B의 셋째 항목이다.

## 질문

WebSocket 연결을 100 · 500 · 1000개 동시에 유지할 때, 이벤트 루프 · goroutine 모델 서버의 메시지 왕복 시간(RTT) · 연결 수립 시간 · 메모리는 어떻게 다른가.

## 선택지

FastAPI async(asyncio), Spring WebFlux(Reactor), Go(goroutine), Node.js(libuv) — 각 서버의 `WS /ws` 에코 엔드포인트. 가설에 있던 스레드 모델 서버(MVC, FastAPI sync)는 측정 대상에 들지 않았다.

## 가설 (원문)

### 가설
**이벤트 루프 모델(FastAPI async, WebFlux, Go)이 스레드 모델(MVC, FastAPI sync)보다 동시 WebSocket 연결 수에서 월등히 유리할 것이다.**

### 근거
- WebSocket은 커넥션을 장시간 유지 → 스레드 모델은 커넥션당 스레드 점유
- 이벤트 루프는 fd 기반으로 수천 커넥션 동시 관리 가능

측정 전 계획(원문 `future-work.md`, 2026-04-05):

**상태:** k6 기본에서 WebSocket 제한적, xk6-websockets 확장 필요

**구현 계획:**

각 서버에 `/ws` 엔드포인트 추가:
- FastAPI: `@app.websocket("/ws")` + `websocket.accept()`
- Spring WebFlux: `WebSocketHandler` 구현
- Go: `golang.org/x/net/websocket` 또는 `gorilla/websocket`
- Node.js: `ws` 패키지

**k6 테스트:**
```bash
# xk6 빌드 필요
xk6 build --with github.com/grafana/xk6-websockets
```

```javascript
import ws from 'k6/x/websockets';
// WebSocket 연결 후 유지, 메시지 수신 측정
```

**테스트 항목:**
- 동시 WebSocket 연결 최대 수 (각 서버별)
- 메시지 브로드캐스트 지연 시간
- 메모리 사용량 vs 연결 수

## 실험 설계 · 결과 (원문)

> 실험일: 2026-04-11
> 환경: Docker (2 CPU, 512MB RAM), k6 서버(별도 PC) → 앱 서버(Docker 호스트)

### 실험 개요

4개 서버에 WebSocket 에코 엔드포인트(`/ws`)를 추가하고, 동시 연결 100/500/1000에서
메시지 RTT(Round-Trip Time), 연결 수립 시간, 메모리 사용량을 비교한다.

### 수행한 작업

각 서버에 `/ws` WebSocket 에코 핸들러를 추가했다. 클라이언트가 보낸 텍스트를 그대로 반환하는 구조.

**변경 파일:**
- `servers/python-fastapi-async/main.py` — `@app.websocket("/ws")` 추가 + `requirements.txt`에 `websockets==16.0`
- `servers/java-spring-webflux/` — `EchoWebSocketHandler.java` + `WebSocketConfig.java` 신규
- `servers/go-server/main.go` — `wsHandler` + `golang.org/x/net/websocket` 의존성 추가
- `servers/node-server/main.js` — `ws` 패키지 + `WebSocketServer` 추가

### 메시지 RTT 결과 (ms)

| 서버 | 100 VU avg | 100 VU p95 | 500 VU avg | 500 VU p95 | 1000 VU avg | 1000 VU p95 |
|------|----------:|-----------:|-----------:|-----------:|------------:|------------:|
| FastAPI async | 2.90 | 8 | 9.54 | 45 | **28.83** | **205** |
| Spring WebFlux | 2.81 | 2 | 3.38 | 3 | 2.71 | 3 |
| Go | 0.93 | 3 | 1.36 | 2 | 2.81 | 3 |
| Node.js | 0.81 | 1 | 0.83 | 2 | 1.16 | 2 |

### 연결 수립 시간 (ws_connecting, ms)

| 서버 | 100 VU avg | 500 VU avg | 1000 VU avg | 1000 VU p95 |
|------|----------:|-----------:|------------:|------------:|
| FastAPI async | 39.63 | 167.33 | **424.58** | **1040** |
| Spring WebFlux | 20.43 | 39.04 | 58.71 | 237.64 |
| Go | 6.50 | 47.19 | 77.89 | 274.37 |
| Node.js | 15.28 | 37.68 | 93.60 | 214.87 |

### 메모리 사용량 (1000 VU 부하 직후)

| 서버 | 메모리 | 동시성 모델 |
|------|-------:|------------|
| Go | **42 MB** | goroutine |
| Node.js | 34 MB | libuv 이벤트 루프 |
| FastAPI async | 83 MB | asyncio 이벤트 루프 |
| Spring WebFlux | **232 MB** | Reactor 이벤트 루프 (JVM) |

### 분석

#### 1. 메시지 RTT — Node.js와 Go가 최상위

100~1000 VU 전 구간에서 Node.js와 Go가 1~3ms RTT로 가장 안정적이다.
Spring WebFlux도 100~1000 VU에서 일관되게 ~3ms를 유지했다.

**FastAPI만 1000 VU에서 급격히 악화** (avg 28.83ms, p95 205ms).
Python의 asyncio 이벤트 루프가 단일 스레드에서 1000개 WebSocket 커넥션의 메시지를
직렬 처리하면서 병목이 발생한 것이다. uvicorn 자체의 Python 오버헤드도 누적된다.

#### 2. 연결 수립 시간 — Go가 가장 빠름, FastAPI가 가장 느림

Go는 1000 VU에서도 avg 78ms로 가장 빠르다. goroutine 생성 비용이 거의 없기 때문.
FastAPI는 1000 VU에서 avg 425ms, p95 1040ms — 연결 수립만으로 1초 이상 걸리는 경우도 있다.

#### 3. 메모리 — Go가 가장 효율적, WebFlux가 가장 높음

Go는 1000 VU 부하에서도 42MB만 사용. goroutine당 메모리 비용이 ~2KB 수준이기 때문.
WebFlux는 232MB로 가장 높지만, 이는 JVM 힙 메모리가 대부분을 차지하며 WebSocket 연결 자체의
비용은 아니다 (idle 상태에서도 ~220MB).
Node.js는 34MB로 Go 다음으로 효율적.

### 결론

| 항목 | 1위 | 2위 | 3위 | 4위 |
|------|-----|-----|-----|-----|
| 메시지 RTT (1000 VU) | Node.js (1.16ms) | Go (2.81ms) | WebFlux (2.71ms) | FastAPI (28.83ms) |
| 연결 수립 (1000 VU) | Go (78ms) | WebFlux (59ms) | Node.js (94ms) | FastAPI (425ms) |
| 메모리 효율 | Go (42MB) | Node.js (34MB) | FastAPI (83MB) | WebFlux (232MB) |

**가설 검증: ✅ 입증** — 이벤트 루프/goroutine 기반 서버가 WebSocket 장기 커넥션에서 우수.
단, FastAPI(Python asyncio)는 1000 동시 연결에서 유의미하게 악화되어, 
같은 이벤트 루프 모델이라도 런타임 성능(CPython vs V8/Go)에 따라 차이가 크다.

## 결정 (결론)

1000 연결에서 Node.js · Go · WebFlux는 RTT 평균 1.16~2.81ms를 유지했고, FastAPI async만 28.83ms(p95 205ms)로 느려졌다. 원문은 이벤트 루프 · goroutine 서버가 WebSocket 장기 연결에 유리하다는 가설을 입증으로 판정하면서, 같은 이벤트 루프 모델이라도 런타임(CPython vs V8 · Go)에 따라 차이가 크다고 적었다.

## 한계

- 가설은 "이벤트 루프 모델 vs 스레드 모델"이었지만, 스레드 모델 서버(MVC, FastAPI sync)는 재지 않았다. 측정한 것은 이벤트 루프 · goroutine 서버 4개 사이의 차이다.
- 각 1회 측정. k6 원본 출력은 저장소에 없다.
- 원문 결론 표의 순위가 같은 원문의 수치와 맞지 않는 곳이 있다. 메시지 RTT(1000 VU)는 WebFlux 2.71ms가 Go 2.81ms보다 작은데 Go가 2위, 연결 수립(1000 VU)은 WebFlux 59ms가 Go 78ms보다 작은데 Go가 1위, 메모리는 Node.js 34MB가 Go 42MB보다 작은데 Go가 1위로 적혀 있다. 원문은 고치지 않았다.
