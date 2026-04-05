# 실험 가설 (Hypotheses)

> 작성일: 2026-04-05
> 실험 환경: Docker 컨테이너 (2 CPU, 512MB RAM), k6 별도 PC (192.168.55.114)

---

## 공통 조건

- I/O-bound 엔드포인트: `GET /io` — sleep 200ms
- CPU-bound 엔드포인트: `GET /cpu` — fibonacci(38) 재귀 연산
- k6 I/O 테스트: 200 VU, ramp-up 30s → sustained 60s → ramp-down 30s
- k6 CPU 테스트: 100 VU, 동일 패턴

---

## H1: FastAPI sync vs async (I/O-bound)

### 가설
**FastAPI async가 sync보다 I/O-bound 처리량이 월등히 높을 것이다.**

### 근거
- sync(`def`): 스레드풀(기본 ~40 스레드)에서 실행. 200 VU가 동시에 요청하면 스레드 40개가 각각 200ms씩 점유. 나머지 160개 요청은 큐잉됨.
  - 예상 처리량: ~40개/200ms = ~200 req/s
- async(`async def`): 이벤트 루프에서 `await asyncio.sleep()` 사용. 이벤트 루프가 블로킹되지 않으므로 200 VU 전부 동시 처리 가능.
  - 예상 처리량: ~200개/200ms = ~1000 req/s

### 예상 결과
- async 서버의 throughput이 sync 대비 **3~5배** 이상
- async 서버의 p95 latency가 ~200ms에 수렴 (sleep 시간)
- sync 서버의 p95 latency가 ~600ms 이상 (큐잉 지연)

---

## H2: FastAPI sync vs async (CPU-bound)

### 가설
**CPU-bound에서는 sync와 async의 차이가 거의 없거나, sync가 약간 유리할 것이다.**

### 근거
- CPU-bound 작업은 sleep이 아니라 실제 CPU를 점유. 이벤트 루프든 스레드풀이든 CPU 코어 수(2)가 병목.
- async 서버에서 CPU-bound 작업은 이벤트 루프를 블로킹하므로 오히려 다른 요청 처리가 지연됨.
- sync 서버는 스레드풀에서 실행되므로 이벤트 루프에 영향 없음.

### 예상 결과
- 두 서버 모두 비슷한 throughput (~2코어분)
- async 서버가 약간 불리할 수 있음 (이벤트 루프 블로킹)

---

## H3: Django sync (WSGI) vs Django async (ASGI + ORM) — I/O-bound

### 가설
**Django async + ORM은 sync와 큰 차이가 없을 것이다.**

### 근거
- Django ORM은 내부적으로 동기 DB 드라이버 사용.
- async view에서 ORM 호출 시 `sync_to_async()`로 스레드풀에 위임해야 함.
- 결국 I/O 처리가 스레드풀을 거치므로 sync와 유사한 병목 발생.
- 이 실험에서는 DB가 아니라 sleep이므로 ORM 제약이 직접 드러나지는 않지만, `sync_to_async(time.sleep)` vs `asyncio.sleep` 차이를 보여줌.

### 예상 결과
- Django async (ORM): sync_to_async를 통해 sleep → sync와 유사한 성능
- Django sync (WSGI): gunicorn gthread 워커로 처리 → 스레드 수만큼 동시 처리

---

## H4: Django async + raw SQL vs Django async + ORM — I/O-bound

### 가설
**raw SQL async 서버가 ORM async 서버보다 I/O-bound 처리량이 훨씬 높을 것이다.**

### 근거
- raw SQL 서버는 `asyncio.sleep()`을 직접 사용 (ORM 우회).
- ORM 서버는 `sync_to_async()`로 스레드풀 위임 → 스레드 수에 의존.
- 이 비교는 "ORM이 async의 이점을 얼마나 상쇄하는가"를 보여줌.

### 예상 결과
- raw SQL async ≈ FastAPI async 수준 처리량
- ORM async ≈ Django sync 수준 처리량
- **차이의 원인이 ORM의 동기 제약임을 입증**

---

## H5: Java Spring MVC vs WebFlux vs Virtual Threads — I/O-bound

### 가설
**WebFlux와 Virtual Threads가 MVC보다 I/O-bound에서 월등히 높은 처리량을 보일 것이다.**
**WebFlux와 Virtual Threads는 비슷한 수준일 것이다.**

### 근거
- MVC: Tomcat 스레드풀 기본 200. 200 VU × 200ms sleep → 스레드 전부 점유. 추가 요청은 큐잉.
  - 그러나 Docker 환경에서 스레드 200개 × ~1MB 스택 = ~200MB → 512MB RAM 내에서 가능.
  - 예상 처리량: ~200개/200ms = ~1000 req/s (스레드풀이 충분하면)
- WebFlux: Netty 이벤트 루프 (코어 수 = 2 스레드). 논블로킹이므로 200 VU 전부 동시 처리.
  - 예상 처리량: ~1000 req/s
- Virtual Threads: Tomcat + virtual thread. `Thread.sleep()`이 carrier thread를 unmount하므로 수천 개 동시 처리 가능.
  - 예상 처리량: ~1000 req/s

### 예상 결과
- MVC: VU 200에서는 스레드풀 200이 충분하므로 의외로 세 모델 모두 비슷할 수 있음.
- **VU를 500 이상으로 올리면** MVC의 스레드풀 한계가 드러날 것.
- WebFlux ≈ Virtual Threads > MVC (고부하 시)

---

## H6: Java Spring MVC vs WebFlux vs Virtual Threads — CPU-bound

### 가설
**CPU-bound에서는 세 모델 모두 비슷한 성능을 보일 것이다.**

### 근거
- CPU-bound는 코어 수(2)가 병목. 스레드 모델과 무관하게 동일.
- WebFlux에서 CPU-bound 작업은 이벤트 루프를 블로킹하므로 약간 불리할 수 있음.

### 예상 결과
- MVC ≈ Virtual Threads ≥ WebFlux (CPU-bound)
- WebFlux가 약간 불리: 이벤트 루프 스레드(2개)가 연산에 점유되면 다른 요청 수락 자체가 지연됨.

---

## H7: Go goroutine — I/O-bound & CPU-bound

### 가설
**Go는 I/O-bound에서 최상위권, CPU-bound에서는 Java와 비슷할 것이다.**

### 근거
- I/O: goroutine + netpoller로 `time.Sleep()`이 OS 스레드를 점유하지 않음. 수만 개 동시 연결 가능.
- CPU: GOMAXPROCS=2 (Docker 2코어). goroutine이 아무리 많아도 CPU 2코어분만 동시 실행.
- Go는 sync/async 구분이 없음. goroutine이 blocking 스타일 코드를 내부적으로 비동기 처리.

### 예상 결과
- I/O: FastAPI async, WebFlux, Virtual Threads와 비슷한 최상위권
- CPU: Java MVC, Virtual Threads와 비슷 (GC 특성 차이로 약간의 변동 가능)

---

## H8: Go의 sync/async 무의미성

### 가설
**Go에서 "sync 스타일"과 "async 스타일" 코드는 성능 차이가 없다.**

### 근거
- Go의 모든 네트워크 I/O는 netpoller를 통해 내부적으로 비동기 처리됨.
- `time.Sleep()`도 goroutine만 park하고 OS 스레드는 해제됨.
- 따라서 코드 스타일과 무관하게 런타임 동작은 동일.
- 이 서버는 단일 구현이지만, 이 가설을 문서화하여 Go의 고유한 동시성 모델을 설명.

### 검증 방법
- 별도 실험 불필요. Go 서버 1개의 I/O-bound 결과가 다른 async 서버들과 동등하면 입증됨.

---

## 요약 표

| 가설 | I/O-bound 예상 순위 | CPU-bound 예상 순위 |
|------|-------------------|-------------------|
| H1 | FastAPI async >> sync | 비슷 |
| H3-H4 | Django raw async >> Django ORM async ≈ Django sync | 비슷 |
| H5-H6 | WebFlux ≈ Virtual ≥ MVC | MVC ≈ Virtual ≥ WebFlux |
| H7-H8 | Go ≈ 최상위 async 그룹 | Go ≈ Java |
