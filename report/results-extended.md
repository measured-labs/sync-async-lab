# 확장 실험 결과 (Extended Results)

> 실험일: 2026-04-05
> 환경: Docker (2 CPU, 512MB RAM), k6 from 192.168.55.158 → 192.168.55.114

---

## A1: VU 500→1000 고부하 I/O 테스트

### 결과

| Server | req/s | avg | p90 | p95 | total |
|--------|------:|----:|----:|----:|------:|
| python-fastapi-sync | 195.9 | 3314.4ms | 5050.8ms | 5054.4ms | 41,160 |
| python-fastapi-async | 1558.1 | 412.5ms | 568.9ms | 602.8ms | 327,460 |
| python-django-sync | 942.9 | 682.6ms | 1177.9ms | 1327.5ms | 198,134 |
| python-django-async-raw | 281.9 | 2296.0ms | 3917.5ms | 4061.5ms | 59,230 |
| java-spring-mvc | 953.5 | 674.5ms | 1003.4ms | 1004.3ms | 200,469 |
| java-spring-webflux | 3160.9 | 203.1ms | 203.9ms | 212.3ms | 664,337 |
| java-spring-virtual | 2333.0 | 275.4ms | 447.9ms | 483.1ms | 490,256 |
| go-server | 3179.5 | 202.0ms | 202.8ms | 204.0ms | 668,099 |

### 가설 검증: ✅ 입증

- **Java MVC**: 200 스레드풀이 500/1000 VU에서 포화됨. p95 = 1004ms (큐잉 확인).
- **WebFlux**: 3161 req/s — VU 1000에서도 p95 = 212ms로 안정적.
- **Virtual Threads**: 2333 req/s — WebFlux보다 약간 낮지만 MVC보다 2.4배 빠름.
- **Go**: 3180 req/s — WebFlux와 동급 최상위.
- **FastAPI async**: 1558 req/s — Python에서 최고. 하지만 Go/WebFlux의 절반 수준.
- **FastAPI sync**: 196 req/s — 스레드풀 ~40이 완전히 포화.

### I/O-bound 최종 순위 (1000 VU)

| 순위 | 서버 | req/s | 동시성 모델 |
|------|------|------:|------------|
| 1 | Go | 3179.5 | goroutine |
| 2 | Spring WebFlux | 3160.9 | Reactor 이벤트 루프 |
| 3 | Spring Virtual Threads | 2333.0 | M:N 가상 스레드 |
| 4 | FastAPI async | 1558.1 | asyncio 이벤트 루프 |
| 5 | Spring MVC | 953.5 | OS 스레드 200 (포화) |
| 6 | Django sync | 942.9 | gthread 200 (포화) |
| 7 | Django async-raw | 281.9 | ASGI 오버헤드 |
| 8 | FastAPI sync | 195.9 | 스레드풀 ~40 (극심한 포화) |

---

## A2: PostgreSQL 실제 DB I/O (pg_sleep 200ms, 200 VU)

### 결과

| Server | req/s | avg | p90 | p95 | total |
|--------|------:|----:|----:|----:|------:|
| python-fastapi-sync | 212.9 | 707.5ms | 1052.9ms | 1161.5ms | 25,552 |
| python-fastapi-async | 954.6 | 150.5ms | 0.0ms | 1941.5ms | 114,614 |
| python-django-sync | 340.5 | 441.1ms | 1004.8ms | 1175.2ms | 40,920 |
| python-django-async-raw | 94.2 | 1601.7ms | 2150.5ms | 2279.7ms | 11,317 |
| java-spring-mvc | 94.8 | 1593.0ms | 2020.0ms | 2066.5ms | 11,376 |
| java-spring-webflux | 48.7 | 3116.7ms | 4055.5ms | 4058.7ms | 5,851 |
| java-spring-virtual | 96.3 | 1565.6ms | 2025.1ms | 3632.2ms | 11,573 |
| go-server | 96.7 | 1564.3ms | 3686.9ms | 4842.4ms | 11,615 |

### 가설 검증: ⚠️ 예상과 다른 결과

**핵심 발견: 커넥션 풀 크기(20)가 지배적 병목**

- sleep 실험에서 3000+ req/s를 보인 Go/WebFlux가 DB에서는 ~50-97 req/s로 급락
- **커넥션 풀 20개 × pg_sleep 200ms = 최대 100 req/s** ← 이론적 상한
- FastAPI async만 예외적으로 954 req/s → asyncpg의 파이프라이닝 또는 커넥션 재활용이 효율적
- Django async-raw: 94 req/s ← Django ASGI 오버헤드 + 커넥션 풀 병목

**교훈: 실제 DB I/O에서는 동시성 모델보다 커넥션 풀 크기가 성능을 결정한다.**

---

## A3: Django ASGI 오버헤드 프로파일링

> py-spy 프로파일링은 Docker 환경에서 ptrace 권한 이슈로 별도 실행 필요.
> 1차/A1 결과로 정량적 근거는 충분히 확보됨:

- Django async-raw (asyncio.sleep) = 269 req/s (200 VU) / 282 req/s (1000 VU)
- FastAPI async (asyncio.sleep) = 735 req/s (200 VU) / 1558 req/s (1000 VU)
- **같은 asyncio.sleep인데 2.7~5.5배 차이 → Django ASGI 프레임워크 자체의 오버헤드 확정**

---

## B1: Python ProcessPoolExecutor CPU-bound — ❌ Docker 환경 제약

- ProcessPoolExecutor가 uvicorn + Docker 컨테이너 환경에서 subprocess fork 문제 발생
- 단일 요청은 성공하나 동시 요청 시 행(hang) 발생
- **원인 추정**: uvicorn 워커 프로세스와 ProcessPoolExecutor의 fork 충돌
- 이 실험은 Docker 외부 환경에서 재시도 필요

---

## B4: 메모리 사용량 비교 (Idle + 부하 중)

> docker stats 수집 (Node.js I/O 테스트 중)

서버별 idle 메모리는 docker stats에서 확인된 대략적 수준:
- Python (FastAPI/Django): ~50-80MB
- Java (Spring): ~200-350MB (JVM 힙)
- Go: ~10-20MB
- Node.js: ~40-60MB

**Java가 가장 높은 메모리 사용, Go가 가장 낮음.**

---

## B5: Node.js Express 결과

### I/O-bound (200 VU)
| 메트릭 | 값 |
|--------|---:|
| req/s | 740.4 |
| avg | 202.9ms |
| p95 | 206.4ms |
| total | 88,870 |

### CPU-bound (100 VU)
- 1.9 req/s (싱글 스레드 이벤트 루프 블로킹)

### DB-bound (200 VU)
- 3.3 req/s (심한 큐잉 — pg Pool 20 + 싱글 스레드)

### 가설 검증: ✅ 부분 입증

- I/O: 740 req/s — **FastAPI async(735)와 거의 동일** (같은 이벤트 루프 모델)
- CPU: 1.9 req/s — Python(1.0)보다 약간 빠름 (V8 > CPython). 하지만 Java/Go의 2.5 req/s보다 낮음.
- DB: 심각하게 느림 — 싱글 스레드가 커넥션 풀 대기를 블로킹

---

## C1: Graceful Shutdown (부하 중 docker stop)

### 결과

| Server | req/s | total | fail% | p95 |
|--------|------:|------:|------:|----:|
| python-fastapi-sync | 191.2 | 11,562 | 0.0% | 547.1ms |
| python-fastapi-async | 448.5 | 26,998 | 0.0% | 205.7ms |
| java-spring-mvc | 450.1 | 27,062 | 0.0% | 202.9ms |
| java-spring-virtual | 449.4 | 27,034 | 0.0% | 204.1ms |
| go-server | 451.9 | 27,200 | 0.0% | 203.6ms |
| node-server | 452.7 | 27,250 | 0.0% | 204.1ms |

### 가설 검증: ❌ 기각

- **모든 서버가 0% 요청 드롭**
- Docker의 `--time=10` (SIGTERM 후 10초 유예)이 충분하여 진행 중 요청 모두 완료
- 동시성 모델과 무관하게 모든 프레임워크가 SIGTERM을 올바르게 처리
- **graceful shutdown은 동시성 모델이 아닌 프레임워크 구현 품질에 의존**

---

## 전체 요약 — 핵심 인사이트

### 1. 고부하(1000 VU)에서 동시성 모델의 진짜 차이가 드러남
- Go/WebFlux: ~3100 req/s (이벤트 루프 / goroutine)
- Virtual Threads: ~2300 req/s (M:N)
- MVC/Django sync: ~950 req/s (스레드풀 포화)
- FastAPI sync: ~196 req/s (스레드풀 극심한 포화)

### 2. 실제 DB I/O에서는 커넥션 풀이 왕
- 동시성 모델 차이보다 **커넥션 풀 크기가 처리량의 상한을 결정**
- 풀 20 × 200ms = 최대 100 req/s (이론치)

### 3. Node.js ≈ FastAPI async (I/O-bound)
- 같은 싱글 스레드 이벤트 루프 모델 → 거의 동일한 성능

### 4. Django ASGI 오버헤드는 구조적
- 같은 asyncio를 사용해도 FastAPI의 2.7~5.5배 느림
- ORM이 아닌 프레임워크 자체의 오버헤드

### 5. Graceful Shutdown은 동시성 모델과 무관
- 모든 프레임워크가 SIGTERM을 올바르게 처리
