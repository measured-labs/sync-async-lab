# ADR-000: 1차 실험 — 9개 서버의 I/O-bound · CPU-bound 처리량 (200 VU · 100 VU)

- 상태: 끝남 — 2026-04-05 측정 · 결과 커밋 f7a53f9
- 원문: [hypotheses.md](../archive/report/hypotheses.md)(가설 H1~H8), [results.md](../archive/report/results.md)(결과 · 가설 검증) — 2026-11-18 이 형식으로 옮김. 원문 줄을 그대로 옮기고 제목 깊이와 절 순서만 맞췄다. 바꾼 낱말 · 표기: "처리 비용이 지배적" → "처리 비용이 대부분을 차지"(2곳); "커넥션 풀이 왕" → "커넥션 풀 크기가 처리량을 결정"(제목); 깨진 글자 13줄을 문맥으로 복원(예: "?트릭" → "메트릭"); 내부 IP를 "k6 서버(별도 PC) · 앱 서버"로. 2026-11-18에 덧붙인 확인 내용은 "한계"(와 각주)에 날짜를 달아 따로 적었다.
- 줄임 이름: H1~H8은 1차 실험의 가설 번호다. 확장 실험(A1~A3, B1~B5, C1, #1 · #5 · #6)은 ADR-001~011에 있다.

## 질문

같은 일(200ms 대기, fibonacci(38) 계산)을 하는 서버를 동시성 모델만 바꿔 만들면 처리량과 응답 시간이 얼마나 달라지는가. 특히 (1) Python에서 sync와 async, (2) Django에서 ORM 경유 async와 raw async, (3) Java에서 MVC · WebFlux · 가상 스레드, (4) Go의 goroutine이 같은 조건에서 어디에 서는가.

## 선택지 (비교한 서버)

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

(README 서버 표의 1~9행. 10~12행은 확장 실험에서 추가했다.)

## 실험 설계

- 측정일: 2026-04-05. 서버는 Docker 컨테이너마다 2 CPU · 512MB RAM(`docker-compose.yml`), k6는 별도 PC에서 실행했다. 한 번에 서버 하나씩 순서대로 측정했다.
- 호스트 하드웨어 · k6 버전 · 반복 횟수: 기록 없음(이 실험의 원문에는 없다. 같은 호스트의 CPU는 ADR-004 · ADR-007 원문에 i7-13700HX로 적혀 있다).

원문 "공통 조건":

- I/O-bound 엔드포인트: `GET /io` — sleep 200ms
- CPU-bound 엔드포인트: `GET /cpu` — fibonacci(38) 재귀 연산
- k6 I/O 테스트: 200 VU, ramp-up 30s → sustained 60s → ramp-down 30s
- k6 CPU 테스트: 100 VU, 동일 패턴

## 가설 (원문)

### H1: FastAPI sync vs async (I/O-bound)

#### 가설
**FastAPI async가 sync보다 I/O-bound 처리량이 월등히 높을 것이다.**

#### 근거
- sync(`def`): 스레드풀(기본 ~40 스레드)에서 실행. 200 VU가 동시에 요청하면 스레드 40개가 각각 200ms씩 점유. 나머지 160개 요청은 큐잉됨.
  - 예상 처리량: ~40개/200ms = ~200 req/s
- async(`async def`): 이벤트 루프에서 `await asyncio.sleep()` 사용. 이벤트 루프가 블로킹되지 않으므로 200 VU 전부 동시 처리 가능.
  - 예상 처리량: ~200개/200ms = ~1000 req/s

#### 예상 결과
- async 서버의 throughput이 sync 대비 **3~5배** 이상
- async 서버의 p95 latency가 ~200ms에 수렴 (sleep 시간)
- sync 서버의 p95 latency가 ~600ms 이상 (큐잉 지연)

---

### H2: FastAPI sync vs async (CPU-bound)

#### 가설
**CPU-bound에서는 sync와 async의 차이가 거의 없거나, sync가 약간 유리할 것이다.**

#### 근거
- CPU-bound 작업은 sleep이 아니라 실제 CPU를 점유. 이벤트 루프든 스레드풀이든 CPU 코어 수(2)가 병목.
- async 서버에서 CPU-bound 작업은 이벤트 루프를 블로킹하므로 오히려 다른 요청 처리가 지연됨.
- sync 서버는 스레드풀에서 실행되므로 이벤트 루프에 영향 없음.

#### 예상 결과
- 두 서버 모두 비슷한 throughput (~2코어분)
- async 서버가 약간 불리할 수 있음 (이벤트 루프 블로킹)

---

### H3: Django sync (WSGI) vs Django async (ASGI + ORM) — I/O-bound

#### 가설
**Django async + ORM은 sync와 큰 차이가 없을 것이다.**

#### 근거
- Django ORM은 내부적으로 동기 DB 드라이버 사용.
- async view에서 ORM 호출 시 `sync_to_async()`로 스레드풀에 위임해야 함.
- 결국 I/O 처리가 스레드풀을 거치므로 sync와 유사한 병목 발생.
- 이 실험에서는 DB가 아니라 sleep이므로 ORM 제약이 직접 드러나지는 않지만, `sync_to_async(time.sleep)` vs `asyncio.sleep` 차이를 보여줌.

#### 예상 결과
- Django async (ORM): sync_to_async를 통해 sleep → sync와 유사한 성능
- Django sync (WSGI): gunicorn gthread 워커로 처리 → 스레드 수만큼 동시 처리

---

### H4: Django async + raw SQL vs Django async + ORM — I/O-bound

#### 가설
**raw SQL async 서버가 ORM async 서버보다 I/O-bound 처리량이 훨씬 높을 것이다.**

#### 근거
- raw SQL 서버는 `asyncio.sleep()`을 직접 사용 (ORM 우회).
- ORM 서버는 `sync_to_async()`로 스레드풀 위임 → 스레드 수에 의존.
- 이 비교는 "ORM이 async의 이점을 얼마나 상쇄하는가"를 보여줌.

#### 예상 결과
- raw SQL async ≈ FastAPI async 수준 처리량
- ORM async ≈ Django sync 수준 처리량
- **차이의 원인이 ORM의 동기 제약임을 입증**

---

### H5: Java Spring MVC vs WebFlux vs Virtual Threads — I/O-bound

#### 가설
**WebFlux와 Virtual Threads가 MVC보다 I/O-bound에서 월등히 높은 처리량을 보일 것이다.**
**WebFlux와 Virtual Threads는 비슷한 수준일 것이다.**

#### 근거
- MVC: Tomcat 스레드풀 기본 200. 200 VU × 200ms sleep → 스레드 전부 점유. 추가 요청은 큐잉.
  - 그러나 Docker 환경에서 스레드 200개 × ~1MB 스택 = ~200MB → 512MB RAM 내에서 가능.
  - 예상 처리량: ~200개/200ms = ~1000 req/s (스레드풀이 충분하면)
- WebFlux: Netty 이벤트 루프 (코어 수 = 2 스레드). 논블로킹이므로 200 VU 전부 동시 처리.
  - 예상 처리량: ~1000 req/s
- Virtual Threads: Tomcat + virtual thread. `Thread.sleep()`이 carrier thread를 unmount하므로 수천 개 동시 처리 가능.
  - 예상 처리량: ~1000 req/s

#### 예상 결과
- MVC: VU 200에서는 스레드풀 200이 충분하므로 의외로 세 모델 모두 비슷할 수 있음.
- **VU를 500 이상으로 올리면** MVC의 스레드풀 한계가 드러날 것.
- WebFlux ≈ Virtual Threads > MVC (고부하 시)

---

### H6: Java Spring MVC vs WebFlux vs Virtual Threads — CPU-bound

#### 가설
**CPU-bound에서는 세 모델 모두 비슷한 성능을 보일 것이다.**

#### 근거
- CPU-bound는 코어 수(2)가 병목. 스레드 모델과 무관하게 동일.
- WebFlux에서 CPU-bound 작업은 이벤트 루프를 블로킹하므로 약간 불리할 수 있음.

#### 예상 결과
- MVC ≈ Virtual Threads ≥ WebFlux (CPU-bound)
- WebFlux가 약간 불리: 이벤트 루프 스레드(2개)가 연산에 점유되면 다른 요청 수락 자체가 지연됨.

---

### H7: Go goroutine — I/O-bound & CPU-bound

#### 가설
**Go는 I/O-bound에서 최상위권, CPU-bound에서는 Java와 비슷할 것이다.**

#### 근거
- I/O: goroutine + netpoller로 `time.Sleep()`이 OS 스레드를 점유하지 않음. 수만 개 동시 연결 가능.
- CPU: GOMAXPROCS=2 (Docker 2코어). goroutine이 아무리 많아도 CPU 2코어분만 동시 실행.
- Go는 sync/async 구분이 없음. goroutine이 blocking 스타일 코드를 내부적으로 비동기 처리.

#### 예상 결과
- I/O: FastAPI async, WebFlux, Virtual Threads와 비슷한 최상위권
- CPU: Java MVC, Virtual Threads와 비슷 (GC 특성 차이로 약간의 변동 가능)

---

### H8: Go의 sync/async 무의미성

#### 가설
**Go에서 "sync 스타일"과 "async 스타일" 코드는 성능 차이가 없다.**

#### 근거
- Go의 모든 네트워크 I/O는 netpoller를 통해 내부적으로 비동기 처리됨.
- `time.Sleep()`도 goroutine만 park하고 OS 스레드는 해제됨.
- 따라서 코드 스타일과 무관하게 런타임 동작은 동일.
- 이 서버는 단일 구현이지만, 이 가설을 문서화하여 Go의 고유한 동시성 모델을 설명.

#### 검증 방법
- 별도 실험 불필요. Go 서버 1개의 I/O-bound 결과가 다른 async 서버들과 동등하면 입증됨.


### 요약 표

| 가설 | I/O-bound 예상 순위 | CPU-bound 예상 순위 |
|------|-------------------|-------------------|
| H1 | FastAPI async >> sync | 비슷 |
| H3-H4 | Django raw async >> Django ORM async ≈ Django sync | 비슷 |
| H5-H6 | WebFlux ≈ Virtual ≥ MVC | MVC ≈ Virtual ≥ WebFlux |
| H7-H8 | Go ≈ 최상위 async 그룹 | Go ≈ Java |

## 결과 (원문)

> 실험일: 2026-04-05 · 환경: Docker (2 CPU, 512MB RAM), k6 서버(별도 PC) → 앱 서버(Docker 호스트)

### 원시 데이터

#### I/O-bound 결과 (GET /io — sleep 200ms, 200 VU)

| Server | req/s | avg | p90 | p95 | total reqs |
|--------|------:|----:|----:|----:|-----------:|
| python-fastapi-sync | 188.5 | 798.3ms | 1009.6ms | 1011.7ms | 22,631 |
| python-fastapi-async | 735.6 | 203.7ms | 205.9ms | 207.3ms | 88,404 |
| python-django-sync | 648.4 | 231.4ms | 333.8ms | 340.0ms | 77,836 |
| python-django-async (ORM) | 260.6 | 576.8ms | 768.9ms | 812.5ms | 31,289 |
| python-django-async-raw | 269.1 | 558.1ms | 718.7ms | 750.2ms | 32,337 |
| java-spring-mvc | 739.8 | 202.6ms | 201.7ms | 202.4ms | 88,890 |
| java-spring-webflux | 741.8 | 202.1ms | 202.2ms | 202.9ms | 89,099 |
| java-spring-virtual | 717.6 | 209.0ms | 215.4ms | 221.0ms | 86,188 |
| go-server | 743.6 | 201.7ms | 202.5ms | 203.0ms | 89,275 |

#### CPU-bound 결과 (GET /cpu — fibonacci(38), 100 VU)

| Server | req/s | avg | p90 | p95 | total reqs |
|--------|------:|----:|----:|----:|-----------:|
| python-fastapi-sync | 1.1 | 59999.9ms | 60000.4ms | 60000.5ms | 150 |
| python-fastapi-async | 1.0 | 58778.8ms | 60000.4ms | 60000.5ms | 153 |
| python-django-sync | 1.1 | 59999.9ms | 60000.4ms | 60000.4ms | 150 |
| python-django-async (ORM) | 1.1 | 59999.9ms | 60000.4ms | 60000.4ms | 150 |
| python-django-async-raw | 1.0 | 59130.6ms | 60000.4ms | 60000.5ms | 152 |
| java-spring-mvc | 2.5 | 30604.5ms | 58151.4ms | 60000.2ms | 328 |
| java-spring-webflux | 2.4 | 27987.3ms | 54657.4ms | 59999.7ms | 346 |
| java-spring-virtual | 2.7 | 27099.0ms | 35403.2ms | 36005.4ms | 381 |
| go-server | 2.3 | 34556.1ms | 43502.9ms | 44532.0ms | 296 |


### 가설 검증

#### H1: FastAPI sync vs async (I/O-bound) — ✅ 가설 입증

| 메트릭 | sync | async | 배수 |
|--------|-----:|------:|-----:|
| req/s | 188.5 | 735.6 | **3.9x** |
| avg latency | 798.3ms | 203.7ms | **3.9x 빠름** |
| p95 latency | 1011.7ms | 207.3ms | **4.9x 빠름** |

**분석:**
- 가설 예상(3~5배)과 정확히 일치. async가 3.9배 높은 처리량.
- sync 서버의 p95가 1초를 넘음 → 스레드풀(~40) 포화로 큐잉 발생 확인.
- async 서버의 p95가 207ms → sleep 200ms + 네트워크 오버헤드 수준. 큐잉 거의 없음.

#### H2: FastAPI sync vs async (CPU-bound) — ✅ 가설 입증

| 메트릭 | sync | async |
|--------|-----:|------:|
| req/s | 1.1 | 1.0 |
| total reqs | 150 | 153 |

**분석:**
- 두 모델 모두 ~1 req/s로 거의 동일. Python GIL + fibonacci(38)이 CPU를 완전히 점유.
- 가설대로 CPU-bound에서는 sync/async 차이 없음.
- Python의 GIL이 2코어 환경에서도 사실상 싱글 스레드로 동작하게 만듦.

#### H3: Django sync vs async+ORM (I/O-bound) — ⚠️ 예상 외 결과

| 메트릭 | sync (WSGI) | async (ORM) |
|--------|------------:|------------:|
| req/s | 648.4 | 260.6 |
| avg latency | 231.4ms | 576.8ms |

**분석:**
- **가설은 "비슷하다"였으나, sync가 오히려 2.5배 빨랐다.**
- Django sync(gunicorn gthread 4 workers × 50 threads = 200 threads)가 200 VU를 효율적으로 처리.
- Django async + `sync_to_async`는 오버헤드가 생각보다 큼. 스레드풀 위임 + 코루틴 전환 비용.
- **교훈: Django에서 ORM을 쓸 거라면 async로 가는 것이 오히려 성능 악화.**

#### H4: Django async-raw vs async+ORM (I/O-bound) — ❌ 가설 기각

| 메트릭 | async-raw | async (ORM) |
|--------|----------:|------------:|
| req/s | 269.1 | 260.6 |
| avg latency | 558.1ms | 576.8ms |

**분석:**
- **가설은 "raw가 훨씬 빠르다"였으나, 두 서버가 거의 동일했다.**
- Django ASGI 자체의 오버헤드가 병목인 것으로 보임. `asyncio.sleep` 직접 사용해도 Django ASGI 미들웨어 처리 비용이 대부분을 차지.
- Django ASGI가 FastAPI 수준의 async 성능을 내지 못하는 원인은 ORM이 아니라 **ASGI 구현 자체의 오버헤드**.
- FastAPI async (735 req/s) vs Django async-raw (269 req/s) → 같은 asyncio.sleep인데 2.7배 차이.

#### H5: Java MVC vs WebFlux vs Virtual Threads (I/O-bound) — ⚠️ 부분 입증

| 메트릭 | MVC | WebFlux | Virtual |
|--------|----:|--------:|--------:|
| req/s | 739.8 | 741.8 | 717.6 |
| avg | 202.6ms | 202.1ms | 209.0ms |
| p95 | 202.4ms | 202.9ms | 221.0ms |

**분석:**
- **가설 "MVC가 뒤처질 것"이 틀림.** 200 VU에서 Tomcat 스레드풀 200이 충분했기 때문.
- 세 모델 모두 ~740 req/s로 거의 동일. 200ms sleep이 병목이라 동시성 모델 차이가 안 드러남.
- VU를 500~1000으로 올려야 MVC의 스레드풀 한계가 드러날 것 (가설에서 언급한 대로).
- Virtual Threads가 약간 느린 건 virtual thread 스케줄링 오버헤드일 수 있음.

#### H6: Java MVC vs WebFlux vs Virtual Threads (CPU-bound) — ✅ 부분 입증

| 메트릭 | MVC | WebFlux | Virtual |
|--------|----:|--------:|--------:|
| req/s | 2.5 | 2.4 | 2.7 |
| total | 328 | 346 | 381 |

**분석:**
- 세 모델 모두 2~3 req/s로 비슷 (2코어 병목).
- Virtual Threads가 약간 우세 (381 reqs). 스레드 관리 오버헤드가 적어서일 수 있음.
- Java가 Python보다 CPU-bound에서 2배 이상 빠름 (GIL 없이 2코어 활용).

#### H7: Go (I/O-bound & CPU-bound) — ✅ 가설 입증

| 메트릭 | Go (IO) | Go (CPU) |
|--------|--------:|---------:|
| req/s | 743.6 | 2.3 |
| p95 | 203.0ms | 44532.0ms |

**분석:**
- I/O: 743.6 req/s로 최상위권 (Java WebFlux/MVC와 동등).
- CPU: 2.3 req/s로 Java와 비슷한 순위.
- 가설대로 Go는 I/O-bound에서 최상위, CPU-bound에서 Java급.

#### H8: Go sync/async 무의미성 — ✅ 입증

- Go 서버 1개의 I/O 결과가 다른 async 서버들(FastAPI async, WebFlux)과 동등 → goroutine이 blocking 스타일 코드를 비동기로 처리함 확인.

### 핵심 발견

#### I/O-bound 처리량 순위

| 순위 | 서버 | req/s |
|------|------|------:|
| 1 | go-server | 743.6 |
| 2 | java-spring-webflux | 741.8 |
| 3 | java-spring-mvc | 739.8 |
| 4 | python-fastapi-async | 735.6 |
| 5 | java-spring-virtual | 717.6 |
| 6 | python-django-sync | 648.4 |
| 7 | python-django-async-raw | 269.1 |
| 8 | python-django-async (ORM) | 260.6 |
| 9 | python-fastapi-sync | 188.5 |

#### 예상 외 발견

1. **Django sync > Django async**: WSGI + gthread가 ASGI보다 빠름. Django에서 async는 오히려 성능 저하.
2. **Django ASGI 자체가 병목**: ORM이 아니라 Django ASGI 미들웨어 처리 비용이 대부분을 차지.
3. **Java MVC = WebFlux = Virtual Threads (200 VU에서)**: 스레드풀 200이 충분하면 모델 차이 없음.
4. **Python CPU-bound는 GIL에 의해 사실상 싱글코어**: 2코어 환경에서도 ~1 req/s.
5. **Java/Go는 CPU-bound에서 Python의 2배 이상**: GIL 없이 멀티코어 활용.


## 결정 (결론)

원문 "가설 검증" · "핵심 발견"을 요약한다.

- 200 VU · 200ms 대기에서는 Go · WebFlux · MVC · FastAPI async · 가상 스레드가 모두 약 720~740 req/s로 비슷했다. Tomcat 스레드풀 200이 200 VU를 감당해 동시성 모델 차이가 드러나지 않았다(→ VU를 올린 ADR-001).
- FastAPI는 async가 sync보다 3.9배 높은 처리량을 냈다(H1).
- Django는 이 설정(sync: gunicorn 4 프로세스 × 50 스레드, async: uvicorn 워커 1개)에서 WSGI + gthread(sync)가 ASGI(async)보다 2.5배 빨랐고, ORM 경유 async와 raw async의 차이는 없었다(H3 · H4). 원문은 원인을 ORM이 아니라 Django ASGI 처리 자체로 봤다(→ ADR-003).
- CPU-bound에서는 Python 서버가 모두 약 1 req/s, Java · Go가 약 2.3~2.7 req/s였다(H2 · H6 · H7). 아래 한계의 실패율을 함께 봐야 한다.

## 한계

- 반복 측정 · 호스트 사양 기록 없음. 결과는 1회분이다.
- 2026-11-18 문서 정리 중 확인(k6 원본 로그 `k6/results/20260405-044231/*.log`의 `http_req_failed` 줄): CPU-bound 측정에서 python-fastapi-sync · python-django-sync · python-django-async는 요청 150건이 모두 실패(100%), python-fastapi-async는 96.07%, python-django-async-raw는 96.71%, java-spring-mvc는 8.53%, java-spring-webflux는 7.51%가 실패했다(k6 기본 타임아웃 60초). 위 CPU-bound 표의 req/s는 실패한 요청을 포함한 값이다. 원문 수치는 고치지 않았다.
- Django sync와 async의 비교(H3 · H4)는 워커 구성이 다르다. Django sync는 gunicorn gthread 4 프로세스 × 50 스레드(`servers/python-django-sync/Dockerfile`), Django async · async-raw는 uvicorn 워커 1개(`servers/python-django-async/Dockerfile`, `servers/python-django-async-raw/Dockerfile`)다. "sync가 2.5배 빠르다"는 이 설정에서의 결과이고, ASGI와 WSGI 모델만의 차이로 볼 수 없다.
- 원문 `results.md`에는 처음 커밋(f7a53f9)부터 깨진 글자가 13줄에 있다. 이 ADR에서는 문맥으로 복원했고(예: 깨진 "?트릭" → "메트릭"), 원문 파일은 그대로 두었다.

## 후속

원문 `results.md` "추가 실험 제안":

1. **VU 500/1000으로 올려서 Java MVC 스레드풀 한계 확인**
2. **Python CPU-bound에서 ProcessPoolExecutor 사용 시 성능 변화**
3. **Django ASGI 오버헤드 원인 추가 프로파일링**
4. **Java Virtual Threads에서 VU 5000 이상 극한 테스트**

원문 `future-work.md` "추가 확장 가능 주제"(작성 2026-04-05, 상태 열은 그 뒤 갱신):

| # | 주제 | 난이도 | 예상 소요 | 상태 |
|---|------|--------|----------|------|
| 1 | Python 3.13 free-threaded (PEP 703) | 중 | 2시간 | ✅ 소스 빌드로 완료 |
| 2 | Rust (Actix-web / Tokio) 서버 추가 | 중 | 3시간 | 미진행 |
| 3 | k8s HPA 오토스케일링 비교 | 높 | 1일 | 미진행 |
| 4 | Grafana + InfluxDB 실시간 대시보드 | 중 | 2시간 | 미진행 |
| 5 | Connection pool 크기별 성능 곡선 (10/20/50/100) | 낮 | 1시간 | ✅ 완료 |
| 6 | JVM warm-up 구간 별도 분석 | 낮 | 30분 | ✅ 완료 |

확장 실험 대응: 1 → ADR-001(VU 500/1000), 2 → ADR-004(ProcessPoolExecutor), 3 → ADR-003(Django ASGI), 4 → 진행 안 됨. 추가 확장 표의 #1 → ADR-005, #5 → ADR-002, #6 → ADR-007.

### 확장 실험 전체 요약 (원문 `results-extended.md` 마지막 절)

#### 1. 고부하(1000 VU)에서 동시성 모델의 진짜 차이가 드러남
- Go/WebFlux: ~3100 req/s (이벤트 루프 / goroutine)
- Virtual Threads: ~2300 req/s (M:N)
- MVC/Django sync: ~950 req/s (스레드풀 포화)
- FastAPI sync: ~196 req/s (스레드풀 극심한 포화)

#### 2. 실제 DB I/O에서는 커넥션 풀 크기가 처리량을 결정
- 동시성 모델 차이보다 **커넥션 풀 크기가 처리량의 상한을 결정**
- 풀 20 × 200ms = 최대 100 req/s (이론치)

#### 3. Node.js ≈ FastAPI async (I/O-bound)
- 같은 싱글 스레드 이벤트 루프 모델 → 거의 동일한 성능

#### 4. Django ASGI 오버헤드는 구조적
- 같은 asyncio를 사용해도 FastAPI의 2.7~5.5배 느림
- ORM이 아닌 프레임워크 자체의 오버헤드

#### 5. Graceful Shutdown은 동시성 모델과 무관
- 모든 프레임워크가 SIGTERM을 올바르게 처리

위 요약에 대한 2026-11-18 각주(원문은 고치지 않았다):

- 1번의 "1000 VU" 값은 500 → 1000 VU 단계 시나리오 전체의 평균이다. 구간별 추정은 [ADR-001](ADR-001-high-concurrency-io.md).
- 2번은 풀 크기 곡선을 FastAPI async 한 서버에서만 잰 결과다. 서버끼리 비교한 DB 측정은 실패율이 높아(FastAPI async 90.32% 등) 동시성 모델과 풀 크기의 비교는 확인되지 않았다 — [ADR-002](ADR-002-db-io-connection-pool.md).
- 4번의 Django ASGI는 uvicorn 워커 1개, 비교한 Django sync는 gunicorn 4 프로세스 × 50 스레드였다.
- 5번은 종료가 실제로 일어났는지 확인되지 않았다. `docker stop`을 보낸 20초 뒤에도 초당 약 500건을 계속 처리했다(`k6/results/shutdown-20260405-094804/go-server.log`) — [ADR-011](ADR-011-graceful-shutdown.md).
