# 확장 실험 가설 (Extended Hypotheses)

> 작성일: 2026-04-05
> 1차 실험 결과 기반

---

## A1: VU 500/1000 고부하 I/O 테스트

### 가설
**VU 500 이상에서 Java MVC의 성능이 급격히 하락하고, WebFlux/Virtual Threads/Go는 안정적일 것이다.**

### 근거
- 1차 실험: 200 VU에서 MVC(740 req/s) = WebFlux(741) = Virtual(717). Tomcat 200 스레드가 충분했음.
- VU 500: 스레드풀 200 초과 → 300개 요청이 큐잉 → latency 급증 예상
- VU 1000: MVC는 심각한 큐잉, WebFlux/Virtual/Go는 여전히 안정적일 것

### 예상 결과
- MVC: VU 500에서 p95 > 1s, VU 1000에서 p95 > 2s
- WebFlux/Virtual/Go: VU 1000에서도 p95 ≈ 200-300ms
- FastAPI async: VU 1000에서도 안정적 (이벤트 루프)
- FastAPI sync: VU 500에서 이미 심각한 큐잉 (스레드풀 ~40)

---

## A2: PostgreSQL 실제 DB I/O

### 가설
**async DB 드라이버(asyncpg)를 사용하는 서버가 sync 드라이버(psycopg2)보다 I/O 처리량이 높을 것이다. 단, 커넥션 풀 크기가 새로운 병목이 될 것이다.**

### 근거
- sleep과 달리 실제 DB I/O는 커넥션 풀을 거침
- async 드라이버는 이벤트 루프에서 직접 I/O → 스레드 전환 없음
- 커넥션 풀 크기(20)가 sleep 실험의 스레드풀과 같은 역할의 병목

### 예상 결과
- async 서버(FastAPI async, WebFlux, Go): 커넥션 풀 크기에 비례하는 처리량
- sync 서버: 스레드풀 × 커넥션풀 이중 병목
- Django async + ORM: sync_to_async + 동기 드라이버 → 최악

---

## A3: Django ASGI 오버헤드 프로파일링

### 가설
**Django ASGI의 병목은 미들웨어 체인과 요청 객체 생성에 있다.**

### 근거
- Django async-raw(269 req/s) vs FastAPI async(735 req/s) → 같은 asyncio.sleep인데 2.7배 차이
- Django는 최소 설정에서도 SecurityMiddleware, SessionMiddleware 등이 기본 로드
- 우리 설정은 INSTALLED_APPS=[]이지만 Django 내부 요청 처리 파이프라인은 여전히 실행

### 예상 결과
- flamegraph에서 Django 내부 요청 처리(WSGIHandler/ASGIHandler)가 시간의 대부분 차지

---

## B1: Python ProcessPoolExecutor CPU-bound

### 가설
**ProcessPoolExecutor를 사용하면 Python CPU-bound 성능이 코어 수에 비례하여 향상될 것이다 (1 req/s → 2 req/s).**

### 근거
- 1차 결과: Python CPU ~1 req/s (GIL → 싱글코어)
- ProcessPoolExecutor는 별도 프로세스에서 실행 → GIL 우회
- 2코어 환경이므로 최대 2배 향상 예상

---

## B2: Java GraalVM Native Image

### 가설
**GraalVM native은 JVM 대비 콜드 스타트가 빠르고 메모리가 적지만, 처리량은 비슷하거나 약간 낮을 것이다.**

### 근거
- GraalVM native: AOT 컴파일 → 즉시 시작, 낮은 메모리
- JIT 최적화 없음 → 장기 실행 시 throughput이 JVM보다 낮을 수 있음

---

## B3: WebSocket 장기 커넥션

### 가설
**이벤트 루프 모델(FastAPI async, WebFlux, Go)이 스레드 모델(MVC, FastAPI sync)보다 동시 WebSocket 연결 수에서 월등히 유리할 것이다.**

### 근거
- WebSocket은 커넥션을 장시간 유지 → 스레드 모델은 커넥션당 스레드 점유
- 이벤트 루프는 fd 기반으로 수천 커넥션 동시 관리 가능

---

## B4: 메모리 사용량 비교

### 가설
**Go와 이벤트 루프 모델이 스레드 모델보다 메모리 효율이 높을 것이다. Java는 JVM 오버헤드로 가장 높을 것이다.**

### 근거
- goroutine: 2-8KB per connection
- OS thread: ~1MB stack per thread
- JVM: 기본 힙 + 메타스페이스 + 스레드 스택

---

## B5: Node.js 추가

### 가설
**Node.js는 I/O-bound에서 FastAPI async와 비슷한 수준이고, CPU-bound에서 Python과 비슷하게 낮을 것이다.**

### 근거
- 같은 싱글 스레드 이벤트 루프 모델
- V8 엔진이 CPython보다 빠르지만 싱글 스레드 한계는 동일

---

## C1: Graceful Shutdown

### 가설
**이벤트 루프 모델이 스레드 모델보다 graceful shutdown이 깨끗할 것이다 (진행 중 요청 드롭률이 낮음).**

### 근거
- 이벤트 루프: 진행 중 작업 완료 후 종료가 자연스러움
- 스레드 모델: 200 스레드가 각각 작업 중 → 전부 완료 대기 or 강제 종료
