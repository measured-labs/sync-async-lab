# sync-async-lab

## 결과와 결론

이 실험은 같은 일을 하는 HTTP 서버를 동시성 모델(스레드풀, 이벤트 루프, 가상 스레드, goroutine)만 바꿔 만들면 I/O 대기 · CPU 계산 · DB 대기에서 처리량이 얼마나 달라지는지 물었다. Python · Java · Go · Node.js 서버 12개를 Docker 컨테이너(2 CPU · 512MB)에 하나씩 띄우고, 별도 PC의 부하 도구 k6로 200ms 대기(`/io`) · fibonacci(38) 계산(`/cpu`) · PostgreSQL `pg_sleep(0.2)`(`/db`) 요청을 보내 초당 처리 요청 수(req/s)와 응답 시간을 쟀다. 200 VU(아래 줄임말 표)에서는 Go · WebFlux · MVC · FastAPI async · 가상 스레드가 717.6~743.6 req/s로 비슷했다. 500 → 1000 VU로 올리자 Go · WebFlux(약 3,160~3,180 req/s) > 가상 스레드(2,333) > MVC(954) 순으로 벌어졌고, 요청 스레드 200개를 쓰는 MVC와 Django sync는 약 1,000 req/s(스레드 200 ÷ 0.2초인 이론 상한) 근처에 머물렀다. 결론: 이 조건에서는 200ms를 기다리는 요청이 스레드 수보다 많아지면 이벤트 루프 · goroutine · 가상 스레드가 앞섰다. DB 대기에서는 FastAPI async 한 서버로 풀 크기만 바꿨을 때 처리량이 풀 크기에 비례했지만(풀 10 → 100에서 48.7 → 425.0 req/s), 서버끼리 비교한 DB 측정은 실패한 요청이 많아 동시성 모델과 풀 크기 중 무엇이 더 큰지는 이 저장소의 측정으로 말할 수 없다.

이 README에 나오는 줄임말:

| 줄임말 | 뜻 |
|---|---|
| VU | k6의 가상 사용자(virtual user). 응답을 받으면 바로 다음 요청을 보낸다. "200 VU" = 동시에 요청하는 사용자 200명 |
| GIL | Global Interpreter Lock. CPython이 한 번에 스레드 하나만 Python 코드를 실행하게 하는 락. CPU 계산을 스레드로 나눠도 병렬로 돌지 않는다 |
| IPC | Inter-Process Communication. 프로세스 사이에 데이터를 주고받는 일(여기서는 pickle 직렬화 + 파이프) |
| RTT | Round-Trip Time. WebSocket 메시지를 보내고 에코를 받기까지 걸린 시간 |
| WSGI · ASGI | Python 웹 서버와 앱 사이의 규약. WSGI는 동기(요청마다 스레드), ASGI는 비동기(이벤트 루프) |
| JIT · AOT | JIT는 실행 중에 자주 쓰는 코드를 기계어로 컴파일(JVM), AOT는 실행 전에 미리 컴파일(GraalVM Native Image) |
| ADR | Architecture Decision Record. 질문 하나마다 설계 · 결과 · 결정을 남기는 문서 |

| 측정 | 서버 / 조건 | req/s | 출처 |
|---|---|---:|---|
| `/io` 200 VU | Go · WebFlux · MVC · FastAPI async · 가상 스레드 | 743.6 · 741.8 · 739.8 · 735.6 · 717.6 | `docs/archive/report/results.md:22` · :20 · :19 · :15 · :21 |
| `/io` 500 → 1000 VU 단계 시나리오 전체 평균 | Go | 3,179.5 | `docs/archive/report/results-extended.md:21` |
| | Spring WebFlux | 3,160.9 | 같은 파일 :19 |
| | Spring 가상 스레드 | 2,333.0 | 같은 파일 :20 |
| | FastAPI async | 1,558.1 | 같은 파일 :15 |
| | Spring MVC | 953.5 | 같은 파일 :18 |
| | Django sync (WSGI) | 942.9 | 같은 파일 :16 |
| | Django async-raw | 281.9 | 같은 파일 :17 |
| | FastAPI sync | 195.9 | 같은 파일 :14 |
| `/db` 200 VU, FastAPI async 한 서버 | 풀 10 · 20 · 50 · 100 | 48.7 · 96.1 · 230.0 · 425.0 | 같은 파일 :577~580 (원본 k6 출력 없음) |

- 측정 조건: 서버마다 Docker `cpus: 2.0` · `mem_limit: 512m`, PostgreSQL 16(`docker-compose.yml`). Spring Boot 3.4.4 · JDK 21, Python 3.12(free-threaded 실험은 3.13.13), Go 1.25, Node.js 22(각 서버의 빌드 파일 · Dockerfile). 측정일 2026-04-05 ~ 04-11. 호스트 CPU는 i7-13700HX(절전 모드)로 일부 실험(ADR-004 · ADR-007)에만 적혀 있고, k6 버전 · 반복 횟수는 기록 없음(결과는 각 1회).
- `/io` 500 → 1000 VU 값은 0 → 500 VU(30초) · 500 VU 유지(60초) · 500 → 1000 VU(30초) · 1000 VU 유지(60초) · 1000 → 0 VU(30초)로 이어지는 3분 30초 전체의 평균이다(`k6/scenarios/high-concurrency-io.js`). 8개 서버 모두 요청 실패 0건이었다(`k6/results/high-concurrency-20260405-074723/*.log`). 구간별 추정치는 [ADR-001](docs/adr/ADR-001-high-concurrency-io.md)에 있다.
- 실패한 요청이 섞인 수치(k6 원본 `k6/results/`와 맞춰 봄 — 원문 수치는 그대로 두었다):
  - CPU-bound(100 VU): Python 서버 5개 96~100%, Java MVC 8.53%, WebFlux 7.51% — [ADR-000](docs/adr/ADR-000-baseline-io-cpu.md)
  - DB I/O(200 VU): FastAPI async 90.32%(954.6 req/s 중 성공은 약 92 req/s), FastAPI sync 62.07%, Django sync 67.88% — [ADR-002](docs/adr/ADR-002-db-io-connection-pool.md)
  - GraalVM Native CPU: 17.5%가 타임아웃 — [ADR-006](docs/adr/ADR-006-graalvm-native.md)
  - Node.js CPU 47.8%, DB 50.3% — [ADR-010](docs/adr/ADR-010-nodejs.md)
- graceful shutdown 결과("0% 요청 드롭")는 종료가 실제로 일어났는지 확인되지 않는다. `docker stop`을 보낸 20초 뒤에도 초당 약 500건을 계속 처리했다(`k6/results/shutdown-20260405-094804/go-server.log`) — [ADR-011](docs/adr/ADR-011-graceful-shutdown.md).
- 실험별 질문 · 설계 · 결과 · 한계는 ADR로 정리했다. 아래 [실험 기록 (ADR)](#실험-기록-adr)에 목록이 있다.

동기/비동기 처리 방식의 성능 차이를 실험적으로 검증하는 프로젝트.

## 실험 대상 서버

| # | 서버 | 프레임워크 | 동시성 모델 | 포트 |
|---|------|-----------|------------|------|
| 1 | python-fastapi-sync | FastAPI + def | 스레드풀 | 8001 |
| 2 | python-fastapi-async | FastAPI + async def | asyncio 이벤트 루프 | 8002 |
| 3 | python-django-sync | Django WSGI (gunicorn) | 프로세스/스레드 | 8003 |
| 4 | python-django-async | Django ASGI (uvicorn) + ORM | asyncio + sync_to_async | 8004 |
| 5 | python-django-async-raw | Django ASGI + raw SQL | 순수 async I/O | 8005 |
| 6 | java-spring-mvc | Spring MVC (Tomcat) | OS 스레드 1:1 | 8006 |
| 7 | java-spring-webflux | Spring WebFlux (Netty) | Reactor 이벤트 루프 | 8007 |
| 8 | java-spring-virtual | Spring MVC + Virtual Threads | M:N 가상 스레드 | 8008 |
| 9 | go-server | Go net/http | goroutine (M:N) | 8009 |
| 10 | node-server | Node.js Express | 싱글 스레드 이벤트 루프 | 8010 |
| 11 | java-spring-mvc-native | Spring MVC + GraalVM Native | AOT 컴파일 | 8011 |
| 12 | python-fastapi-freethreaded | Starlette + Python 3.13t (no-GIL) | free-threading | 8012 |

## 엔드포인트

| 엔드포인트 | 역할 |
|-----------|------|
| GET /io | I/O-bound (sleep 200ms) |
| GET /cpu | CPU-bound (fibonacci 38) |
| GET /db | DB I/O (PostgreSQL pg_sleep 200ms) |
| GET /cpu-mp | CPU (ProcessPoolExecutor) — fastapi-async 전용 |
| GET /cpu-mt | CPU (ThreadPoolExecutor, no-GIL) — freethreaded 전용 |
| WS /ws | WebSocket 에코 — fastapi-async, webflux, go, node |

## 핵심 결과

### I/O-bound 처리량 (500 → 1000 VU 단계 시나리오 전체 평균)

| 순위 | 서버 | req/s |
|------|------|------:|
| 1 | Go | 3,180 |
| 2 | Spring WebFlux | 3,161 |
| 3 | Spring Virtual Threads | 2,333 |
| 4 | FastAPI async | 1,558 |
| 5 | Spring MVC | 954 |
| 6 | Django sync (WSGI) | 943 |
| 7 | Django async-raw | 282 |
| 8 | FastAPI sync | 196 |

### 주요 발견

- **이 설정에서 Django async가 sync보다 느렸다**: WSGI(gunicorn gthread 4 프로세스 × 50 스레드)가 ASGI(uvicorn 워커 1개)보다 2.5배 빠름(200 VU `/io`). 워커 수가 달라 모델만의 차이는 아니다
- **고부하에서 동시성 모델 차이가 극명**: 200 VU에서 비슷하던 서버들이 1000 VU에서 3배 이상 차이
- **DB I/O에서는 풀 크기가 처리량 상한을 정했다(FastAPI async 한 서버)**: 풀 크기 곡선은 FastAPI async에서만 쟀고, 서버끼리 비교한 DB 측정은 실패율이 높아(위 목록) 동시성 모델과의 비교는 확인되지 않았다
- **Go는 blocking 코드로 최상위 성능**: sync/async 구분 없이 goroutine이 자동 비동기
- **Graceful Shutdown**: 원문 결론은 "모든 프레임워크가 0% 요청 드롭"이지만, 종료가 실제로 일어났는지 확인되지 않았다(`docker stop` 20초 뒤에도 초당 약 500건 계속 처리 — `k6/results/shutdown-20260405-094804/go-server.log`)

### 추가 실험 결과

| 실험 | 핵심 결과 |
|------|----------|
| GraalVM Native Image | 콜드스타트 18.8x 빠름, 메모리 5.7x 절약, CPU 처리량 20% 낮음(Native는 17.5% 타임아웃 포함. 성공 건만 세면 약 29~34% 낮음 — 원문 표의 total · fail%로 29%, req/s · fail%로 34%) |
| ProcessPoolExecutor | GIL 우회 1.33x 향상 (IPC 오버헤드로 2x 미달). 1회 측정 · k6 원본 없음 · 다른 실험과 달리 Docker 밖 로컬 · 10 VU |
| Python 3.13 free-threaded | **GIL 없이 ThreadPoolExecutor로 2.16x CPU 병렬화 성공**. 1회 측정 · k6 원본 없음 · 2 VU(요청 5건 · 10건) |
| WebSocket 동시 연결 | Go/Node RTT ~1ms는 100 VU 값(1000 VU에서 Go 2.81ms, Node 1.16ms), FastAPI 1000 VU에서 29ms로 악화 |
| Connection pool 곡선 | 풀 크기에 비례 (이론적 상한의 85~97% 달성) |
| JVM warm-up | 관찰 미미 — CPU 절전 모드의 주파수 변동 때문에 JIT 효과를 따로 떼어 관측하지 못함(원문 판정). 6~10번째 요청이 첫 5회보다 22% 빨랐지만 16~20번째에 다시 느려졌다 |

## 실행

```bash
# 서버 전체 기동 (Docker, PostgreSQL 포함)
docker compose up -d

# k6 테스트 (별도 PC에서)
cd k6
./run-all.sh                  # 기본 I/O + CPU 테스트
./run-high-concurrency.sh     # 500/1000 VU 고부하
./run-db-bound.sh             # PostgreSQL DB I/O
```

## 실험 환경

- Docker 리소스 제한: 2 CPU, 512MB RAM (전 서버 동일)
- PostgreSQL 16 (Docker, 동일 리소스 제한)
- k6: 별도 PC에서 192.168.55.114 대상으로 실행
- 측정: 1개 서버씩 순차적으로 요청 (컨텍스트 스위칭 방지)

## 폴더 구조

```
servers/          # 12개 서버 소스
k6/               # k6 테스트 시나리오 + 실행 스크립트
docs/
  adr/              # 실험별 기록 ADR-000~011 (git 추적)
  archive/report/   # ADR로 옮기기 전 원문 (git 추적)
    hypotheses.md         # 1차 가설 (H1-H8)
    hypotheses-extended.md # 확장 가설 (A1-C1)
    results.md            # 1차 결과
    results-extended.md   # 확장 결과
    future-work.md        # 미완료 실험 + 향후 작업
  (그 밖의 docs/)   # 설계 · 작업 문서 (git 미추적)
```

## 실험 기록 (ADR)

가설 번호(H1~H8)와 확장 실험 번호(A = 기존 서버로 바로 하는 확장, B = 새 서버 · 설정이 필요한 실험, C = 운영 관점, # = 추가 확장 주제 표의 번호)는 옮기기 전 원문에서 붙인 이름이다.

| ADR | 질문 | 원문 번호 |
|---|---|---|
| [ADR-000](docs/adr/ADR-000-baseline-io-cpu.md) | 9개 서버의 I/O-bound · CPU-bound 처리량 (200 VU · 100 VU) | H1~H8 |
| [ADR-001](docs/adr/ADR-001-high-concurrency-io.md) | VU 500 → 1000에서 동시성 모델 차이 | A1 |
| [ADR-002](docs/adr/ADR-002-db-io-connection-pool.md) | 실제 DB I/O와 커넥션 풀 크기 | A2 · #5 |
| [ADR-003](docs/adr/ADR-003-django-asgi-overhead.md) | Django ASGI 오버헤드 | A3 |
| [ADR-004](docs/adr/ADR-004-python-processpool.md) | ProcessPoolExecutor로 GIL 우회 | B1 |
| [ADR-005](docs/adr/ADR-005-python-free-threaded.md) | Python 3.13 free-threaded의 ThreadPoolExecutor 병렬화 | #1 |
| [ADR-006](docs/adr/ADR-006-graalvm-native.md) | GraalVM Native Image — 시작 시간 · 메모리 · 처리량 | B2 |
| [ADR-007](docs/adr/ADR-007-jvm-warmup.md) | JVM warm-up 구간 | #6 |
| [ADR-008](docs/adr/ADR-008-websocket.md) | WebSocket 동시 연결 | B3 |
| [ADR-009](docs/adr/ADR-009-memory.md) | 서버별 메모리 사용량 | B4 |
| [ADR-010](docs/adr/ADR-010-nodejs.md) | Node.js Express 추가 | B5 |
| [ADR-011](docs/adr/ADR-011-graceful-shutdown.md) | 부하 중 graceful shutdown | C1 |

옮기기 전 원문: [1차 가설](docs/archive/report/hypotheses.md) · [1차 결과](docs/archive/report/results.md) · [확장 가설](docs/archive/report/hypotheses-extended.md) · [확장 결과](docs/archive/report/results-extended.md) · [미완료 실험 및 향후 작업](docs/archive/report/future-work.md)
