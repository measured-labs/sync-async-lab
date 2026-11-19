# ADR-002: 실제 DB I/O와 커넥션 풀 크기 (A2 · #5)

- 상태: 끝남 — A2 2026-04-05 측정(결과 커밋 225438a) · #5 2026-04-11 측정(결과 커밋 5701935)
- 원문: [hypotheses-extended.md](../archive/report/hypotheses-extended.md) "A2", [results-extended.md](../archive/report/results-extended.md) "A2" · "#5" — 2026-11-18 이 형식으로 옮김. 원문 줄을 그대로 옮기고 제목 깊이와 절 순서만 맞췄다. 바꾼 낱말 · 표기: "지배적 병목" → "가장 큰 병목"; 내부 IP를 "k6 서버(별도 PC) · 앱 서버"로. 2026-11-18에 덧붙인 확인 내용은 "한계"(와 각주)에 날짜를 달아 따로 적었다.
- 원문 판정: A2 "⚠️ 예상과 다른 결과", #5 "✅ 입증 (풀 크기 ∝ 처리량)"
- 줄임 이름: A2는 확장 실험 목록의 둘째 항목, #5는 [future-work.md](../archive/report/future-work.md) "추가 확장 가능 주제" 표의 5번(커넥션 풀 크기별 곡선)이다.
- 선행: [ADR-000](ADR-000-baseline-io-cpu.md) · [ADR-001](ADR-001-high-concurrency-io.md) — sleep으로 흉내 낸 I/O에서는 Go · WebFlux가 3,000 req/s를 넘었다.

## 질문

sleep이 아니라 실제 DB 쿼리(PostgreSQL `pg_sleep(0.2)`)를 기다리면, async 드라이버를 쓰는 서버가 sync 드라이버보다 유리한가. 아니면 커넥션 풀 크기가 처리량을 정하는가.

## 선택지

- A2: 8개 서버(python-fastapi-sync, python-fastapi-async, python-django-sync, python-django-async-raw, java-spring-mvc, java-spring-webflux, java-spring-virtual, go-server)의 `GET /db`. 서버별 커넥션 풀 설정(2026-11-18 코드 확인):

| 서버 | 풀 설정 | 근거 |
|---|---|---|
| python-fastapi-sync | psycopg2 `ThreadedConnectionPool(5, 20)` — 최대 20 | `servers/python-fastapi-sync/main.py:17-18` |
| python-fastapi-async | asyncpg `max_size=POOL_SIZE`(기본 20) | `servers/python-fastapi-async/main.py:18-21` |
| python-django-sync | psycopg2 `ThreadedConnectionPool(5, 20)`를 모듈 전역에 둠. gunicorn 워커 4개가 각자 만들므로 워커마다 20, 합쳐 최대 80 | `servers/python-django-sync/config/views.py:9-10`, `Dockerfile` `--workers 4` |
| python-django-async-raw | asyncpg `max_size=20` | `servers/python-django-async-raw/config/views.py:14-16` |
| java-spring-mvc · java-spring-virtual | HikariCP `maximum-pool-size=20` | 각 `application.properties:7`(mvc는 :6) |
| java-spring-webflux | R2DBC 풀 설정 없음. 라이브러리 기본값을 썼을 것으로 추정(확인하지 않음) | `servers/java-spring-webflux/src/main/resources/application.properties` |
| go-server | `db.SetMaxOpenConns(20)` | `servers/go-server/main.go:80` |
- #5: python-fastapi-async(asyncpg) 하나로 풀 크기만 10 · 20 · 50 · 100으로 바꿈.

## 실험 설계

- 엔드포인트: `GET /db` — `SELECT pg_sleep(0.2)`. PostgreSQL 16(Docker, 2 CPU · 512MB).
- k6 시나리오 `k6/scenarios/db-bound.js`: 30초 동안 200 VU까지 → 200 VU 60초 → 30초 동안 0까지. 실행 스크립트 `k6/run-db-bound.sh`.
- #5: 환경변수 `POOL_SIZE`로 asyncpg 풀 크기를 바꿔 4번 실행(아래 원문 "수행한 작업").

### 가설 (원문, A2)

#### 가설
**async DB 드라이버(asyncpg)를 사용하는 서버가 sync 드라이버(psycopg2)보다 I/O 처리량이 높을 것이다. 단, 커넥션 풀 크기가 새로운 병목이 될 것이다.**

#### 근거
- sleep과 달리 실제 DB I/O는 커넥션 풀을 거침
- async 드라이버는 이벤트 루프에서 직접 I/O → 스레드 전환 없음
- 커넥션 풀 크기(20)가 sleep 실험의 스레드풀과 같은 역할의 병목

#### 예상 결과
- async 서버(FastAPI async, WebFlux, Go): 커넥션 풀 크기에 비례하는 처리량
- sync 서버: 스레드풀 × 커넥션풀 이중 병목
- Django async + ORM: sync_to_async + 동기 드라이버 → 최악

## 결과 (원문)

### A2: PostgreSQL 실제 DB I/O (pg_sleep 200ms, 200 VU)

> 실험일: 2026-04-05 · 환경: Docker (2 CPU, 512MB RAM), k6 서버(별도 PC) → 앱 서버(Docker 호스트)

#### 결과

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

#### 가설 검증: ⚠️ 예상과 다른 결과

**핵심 발견: 커넥션 풀 크기(20)가 가장 큰 병목**

- sleep 실험에서 3000+ req/s를 보인 Go/WebFlux가 DB에서는 ~50-97 req/s로 급락
- **커넥션 풀 20개 × pg_sleep 200ms = 최대 100 req/s** ← 이론적 상한
- FastAPI async만 예외적으로 954 req/s → asyncpg의 파이프라이닝 또는 커넥션 재활용이 효율적

> 2026-11-18 주석: 이 해석은 철회한다. 954.6 req/s는 요청 114,614건 중 103,524건(90.32%)이 실패한 값이고(`k6/results/db-bound-20260405-084137/python-fastapi-async.log:103922`), 실패는 모두 k6 경고 `connection refused`로 08:45:18~23(UTC)에 몰려 있다. 성공한 요청만 세면 약 92 req/s로 풀 20의 이론 상한(100 req/s) 안쪽이다. asyncpg가 효율적이어서 나온 수치가 아니다.
- Django async-raw: 94 req/s ← Django ASGI 오버헤드 + 커넥션 풀 병목

**교훈: 실제 DB I/O에서는 동시성 모델보다 커넥션 풀 크기가 성능을 결정한다.**

### #5: Connection Pool 크기별 성능 곡선 — ✅ 입증 (풀 크기 ∝ 처리량)

> 실험일: 2026-04-11
> 환경: Docker (2 CPU, 512MB RAM), FastAPI async (asyncpg), pg_sleep(0.2s), 200 VU
> k6 서버(별도 PC) → 앱 서버 :8002

#### 가설

커넥션 풀 크기가 DB I/O 처리량의 상한을 직접 결정한다.
이론적 상한 = `pool_size / query_time` = `pool_size / 0.2s`

#### 결과

| Pool Size | req/s (실측) | avg latency | p95 | 이론적 상한 | 달성률 |
|----------:|------------:|------------:|----:|----------:|-------:|
| 10 | 48.7 | 3.12s | 4.26s | 50 | 97.4% |
| 20 | 96.1 | 1.56s | 2.23s | 100 | 96.1% |
| 50 | 230.0 | 653ms | 1.02s | 250 | 92.0% |
| 100 | 425.0 | 353ms | 604ms | 500 | 85.0% |

#### 수행한 작업

`servers/python-fastapi-async/main.py`에서 커넥션 풀 크기를 환경변수(`POOL_SIZE`)로 변경 가능하게 수정:

```python
pool_size = int(os.environ.get("POOL_SIZE", "20"))
db_pool = await asyncpg.create_pool(
    host=DB_HOST, port=5432, database="bench", user="bench", password="bench",
    min_size=min(5, pool_size), max_size=pool_size
)
```

Docker 컨테이너를 `POOL_SIZE=N`으로 환경변수를 주며 4회 반복 테스트.
PostgreSQL `max_connections=100` (기본값)으로 100까지 테스트 가능.

#### 분석

1. **풀 크기 10~50 구간에서는 이론적 상한의 92~97%를 달성** — 거의 완벽한 선형 확장
2. **풀 100에서 달성률 85%로 하락** — 원인:
   - PostgreSQL 서버 쪽 CPU/I/O 부하 증가 (100개 동시 세션 관리)
   - asyncpg 커넥션 관리 오버헤드 증가
   - Docker 2 CPU 제약으로 이벤트 루프 + 100개 커넥션 처리에 CPU 경합
3. **avg latency는 풀이 커질수록 감소** — 큐잉 대기 시간 감소 (200 VU / pool_size = 큐 깊이)
   - Pool 10: 200 VU / 10 커넥션 = 20 대기열 → avg 3.12s
   - Pool 100: 200 VU / 100 커넥션 = 2 대기열 → avg 353ms

#### 결론

**커넥션 풀 크기는 DB-bound 워크로드에서 가장 중요한 단일 튜닝 파라미터다.**
동시성 모델(async/sync/goroutine)보다 풀 크기가 처리량을 더 직접적으로 결정한다.

프로덕션 지침:
- `pool_size ≈ expected_concurrent_db_requests`로 설정
- PostgreSQL `max_connections`을 모든 앱 서버의 풀 합산보다 높게
- 풀이 너무 크면 PostgreSQL 서버 부하로 역효과 (shared_buffers, work_mem 경합)

## 결정 (결론)

원문의 결론은 "실제 DB I/O에서는 동시성 모델보다 커넥션 풀 크기가 처리량의 상한을 정한다"였다. 측정이 보여 주는 범위는 그보다 좁다: 풀 크기 곡선은 FastAPI async 한 서버에서만 쟀고, 서버끼리 비교한 A2는 실패율이 높은 서버가 많아(아래 한계) 동시성 모델과 풀 크기 중 무엇이 더 큰지는 확인되지 않았다. 풀 20 × 200ms의 이론 상한은 100 req/s이고, A2에서 Go · MVC · 가상 스레드 · Django async-raw가 모두 94~97 req/s에 머물렀다. #5에서 풀 크기를 10 → 100으로 키우자 처리량이 48.7 → 425.0 req/s로 늘었고, 이론 상한의 85~97%였다.

## 한계

- 1회 측정. 호스트 하드웨어 · k6 버전 기록 없음.
- 2026-11-18 문서 정리 중 확인(k6 원본 로그 `k6/results/db-bound-20260405-084137/`): python-fastapi-async의 954.6 req/s는 요청 114,614건 중 103,524건(90.32%)이 실패한 값이다(`python-fastapi-async.log` 103922행). 성공한 요청만 세면 11,090건 / 120초 ≈ 92 req/s로, 풀 20의 이론 상한(100 req/s)과 #5의 풀 20 결과(96.1 req/s) 안쪽이다. 원문의 "asyncpg의 파이프라이닝 또는 커넥션 재활용이 효율적"이라는 해석은 이 실패율을 고려하지 않았다. 같은 측정에서 python-fastapi-sync는 62.07%(398행), python-django-sync는 67.88%(398행)가 실패했다. 원문 수치는 고치지 않았다.
- WebFlux가 48.7 req/s로 풀 20 상한의 절반에 그친 이유는 조사하지 않았다.
- #5는 python-fastapi-async 한 서버로만 쟀다. 다른 서버에서도 같은 비례가 나오는지는 재지 않았다.
- #5(풀 크기 곡선)의 k6 원본 출력은 저장소에 없다. 수치의 근거는 원문 정리 문서뿐이다.
- A2 FastAPI async의 실패 103,524건은 모두 k6 경고 `connection refused`였고(`k6/results/db-bound-20260405-084137/python-fastapi-async.log`), 경고 시각은 08:45:18~08:45:23(UTC)에 몰려 있다. 그 몇 초 동안 서버가 연결을 받지 못한 상태였던 것으로 보이며, 원인은 확인하지 않았다.
- Django sync는 워커마다 풀 20(합쳐 최대 80)이라 다른 서버의 풀 20과 조건이 다르고, 67.88%가 실패해 처리량을 비교할 수 없다.
