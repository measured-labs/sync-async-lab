# 미완료 실험 및 향후 작업 (Future Work)

> 작성일: 2026-04-05

---

## 건너뛴 실험

### B1: Python ProcessPoolExecutor CPU-bound

**상태:** Docker + uvicorn 환경에서 fork 충돌로 실패

**문제:**
- `ProcessPoolExecutor`가 uvicorn 워커 프로세스 내에서 서브프로세스를 fork할 때 충돌 발생
- 단일 요청은 성공하지만, 동시 요청 시 행(hang) 발생
- startup 이벤트로 초기화 위치를 옮겨도 Docker 컨테이너 환경에서 동일 문제

**재시도 방안:**
1. Docker 외부(로컬)에서 직접 실행하여 fork 충돌 확인
2. `multiprocessing.set_start_method('spawn')` 설정 후 테스트
3. uvicorn `--workers 1` + ProcessPoolExecutor vs `--workers 2` 비교
4. Celery 등 외부 워커 프로세스로 CPU 작업 위임하는 구조 테스트

**기대 결과:** GIL 우회 시 2코어 환경에서 ~2 req/s (기존 ~1 req/s의 2배)

---

### B2: Java GraalVM Native Image

**상태:** 빌드 시간 (10분+)으로 미진행

**구현 계획:**
```dockerfile
FROM ghcr.io/graalvm/native-image-community:21 AS build
WORKDIR /app
COPY . .
RUN gradle nativeCompile --no-daemon

FROM gcr.io/distroless/base
COPY --from=build /app/build/native/nativeCompile/spring-mvc-native .
CMD ["./spring-mvc-native"]
```

**build.gradle.kts 변경:**
```kotlin
plugins {
    id("org.graalvm.buildtools.native") version "0.10.4"
}
```

**테스트 항목:**
- 콜드 스타트 시간 (JVM ~3s vs Native ~0.1s 예상)
- 메모리 사용량 (JVM ~300MB vs Native ~50MB 예상)
- Throughput 비교 (JIT 최적화 없어서 JVM보다 낮을 수 있음)
- `/io`, `/cpu`, `/db` 전부 테스트

---

### B3: WebSocket 장기 커넥션 테스트

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

---

### A3: Django ASGI py-spy 프로파일링

**상태:** Docker ptrace 권한 이슈로 미진행 (정량적 데이터는 확보 완료)

**재시도 방안:**
```bash
# Docker에서 ptrace 허용
docker run --cap-add SYS_PTRACE ...

# 또는 로컬 실행
uvicorn config.asgi:application --port 8005 &
py-spy record -o flamegraph.svg --pid $(pgrep -f uvicorn)
```

**확보된 정량 데이터:**
- Django async-raw vs FastAPI async: 같은 asyncio.sleep인데 2.7배 (200VU) ~ 5.5배 (1000VU) 차이
- Django ASGI 프레임워크 자체의 오버헤드가 원인이라는 결론은 확정

---

## 추가 확장 가능 주제

| # | 주제 | 난이도 | 예상 소요 | 상태 |
|---|------|--------|----------|------|
| 1 | Python 3.13 free-threaded (PEP 703) | 중 | 2시간 | ❌ Docker 이미지 미제공 |
| 2 | Rust (Actix-web / Tokio) 서버 추가 | 중 | 3시간 | 미진행 |
| 3 | k8s HPA 오토스케일링 비교 | 높 | 1일 | 미진행 |
| 4 | Grafana + InfluxDB 실시간 대시보드 | 중 | 2시간 | 미진행 |
| 5 | Connection pool 크기별 성능 곡선 (10/20/50/100) | 낮 | 1시간 | ✅ 완료 |
| 6 | JVM warm-up 구간 별도 분석 | 낮 | 30분 | ✅ 완료 |

### #1 Python 3.13 free-threaded — 미진행 사유

- 공식 Docker Hub에 `python:3.13t` 또는 free-threaded 전용 이미지가 없음
- 표준 python:3.13-slim은 `--disable-gil`로 컴파일되지 않아 `PYTHON_GIL=0` 설정 시 Fatal Error
- 자체 빌드(소스 컴파일)는 가능하나 30분+ 소요 + 의존성 호환성 미보장
- PEP 703 구현이 안정화되면 공식 이미지 출시 후 재시도 권장
